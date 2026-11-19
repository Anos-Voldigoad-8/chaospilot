"""Data agent: builds chaos scenarios from real, keyless public data sources.

The agent fetches real outage and traffic data from public APIs that need no
key, converts each source into one or more :class:`Scenario` objects, and
persists them (plus a fetch log) to SQLite so experiments can run entirely
offline.

Sources (all keyless):
  * Statuspage incident feeds  -- githubstatus.com, cloudflarestatus.com
  * GitHub public events       -- replacement for the (now dead) Wikimedia
                                  pageviews API; gives a real activity signal
  * Open-Meteo hourly forecast -- weather as a second load signal

If a live fetch fails, the agent falls back to a cached response and then to
the committed seed dataset. It logs which source was used for every scenario.
The app never crashes on network problems.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, field_validator

from agent.llm import default_client, extract_json_object
from db import ChaosDatabase

#: Where raw responses are cached so repeated runs work offline.
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"
#: Committed seed dataset used as the last-resort fallback.
SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed"

HTTP_TIMEOUT = 10.0
HTTP_RETRIES = 3
USER_AGENT = "ChaosPilotDataAgent/1.0"

FAULT_KINDS: tuple[str, ...] = ("kill", "latency", "memory")
SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "critical")

#: Keyword -> simulated service. Maps real incident component names to the
#: six simulated services.
KEYWORD_SERVICE_MAP: dict[str, tuple[str, ...]] = {
    "gateway": ("gateway", "api", "edge", "proxy", "frontend", "ingress", "lb"),
    "auth": ("auth", "login", "identity", "session", "sso", "oauth", "sso", "keycloak"),
    "orders": ("order", "checkout", "cart", "purchase", "basket"),
    "payments": ("payment", "pay", "stripe", "charge", "billing", "invoice", "paypal"),
    "cache": ("cache", "redis", "memcached", "session-store"),
    "db": ("db", "database", "postgres", "mysql", "sql", "storage", "warehouse", "db-primary"),
}

#: Statuspage base URLs that expose /api/v2/incidents.json without a key.
STATUSSPAGE_BASES: tuple[str, ...] = (
    "https://www.githubstatus.com",
    "https://www.cloudflarestatus.com",
)

#: GitHub public events (replacement for the dead Wikimedia pageviews API).
GITHUB_EVENTS_URL = "https://api.github.com/events"

#: Open-Meteo hourly forecast (no key).
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


#: Where the data for a scenario ultimately came from.
DataSource = Literal["live", "cached", "seed"]


class Scenario(BaseModel):
    """One chaos scenario built from real data, runnable by the simulator."""

    fault_type: str = Field(..., description="kill | latency | memory")
    target_service: str = Field(..., min_length=1)
    duration_minutes: float = Field(..., gt=0)
    severity: str = Field(..., description="low | medium | high | critical")
    load_curve: list[dict[str, Any]] = Field(default_factory=list)
    source: str = Field(..., description="statuspage | github | openmeteo | seed")
    source_url: str = Field(..., min_length=1)
    data_source: DataSource
    title: str = Field(..., min_length=1)

    @field_validator("fault_type")
    @classmethod
    def _valid_fault(cls, value: str) -> str:
        if value not in FAULT_KINDS:
            raise ValueError(f"unknown fault type: {value}")
        return value

    @field_validator("target_service")
    @classmethod
    def _valid_service(cls, value: str) -> str:
        if value not in {"gateway", "auth", "orders", "payments", "cache", "db"}:
            raise ValueError(f"unknown service: {value}")
        return value

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, value: str) -> str:
        if value not in SEVERITIES:
            raise ValueError(f"unknown severity: {value}")
        return value


class SourcePick(BaseModel):
    """The LLM's (validated) choice of which source to collect from next."""

    source: str = Field(..., description="statuspage | github | openmeteo")
    params: dict[str, Any] = Field(default_factory=dict)


class DataAgent:
    """Collects real public data and turns it into persistable scenarios."""

    def __init__(self, database: ChaosDatabase, hub: Any | None = None) -> None:
        self.database = database
        self.hub = hub
        self.rng = random.Random(20260101)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._client = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}
        )

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #
    async def collect(self) -> list[dict[str, Any]]:
        """Run one collection cycle and return the persisted scenarios."""
        await self._log("info", "data agent: collection started")
        picks = await self._pick_sources()
        await self._log(
            "info", f"data agent: source plan -> {[p.source for p in picks]}"
        )

        scenarios: list[Scenario] = []
        for pick in picks:
            try:
                fetched = await self._fetch_source(pick)
            except Exception as exc:  # never let one source kill the run
                await self._log("warn", f"data agent: {pick.source} failed: {exc}")
                continue
            try:
                built = await self._convert(fetched)
            except Exception as exc:  # bad source shape must not crash the app
                await self._log("warn", f"data agent: converting {pick.source} failed: {exc}")
                continue
            scenarios.extend(built)

        # Last resort: seed dataset so /scenarios is never empty.
        if not scenarios:
            await self._log("info", "data agent: no source data; using seed dataset")
            scenarios = self._seed_scenarios()

        persisted = [self._persist(scenario) for scenario in scenarios]
        await self._log("info", f"data agent: collection done ({len(persisted)} scenarios)")
        return persisted

    # ------------------------------------------------------------------ #
    # Source selection (LLM with seeded-random fallback)
    # ------------------------------------------------------------------ #
    async def _pick_sources(self) -> list[SourcePick]:
        """Ask the LLM which sources to collect; fall back to seeded random."""
        system = (
            "You are a data-collection planner for ChaosPilot. Return ONE JSON "
            "object with a key \"picks\" holding an array of source picks. Each "
            "pick has \"source\" (one of: statuspage, github, openmeteo) and "
            "optional \"params\". Pick 1-3 diverse sources. No markdown fences."
        )
        user = "Choose which keyless public data sources to collect from now."
        client = default_client()
        picks: list[SourcePick] = []
        if client is not None:
            for attempt in range(2):
                try:
                    raw = await client.complete(system, user)
                    data = extract_json_object(raw)
                    picks = [SourcePick(**item) for item in data.get("picks", [])]
                    if picks:
                        return picks
                except Exception:
                    await self._log("warn", f"data agent: LLM pick attempt {attempt + 1} failed")
        # Seeded random fallback.
        sources = ["statuspage", "github", "openmeteo"]
        self.rng.shuffle(sources)
        return [SourcePick(source=s, params={}) for s in sources[:2]]

    # ------------------------------------------------------------------ #
    # Fetching (retries, cache, fallback)
    # ------------------------------------------------------------------ #
    async def _fetch_source(self, pick: SourcePick) -> dict[str, Any]:
        """Fetch one source, returning {source, source_url, data, data_source}."""
        if pick.source == "statuspage":
            base = self.rng.choice(STATUSSPAGE_BASES)
            url = f"{base}/api/v2/incidents.json"
        elif pick.source == "github":
            url = GITHUB_EVENTS_URL
        elif pick.source == "openmeteo":
            url = (
                f"{OPEN_METEO_URL}?latitude=40.71&longitude=-74.01"
                f"&hourly=temperature_2m,precipitation"
            )
        else:
            raise ValueError(f"unknown source: {pick.source}")

        cache_key = self._cache_key(url)

        # 1. Try live.
        data, status = await self._fetch_with_retry(url)
        if data is not None:
            self._cache_write(cache_key, data)
            self.database.insert_fetch_log(url=url, status="live", rows=self._row_count(data))
            await self._log("info", f"data agent: LIVE {url}")
            return {"source": pick.source, "source_url": url, "data": data, "data_source": "live"}

        # 2. Fall back to cache.
        cached = self._cache_read(cache_key)
        if cached is not None:
            self.database.insert_fetch_log(url=url, status="cached", rows=self._row_count(cached))
            await self._log("info", f"data agent: CACHED {url}")
            return {"source": pick.source, "source_url": url, "data": cached, "data_source": "cached"}

        # 3. Seed dataset as last resort.
        seed = self._seed_data(pick.source)
        self.database.insert_fetch_log(url=url, status="seed", rows=self._row_count(seed))
        await self._log("info", f"data agent: SEED {url}")
        return {"source": pick.source, "source_url": url, "data": seed, "data_source": "seed"}

    async def _fetch_with_retry(self, url: str) -> tuple[Any | None, int]:
        """GET with exponential backoff; returns (data, status) or (None, 0)."""
        last_status = 0
        for attempt in range(HTTP_RETRIES):
            try:
                response = await self._client.get(url)
                last_status = response.status_code
                if response.status_code == 200:
                    return response.json(), response.status_code
                await self._log("warn", f"data agent: {url} HTTP {response.status_code}")
            except Exception as exc:  # network failure
                last_status = 0
                await self._log("warn", f"data agent: {url} attempt {attempt + 1} error: {exc}")
            if attempt < HTTP_RETRIES - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
        return None, last_status

    # ------------------------------------------------------------------ #
    # Conversion -> scenarios
    # ------------------------------------------------------------------ #
    async def _convert(self, fetched: dict[str, Any]) -> list[Scenario]:
        source = fetched["source"]
        data = fetched["data"]
        data_source = fetched["data_source"]
        url = fetched["source_url"]
        if source == "statuspage":
            return self._convert_statuspage(data, url, data_source)
        if source == "github":
            return self._convert_github(data, url, data_source)
        if source == "openmeteo":
            return self._convert_openmeteo(data, url, data_source)
        return []

    def _convert_statuspage(self, data: Any, url: str, data_source: DataSource) -> list[Scenario]:
        incidents = []
        if isinstance(data, Mapping):
            incidents = data.get("incidents", []) or []
        elif isinstance(data, list):
            incidents = data
        scenarios: list[Scenario] = []
        for incident in incidents[:10]:
            if not isinstance(incident, Mapping):
                continue
            name = str(incident.get("name") or incident.get("title") or "incident")
            impact = str(incident.get("impact") or "minor")
            service = self._map_component(name)
            severity = _impact_to_severity(impact)
            duration = self._duration_from_incident(incident)
            scenarios.append(
                Scenario(
                    fault_type=_fault_from_impact(impact),
                    target_service=service,
                    duration_minutes=duration,
                    severity=severity,
                    load_curve=[],
                    source="statuspage",
                    source_url=url,
                    data_source=data_source,
                    title=f"{name} ({service})",
                )
            )
        return scenarios

    def _convert_github(self, data: Any, url: str, data_source: DataSource) -> list[Scenario]:
        events = data if isinstance(data, list) else []
        scenarios: list[Scenario] = []
        # Build a simple load curve: event counts per hour.
        load_curve = self._event_load_curve(events)
        for index in range(min(3, len(events))):
            event = events[index] if isinstance(events[index], Mapping) else {}
            scenarios.append(
                Scenario(
                    fault_type="latency",
                    target_service="gateway",
                    duration_minutes=15.0,
                    severity="medium",
                    load_curve=load_curve,
                    source="github",
                    source_url=url,
                    data_source=data_source,
                    title=f"github activity: {str(event.get('type') or 'event')[:60]}",
                )
            )
        if not scenarios:
            scenarios.append(
                Scenario(
                    fault_type="latency",
                    target_service="gateway",
                    duration_minutes=15.0,
                    severity="low",
                    load_curve=load_curve,
                    source="github",
                    source_url=url,
                    data_source=data_source,
                    title="github public activity",
                )
            )
        return scenarios

    def _convert_openmeteo(
        self, data: Any, url: str, data_source: DataSource
    ) -> list[Scenario]:
        hourly = data.get("hourly", {}) if isinstance(data, Mapping) else {}
        times = hourly.get("time", []) or []
        temps = hourly.get("temperature_2m", []) or []
        load_curve = [
            {"t": str(t), "v": float(temp) if temp is not None else 0.0}
            for t, temp in zip(times, temps, strict=False)
        ]
        peak = max((float(t) for t in temps if t is not None), default=15.0)
        severity = "high" if peak > 25 else ("medium" if peak > 15 else "low")
        return [
            Scenario(
                fault_type="memory",
                target_service="cache",
                duration_minutes=20.0,
                severity=severity,
                load_curve=load_curve,
                source="openmeteo",
                source_url=url,
                data_source=data_source,
                title=f"weather load signal (peak {peak:.1f}C)",
            )
        ]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    #: Tie-break priority for the component mapper: more specific / leaf
    #: services win when several services match the same number of keywords.
    MAPPER_PRIORITY: tuple[str, ...] = ("cache", "db", "payments", "orders", "auth", "gateway")

    def _map_component(self, name: str) -> str:
        """Map a real component name to the closest simulated service.

        Counts distinct keyword matches per service; the service with the most
        matches wins. Ties are broken by :attr:`MAPPER_PRIORITY` so a word like
        ``session`` in "session cache" doesn't wrongly claim auth.
        """
        text = name.lower()
        best_service = "gateway"
        best_score = 0
        for service in self.MAPPER_PRIORITY:
            keywords = KEYWORD_SERVICE_MAP[service]
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_service = service
        return best_service

    def _duration_from_incident(self, incident: Mapping[str, Any]) -> float:
        for key in ("duration_minutes", "duration"):
            value = incident.get(key)
            if isinstance(value, int | float):
                return float(value)
        # Statuspage incidents don't always carry duration; derive from impact.
        impact = str(incident.get("impact") or "minor").lower()
        return {"minor": 15.0, "moderate": 45.0, "major": 120.0, "critical": 240.0}.get(impact, 30.0)

    def _event_load_curve(self, events: list[Any]) -> list[dict[str, Any]]:
        """Bin GitHub events into an hourly load curve."""
        counts: dict[str, int] = {}
        for event in events:
            if not isinstance(event, Mapping):
                continue
            ts = str(event.get("created_at") or "")[:13]  # hour
            counts[ts] = counts.get(ts, 0) + 1
        if not counts:
            return [{"t": "00", "v": 1.0}]
        total = sum(counts.values()) or 1
        return [{"t": hour, "v": round(count / total, 4)} for hour, count in sorted(counts.items())]

    def _seed_scenarios(self) -> list[Scenario]:
        """Build scenarios from the committed seed dataset (offline last resort)."""
        path = SEED_DIR / "incidents_seed.json"
        scenarios: list[Scenario] = []
        if not path.exists():
            return scenarios
        try:
            incidents = json.loads(path.read_text())
        except (ValueError, OSError):
            return scenarios
        for incident in incidents[:12]:
            service = str(incident.get("component") or "gateway")
            if service not in {"gateway", "auth", "orders", "payments", "cache", "db"}:
                service = "gateway"
            scenarios.append(
                Scenario(
                    fault_type=str(incident.get("fault_type") or "latency"),
                    target_service=service,
                    duration_minutes=float(incident.get("duration_minutes") or 30),
                    severity=str(incident.get("impact") or "medium"),
                    load_curve=[],
                    source="seed",
                    source_url="scripts/build_seed.py",
                    data_source="seed",
                    title=str(incident.get("title") or "seed incident"),
                )
            )
        return scenarios

    def _seed_data(self, source: str) -> Any:
        if source == "statuspage":
            return {"incidents": self._load_json("incidents_seed.json", [])}
        if source == "github":
            return []
        if source == "openmeteo":
            return {"hourly": {"time": [], "temperature_2m": []}}
        return {}

    def _load_json(self, filename: str, default: Any) -> Any:
        path = SEED_DIR / filename
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text())
        except (ValueError, OSError):
            return default

    # ------------------------------------------------------------------ #
    # Cache
    # ------------------------------------------------------------------ #
    def _cache_key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16] + ".json"

    def _cache_write(self, key: str, data: Any) -> None:
        with suppress(OSError):
            (CACHE_DIR / key).write_text(json.dumps(data), encoding="utf-8")

    def _cache_read(self, key: str) -> Any | None:
        path = CACHE_DIR / key
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    @staticmethod
    def _row_count(data: Any) -> int:
        if isinstance(data, list):
            return len(data)
        if isinstance(data, Mapping):
            total = 0
            for value in data.values():
                if isinstance(value, list):
                    total += len(value)
            return total or 1
        return 1

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _persist(self, scenario: Scenario) -> dict[str, Any]:
        scenario_id = self.database.insert_scenario(
            fault_type=scenario.fault_type,
            target_service=scenario.target_service,
            duration_minutes=scenario.duration_minutes,
            severity=scenario.severity,
            load_curve=scenario.load_curve,
            source=scenario.source,
            source_url=scenario.source_url,
            data_source=scenario.data_source,
            title=scenario.title,
        )
        return scenario.model_dump() | {"id": scenario_id}

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    async def _log(self, level: str, text: str) -> None:
        if self.hub is not None:
            await self.hub.log(level, text)


def _impact_to_severity(impact: str) -> str:
    mapping = {"minor": "low", "moderate": "medium", "major": "high", "critical": "critical"}
    return mapping.get(impact.lower(), "medium")


def _fault_from_impact(impact: str) -> str:
    impact = impact.lower()
    if impact in ("critical", "major"):
        return "kill"
    if impact == "moderate":
        return "latency"
    return "memory"

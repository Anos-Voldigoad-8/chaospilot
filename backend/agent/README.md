# Phase 6 agent

The agent turns chaos experiments into a closed loop: plan one, observe it,
then explain it. Everything runs in the backend; the browser only receives
non-secret plans and reports.

## Modules

| File | Responsibility |
| --- | --- |
| `tools.py` | `get_topology()`, `inject_fault(service, type, value)`, `read_metrics(service)`, `read_logs(service)`, `rollback()` |
| `planner.py` | Sends the topology to the LLM and validates its JSON with `ExperimentPlan`; falls back to the most-called service after two bad responses |
| `context.py` | Builds the postmortem evidence: topology, per-service status timeline, anomaly scores and phase timings |
| `postmortem.py` | Asks the LLM for root cause, blast radius and exactly three fixes under 120 words, with a same-shaped template fallback |
| `service.py` | Orchestrates the steps and streams them through the WebSocket as `log` events |
| `models.py` | Pydantic schemas for plans and postmortems |
| `llm.py` | Provider access through `core.config.LLMSettings` and safe JSON extraction |

## API

```bash
# Ask for one experiment plan. Uses Ollama (default) or the configured
# OpenAI-compatible endpoint; never calls a provider from the browser.
curl -X POST http://127.0.0.1:8090/agent/plan

# Provider mode without exposing a key.
curl http://127.0.0.1:8090/agent/status
```

Example plan:

```json
{
  "fault": "latency",
  "target": "payments",
  "hypothesis": "Delaying payments should expose missing timeouts in orders.",
  "value": 2000.0,
  "source": "llm"
}
```

If the LLM is offline or returns invalid JSON twice, the response has
`"source": "rule"` and targets the service with the most direct callers (`db`
in the current topology).

## Live experiment steps

The experiment runner calls the agent at each phase and broadcasts normal
`log` frames, for example:

```text
agent: tool get_topology() -> 6 services, 6 edges
agent: baseline metrics auth 11ms, cache 6ms, db 5ms, ...
agent: inject_fault(payments, latency) active; collecting the anomaly window
agent: collecting topology, status timeline and anomaly scores
agent: postmortem ready (llm, 74 words)
```

The final `postmortem` frame adds `source` and `structured` fields while
keeping `text` compatible with the existing console:

```json
{
  "type": "postmortem",
  "text": "Root cause: ... Blast radius: ... Fixes: 1) ... 2) ... 3) ...",
  "source": "llm",
  "structured": {
    "root_cause": "...",
    "blast_radius": "...",
    "fixes": ["...", "...", "..."],
    "word_count": 74
  }
}
```

## Configuration

The agent reuses the existing LLM settings, so no new secrets are introduced:

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | local Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.1` | local model name |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | hosted compatible endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | hosted model name |
| `OPENAI_API_KEY` | unset | required only for the hosted provider |
| `LLM_TIMEOUT_SECONDS` | `60` | provider request timeout |

When no provider is reachable the planner and postmortem use their
deterministic fallbacks, so `/agent/plan` and every experiment still work
offline.

## Tests

`backend/tests/test_agent_phase6.py` injects a fake LLM and covers a valid
plan, two invalid responses, the rule fallback, postmortem word limits, the
template fallback, the tools and both `/agent/plan` modes. The Phase 3 API
tests also verify that an experiment streams `agent:` logs and a structured
postmortem.

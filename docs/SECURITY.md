# Security policy

**This repository is public. Treat every commit as world-readable.**

## Golden rules

1. **No secrets in git.** Not in code, tests, docs, compose files, issues or
   screenshots.
2. **Backend reads secrets from the environment** via `python-dotenv` and
   `pydantic-settings` (`backend/core/config.py`) and the Phase 3 API settings
   in `backend/api_config.py`. No hardcoded fallbacks.
3. **Frontend gets public configuration only.** `import.meta.env` values must
   start with `VITE_` and be non-secret. An API key must never reach the
   browser bundle.
4. **All LLM traffic originates in the backend.** The frontend calls
   `POST /api/agent/diagnose`; it never talks to Ollama or OpenAI directly.
5. **Compose uses indirection only.** `env_file: ../.env` and `${VAR}` — never
   literal credentials.

## Environment files

```bash
cp .env.example .env
# fill in real values locally
```

- `.env` is ignored by git (`.env`, `.env.*`, `!.env.example`).
- `.env.example` contains **placeholders only** and is safe to publish.
- The backend loads `.env` from the repository root and optionally
  `backend/.env`.
- Production deployments should inject variables through the platform's secret
  manager rather than a file.

## Secret scanning

Installed once per clone:

```bash
pip install pre-commit
pre-commit install
```

The hook configuration (`.pre-commit-config.yaml`) runs:

1. **gitleaks** (`v8.30.1`) over staged changes, with the rules in
   `.gitleaks.toml`.
2. **`scripts/check_secrets.py`** — a fast fallback that also blocks staged
   `.env`, `*.pem`, `*.key` and `*.db` files.
3. A Python syntax check for changed files.

Rules:

- **Never** use `git commit --no-verify` to skip scanning.
- Run `pre-commit run --all-files` before opening a PR.
- CI must run gitleaks on every push once CI exists.

## If a secret leaks

1. **Rotate/revoke it immediately** at the provider. Assume compromise.
2. Remove it from the working tree and replace it with an env lookup.
3. Purge it from history (`git filter-repo` or BFG) and force-push the cleaned
   branches after coordinating with maintainers.
4. Audit provider logs for misuse.

Deleting it in a follow-up commit is **not** sufficient: the value remains in
history and in GitHub caches.

## Threat model notes

- ChaosPilot is a lab tool. It can stop containers and inject faults; do not
  point it at systems you do not own.
- The API has no authentication. Bind it to `127.0.0.1` (default) and never
  expose it to the public internet.
- SQLite contains operational telemetry, not credentials.
- LLM prompts include telemetry and fault metadata. Do not feed production
  secrets into the lab.
- CORS is restricted to the configured local frontend origins.

## Reporting

This is a learning/demo project, but please still report security issues
privately to the maintainers instead of opening a public issue with details.

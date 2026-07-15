# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

IdentityHub turns Non-Human Identity (NHI) findings into tracked **Jira** tickets, from a web UI or REST API. It's a **Flask REST API** (`identityhub/`) + a **React/TypeScript SPA** (`frontend/`) in one repo. Deep dives live in `README.md`, `DESIGN.md`, and `docs/` (`architecture.md`, `data-model.md`, `technology-stack.md`, `design-decisions.md`).

## Commands

Invoke Python tools via `.venv/bin/...`. Backend/frontend are driven from the `Makefile`.

```bash
make install                                     # .venv + backend + frontend deps
make init-db                                     # flask db upgrade
make dev                                          # Flask :5000 + Vite :5173 (hot reload) — open :5173
make build                                        # compile SPA to frontend/dist
make serve                                        # build SPA + serve all from Flask :5000

.venv/bin/python -m pytest                        # backend suite (pytest.ini: testpaths=tests)
.venv/bin/python -m pytest -m smoke               # fast critical-path gate
.venv/bin/python -m pytest tests/test_auth.py::test_name -v   # single test
cd frontend && npm test                           # vitest;  npm run lint  (eslint)
.venv/bin/python -m pytest e2e/                    # Playwright, opt-in (needs `make build` first)
```

## Architecture

- **App factory**: `identityhub/__init__.py` `create_app()` picks a `config.py` class by `FLASK_ENV` (`development`/`testing`/`e2e`/`production`), wires extensions (`identityhub/extensions.py`), blueprints, error handlers, CLI, and the SPA catch-all route.
- **Layered flow** (`docs/architecture.md`): Blueprint (`identityhub/blueprints/*`, all under `/api/*`) → auth middleware → Service → Model → SQLite. Blueprints validate/shape only and **never** call external systems directly — they delegate to services.
- **Services** (`identityhub/services/*`): `jira_service` (Jira Cloud REST v3, centralizes status→error mapping), `crypto_service` (Fernet), `nhi_digest` (blog scrape + Claude summary, run via `flask nhi-digest`, see `identityhub/cli/`).
- **Auth** (`identityhub/middleware/auth.py`): `@require_session` (cookie) or `@require_auth` (cookie **or** `X-API-Key`); both set `g.current_user` + `g.auth_method`. Absolute session timeout (`SESSION_LIFETIME_HOURS`, default 8h) enforced in a `before_request` in `__init__.py`.
- **Errors** (`identityhub/utils/errors.py`): raise `AppError` subclasses (`ValidationError` 400 … `JiraUnavailableError` 503) — handlers convert to `{"error","message"}` JSON. Prefer these over ad-hoc `jsonify(...), code`.

## Key constraints

- **Tickets are NOT persisted** — dashboard reads live from Jira every request; Jira is the source of truth. Never add a local Ticket table/cache. (`docs/data-model.md`)
- **Multi-tenant**: every query is scoped to `g.current_user.id`. New user-data endpoints must filter by the current user.
- **Three tables only** (`identityhub/models/*`): `User` (bcrypt), `JiraCredential` (Fernet-encrypted, 1:1), `ApiKey` (SHA-256 hashed, `nhk_` prefix, N:1).
- **Secrets from `.env`** (`SECRET_KEY`, `FERNET_KEY`, `ANTHROPIC_API_KEY`; see `.env.example`). `FERNET_KEY` is required to en/decrypt Jira credentials.
- **Migrations** via Flask-Migrate: `.venv/bin/flask db migrate -m "..."` → `flask db upgrade` (auto-run at container boot by `entrypoint.sh`).
- **SPA serving**: dev = Vite proxies `/api` → Flask (`frontend/vite.config.ts`); prod = one gunicorn process serves `frontend/dist` + JSON-404s unmatched `/api/*`. `frontend/src/` layout: `api/`, `context/AuthContext`, `hooks/`, `pages/`, `components/` (`ui/`, `layout/`, modals, `ProtectedRoute`).

## Tests

Fixtures in `tests/conftest.py` (`client`, `authenticated_client`, `register_and_login()`). E2E stubs Jira at the `requests` layer (`e2e/conftest.py`) — no live Jira account needed; a bare `pytest` skips `e2e/`.

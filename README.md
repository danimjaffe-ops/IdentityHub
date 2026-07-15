# IdentityHub

**IdentityHub is a Non-Human Identity (NHI) management platform with Jira
integration.** It gives security teams one place to turn NHI findings — stale
service accounts, overprivileged keys, expiring credentials — into tracked Jira
tickets, from either a web UI or a REST API.

Non-human identities (service accounts, API keys, tokens, workload identities)
now vastly outnumber human users, and their sprawl is hard to remediate.
IdentityHub closes the loop between *finding* an NHI risk and *acting* on it:
connect your Jira workspace once, then create and monitor remediation tickets
manually from the dashboard or automatically from your scanners and CI/CD
pipelines.

## Features

- **Jira ticket creation** — file NHI findings as Jira issues (summary +
  description) into any project you have access to.
- **Live ticket tracking** — the dashboard shows your most recent tickets pulled
  **live from Jira**, so it always reflects reality (deleted/edited issues
  update immediately). Jira is the single source of truth — nothing is cached.
- **REST API for automation** — scanners and CI/CD create tickets
  programmatically with an `X-API-Key` header. Generate, label, and revoke keys
  from Settings.
- **Secure Jira connection** — connect with your Atlassian email + API token;
  credentials are validated against Jira and **encrypted at rest**.
- **Account & auth** — email/password accounts, session-cookie login for the
  web UI, per-user data isolation (multi-tenant), and account deletion.
- **NHI blog digest (bonus)** — a CLI command that fetches the latest
  oasis.security blog post, summarizes it with Claude, and files it as a Jira
  ticket — cron-able for a recurring feed.

## Documentation

| Doc | What's inside |
|-----|---------------|
| [docs/architecture.md](docs/architecture.md) | Folder architecture and how the layers fit together |
| [docs/data-model.md](docs/data-model.md) | Entities, tables, relationships, and why tickets aren't persisted |
| [docs/technology-stack.md](docs/technology-stack.md) | Backend, frontend, and tooling choices with versions |
| [docs/design-decisions.md](docs/design-decisions.md) | Key decisions and their rationale (summary) |
| [docs/openapi.yaml](docs/openapi.yaml) | OpenAPI 3.1 spec for the REST API. Browse it interactively at `/api/docs` (Swagger UI) when the app is running. |
| [DESIGN.md](DESIGN.md) | Full design doc: tradeoffs, open questions, and how this scales |

## Setup

There are two ways to run IdentityHub:

- **[Option A — Docker](#option-a--run-with-docker-recommended-for-demoqa)**:
  the fastest way to see the whole system. Recommended for demos and QA. No
  Python or Node needed — just Docker.
- **[Option B — Local dev mode](#option-b--local-dev-mode-make-dev)**: run the
  backend and frontend dev servers directly for active development, with hot
  reload so code changes appear live.

All you need for either is a free
[Jira Cloud](https://www.atlassian.com/software/jira/free) account with an
[API token](https://id.atlassian.com/manage-profile/security/api-tokens).

### Option A — Run with Docker (recommended for demo/QA)

Runs the app the way it really deploys: one container where **gunicorn** serves
both the API and the compiled React UI. Good for demos, QA, and showing the
real system architecture — no Python or Node installed locally.

**Prerequisites:** Docker (with Compose).

```bash
# 1. Configure environment (secrets are read from .env, never baked into the image)
cp .env.example .env
# Edit .env — set SECRET_KEY and FERNET_KEY (see .env.example for generation commands)

# 2. Build and start
docker compose up --build
```

Open http://localhost:8000 in your browser.

Notes:
- The frontend is compiled during the image build (multi-stage: Node builds the
  SPA, then it's served by Flask/gunicorn) — there is no Vite dev server here.
- Database migrations run automatically on startup (`flask db upgrade`).
- SQLite data persists in the `identityhub-data` Docker volume across restarts.
  Run `docker compose down -v` to wipe it and start fresh.
- Served over plain HTTP, so `SESSION_COOKIE_SECURE` is disabled in
  `docker-compose.yml`; a real HTTPS deployment should re-enable it.
- **Runs alongside `make dev`.** The container publishes on host port **8000**
  (the app listens on 5000 *inside* the container), so `make dev` keeps
  5000/5173 free. Change the host port with `APP_PORT=9000 docker compose up`.

### Option B — Local dev mode (`make dev`)

Use this when you're **working on the code**. It runs the Flask API and the
Vite dev server directly on your machine (not in Docker), giving you **hot
reload**: edit a Python file and Flask restarts; edit a React file and the
browser updates instantly — no rebuild, no image to rebuild.

**Prerequisites:** Python 3.9+ and Node.js 18+.

```bash
# 1. Clone and install (creates .venv, installs backend + frontend deps)
make install

# 2. Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY and FERNET_KEY (see .env.example for generation commands)

# 3. Initialize the database
make init-db

# 4. Run both dev servers (Flask :5000 + Vite :5173)
make dev
```

Open http://localhost:5173 in your browser. (The Vite dev server proxies
`/api` calls to Flask on :5000.)

### First use

1. **Register** — create an account on the login page.
2. **Connect Jira** — paste your Atlassian site URL, email, and API token.
3. **Create a ticket** — select a project, fill in the title and description.
4. **View recent tickets** — see your 10 most recent tickets; click to open in Jira.

## Using the REST API

External systems can create tickets programmatically. Generate an API key from
the Settings page, then:

```bash
curl -X POST http://localhost:5000/api/tickets \
  -H "X-API-Key: nhk_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "project_key": "NHI",
    "summary": "Stale Service Account: svc-deploy-prod",
    "description": "Last used 90 days ago. Recommend rotation."
  }'
```

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/tickets` | API key or session | Create a ticket |
| GET | `/api/tickets?project_key=X&limit=10` | API key or session | List recent tickets |

Keys use the `nhk_` prefix, carry 256-bit entropy, and are stored as SHA-256
hashes.

## NHI blog digest

```bash
# Requires ANTHROPIC_API_KEY in .env
flask nhi-digest --user-email you@example.com --project-key NHI

# Preview without creating a ticket
flask nhi-digest --user-email you@example.com --project-key NHI --dry-run
```

## Development

```bash
make dev            # Run Flask + Vite dev servers
make dev-backend    # Flask only (port 5000)
make dev-frontend   # Vite only (port 5173)
make build          # Build frontend for production
make serve          # Build frontend + serve everything from Flask
```

### Tests

Three suites cover the stack:

```bash
# Backend unit + blueprint + service + smoke tests (pytest)
.venv/bin/python -m pytest              # full backend suite
.venv/bin/python -m pytest -m smoke     # fast critical-path smoke gate only

# Frontend unit/component tests (vitest + Testing Library)
cd frontend && npm test

# End-to-end browser tests (Playwright, full stack, Jira stubbed)
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
make build                              # E2E serves the built SPA
.venv/bin/python -m pytest e2e/
```

A bare `pytest` runs only the backend `tests/` suite; the browser-based `e2e/`
suite is invoked explicitly so day-to-day runs stay fast and browser-free.

## Security highlights

- Jira credentials encrypted at rest (Fernet: AES-128-CBC + HMAC)
- Passwords hashed with bcrypt
- Session cookies: `httpOnly`, `SameSite=Lax` (`Secure` in production)
- Absolute session timeout: logins expire a fixed time after sign-in regardless of activity (default 8h, `SESSION_LIFETIME_HOURS`)
- API keys: 256-bit entropy, SHA-256 hashed, `nhk_` prefix for identification
- Multi-tenancy: every query scoped to the authenticated user
- Jira credentials validated against `/rest/api/3/myself` before storage

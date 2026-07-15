# Technology Stack

IdentityHub pairs a Python/Flask REST API with a TypeScript/React single-page
app. Everything runs locally with no external infrastructure beyond a Jira
Cloud account (and, optionally, the Anthropic API for the blog digest).

## Backend

| Concern            | Choice                        | Version   | Why |
|--------------------|-------------------------------|-----------|-----|
| Language           | Python                        | 3.9+      | |
| Web framework      | Flask                         | 3.1.1     | Lightweight, blueprint-based routing |
| ORM                | SQLAlchemy (Flask-SQLAlchemy) | 3.1.1     | Mature ORM, DB-agnostic |
| Migrations         | Flask-Migrate (Alembic)       | 4.1.0     | Versioned schema changes |
| Database           | SQLite                        | (stdlib)  | Zero-setup for a PoC; swappable via `DATABASE_URL` |
| Session auth       | Flask-Login                   | 0.6.3     | Cookie sessions, `user_loader`, `strong` protection |
| CORS               | Flask-CORS                    | 5.0.1     | Allow the Vite dev origin with credentials |
| Password hashing   | bcrypt                        | 4.2.1     | Adaptive, salted password hashing |
| Encryption         | cryptography (Fernet)         | 44.0.0    | AES-128-CBC + HMAC for Jira secrets at rest |
| HTTP client        | requests                      | 2.32.3    | Calls to the Jira Cloud REST API |
| Config             | python-dotenv                 | 1.1.0     | Loads `.env` / `.flaskenv` |
| AI summarization   | anthropic                     | 0.52.0    | Claude summaries for the blog digest |
| HTML parsing       | beautifulsoup4 + lxml         | 4.13.4 / 5.4.0 | Scrape the NHI blog |

Full pinned list: [`requirements.txt`](../requirements.txt).

### External services

- **Jira Cloud REST API v3** — authenticated with per-user email + API token
  (HTTP Basic). Wrapped by `JiraService`; the app never persists tickets.
- **Anthropic API (Claude)** — used only by the `flask nhi-digest` CLI command,
  via `ANTHROPIC_API_KEY`. Model: `claude-sonnet-5`.

## Frontend

| Concern         | Choice              | Version  | Why |
|-----------------|---------------------|----------|-----|
| Language        | TypeScript          | ~5.8.3   | Type safety across API boundary |
| UI library      | React               | 19.1.0   | Component model |
| Routing         | react-router-dom    | 7.6.0    | Client-side routing, protected routes |
| Build tool      | Vite                | 6.3.5    | Fast dev server + optimized production build |
| Styling         | Tailwind CSS        | 3.4.17   | Utility-first styling (via PostCSS + autoprefixer) |
| Linting         | ESLint              | 9.25.0   | With React Hooks + Refresh plugins |

Full list: [`frontend/package.json`](../frontend/package.json).

The frontend has **no data-fetching or state-management library** — it uses the
native `fetch` API wrapped in a small typed client (`src/api/client.ts`, always
sends `credentials: "include"`) and React Context (`AuthContext`) for the
current user. This keeps the dependency surface minimal for a PoC.

## Tooling & runtime

- **Make** — task runner (`make install`, `make dev`, `make build`,
  `make serve`, `make init-db`). See [`Makefile`](../Makefile).
- **pytest** — backend test suite (`tests/`), using an in-memory SQLite DB
  (`TestingConfig`).
- **Flask CLI** — `flask db upgrade` (migrations) and the custom
  `flask nhi-digest` command.

## Configuration

Environment-driven via `config.py`, selected by `FLASK_ENV`
(`development` / `testing` / `production`):

| Variable            | Purpose |
|---------------------|---------|
| `SECRET_KEY`          | Flask session signing |
| `FERNET_KEY`          | Symmetric key for encrypting Jira credentials |
| `DATABASE_URL`        | DB connection string (defaults to SQLite file) |
| `ANTHROPIC_API_KEY`   | Claude access for the blog digest (optional) |
| `SESSION_LIFETIME_HOURS` | Absolute session timeout in hours (default `8`) |
| `FLASK_ENV`           | Selects the config class |

Production hardens cookies (`SESSION_COOKIE_SECURE = True`); development and
testing relax it for local HTTP. Sessions carry an **absolute timeout**:
`PERMANENT_SESSION_LIFETIME` (from `SESSION_LIFETIME_HOURS`) bounds how long a
login is valid after sign-in, and `SESSION_REFRESH_EACH_REQUEST = False` keeps
that deadline from sliding on activity. See [`.env.example`](../.env.example)
for generation commands.

## Runtime topology

```
Development                              Production
───────────                              ──────────
Vite dev server  :5173  ──/api proxy──▶  Single Flask process  :5000
Flask dev server :5000                   ├── /api/*        → blueprints
                                         └── /*            → frontend/dist (SPA)
```

For the rationale behind these choices, see [design-decisions.md](design-decisions.md)
and the full [DESIGN.md](../DESIGN.md).

# Folder Architecture

IdentityHub is a monorepo containing a **Flask REST API** (`identityhub/`) and a
**React SPA** (`frontend/`). In development they run as two servers; in
production Flask serves the built frontend as static files.

```
FlaskProject/
├── app.py                  # Entry point: app = create_app()
├── config.py               # Config classes (Development / Testing / Production)
├── requirements.txt        # Python dependencies
├── Makefile                # install / dev / build / serve / init-db targets
├── .flaskenv               # FLASK_APP=app.py (loaded by flask CLI)
├── .env / .env.example     # SECRET_KEY, FERNET_KEY, ANTHROPIC_API_KEY, ...
│
├── identityhub/            # ── Flask application package ──
│   ├── __init__.py         #   App factory (create_app), extension init, SPA fallback route
│   ├── extensions.py       #   Singletons: db, migrate, login_manager, cors
│   │
│   ├── blueprints/         #   HTTP routes, grouped by resource, all under /api/*
│   │   ├── __init__.py     #     register_blueprints() wires URL prefixes
│   │   ├── auth.py         #     /api/auth   — register, login, logout, me, delete account
│   │   ├── jira.py         #     /api/jira   — connect/disconnect credentials, status, projects
│   │   ├── tickets.py      #     /api/tickets — create + list (live from Jira)
│   │   └── api_keys.py     #     /api/keys   — generate, list, revoke API keys
│   │
│   ├── models/             #   SQLAlchemy ORM models (one file per table)
│   │   ├── user.py         #     User (auth, bcrypt password, relationships)
│   │   ├── jira_credential.py  # JiraCredential (encrypted, 1:1 with User)
│   │   └── api_key.py      #     ApiKey (SHA-256 hashed, N:1 with User)
│   │
│   ├── services/           #   Business logic, isolated from HTTP layer
│   │   ├── jira_service.py #     Jira Cloud REST API v3 client
│   │   ├── crypto_service.py #   Fernet encrypt() / decrypt() helpers
│   │   └── nhi_digest.py   #     Blog scraper + Claude summarization
│   │
│   ├── middleware/         #   Auth decorators
│   │   └── auth.py         #     @require_session, @require_auth (session OR API key)
│   │
│   ├── cli/                #   Flask CLI commands
│   │   └── digest.py       #     `flask nhi-digest` command
│   │
│   └── utils/              #   Cross-cutting helpers
│       └── errors.py       #     AppError hierarchy + JSON error handlers
│
├── frontend/               # ── React SPA (Vite + TypeScript) ──
│   ├── index.html          #   HTML entry
│   ├── vite.config.ts      #   Dev server (port 5173) + /api proxy to Flask
│   ├── tailwind.config.js  #   Tailwind theme
│   ├── package.json        #   React 19, react-router-dom 7
│   └── src/
│       ├── main.tsx        #     React root
│       ├── App.tsx         #     Router: /login, / (dashboard), /settings
│       ├── api/            #     Typed API client modules (client, auth, jira, tickets, keys)
│       ├── components/     #     ui/ primitives, layout/ shell, feature modals, ProtectedRoute
│       ├── pages/          #     LoginPage, DashboardPage, SettingsPage
│       ├── context/        #     AuthContext (current user, login/logout)
│       ├── hooks/          #     useAuth, useApi
│       └── types/          #     Shared TypeScript interfaces
│
├── migrations/             # Alembic (Flask-Migrate) migration scripts
│   └── versions/           #   Ordered schema migrations
│
├── tests/                  # Backend pytest suite
│   ├── conftest.py         #   Fixtures (app, client, authenticated user)
│   └── test_*.py           #   Per-blueprint tests
│
├── docs/                   # This documentation
├── DESIGN.md               # Full design rationale, tradeoffs, future work
└── README.md               # Setup + usage
```

## Layering

The backend follows a conventional layered flow, keeping HTTP concerns out of
business logic:

```
Request → Blueprint (validate input, shape response)
            ↓ uses
          Middleware (@require_auth / @require_session sets g.current_user)
            ↓ calls
          Service (JiraService, crypto, digest — business logic, external I/O)
            ↓ reads/writes
          Model (SQLAlchemy) → SQLite
```

- **Blueprints** never talk to external systems directly; they delegate to
  services. They own request parsing, validation, and response formatting.
- **Services** are framework-light and hold the domain logic (talking to Jira,
  encrypting secrets, scraping/summarizing). `JiraService` is instantiated with
  a `JiraCredential` and decrypts secrets lazily.
- **Middleware** decorators resolve the caller into `g.current_user` and record
  `g.auth_method` (`"session"` or `"api_key"`), so blueprints stay auth-agnostic.
- **Errors** raised anywhere as `AppError` subclasses are converted to JSON by
  the handlers registered in `utils/errors.py`.

## Request routing (production)

In production a single Flask process serves everything. The catch-all route in
`identityhub/__init__.py` returns `frontend/dist` assets and falls back to
`index.html` for client-side routes, while any unmatched `/api/*` path returns a
JSON 404 instead of the SPA. In development, Vite (5173) proxies `/api` to
Flask (5000), so the frontend code is identical in both modes.

See [technology-stack.md](technology-stack.md) for the tools involved and
[data-model.md](data-model.md) for the persisted entities.

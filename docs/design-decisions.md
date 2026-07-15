# Design Decisions

This is a summary of the key decisions baked into the current implementation.
For the full treatment — including decisions still to be made, open product
questions, and improvements for scaling beyond a PoC — see the root
[DESIGN.md](../DESIGN.md).

## 1. Monolithic Flask API + React SPA

**Decision:** One Flask app exposing a JSON REST API under `/api/*`, plus a
separate React SPA. In production Flask serves the built SPA; in development
Vite proxies `/api` to Flask.

**Why:** Clean separation of concerns with a single deployable unit. The SPA is
fully decoupled from the API (talks only HTTP/JSON), so it could later be hosted
on a CDN unchanged. A microservice split would be premature for this scope.

## 2. Two authentication methods: sessions + API keys

**Decision:** The web UI uses **session cookies** (Flask-Login, `httpOnly`,
`SameSite=Lax`, `strong` protection). Programmatic clients (scanners, CI/CD) use
**API keys** via the `X-API-Key` header. The `@require_auth` decorator accepts
either; `@require_session` accepts only cookies (used for account management).

**Why:** Cookies are the right fit for a browser (automatic, XSS-resistant when
`httpOnly`). API keys suit headless automation, which is the primary way tickets
get created. Both resolve to the same `g.current_user`, so route handlers stay
auth-agnostic.

Sessions carry an **absolute timeout** (default 8h, `SESSION_LIFETIME_HOURS`): a
`login_at` timestamp is stamped at sign-in and checked in a `before_request`
hook, so a login expires a fixed time after it starts regardless of activity.
API-key requests carry no session and are unaffected.

## 3. Jira via API token, not OAuth 2.0

**Decision:** Users paste their Atlassian **email + API token**; the app stores
them encrypted and calls Jira with HTTP Basic auth.

**Why:** No OAuth app registration, callback URLs, or token-refresh machinery —
fastest path to a working integration for a PoC. The tradeoff (broad token
scope, manual revocation) is acceptable here; OAuth 3LO is documented as a
future improvement in DESIGN.md.

## 4. Credentials encrypted at rest (Fernet)

**Decision:** Jira email and API token are encrypted with **Fernet**
(AES-128-CBC + HMAC) using a `FERNET_KEY` env var, stored as `LargeBinary`.
Passwords are hashed with **bcrypt**. API keys are stored only as **SHA-256**
hashes plus a display prefix.

**Why:** Secrets should never be recoverable from a database dump. Fernet is
reversible (we must send the real token to Jira); passwords and API keys are
one-way (we only ever compare), so hashing is stronger and correct there.

## 5. SQLite via SQLAlchemy + Flask-Migrate

**Decision:** SQLite for storage, accessed through SQLAlchemy, with schema
managed by Alembic migrations. The DB URI is overridable via `DATABASE_URL`.

**Why:** Zero-setup persistence for a PoC. Because access goes through the ORM
and a config-driven URI, moving to PostgreSQL later is a config change, not a
rewrite.

## 6. Jira is the single source of truth for tickets

**Decision:** Tickets are **not** persisted locally (the original `tickets`
table was dropped). Create proxies straight to Jira; "Recent Tickets" is fetched
live via JQL on each request.

**Why:** Avoids a stale local cache and a sync problem. Tickets deleted or
edited in Jira reflect immediately. The cost is a hard dependency on Jira
availability — handled explicitly (see #7).

## 7. Graceful degradation vs. real errors

**Decision:** `JiraUnavailableError` (connection failure, timeout, HTTP 5xx) is
distinguished from `JiraError` (auth/permission/validation). On the list
endpoint, an *unavailable* Jira returns `{"tickets": [], "unavailable": true}`
so the dashboard shows a notice; genuine errors (bad credentials, 403) still
surface to the user.

**Why:** An outage shouldn't look like a bug, and a bug shouldn't be silently
swallowed as an outage. Since there's no local cache to fall back on, the UI
needs to tell these two states apart.

## 8. Per-user multi-tenancy

**Decision:** Every DB query is scoped by `user_id`; each user has at most one
Jira connection and their own API keys. Jira reads use the caller's own
credentials.

**Why:** Simple, enforceable isolation with no user able to read another's data
— sufficient for the PoC. An org/RBAC model is noted as future work.

## 9. Minimal frontend dependencies

**Decision:** No data-fetching or global-state library. Native `fetch` behind a
small typed client, plus React Context for auth.

**Why:** Keeps the surface small and the app easy to reason about at this size.

## 10. Structured errors via an exception hierarchy

**Decision:** Domain code raises `AppError` subclasses (`ValidationError`,
`NotFoundError`, `ConflictError`, `JiraError`, `JiraUnavailableError`, …), each
carrying an HTTP status. Central handlers in `utils/errors.py` render them (and
generic 404/405/500) as consistent JSON `{error, message}`.

**Why:** Handlers raise intent, not HTTP plumbing; every error response has the
same shape for the frontend to consume.

## 11. Blog digest as a CLI command

**Decision:** The NHI blog digest (scrape → Claude summary → Jira ticket) is a
Flask CLI command (`flask nhi-digest`) with a `--dry-run`, not an HTTP endpoint.

**Why:** It's a batch/scheduled job, not an interactive request. A CLI command
is trivially cron-able and keeps the long-running scrape+LLM work off the web
request path.

---

For decisions still open, product questions, and how this would evolve into a
larger system (async ticket creation, OAuth 3LO, org/RBAC, PostgreSQL,
event-driven architecture, observability, deployment), see
[DESIGN.md](../DESIGN.md).

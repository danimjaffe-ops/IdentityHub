# IdentityHub — Design Document

## Overview

IdentityHub is a Non-Human Identity (NHI) management platform with Jira integration. Users can report NHI findings (stale service accounts, overprivileged keys, expiring credentials) as Jira tickets — from both a web UI and a programmatic REST API.

This document captures architectural decisions, open questions, and known tradeoffs between the PoC scope and a production system.

---

## 1. Decisions Made

### 1.1 Architecture: Monolithic Flask API + React SPA

**Decision:** Single Flask process serving a JSON API, with a React/Vite SPA as the frontend. In production, Flask serves the built SPA static files. In development, Vite runs a dev server with a proxy to Flask.

**Why:** Clear separation between UI and backend layers (an explicit evaluation criterion) while keeping deployment to a single process. The API is the contract — the React UI and external API consumers (scanners, CI/CD) both call the same endpoints. No BFF (Backend-for-Frontend) indirection.

**Alternatives considered:**
- Server-rendered Jinja templates: simpler, but weaker UI/backend separation. The REST API would exist alongside server-rendered routes, muddying the architecture.
- Separate API server + SPA with NGINX: production-grade but overkill for a PoC.

### 1.2 Authentication: Session Cookies (Web) + API Keys (Programmatic)

**Decision:** Web users authenticate via Flask-Login with server-side sessions stored as httpOnly cookies. External systems authenticate via `X-API-Key` header with SHA-256 hashed keys.

**Why:** Two distinct auth mechanisms for two distinct use cases:
- **Sessions** for browser users: httpOnly + SameSite=Lax cookies are immune to XSS token theft (unlike JWT in localStorage). Flask-Login handles the entire lifecycle.
- **API keys** for machines: stateless, no session overhead, easy to rotate. The `nhk_` prefix makes keys identifiable in logs and secret scanners.

**Why not JWT?** JWTs solve a problem we don't have (stateless auth across distributed services). This is a single-server PoC. Sessions are simpler, more secure by default, and revocable instantly (no token expiry window). The REST API already uses API keys, so JWT adds no value.

**Why SHA-256 for API keys instead of bcrypt?** API keys are machine-generated with 256 bits of entropy (64 hex characters). Brute-force is infeasible regardless of hash speed. SHA-256 enables O(1) DB lookup by hash, which bcrypt cannot do (you'd need to hash-and-compare against every stored key). This is a deliberate, security-sound choice — not a shortcut.

### 1.3 Jira Integration: API Token (not OAuth 2.0)

**Decision:** Users provide their Atlassian email + API token, which are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256). The app uses these to call Jira's REST API v3 with HTTP Basic Auth.

**Why:** Zero setup friction — the reviewer doesn't need to register an OAuth app on developer.atlassian.com or configure callback URLs. Just generate a token at https://id.atlassian.com/manage-profile/security/api-tokens and paste it in.

**Security measures:**
- Credentials encrypted at rest with Fernet. Encryption key (`FERNET_KEY`) loaded from environment variable, never committed to source control.
- Credentials validated against Jira's `/rest/api/3/myself` endpoint before being stored — we never persist credentials that don't work.
- Email stored encrypted (not plaintext) because it's part of the auth credential pair.
- Site URL stored in plaintext (it's a public domain, not a secret).

**Tradeoff:** API tokens don't expire automatically, don't support scoped permissions, and can't be revoked per-app. OAuth 2.0 (3LO) would be better for a production product. See section 4.

### 1.4 Database: SQLite via SQLAlchemy + Flask-Migrate

**Decision:** SQLite for storage, SQLAlchemy as the ORM, Flask-Migrate (Alembic) for schema migrations.

**Why:** Zero-config, file-based, no external service needed. The reviewer runs `make install && make dev` — no Docker, no PostgreSQL setup. SQLAlchemy's abstraction means swapping to PostgreSQL is a config change (`DATABASE_URL` env var), not a code change.

**Schema design:**
- **User**: email (unique), bcrypt password hash
- **JiraCredential**: one-to-one with User. Encrypted email + token. Unique constraint on user_id prevents duplicate connections.
- **ApiKey**: SHA-256 hash (unique index for lookup), prefix for display, soft-delete via `is_active` flag for audit trail.

> Note: there is no `Ticket` table. Tickets are read live from Jira (see 1.6); Jira is the single source of truth and nothing is persisted locally.

### 1.5 Multi-Tenancy: Per-User Isolation

**Decision:** Every database query filters by `user_id`. Users see only their own Jira credentials and API keys. Enforced at the middleware level — `g.current_user` is set by the auth decorator, and all downstream code uses it. Ticket isolation is handled by Jira itself: each user lists tickets through their own Jira credential with `reporter = currentUser()` (see 1.6).

**Why:** The requirement says "multiple concurrent users without data interference." Per-user isolation is the simplest model that satisfies this. No shared state, no cross-user queries, no authorization matrix.

### 1.6 Recent Tickets: Live from Jira (Single Source of Truth)

**Decision:** "Recent Tickets" is fetched live from Jira via JQL (`reporter = currentUser()`, optionally scoped to a project, `ORDER BY created DESC`, endpoint `GET /rest/api/3/search/jql`). Created tickets are **not** persisted locally — there is no `tickets` table. Ticket creation returns the Jira key/id straight from the create call.

> **History:** The original design cached every created ticket in a local `tickets` table and rendered "Recent Tickets" from that table. Because nothing reconciled the table with Jira, a ticket **deleted in Jira still appeared** in the list — the bug that motivated this change. Reading live makes deletions (and edits, and tickets created outside the app) reflect immediately.

**Why:**
- **Correctness over caching:** a local copy inevitably drifts from Jira. Reading live means the displayed list always matches Jira's actual state.
- **Simpler model:** no `tickets` table, no migration to keep in sync, no per-row lifecycle to reconcile.
- **Isolation moves to Jira:** each user queries with their own Jira credential and `reporter = currentUser()`, so users see only their own recently-created issues without app-level `user_id` filtering.

**Resilience (Jira outage handling):** Because the read path now depends on Jira, `list_tickets` distinguishes a Jira *outage* from a *real error*:
- Connection failure, timeout, or 5xx → `JiraUnavailableError` → the endpoint returns `200 {"tickets": [], "unavailable": true}` and the dashboard shows a "Jira is currently unavailable" notice instead of breaking.
- Bad credentials / permission errors (401/403) → still surface to the user (502), because they are genuine misconfiguration, not an outage.

We deliberately do **not** fall back to a stale local cache on outage — the whole point of the change is to never show deleted/stale tickets. An outage yields an empty list with a clear notice.

**Tradeoffs:**
- Listing costs a Jira API round-trip per load (previously a local query).
- During a Jira outage, Recent Tickets is empty (with a notice) rather than serving cached rows.
- We no longer keep an audit log of app-created tickets or their `source` (web/api/cli) origin. If an audit trail is later required, it should be a separate append-only log — never the display source. See 4.6.

### 1.7 Jira Field Scope: Summary + Description + Issue Type

**Decision:** Ticket creation supports three fields: summary (title), description (body text), and issue type (defaults to "Task"). No priority, labels, components, assignee, custom fields, or sprints.

**Why:** The exercise asks us to define which fields to support and document the reasoning. These three fields are:
- **Sufficient** for the NHI finding use case (title like "Stale Service Account: svc-deploy-prod" + description with finding details).
- **Universal** — every Jira project has these fields. Custom fields vary per project and require schema discovery.
- **Simple** — adding more fields increases validation complexity and UI surface area without demonstrating architectural skills.

A production version would add a field-mapping configuration per project. See section 4.

### 1.8 Synchronous Request-Response (No Event-Driven Architecture)

**Decision:** All operations are synchronous. Ticket creation blocks until the Jira API responds. No message queue, no background workers, no event bus.

**Why:** For a PoC with low concurrency, synchronous is correct:
- Simpler to reason about, debug, and test.
- No infrastructure dependencies (Redis, RabbitMQ, Celery).
- Error handling is straightforward — the user sees success or failure immediately.
- The Jira API responds in 200-500ms typically, which is acceptable for a PoC.

See section 4 for where async/event-driven patterns would matter at scale.

### 1.9 Blog Digest: CLI Command with Optional Cron

**Decision:** The NHI Blog Digest is a Flask CLI command (`flask nhi-digest`) that runs once when invoked. Scheduling is left to the operator (cron, systemd timer, CI/CD scheduled job).

**Why:** The exercise says "any trigger/scheduled can work." A CLI command is the most portable option — it works with any scheduling system. Embedding a scheduler in the Flask app (e.g., APScheduler) couples the background job to the web process lifecycle, which is fragile.

---

## 2. Decisions That Need to Be Made

### 2.1 Session Storage Backend

**Current:** Flask's default cookie-based sessions (signed, not encrypted). Session data is stored client-side in the cookie, signed with `SECRET_KEY`.

**Issue:** Cookie-based sessions can't be revoked server-side (logging out clears the client cookie, but a captured cookie remains valid until it expires). An **absolute session timeout** (`PERMANENT_SESSION_LIFETIME`, default 8h via `SESSION_LIFETIME_HOURS`) bounds that exposure window — a stamped `login_at` is checked in a `before_request` hook and the deadline does not slide with activity (`SESSION_REFRESH_EACH_REQUEST = False`) — but it does not give *instant* revocation. For a PoC this is acceptable, but a production system needs server-side sessions.

**Options:**
- Flask-Session with Redis: server-side storage, instant revocation, but adds Redis dependency.
- Flask-Session with SQLAlchemy: server-side storage using the existing DB, no new dependencies, but adds DB load on every request.
- Keep cookie-based for the PoC, document the limitation.

**Current choice:** Cookie-based (PoC simplicity). Revisit if security review flags it.

### 2.2 CORS Configuration

**Current:** Flask-CORS allows `http://localhost:5173` (Vite dev server) with `supports_credentials=True`.

**Needs decision:** In production, the SPA is served from Flask (same origin), so CORS isn't needed. Should CORS be disabled entirely in production config, or should it allow configurable origins for cases where the SPA is hosted separately?

### 2.3 API Key Scoping

**Current:** An API key grants full access to the user's account (create tickets, list tickets). There's no per-key permission scoping.

**Needs decision:** Should API keys be scopeable (e.g., "this key can only create tickets in project X")? For the PoC, full access per key is fine. But if a user generates a key for a CI pipeline, they might want to limit its blast radius.

### 2.4 Error Response Standardization

**Current:** Error responses follow `{ "error": "<type>", "message": "<detail>" }`.

**Needs decision:** Should we adopt a formal error standard like RFC 7807 (Problem Details for HTTP APIs)? It adds `type` (URI), `title`, `status`, `detail`, and `instance` fields. More structured, but heavier for a PoC.

### 2.5 Jira Cloud vs. Data Center

**Current:** The implementation targets Jira Cloud (REST API v3, ADF for descriptions, `*.atlassian.net` domains).

**Needs decision:** Should we support Jira Data Center (on-premise)? It uses REST API v2, wiki markup for descriptions, and arbitrary domains. Supporting both adds branching logic in the Jira service layer.

**Current choice:** Cloud only. Document as a known limitation.

---

## 3. Questions to Ask (Product/Stakeholder)

### 3.1 Ticket Enrichment
> Should the NHI finding ticket include structured metadata beyond title and description? For example: severity level, affected identity type (service account / API key / certificate), cloud provider, last-seen timestamp, remediation steps. These could map to Jira labels, priority, or custom fields.

### 3.2 Jira Project Restrictions
> Should users be able to create tickets in any Jira project, or should there be a way for admins to restrict which projects are available? A "scanner" API key posting to the wrong project could create noise.

### 3.3 Ticket Deduplication
> If a scanner reports the same stale service account twice, should we detect the duplicate and update the existing ticket instead of creating a new one? This requires a deduplication key (e.g., identity name + project).

### 3.4 Bulk Ticket Creation
> The REST API creates one ticket per request. Should there be a bulk endpoint for scanners that discover hundreds of findings at once? This has implications for rate limiting and Jira API quotas.

### 3.5 Webhook / Callback Support
> When a ticket is created via the API, should we support a callback URL that receives the Jira ticket key once creation completes? This matters if we move to async ticket creation.

### 3.6 Audit Logging
> Beyond tracking which tickets were created, should we log all actions (login, credential changes, API key generation, failed auth attempts)? This would be important for compliance in an identity management product.

### 3.7 Ticket Lifecycle
> Should the app track ticket status changes after creation (e.g., mark a finding as "resolved" when the Jira ticket moves to Done)? This would require Jira webhooks or periodic polling.

### 3.8 Multi-User Jira Workspaces
> Can multiple IdentityHub users connect to the same Jira workspace? If so, do they see each other's tickets (created through the app), or is visibility strictly per-user? The current design is per-user — User A cannot see tickets User B created, even in the same Jira project.

### 3.9 Blog Digest Scope
> The bonus feature fetches from oasis.security/blog specifically. Should the blog digest be configurable (any RSS/blog URL), or is this a fixed integration with Oasis Security's content?

---

## 4. Improvements for a Larger System (Fine for PoC)

### 4.1 Async Ticket Creation

**PoC:** Synchronous — the API blocks until Jira responds (~200-500ms).

**Production:** Jira API calls should be offloaded to a task queue (Celery + Redis). The API returns `202 Accepted` with a ticket ID immediately. The client polls or subscribes (WebSocket/SSE) for the final Jira key. Benefits:
- API response time drops to ~20ms regardless of Jira latency.
- Automatic retries on transient Jira failures.
- Rate limit management (Jira Cloud allows ~100 requests/minute per user).

### 4.2 OAuth 2.0 (3-Legged) for Jira

**PoC:** API token pasted by the user, encrypted at rest.

**Production:** Atlassian OAuth 2.0 (3LO) with PKCE:
- Scoped permissions (read projects, create issues — nothing more).
- Automatic token refresh (refresh tokens with configurable expiry).
- Per-app revocation (user can revoke IdentityHub's access without rotating their global API token).
- Consent screen shows exactly what the app can do.
- Eliminates the need to store long-lived credentials entirely — only refresh tokens, which are scoped and revocable.

### 4.3 Organization Model with RBAC

**PoC:** Per-user isolation, no concept of teams.

**Production:** 
- Organizations with multiple users.
- Roles: Admin (manage Jira connection, API keys, user invites), Member (create tickets, view team tickets), Viewer (read-only).
- Shared Jira connection per organization (one OAuth grant, used by all members).
- Ticket visibility scoped to the organization, not the individual.

### 4.4 Database: PostgreSQL + Connection Pooling

**PoC:** SQLite (single-writer, file-based).

**Production:**
- PostgreSQL for concurrent writes, proper transactions, and JSON column support.
- Connection pooling (PgBouncer or SQLAlchemy pool) for efficiency under load.
- Read replicas for the "recent tickets" query path if read volume is high.
- The SQLAlchemy ORM layer means this is a config change, not a code rewrite.

### 4.5 Event-Driven Architecture

**PoC:** Direct, synchronous calls.

**Production:** Event bus (e.g., Redis Streams, Kafka, or even a simple PostgreSQL LISTEN/NOTIFY):
- `ticket.created` event triggers: Slack notification, audit log, analytics update, SLA timer start.
- `jira.webhook` events trigger: ticket status sync, resolution tracking.
- `credential.expiring` events trigger: reminder notifications.
- Decouples the write path from downstream consumers — adding a new reaction doesn't modify the ticket creation code.

### 4.6 Jira Ticket Sync

**PoC:** Recent Tickets is read live from Jira (see 1.6), so status and deletions are always current on read. There is no local ticket store to reconcile.

**Production:** Even with live reads, a push model beats querying Jira on every dashboard load:
- Register a Jira webhook to receive create / update / delete / status-change events.
- Maintain a read-optimized projection updated from those events, with a periodic reconciliation job to catch missed webhooks.
- `ticket.created` and status-change events can then drive Slack notifications, SLA timers, and analytics without re-querying Jira.
- If an audit trail of app-created tickets is needed, capture it here as a separate append-only log — kept distinct from the display path so it can never reintroduce the stale-data bug.

### 4.7 Field Mapping and Custom Fields

**PoC:** Fixed fields (summary, description, issue type).

**Production:**
- Per-project field mapping configuration.
- Discovery of available issue types, priorities, components, and custom fields via Jira's `/rest/api/3/issue/createmeta` endpoint.
- Template system: pre-configured ticket templates for common NHI finding types (stale account, overprivileged key, expiring certificate).
- Markdown-to-ADF conversion for rich descriptions.

### 4.8 Rate Limiting and Abuse Prevention

**PoC:** No rate limiting.

**Production:**
- Per-API-key rate limits (e.g., 60 requests/minute).
- Per-user Jira API call budget (respecting Atlassian's rate limits).
- Request size limits on description field.
- CAPTCHA or proof-of-work on registration to prevent spam accounts.

### 4.9 Observability

**PoC:** Flask's default logging.

**Production:**
- Structured JSON logging (correlation IDs across request lifecycle).
- Metrics: ticket creation latency, Jira API error rate, active sessions, API key usage.
- Distributed tracing (OpenTelemetry) for the full request path: Flask → Jira API → DB.
- Health check endpoint (`/api/health`) for load balancer probes.
- Alerting on: Jira credential failures (token revoked?), error rate spikes, queue depth.

### 4.10 Security Hardening

**PoC:** Fernet encryption, bcrypt passwords, httpOnly cookies, absolute session timeout, input validation.

**Production additions:**
- Server-side sessions (Redis-backed) for instant revocation.
- CSRF protection (double-submit cookie pattern for the SPA).
- Content Security Policy headers.
- API key IP allowlisting.
- Secrets management (AWS Secrets Manager / HashiCorp Vault) instead of env vars.
- Encryption key rotation support (Fernet MultiFernet with key versioning).
- Penetration testing and OWASP ZAP scan.
- SOC 2 compliance logging (all auth events, credential access, data export).

### 4.11 Deployment

**PoC:** `make dev` runs Flask dev server + Vite dev server locally.

**Production:**
- Docker multi-stage build (Node build stage → Python runtime stage).
- Gunicorn/uWSGI as the WSGI server (not Flask's dev server).
- NGINX reverse proxy for TLS termination, static file serving, and request buffering.
- Kubernetes or ECS for orchestration, auto-scaling, and rolling deployments.
- CI/CD pipeline: lint → test → build → deploy with environment promotion (staging → production).

---

## Appendix: Technology Stack Summary

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.10 |
| Web Framework | Flask | 3.1 |
| ORM | SQLAlchemy (via Flask-SQLAlchemy) | 3.1 |
| Migrations | Alembic (via Flask-Migrate) | 4.1 |
| Database | SQLite | (bundled) |
| Session Management | Flask-Login | 0.6 |
| Password Hashing | bcrypt | 4.2 |
| Credential Encryption | cryptography (Fernet) | 44.0 |
| HTTP Client | requests | 2.32 |
| Frontend Framework | React | 18.x |
| Build Tool | Vite | 6.x |
| CSS | Tailwind CSS | 3.x |
| Routing | react-router-dom | 6.x |
| Language (Frontend) | TypeScript | 5.x |
| AI Summarization | Anthropic Claude API | claude-sonnet-4-20250514 |
| Web Scraping | BeautifulSoup + lxml | 4.13 / 5.4 |

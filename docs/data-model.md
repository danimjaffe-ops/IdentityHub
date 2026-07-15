# Data Model

IdentityHub persists only what it must: **users, their (encrypted) Jira
credentials, and their API keys.** Tickets are **not** stored — Jira is the
single source of truth for tickets, so the app reads them live and holds no
local copy (the original `tickets` table was dropped in migration
`a1b2c3d4e5f6`).

The database is SQLite via SQLAlchemy, managed with Flask-Migrate (Alembic).

## Entity–relationship overview

```
┌────────────────────┐
│       User         │
│────────────────────│
│ id            PK    │
│ email     UNIQUE    │
│ password_hash       │   1        0..1   ┌──────────────────────────┐
│ created_at          │───────────────────│     JiraCredential       │
└────────────────────┘                    │──────────────────────────│
          │ 1                              │ id                 PK     │
          │                                │ user_id     FK, UNIQUE    │
          │ N                              │ site_url                  │
┌────────────────────┐                     │ email_encrypted   (bytes) │
│      ApiKey        │                     │ api_token_encrypted (bytes)│
│────────────────────│                     │ created_at                │
│ id            PK    │                     └──────────────────────────┘
│ user_id       FK    │
│ key_hash  UNIQUE    │
│ key_prefix          │
│ label               │
│ is_active           │
│ last_used_at        │
│ created_at          │
└────────────────────┘
```

Relationships (declared in `identityhub/models/`):

- `User` **1 : 0..1** `JiraCredential` — a user has at most one Jira connection
  (`user_id` is `UNIQUE`). `cascade="all, delete-orphan"`.
- `User` **1 : N** `ApiKey` — many keys per user (`lazy="dynamic"`).
  `cascade="all, delete-orphan"`.
- Deleting a `User` cascades to its credential and keys.

## Tables

### `users`

| Column          | Type          | Constraints                     | Notes |
|-----------------|---------------|---------------------------------|-------|
| `id`            | Integer       | PK                              | |
| `email`         | String(255)   | UNIQUE, NOT NULL, indexed       | Normalized to lowercase on write |
| `password_hash` | String(255)   | NOT NULL                        | **bcrypt** hash (never plaintext) |
| `created_at`    | DateTime      | NOT NULL, default now (UTC)     | |

Methods: `set_password()` / `check_password()` (bcrypt), `to_dict()` (exposes
`has_jira_credentials`, never the hash).

### `jira_credentials`

| Column                 | Type        | Constraints              | Notes |
|------------------------|-------------|--------------------------|-------|
| `id`                   | Integer     | PK                       | |
| `user_id`              | Integer     | FK→users, UNIQUE, NOT NULL | Enforces one connection per user |
| `site_url`             | String(500) | NOT NULL                 | e.g. `https://your-org.atlassian.net` (plaintext) |
| `email_encrypted`      | LargeBinary | NOT NULL                 | **Fernet**-encrypted Jira email |
| `api_token_encrypted`  | LargeBinary | NOT NULL                 | **Fernet**-encrypted Jira API token |
| `created_at`           | DateTime    | NOT NULL, default now    | |

The secrets are encrypted at rest with Fernet (AES-128-CBC + HMAC) via
`crypto_service`. `site_url` is stored in plaintext because it is not sensitive.

### `api_keys`

| Column         | Type        | Constraints                | Notes |
|----------------|-------------|----------------------------|-------|
| `id`           | Integer     | PK                         | |
| `user_id`      | Integer     | FK→users, NOT NULL, indexed | |
| `key_hash`     | String(64)  | UNIQUE, NOT NULL, indexed  | **SHA-256** of the full key |
| `key_prefix`   | String(12)  | NOT NULL                   | First 12 chars (`nhk_xxxxxxxx`) for display |
| `label`        | String(100) | nullable                   | User-supplied name |
| `is_active`    | Boolean     | NOT NULL, default true     | Revocation flips this to false (soft delete) |
| `last_used_at` | DateTime    | nullable                   | Updated on each authenticated API call |
| `created_at`   | DateTime    | NOT NULL, default now      | |

**Key lifecycle:** on generation the raw key `nhk_<64 hex chars>` (256-bit
entropy) is returned to the user **exactly once**; only its SHA-256 hash and
12-char prefix are stored. Authentication hashes the incoming `X-API-Key`
header and looks up an active record. Revocation sets `is_active = false`
rather than deleting, preserving the audit trail (`last_used_at`).

## Tickets (not persisted)

There is no `tickets` table. Ticket create/list operations proxy Jira Cloud
directly:

- **Create** (`POST /api/tickets`) calls `JiraService.create_issue()` and
  returns the Jira key/id without saving anything locally.
- **List** (`GET /api/tickets`) calls `JiraService.search_recent()`, which runs
  a JQL query (`reporter = currentUser() ORDER BY created DESC`, optionally
  scoped to a project). Results are shaped to a common ticket dict so the
  frontend renders create-responses and list-results interchangeably (see the
  `Ticket` interface in `frontend/src/types/index.ts`).

Because Jira is authoritative, tickets deleted in Jira disappear immediately,
and if Jira is unreachable the list endpoint returns an explicit
`unavailable: true` state instead of stale cached data.

## Multi-tenancy

Every query is scoped to the authenticated user (`user_id`), so no user can see
another's credentials, keys, or tickets. Jira reads are naturally isolated too,
since each user's queries run against their own Jira credentials.

## Migrations

Schema changes live in `migrations/versions/` (Alembic). Apply them with
`make init-db` (`flask db upgrade`). Current history:

1. `192c4ee5d9c2` — initial schema (users, jira_credentials, api_keys, and the
   original tickets table).
2. `a1b2c3d4e5f6` — drop the `tickets` table (switch to Jira as source of truth).

# Design: customer accounts and JWT authentication

## Problem

Every table and every endpoint implicitly assumed exactly one, unnamed
user. There was no record of *who* the data belongs to, no login, and
nothing stopping any process on localhost from hitting the API.

## Decision

Add a real `customers` table and scope every piece of data (transactions,
ingested files, Mongo-stored statements) to a `customer_id`. Protect the
API with JWT bearer tokens issued from a password login, rather than a
cosmetic "Hello {name}" with no gate behind it -- this is a genuine
multi-user-ready foundation, not a UI decoration, even though exactly one
customer exists today.

## First-run bootstrap, not a registration form

A registration UI is the wrong shape for an app with exactly one intended
user. Instead:

1. On backend startup, if no customer row exists, one is seeded (name
   and email from `CUSTOMER_NAME` / `CUSTOMER_EMAIL` env vars, defaulting
   to "Vasanthageethan Arputharaj" / the project owner's email) with
   `password_hash = NULL`.
2. `GET /auth/status` reports whether a password has been set yet.
3. While unset, the frontend shows a one-time "Set up your password"
   screen, which calls `POST /auth/set-password` -- **this endpoint only
   works when `password_hash IS NULL`**; it closes itself permanently
   after the first successful call. No way to use it to take over an
   already-configured account.
4. From then on, `POST /auth/login` (email + password) is the only way
   in, same as any normal app.

This means Claude (or anyone else working in this repo) never sees or
handles the real password -- it's typed directly into the browser.

## Auth mechanics (`backend/auth.py`)

- **Password hashing: bcrypt**, via the `bcrypt` package directly (not a
  heavier framework) -- industry-standard, built-in salt, no reason to
  hand-roll anything here.
- **Sessions: JWT**, via `PyJWT`, signed with `JWT_SECRET_KEY` (env var;
  if unset, a random key is generated at process start -- fine for local
  dev, but means tokens don't survive a restart, so set it in `.env` for
  persistent sessions). Tokens carry `customer_id` and expire after
  `JWT_EXPIRY_HOURS` (env var, default 168 = 7 days).
- A FastAPI dependency, `get_current_customer`, reads the `Authorization:
  Bearer <token>` header, validates it, and returns the customer row --
  every data endpoint takes this as a dependency instead of trusting an
  implicit single user.

## Schema

```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT UNIQUE NOT NULL,   -- public-facing id (uuid4), not the row id
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,                 -- NULL until first-run setup completes
    created_at TEXT NOT NULL
);
```

`transactions` and `ingested_files` each gain a nullable `customer_id
TEXT` column (SQLite can't add a `NOT NULL` column with no default to a
populated table in one step); existing rows are backfilled to the seeded
customer on first startup after this migration, same manual-backfill
approach as `docs/design-sqlite-persistence.md` already uses. GridFS
documents gain `metadata.customer_id`, backfilled the same way via a
bulk `update_many`.

`customer_id` is a separate field from the row's own primary key
deliberately -- it's the id that ever appears in a URL, a JWT, or a log
line, so it should never leak information about row counts or let a
client guess adjacent ids the way a sequential integer would.

## What's explicitly not built

No password reset flow, no email verification, no multi-factor, no
registration for a second customer. All of that is real scope for an app
that might one day have more than one user; this app doesn't yet, and the
bootstrap-then-login flow is intentionally the smallest thing that is
still a real login, not a toy. Revisit if a second customer ever becomes
a real requirement -- Phase 5's AWS re-platform is the natural point to
reconsider this against Cognito or a managed auth provider instead of
hand-rolled JWTs.

## Transport security note

Tokens travel over plain HTTP, same as everything else in this app --
it's local-only, never exposed past `localhost`, consistent with Mongo
having no auth either for the same reason. This stops being acceptable
the moment this app is ever reachable from anywhere but the machine
running it.

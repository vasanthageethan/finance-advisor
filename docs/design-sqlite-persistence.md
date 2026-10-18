# Design: local persistence with SQLite

## Problem

Transactions live in an in-memory Python list (`main._TRANSACTIONS`). Every
backend restart loses all data, and the real-statement auto-loader
(`_load_local_statements`) re-parses and re-appends every PDF on every
startup since nothing records what's already been ingested.

## Decision

Add a SQLite file (`backend/db.py`, data at `backend/data/finance.db`,
already gitignored) as the persistence layer for Phase 1/2. Not DynamoDB:
that's explicitly a Phase 5 (AWS re-platform) decision per
`CAREER_ROADMAP.md`, and jumping there now would mean standing up AWS
infra before the data model or query patterns have stabilized. SQLite is
zero-cost, zero-setup, and keeps the fast local dev loop Phase 1 was built
around -- a single file, no server process, no new paid dependency.

## Schema

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,              -- ISO 8601
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT,
    category_source TEXT,            -- "rule" | "hf" | "fallback" | "claude" | "manual"
    confidence REAL,
    account TEXT                     -- which statement/issuer this came from
);

CREATE TABLE ingested_statements (
    issuer TEXT NOT NULL,
    filename TEXT NOT NULL,
    PRIMARY KEY (issuer, filename)
);
```

`ingested_statements` is the idempotency guard: `_load_local_statements`
now checks it before parsing a PDF, so restarting the backend doesn't
re-ingest (and duplicate) every statement in the gitignored local folders.
There's no corresponding guard on the generic CSV upload or an issuer's PDF
re-uploaded through the API -- those are explicit user actions, not
startup side effects, so duplicate-on-purpose is the user's call, not a bug
to silently prevent. If that becomes a real annoyance, a content hash per
transaction is the next step, not added here speculatively.

## Concurrency

One SQLite connection, opened once at app startup (`check_same_thread=False`),
reused across requests. FastAPI's sync route handlers run in a thread pool,
but this app has no concurrent-write scenario worth building for yet --
single local user, infrequent uploads. Revisit if that stops being true.

## Failure mode

A corrupt or locked `finance.db` fails loudly at startup (SQLite raises,
uvicorn won't come up) rather than silently falling back to in-memory --
better to notice immediately than to quietly lose persistence.

## What this doesn't solve

No migrations tooling (schema changes are manual `ALTER TABLE` for now --
fine at this scale), no multi-user access, no backup strategy. None of
those matter until there's more than one user or the schema needs to
change under real data, at which point Phase 5's DynamoDB move is the
right time to revisit, not before.

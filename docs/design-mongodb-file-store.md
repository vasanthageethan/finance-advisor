# Design: MongoDB as the raw file store

## Problem

Real statement PDFs currently live in gitignored folders on local disk
(`chase-credit/`, `chase-checking/`, `capitalone-credit/`,
`sofi-checkings-savings/` at the repo root), and the backend's startup
lifespan walks those folders directly. That only works on one machine,
has no record of *when* a file was uploaded or by what path, and ties the
app to a filesystem layout that won't survive Phase 5's move off a single
local process.

## Decision

Add MongoDB (via GridFS) as a raw landing zone for uploaded files, sitting
in front of the SQLite relational store rather than replacing it:

- **MongoDB (GridFS)** holds the raw bytes of every uploaded statement --
  PDF or CSV -- plus upload metadata (issuer, original filename, content
  type, a SHA-256 of the bytes, upload timestamp). Nothing here is
  normalized or categorized; it's the unmodified source of truth for "what
  was actually uploaded."
- **SQLite** stays the parsed, categorized, queryable layer (`transactions`
  table), plus a new `ingested_files` table that records which Mongo
  file ids have already been parsed into transactions -- the idempotency
  guard, now keyed by Mongo's `_id` instead of a local issuer+filename
  pair.

This is a real raw-vs-curated split (the same shape as a landing zone
feeding a warehouse), not two databases for the same job. It's also not a
substitute for Phase 5's S3 plan in `CAREER_ROADMAP.md` -- GridFS is the
local-dev equivalent of "durable blob storage in front of structured
storage," and the Phase 5 re-platform is where that becomes S3 for the
same reason DynamoDB replaces SQLite there, not before.

## Why content-hash dedup, not filename

Files are deduplicated by `sha256(bytes)`, not by `(issuer, filename)`.
A bank renaming its export format, or the same statement re-downloaded
under a different filename, shouldn't produce a duplicate upload; a
filename collision hiding a genuinely different file (unlikely for bank
exports, but possible) shouldn't be silently skipped either. Hashing the
actual bytes is correct in both directions in a way filename-matching
isn't.

## Schema

GridFS (`fs.files` / `fs.chunks`, bucket name `statements`), one document
per uploaded file, with:

```json
{
  "_id": ObjectId,
  "filename": "chase-credit-jul.pdf",
  "uploadDate": ISODate,
  "metadata": {
    "issuer": "chase_credit",
    "content_type": "application/pdf",
    "sha256": "..."
  }
}
```

SQLite:

```sql
CREATE TABLE ingested_files (
    mongo_file_id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    filename TEXT NOT NULL
);
```

(Replaces the earlier `ingested_statements(issuer, filename)` table from
`docs/design-sqlite-persistence.md`.)

## Flow

- **Upload** (`/upload`, `/upload/statement`): store the raw bytes in
  GridFS first (dedup by hash -- if the hash already exists, reuse that
  file id instead of storing a second copy), then parse + categorize +
  insert into SQLite, recording the Mongo file id in `ingested_files`.
- **Startup**: list every file in GridFS; for any whose id isn't yet in
  `ingested_files`, parse it from the stored bytes and ingest. This
  replaces walking local disk folders -- Mongo is now the single source
  of "what files exist," SQLite is "what's been loaded from them."
- **One-time migration**: the real statements already sitting in the
  local gitignored folders are backfilled into Mongo by
  `backend/scripts/migrate_local_files_to_mongo.py`, run once. After
  that, the local folders are no longer read by the running app (they're
  just where the migration script looked).

## Hosting

Local MongoDB via a container, `mongo:7`, no auth (local dev only, never
exposed). Docker wasn't installed on this machine; Podman (already
present) runs the same image as a drop-in substitute --
`docker-compose.yml` is still checked in for portability/documentation,
since it's what most tooling expects, but the actual local run command is
`podman run` (or `podman machine start` first if the VM isn't up).
`MONGODB_URI` is an environment variable (default
`mongodb://localhost:27017`), never hardcoded, so pointing at Atlas later
is a config change, not a code change.

## Testing

Tests run against a real local MongoDB (same container), using a
dedicated test database name (`finance_advisor_test`) that's dropped
between tests -- not a mock. GridFS's behavior (chunking, metadata
queries) is part of what's being tested, and a mocking library that
doesn't faithfully reproduce it would validate against a fiction. This
does mean `pytest` now requires the Mongo container running locally,
same as it already implicitly requires nothing else external -- documented
in the test README note.

## What this doesn't solve

No auth on the local Mongo container (fine for local-only, would need to
change before ever being reachable off localhost), no backup strategy,
and the one-time migration script is exactly that -- one-time, not a
general sync tool. None of those matter at this scale; revisit if any of
it stops being true.

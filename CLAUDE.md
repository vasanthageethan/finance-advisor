# CLAUDE.md — Project Guide for Claude Code Sessions

This file is auto-loaded by Claude Code when you work in this repo. Read it
first, before touching code, so you understand why this project exists and
what "done" looks like at each stage.

## Who this is for and why

Vasanth is an SE1 at Dish Network / Boost Mobile on the order orchestration
team, working daily with AWS CloudWatch, S3, Lambda, Step Functions, EKS,
DynamoDB, MongoDB, and Dynatrace. He's also building MCP servers at work to
connect logs, Dynatrace, and GitLab for anomaly detection and incident
handling. The goal is a promotion path toward cloud systems designer/architect
roles with strong applied-AI skills, plus a portfolio that's competitive in
today's job market.

This repo — a personal finance advisor — is the vehicle for that. It is not
just a personal-finance app; it's a deliberately designed system meant to
demonstrate architecture judgment (why this data store, why this tiering of
AI calls, why this failure mode is handled this way) and applied AI patterns
(hybrid local-model + LLM pipelines, cost-aware routing) that map directly to
the cloud/AI architect track. Treat every design decision as something that
should be defensible in an interview.

Full multi-phase plan and career strategy (certs, learning resources, LinkedIn
cadence): see `CAREER_ROADMAP.md` in this same folder. This file (CLAUDE.md)
is the technical/project context; that file is the career context. Keep both
current as the project evolves.

## Current status

Phase 1 is built and verified against real statement data, not just the
sample CSV:

- Backend (`backend/`): FastAPI app. `/upload` parses a generic CSV export
  and categorizes each transaction; `/upload/statement` parses real bank/card
  PDF statements via `backend/statement_parsers/` (Chase checking, Chase
  credit, Capital One credit, SoFi checking & savings) and refuses to ingest
  a statement if the parsed transaction total doesn't reconcile against the
  statement's own declared total — a fail-closed data-integrity check, not
  yet written up as its own design doc. `/summary` aggregates spend by month
  and category; `/insights` generates a written trend narrative and flags
  anomalies, routed through a pluggable backend (`backend/insights.py`) —
  a local model (Ollama, `qwen2.5:3b-instruct`, free, default) when
  `ANTHROPIC_API_KEY` is unset, Claude (`claude-sonnet-5`) when it is. See
  `docs/design-local-insights-model.md`.
- Every uploaded file (CSV or PDF) is stored raw in MongoDB/GridFS first
  (`backend/filestore.py`, deduplicated by content hash), then parsed into
  SQLite (`backend/db.py`) -- a raw-landing-zone-vs-curated-store split, see
  `docs/design-mongodb-file-store.md` and `docs/design-sqlite-persistence.md`.
  On backend startup, any Mongo file not yet reflected in SQLite is parsed
  and loaded automatically, so the dashboard has data without re-uploading
  through the browser each session. The real statement PDFs that used to
  live directly in gitignored per-issuer folders at the repo root
  (`chase-credit/`, etc.) were migrated into Mongo via
  `backend/scripts/migrate_local_files_to_mongo.py` -- those folders are no
  longer read by the running app.
- The whole API requires auth now. A `customers` table (`backend/db.py`)
  plus JWT bearer tokens (`backend/auth.py`) scope every transaction,
  ingested-file record, and Mongo-stored file to a `customer_id` — see
  `docs/design-auth-and-customers.md`. First run shows a one-time "set
  your password" screen (`GET /auth/status`, `POST /auth/set-password`,
  closes itself permanently once a password exists) for the first/owner
  account; `POST /auth/register` (name/email/password) is open after
  that for any additional customer, each one starting with zero data,
  fully isolated by `customer_id` from every other account. `/health`
  stays unauthenticated (pure liveness, no customer data); everything
  else requires a bearer token.
- Frontend (`frontend/`): React + Vite, gated by `AuthGate.jsx`
  (landing / setup / login / register / authenticated) with a
  "Create account" option alongside "Sign in", showing "Hello {first
  name}" + a logout button once signed in. Upload form has an account
  selector (`ACCOUNTS` in
  `frontend/src/api.js`, kept in sync with the backend's `PARSERS`
  registry) that routes to either the CSV or PDF upload endpoint; a trend
  line (`SpendTrendChart`) and a ranked category-breakdown bar chart
  (`CategoryBreakdownChart`, with a month picker) replaced the original
  single stacked bar; a "Statement coverage" card flags accounts missing
  a recent month's statement; a button to fetch AI insights. The category
  breakdown also shows a historical FX-converted amount (e.g. Student
  Loan Payment in INR) wherever `backend/categorizer.py`'s
  `CATEGORY_CURRENCY` maps that category to a currency.
- Categorization is three-tier by design — see "Architecture decisions"
  below. Each transaction is tagged with `category_source` (`rule` / `hf` /
  `fallback`) and a confidence score, so the "most spend resolves through
  the free tier" claim is measurable per real statement, not just asserted
  against the 25-row sample set.
- Automated tests exist now: 115 passing (`backend/tests/`), covering the
  API (including the full auth/registration flow and per-customer data
  isolation), the categorizer, the Chase/Capital One/SoFi parsers,
  `filestore.py`, and `fx.py`.
- Still not done: no CI, no evaluation harness yet for `/insights` output
  quality, no password-reset flow (not needed yet for a single-customer
  app — see the design doc's "what's explicitly not built" section).

## Architecture decisions (and the reasoning to reuse/defend)

**Real customer accounts and JWT auth, not a cosmetic "Hello {name}."**
Every table and endpoint used to assume exactly one implicit user. A
`customers` table plus `customer_id` scoping on transactions, ingested
files, and Mongo-stored statements is a genuine multi-user-ready
foundation, even though exactly one customer exists today — the
difference between a decoration and an architecture decision. First run
is a one-time password-bootstrap screen for the first/owner account,
closing itself permanently the moment a password is set; real
registration (`POST /auth/register`) is open after that for any
additional customer — a deliberate reversal of the original "no
registration" call once a second customer became a real requirement. See
`docs/design-auth-and-customers.md`.

**Deliberately no bank-aggregator API (Plaid/SimpleFIN/etc.).** Evaluated
and explicitly rejected: every option in that category is a third party
that holds a copy of your transaction data, and for US retail banks
there's no way around that -- unlike EU/UK Open Banking (PSD2), US banks
don't expose direct consumer APIs. Manual statement download -> upload is
the only path where nobody but the bank and this app ever sees the data,
so it stays the ingestion method even though it's less automated. Worth
defending explicitly: "I evaluated the industry-standard integration and
chose not to use it, for a specific, statable reason" is a stronger
architecture story than defaulting to whatever's common.

**Historical FX conversion (`backend/fx.py`), general-purpose, not an
INR special case.** Student Loan Payment (confirmed recurring Remitly
transfers to India) is the one real use case today, but the conversion
utility takes any (date, amount, currency) -- extending to a second
country is a one-line config change in `categorizer.py`'s
`CATEGORY_CURRENCY`, not new plumbing. Each transaction is converted at
its own date's rate and summed, rather than applying one rate to a
month's aggregate, which would be wrong whenever the rate moved
mid-month. Frankfurter (ECB rates) was chosen specifically because it's
free with no API key and no rate limit -- verified live before building
against it, see `docs/design-fx-conversion.md`.

**Three-tier categorization instead of "just call an LLM on everything."**
Tier 1 is keyword/merchant rules (`backend/categorizer.py::RULES`) — free,
instant, and covers the bulk of real spend because merchant strings repeat
heavily ("AMAZON.COM", "SHELL OIL #123"). Tier 2 is a local Hugging Face
zero-shot classifier, used only when rules miss — still free, runs on-device.
Tier 3, the Claude API, is reserved for `/insights` — turning aggregate
numbers into a narrative and catching anomalies a fixed threshold would miss.
The point: route the repetitive, low-reasoning work to cheap tiers and spend
the frontier model's budget only where language reasoning is the actual
bottleneck. This is a pattern worth explicitly naming in interviews and
LinkedIn posts — it's the same tiering logic that matters in the MCP/log
anomaly-detection work at Dish.

**Polyglot persistence: MongoDB for raw files, SQLite for the relational
store.** Every uploaded file lands in MongoDB/GridFS unmodified first
(deduplicated by SHA-256, not filename), and only the parsed, categorized
result goes into SQLite's `transactions` table. This is a real raw-vs-curated
split, not two databases doing the same job — worth naming explicitly as
the same shape as a landing zone feeding a warehouse. Neither is the Phase 5
decision: DynamoDB and S3 are the AWS-platform equivalents of this same
split, revisited with that migration's own tradeoffs (query patterns, access
frequency, schema) rather than assumed to carry over unchanged. See
`docs/design-mongodb-file-store.md` and `docs/design-sqlite-persistence.md`.

**PDF ingestion is live, not deferred.** Four issuer-specific parsers
(`backend/statement_parsers/`) handle real Chase/Capital One/SoFi PDF
statements, each required to reconcile its parsed total against the
statement's own declared total before anything is ingested — a fail-closed
data-integrity check worth its own design doc if it hasn't gotten one yet.

## Roadmap (detail in CAREER_ROADMAP.md)

1. Spend ingestion and categorization — **current phase**.
2. Trend analysis and reporting (monthly rollups, anomaly flags) — direct
   parallel to the Dynatrace/log anomaly detection work at Dish; worth
   drawing that connection explicitly when this phase ships.
3. Goal setting and forecasting.
4. Investment/stock tracking (read-only and advisory only — never automate
   trades or money movement).
5. Re-platform onto AWS (Lambda, Step Functions, DynamoDB, S3, CloudWatch) —
   the phase that turns this from "a script that works" into "a system that
   was designed," which is the actual point of the whole project.

Before starting a new phase, write a short design doc (even half a page):
what the components are, what the failure modes are, why this data store
over that one. That habit matters more than any individual technology choice
for the architect track this project is meant to support.

## Conventions

- Keep real statement data out of git. `backend/data/` is gitignored for
  this reason — never remove that from `.gitignore`, and never commit a real
  CSV export.
- `ANTHROPIC_API_KEY` must be set as an environment variable, never hardcoded.
- `JWT_SECRET_KEY` (env var, never hardcoded) should be set in `backend/.env`
  for persistent login sessions. If unset, a random key is generated at
  each process start, which invalidates every issued token on restart —
  expected and documented (`docs/design-auth-and-customers.md`), not a bug,
  but worth setting once `.env` exists anyway. Never ask the user for their
  actual password or paste it into a session — it's typed directly into
  the browser's login/setup form and never touches this codebase.
- The backend needs MongoDB reachable before it will start (startup fails
  loudly rather than silently skipping file loading, same philosophy as a
  corrupt SQLite file). Docker isn't installed on this machine; run it via
  Podman instead: `podman machine start` once, then
  `podman run -d --name finance-mongo -p 27017:27017 -v finance-mongo-data:/data/db mongo:7`.
  `docker-compose.yml` at the repo root is kept for portability if real
  Docker is ever installed. `MONGODB_URI` (default
  `mongodb://localhost:27017`) is an environment variable, never hardcoded,
  same convention as `ANTHROPIC_API_KEY`.
- This machine is an 8GB M2 and runs close to its memory limit with
  everything else open — the Podman VM was deliberately shrunk from its
  3.8GB default to 1.5GB (`podman machine set --memory 1536`) to make room
  for the local insights model. Keep that in mind before adding another
  memory-heavy local service.
- `/insights` needs either `ollama serve` running locally with
  `qwen2.5:3b-instruct` pulled (`ollama pull qwen2.5:3b-instruct`), or
  `ANTHROPIC_API_KEY` set — see `docs/design-local-insights-model.md`.
  `OLLAMA_MODEL`/`OLLAMA_URL` are environment variables with sane
  defaults, never hardcoded.
- Extend `RULES` in `categorizer.py` as real merchant strings are observed —
  this is expected to grow over time and is the highest-leverage, lowest-cost
  place to improve categorization accuracy.
- New categories should be added to both `CATEGORIES` and `RULES` in
  `categorizer.py` together, and reflected in the zero-shot candidate labels
  automatically (they share the same list).

## Prompt-coaching hook (why you may see extra notes in responses)

This repo has a `UserPromptSubmit` hook (`.claude/hooks/prompt_coach.py`,
registered in `.claude/settings.json`) that evaluates the quality of each
prompt Vasanth submits and asks Claude to append a short coaching note. This
is intentional and requested — the goal is to help him build better prompting
habits over time, not a bug to "fix" by removing the hook. A running log of
scored prompts is kept locally (see `.claude/prompt-coaching-log.md`,
gitignored) so he can track improvement across sessions. Leave the hook in
place unless he explicitly asks to remove or change it.

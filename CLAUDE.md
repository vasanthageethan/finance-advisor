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

Phase 1 scaffold is built and locally verified:

- Backend (`backend/`): FastAPI app. `/upload` parses a CSV statement and
  categorizes each transaction; `/summary` aggregates spend by month and
  category; `/insights` calls Claude to generate a written trend narrative
  and flag anomalies.
- Frontend (`frontend/`): React + Vite. Upload form, stacked bar chart of
  spend by category/month (recharts), a button to fetch AI insights.
- Categorization is three-tier by design — see "Architecture decisions"
  below. Verified against `backend/sample_data/sample_transactions.csv`: all
  25 sample transactions resolved through the free rule tier.
- Not yet done: testing against real statement data, `ANTHROPIC_API_KEY`
  has not been exercised live, no automated tests exist yet, error handling
  is minimal (happy-path only), no persistence layer (in-memory store only,
  resets on backend restart).

## Architecture decisions (and the reasoning to reuse/defend)

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

**In-memory store for now, DynamoDB later.** Phase 1 intentionally skips a
real database to keep the loop fast. Phase 5 (AWS re-platform) is where this
becomes a real architectural decision — document the tradeoffs when that
migration happens (query patterns, access frequency, schema) rather than
just swapping the storage class.

**CSV-first ingestion.** Statement PDFs were explicitly deferred — CSV export
from the bank/card portal is the input for now. If PDF ingestion is added
later, treat it as a distinct phase with its own design doc (OCR accuracy,
statement format variance across issuers are real problems, not a quick
addition).

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

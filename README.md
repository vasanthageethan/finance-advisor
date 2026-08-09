# Personal Finance Advisor — Phase 1

Spend ingestion, hybrid categorization, and AI-generated insights from your
own bank/card CSV exports. See `CAREER_ROADMAP.md` for the full multi-phase
plan and the career strategy this project is meant to support.

## Architecture

FastAPI backend, React (Vite) frontend, three-tier categorization:

1. Keyword rules (`backend/categorizer.py::RULES`) — instant, free, covers most repeat merchants.
2. Local Hugging Face zero-shot model — catches whatever the rules miss, still free, runs on your machine.
3. Claude API (`backend/insights.py`) — used only to turn the aggregated numbers into a written narrative and flag anomalies, not for per-transaction categorization.

This tiering keeps API costs near zero for the repetitive part of the job
(categorization) and spends the frontier model's budget only where language
reasoning is actually the bottleneck (summarization, anomaly narrative).

## Setup

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here   # only needed for /insights
uvicorn main:app --reload --port 8000
```

First call to `/upload` will download the Hugging Face model (a few hundred MB) — expect it to be slow once, fast after.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed localhost URL, then upload `backend/sample_data/sample_transactions.csv` to try it end to end before using real statements.

## Getting your real data in

Export transactions as CSV from your bank/card's online portal (usually under Statements or Account Activity → Export). The uploader expects at minimum `date`, `description`, `amount` columns — rename headers in the CSV if your bank uses different names. Keep real statement files out of git; `.gitignore` already excludes anything under `backend/data/`.

## What's next (see CAREER_ROADMAP.md for detail)

Phase 2 adds trend/anomaly reporting, Phase 3 adds goal setting and forecasting, Phase 4 adds investment tracking, and Phase 5 re-platforms this onto AWS (Lambda, Step Functions, DynamoDB, S3, CloudWatch) as the architecture showcase piece.

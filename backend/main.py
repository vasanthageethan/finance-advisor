import io
import json
import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date

from dotenv import load_dotenv

# Must run before any of this project's own modules are imported --
# filestore.py reads MONGODB_URI at import time, and insights.py reads
# ANTHROPIC_API_KEY at request time, but both should see whatever a local
# backend/.env provides either way.
load_dotenv()

import anthropic
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import db
import filestore
from categorizer import NON_SPEND_CATEGORIES, categorize
from insights import generate_insights
from models import AccountCoverage, CategorySummary, CoverageResponse, InsightsResponse, MonthlySummary, Transaction
from statement_parsers import PARSERS, parse_statement
from statement_parsers.base import RawTransaction

# Expected CSV columns. Adjust to match your bank/card export headers --
# most exports use some variant of these three.
EXPECTED_COLUMNS = {"date", "description", "amount"}


def _ingest_raw_transactions(raw_transactions, account: str | None) -> list[Transaction]:
    new_transactions = []
    for raw in raw_transactions:
        cat = categorize(raw.description)
        txn = Transaction(date=raw.date, description=raw.description, amount=raw.amount, account=account, **cat)
        new_transactions.append(txn)
    db.insert_transactions(
        [
            {
                "date": t.date.isoformat(),
                "description": t.description,
                "amount": t.amount,
                "category": t.category,
                "category_source": t.category_source,
                "confidence": t.confidence,
                "account": t.account,
            }
            for t in new_transactions
        ]
    )
    return new_transactions


def _parse_csv_bytes(raw: bytes) -> list[RawTransaction]:
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip().lower() for c in df.columns]

    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required column(s): {sorted(missing)}. Expected at least: {sorted(EXPECTED_COLUMNS)}")

    return [
        RawTransaction(date=row["date"], description=str(row["description"]), amount=float(row["amount"]))
        for _, row in df.iterrows()
    ]


def _ingest_mongo_file(file_id: str, issuer: str, filename: str, content_type: str) -> list[Transaction]:
    """Parse one already-stored-in-Mongo file and load it into SQLite,
    recording the file id so it's never re-parsed. Raises on a CSV schema
    problem or a PDF that fails reconciliation -- callers decide whether
    that's fatal (an explicit upload) or just skipped (startup catch-up)."""
    raw = filestore.get_file_bytes(file_id)

    if content_type == "text/csv":
        raw_transactions = _parse_csv_bytes(raw)
    else:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(raw)
            tmp.flush()
            parsed = parse_statement(issuer, tmp.name)
        if not parsed.reconciliation.reconciled:
            raise ValueError(
                "Parsed transactions don't reconcile against the statement's own declared total "
                f"(parsed {parsed.reconciliation.parsed_total}, declared {parsed.reconciliation.declared_total})."
            )
        raw_transactions = parsed.transactions

    transactions = _ingest_raw_transactions(raw_transactions, issuer)
    db.mark_file_ingested(file_id, issuer, filename)
    return transactions


def _load_from_filestore() -> None:
    """Startup catch-up: parse any Mongo-stored file that hasn't made it
    into SQLite yet. Mongo is the source of truth for 'what was uploaded';
    this is what keeps SQLite caught up with it across restarts."""
    for f in filestore.list_files():
        if db.is_file_ingested(f["file_id"]):
            continue
        try:
            _ingest_mongo_file(f["file_id"], f["issuer"], f["filename"], f["content_type"])
        except Exception as exc:
            print(f"[startup] skipping {f['filename']}: {exc}")
            continue
        print(f"[startup] loaded transactions from {f['filename']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    filestore.connect()
    _load_from_filestore()
    yield


app = FastAPI(title="Personal Finance Advisor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server default
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload", response_model=list[Transaction])
async def upload_statement(file: UploadFile = File(...), account: str | None = Form(None)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported on this endpoint")

    raw = await file.read()
    issuer = account or "other"

    try:
        raw_transactions = _parse_csv_bytes(raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    # Store the raw upload in Mongo regardless -- it's the landing zone,
    # not conditional on parsing having gone well.
    file_id, _ = filestore.store_file(raw, file.filename, issuer, "text/csv")
    transactions = _ingest_raw_transactions(raw_transactions, account)
    db.mark_file_ingested(file_id, issuer, file.filename)
    return transactions


@app.post("/upload/statement", response_model=list[Transaction])
async def upload_pdf_statement(file: UploadFile = File(...), issuer: str = Form(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported on this endpoint")
    if issuer not in PARSERS:
        raise HTTPException(400, f"Unknown issuer '{issuer}'. Known: {sorted(PARSERS)}")

    raw = await file.read()
    file_id, _ = filestore.store_file(raw, file.filename, issuer, "application/pdf")

    try:
        return _ingest_mongo_file(file_id, issuer, file.filename, "application/pdf")
    except ValueError as exc:
        raise HTTPException(
            422, f"{exc} Refusing to ingest a statement that may have been parsed incorrectly."
        ) from exc


@app.get("/summary", response_model=list[MonthlySummary])
def summary():
    transactions = db.fetch_all_transactions()
    if not transactions:
        raise HTTPException(404, "No transactions uploaded yet")

    by_month: dict[str, list] = defaultdict(list)
    for t in transactions:
        month_key = t["date"][:7]  # "YYYY-MM-DD" -> "YYYY-MM"
        by_month[month_key].append(t)

    summaries = []
    for month in sorted(by_month.keys()):
        # Exclude refunds/income (negative amounts) and inter-account
        # transfers like paying off your own credit card from checking --
        # those aren't spend, and double-count purchases already counted
        # on the other account's statement.
        txns = [
            t for t in by_month[month] if t["amount"] > 0 and (t["category"] or "Other") not in NON_SPEND_CATEGORIES
        ]
        total = sum(t["amount"] for t in txns)

        by_cat: dict[str, list] = defaultdict(list)
        for t in txns:
            by_cat[t["category"] or "Other"].append(t)

        cat_summaries = [
            CategorySummary(
                category=cat,
                total=round(sum(t["amount"] for t in items), 2),
                transaction_count=len(items),
                pct_of_spend=round(sum(t["amount"] for t in items) / total * 100, 1) if total else 0.0,
            )
            for cat, items in sorted(by_cat.items(), key=lambda kv: -sum(t["amount"] for t in kv[1]))
        ]

        summaries.append(MonthlySummary(month=month, total_spend=round(total, 2), by_category=cat_summaries))

    return summaries


@app.get("/coverage", response_model=CoverageResponse)
def coverage():
    """
    Which of the known accounts (PARSERS) have a statement on file for each
    month, so a gap (forgot to download/upload last month's SoFi statement,
    say) is visible on the dashboard instead of silently skewing /summary.
    A transaction's presence in a given month is used as the proxy for
    "a statement for that month was ingested" -- consistent with how
    /summary already buckets by month, and avoids needing to separately
    persist each statement's declared period.
    """
    transactions = db.fetch_all_transactions()
    current_month = date.today().strftime("%Y-%m")

    by_account_month: dict[str, set[str]] = defaultdict(set)
    all_months: set[str] = set()
    for t in transactions:
        if t["account"] not in PARSERS:
            continue  # generic/"other" CSV uploads aren't tied to a monthly statement cadence
        month = t["date"][:7]
        if month == current_month:
            continue  # this month's statement isn't expected yet
        all_months.add(month)
        by_account_month[t["account"]].add(month)

    months = sorted(all_months)
    accounts = [
        AccountCoverage(
            account=account,
            covered_months=sorted(by_account_month[account]),
            missing_months=sorted(set(months) - by_account_month[account]),
        )
        for account in sorted(PARSERS)
    ]
    return CoverageResponse(months=months, accounts=accounts)


@app.get("/insights", response_model=InsightsResponse)
def insights():
    monthly = summary()  # reuse the aggregation above
    payload = [m.model_dump() for m in monthly]
    try:
        result = generate_insights(payload)
    except RuntimeError as exc:
        # ANTHROPIC_API_KEY not configured -- a setup problem, not a Claude failure.
        raise HTTPException(503, f"AI insights are unavailable: {exc}") from exc
    except anthropic.AnthropicError as exc:
        raise HTTPException(503, f"AI insights are temporarily unavailable (Claude API error: {exc}).") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            502, "AI insights are unavailable: the model returned a response in an unexpected format."
        ) from exc
    return InsightsResponse(**result)


@app.get("/health")
def health():
    return {"status": "ok", "transactions_loaded": db.count_transactions()}

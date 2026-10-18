import io
import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from categorizer import NON_SPEND_CATEGORIES, categorize
from insights import generate_insights
from models import CategorySummary, InsightsResponse, MonthlySummary, Transaction
from statement_parsers import PARSERS, parse_statement
from statement_parsers.base import RawTransaction

# In-memory store for the local prototype. Phase 5 (AWS re-platform) swaps
# this for DynamoDB.
_TRANSACTIONS: list[Transaction] = []

# Expected CSV columns. Adjust to match your bank/card export headers --
# most exports use some variant of these three.
EXPECTED_COLUMNS = {"date", "description", "amount"}

# Real statement PDFs live outside the repo tree in gitignored folders at
# the project root (never committed -- they're actual financial
# documents). If they're present locally, load them automatically on
# startup so the dashboard has data without re-uploading through the
# browser every session.
_REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_STATEMENT_DIRS = {
    "chase_credit": _REPO_ROOT / "chase-credit",
    "chase_checking": _REPO_ROOT / "chase-checking",
    "capitalone_credit": _REPO_ROOT / "capitalone-credit",
    "sofi_checking_savings": _REPO_ROOT / "sofi-checkings-savings",
}


def _ingest_raw_transactions(raw_transactions, account: str | None) -> list[Transaction]:
    new_transactions = []
    for raw in raw_transactions:
        cat = categorize(raw.description)
        txn = Transaction(date=raw.date, description=raw.description, amount=raw.amount, account=account, **cat)
        new_transactions.append(txn)
    _TRANSACTIONS.extend(new_transactions)
    return new_transactions


def _load_local_statements() -> None:
    for issuer, directory in LOCAL_STATEMENT_DIRS.items():
        if not directory.is_dir():
            continue
        for pdf_path in sorted(directory.glob("*.pdf")):
            try:
                parsed = parse_statement(issuer, str(pdf_path))
            except Exception as exc:
                print(f"[startup] skipping {pdf_path.name}: {exc}")
                continue
            if not parsed.reconciliation.reconciled:
                print(
                    f"[startup] skipping {pdf_path.name}: parsed total "
                    f"{parsed.reconciliation.parsed_total} != declared total "
                    f"{parsed.reconciliation.declared_total}"
                )
                continue
            _ingest_raw_transactions(parsed.transactions, issuer)
            print(f"[startup] loaded {len(parsed.transactions)} transactions from {pdf_path.name}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_local_statements()
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
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip().lower() for c in df.columns]

    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            400,
            f"CSV is missing required column(s): {sorted(missing)}. "
            f"Expected at least: {sorted(EXPECTED_COLUMNS)}",
        )

    raw_transactions = [
        RawTransaction(date=row["date"], description=str(row["description"]), amount=float(row["amount"]))
        for _, row in df.iterrows()
    ]
    return _ingest_raw_transactions(raw_transactions, account)


@app.post("/upload/statement", response_model=list[Transaction])
async def upload_pdf_statement(file: UploadFile = File(...), issuer: str = Form(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported on this endpoint")
    if issuer not in PARSERS:
        raise HTTPException(400, f"Unknown issuer '{issuer}'. Known: {sorted(PARSERS)}")

    raw = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(raw)
        tmp.flush()
        parsed = parse_statement(issuer, tmp.name)

    if not parsed.reconciliation.reconciled:
        raise HTTPException(
            422,
            "Parsed transactions don't reconcile against the statement's own declared total "
            f"(parsed {parsed.reconciliation.parsed_total}, declared {parsed.reconciliation.declared_total}). "
            "Refusing to ingest a statement that may have been parsed incorrectly.",
        )

    return _ingest_raw_transactions(parsed.transactions, issuer)


@app.get("/summary", response_model=list[MonthlySummary])
def summary():
    if not _TRANSACTIONS:
        raise HTTPException(404, "No transactions uploaded yet")

    by_month: dict[str, list[Transaction]] = defaultdict(list)
    for t in _TRANSACTIONS:
        month_key = t.date.strftime("%Y-%m")
        by_month[month_key].append(t)

    summaries = []
    for month in sorted(by_month.keys()):
        # Exclude refunds/income (negative amounts) and inter-account
        # transfers like paying off your own credit card from checking --
        # those aren't spend, and double-count purchases already counted
        # on the other account's statement.
        txns = [t for t in by_month[month] if t.amount > 0 and (t.category or "Other") not in NON_SPEND_CATEGORIES]
        total = sum(t.amount for t in txns)

        by_cat: dict[str, list[Transaction]] = defaultdict(list)
        for t in txns:
            by_cat[t.category or "Other"].append(t)

        cat_summaries = [
            CategorySummary(
                category=cat,
                total=round(sum(t.amount for t in items), 2),
                transaction_count=len(items),
                pct_of_spend=round(sum(t.amount for t in items) / total * 100, 1) if total else 0.0,
            )
            for cat, items in sorted(by_cat.items(), key=lambda kv: -sum(t.amount for t in kv[1]))
        ]

        summaries.append(MonthlySummary(month=month, total_spend=round(total, 2), by_category=cat_summaries))

    return summaries


@app.get("/insights", response_model=InsightsResponse)
def insights():
    monthly = summary()  # reuse the aggregation above
    payload = [m.model_dump() for m in monthly]
    result = generate_insights(payload)
    return InsightsResponse(**result)


@app.get("/health")
def health():
    return {"status": "ok", "transactions_loaded": len(_TRANSACTIONS)}

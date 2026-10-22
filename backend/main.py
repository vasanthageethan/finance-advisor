import io
import json
import os
import sqlite3
import tempfile
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from dotenv import load_dotenv

# Must run before any of this project's own modules are imported --
# filestore.py reads MONGODB_URI at import time, and insights.py reads
# ANTHROPIC_API_KEY at request time, but both should see whatever a local
# backend/.env provides either way.
load_dotenv()

import anthropic
import httpx
import ollama
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import auth
import db
import filestore
import fx
from categorizer import CATEGORY_CURRENCY, NON_SPEND_CATEGORIES, categorize
from insights import generate_insights
from models import (
    AccountCoverage,
    AuthStatusResponse,
    CategorySummary,
    CoverageResponse,
    CustomerProfile,
    FxRateResponse,
    InsightsResponse,
    LoginRequest,
    LoginResponse,
    MonthlySummary,
    RegisterRequest,
    SetPasswordRequest,
    Transaction,
)
from statement_parsers import PARSERS, parse_statement
from statement_parsers.base import RawTransaction

# Expected CSV columns. Adjust to match your bank/card export headers --
# most exports use some variant of these three.
EXPECTED_COLUMNS = {"date", "description", "amount"}


def _ingest_raw_transactions(customer_id: str, raw_transactions, account: str | None) -> list[Transaction]:
    new_transactions = []
    for raw in raw_transactions:
        cat = categorize(raw.description)
        txn = Transaction(date=raw.date, description=raw.description, amount=raw.amount, account=account, **cat)
        new_transactions.append(txn)
    db.insert_transactions(
        customer_id,
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
        ],
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


def _ingest_mongo_file(customer_id: str, file_id: str, issuer: str, filename: str, content_type: str) -> list[Transaction]:
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

    transactions = _ingest_raw_transactions(customer_id, raw_transactions, issuer)
    db.mark_file_ingested(customer_id, file_id, issuer, filename)
    return transactions


def _load_from_filestore(customer_id: str) -> None:
    """Startup catch-up: parse any Mongo-stored file that hasn't made it
    into SQLite yet. Mongo is the source of truth for 'what was uploaded';
    this is what keeps SQLite caught up with it across restarts."""
    for f in filestore.list_files(customer_id):
        if db.is_file_ingested(f["file_id"]):
            continue
        try:
            _ingest_mongo_file(customer_id, f["file_id"], f["issuer"], f["filename"], f["content_type"])
        except Exception as exc:
            print(f"[startup] skipping {f['filename']}: {exc}")
            continue
        print(f"[startup] loaded transactions from {f['filename']}")


def _seed_customer() -> sqlite3.Row:
    """This app has exactly one customer. Seed it on first run (password
    unset until /auth/set-password's one-time bootstrap), then backfill
    any pre-auth data to it -- see docs/design-auth-and-customers.md."""
    customer = db.get_any_customer()
    if customer is None:
        customer_id = str(uuid.uuid4())
        name = os.environ.get("CUSTOMER_NAME", "Vasanthageethan Arputharaj")
        email = os.environ.get("CUSTOMER_EMAIL", "vasanthageethan1102@gmail.com")
        db.create_customer(customer_id, name, email, datetime.now(timezone.utc).isoformat())
        customer = db.get_customer_by_customer_id(customer_id)
    db.migrate_customer_id_column(customer["customer_id"])
    filestore.backfill_customer_id(customer["customer_id"])
    return customer


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    filestore.connect()
    customer = _seed_customer()
    _load_from_filestore(customer["customer_id"])
    yield


app = FastAPI(title="Personal Finance Advisor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server default
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/auth/status", response_model=AuthStatusResponse)
def auth_status():
    customer = db.get_any_customer()
    return AuthStatusResponse(password_set=bool(customer and customer["password_hash"]))


@app.post("/auth/set-password", response_model=LoginResponse)
def set_password(body: SetPasswordRequest):
    """One-time bootstrap -- only works while no password has been set
    yet. Closes itself permanently after the first successful call, see
    docs/design-auth-and-customers.md."""
    customer = db.get_any_customer()
    if customer is None:
        raise HTTPException(503, "No customer account exists yet -- restart the backend first.")
    if customer["password_hash"]:
        raise HTTPException(403, "A password is already set. Use /auth/login instead.")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")

    db.set_customer_password(customer["customer_id"], auth.hash_password(body.password))
    token = auth.create_access_token(customer["customer_id"])
    return LoginResponse(access_token=token, customer_id=customer["customer_id"], name=customer["name"])


@app.post("/auth/register", response_model=LoginResponse)
def register(body: RegisterRequest):
    """Create an additional customer account. Separate from
    /auth/set-password's one-time bootstrap, which is specifically for the
    first/owner account -- see docs/design-auth-and-customers.md. A new
    registrant starts with zero transactions/files, correctly isolated
    from every other customer's data."""
    if not body.name.strip():
        raise HTTPException(400, "Name is required.")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if db.get_customer_by_email(body.email):
        raise HTTPException(409, "An account with this email already exists.")

    customer_id = str(uuid.uuid4())
    db.create_customer(customer_id, body.name.strip(), body.email, datetime.now(timezone.utc).isoformat())
    db.set_customer_password(customer_id, auth.hash_password(body.password))

    token = auth.create_access_token(customer_id)
    return LoginResponse(access_token=token, customer_id=customer_id, name=body.name.strip())


@app.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    customer = db.get_customer_by_email(body.email)
    if not customer or not customer["password_hash"] or not auth.verify_password(body.password, customer["password_hash"]):
        raise HTTPException(401, "Incorrect email or password.")

    token = auth.create_access_token(customer["customer_id"])
    return LoginResponse(access_token=token, customer_id=customer["customer_id"], name=customer["name"])


@app.get("/auth/me", response_model=CustomerProfile)
def me(customer_id: str = Depends(auth.require_bearer_token)):
    customer = db.get_customer_by_customer_id(customer_id)
    if not customer:
        raise HTTPException(401, "Not authenticated")
    return CustomerProfile(customer_id=customer["customer_id"], name=customer["name"], email=customer["email"])


@app.post("/upload", response_model=list[Transaction])
async def upload_statement(
    file: UploadFile = File(...),
    account: str | None = Form(None),
    customer_id: str = Depends(auth.require_bearer_token),
):
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
    file_id, _ = filestore.store_file(customer_id, raw, file.filename, issuer, "text/csv")
    transactions = _ingest_raw_transactions(customer_id, raw_transactions, account)
    db.mark_file_ingested(customer_id, file_id, issuer, file.filename)
    return transactions


@app.post("/upload/statement", response_model=list[Transaction])
async def upload_pdf_statement(
    file: UploadFile = File(...),
    issuer: str = Form(...),
    customer_id: str = Depends(auth.require_bearer_token),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported on this endpoint")
    if issuer not in PARSERS:
        raise HTTPException(400, f"Unknown issuer '{issuer}'. Known: {sorted(PARSERS)}")

    raw = await file.read()
    file_id, _ = filestore.store_file(customer_id, raw, file.filename, issuer, "application/pdf")

    try:
        return _ingest_mongo_file(customer_id, file_id, issuer, file.filename, "application/pdf")
    except ValueError as exc:
        raise HTTPException(
            422, f"{exc} Refusing to ingest a statement that may have been parsed incorrectly."
        ) from exc


def _build_category_summary(cat: str, items: list, total: float) -> CategorySummary:
    summary = CategorySummary(
        category=cat,
        total=round(sum(t["amount"] for t in items), 2),
        transaction_count=len(items),
        pct_of_spend=round(sum(t["amount"] for t in items) / total * 100, 1) if total else 0.0,
    )
    target_currency = CATEGORY_CURRENCY.get(cat)
    if target_currency:
        try:
            # Each transaction converted at its own date's rate, then
            # summed -- applying one rate to the whole month's total would
            # be wrong whenever the rate moved during the month. See
            # docs/design-fx-conversion.md.
            summary.converted_total = round(sum(fx.convert(t["amount"], t["date"], "USD", target_currency) for t in items), 2)
            summary.converted_currency = target_currency
        except httpx.HTTPError:
            # FX lookup is a nice-to-have enrichment -- a transient network
            # failure shouldn't take down /summary entirely.
            pass
    return summary


def _compute_summary(customer_id: str) -> list[MonthlySummary]:
    transactions = db.fetch_all_transactions(customer_id)
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
            _build_category_summary(cat, items, total)
            for cat, items in sorted(by_cat.items(), key=lambda kv: -sum(t["amount"] for t in kv[1]))
        ]

        # Same "a transaction in this month" proxy /coverage uses for "a
        # statement was ingested" -- a month missing one of the known
        # accounts' statements (most often just-not-downloaded-yet) would
        # otherwise show a misleadingly narrow category breakdown with no
        # indication anything's missing.
        accounts_present = {t["account"] for t in by_month[month] if t["account"] in PARSERS}
        is_partial = len(accounts_present) < len(PARSERS)

        summaries.append(
            MonthlySummary(
                month=month, total_spend=round(total, 2), by_category=cat_summaries, is_partial=is_partial
            )
        )

    return summaries


@app.get("/summary", response_model=list[MonthlySummary])
def summary(customer_id: str = Depends(auth.require_bearer_token)):
    return _compute_summary(customer_id)


def _compute_coverage(customer_id: str) -> CoverageResponse:
    """
    Which of the known accounts (PARSERS) have a statement on file for each
    month, so a gap (forgot to download/upload last month's SoFi statement,
    say) is visible on the dashboard instead of silently skewing /summary.
    A transaction's presence in a given month is used as the proxy for
    "a statement for that month was ingested" -- consistent with how
    /summary already buckets by month, and avoids needing to separately
    persist each statement's declared period.
    """
    transactions = db.fetch_all_transactions(customer_id)
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


@app.get("/coverage", response_model=CoverageResponse)
def coverage(customer_id: str = Depends(auth.require_bearer_token)):
    return _compute_coverage(customer_id)


@app.get("/fx/latest", response_model=FxRateResponse)
def latest_fx_rate(
    base: str = "USD", target: str = "INR", customer_id: str = Depends(auth.require_bearer_token)
):
    try:
        rate, resolved_date = fx.get_latest_rate(base, target)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"Could not reach the exchange rate service: {exc}") from exc
    except KeyError as exc:
        raise HTTPException(400, f"Unknown currency code: {exc}") from exc
    return FxRateResponse(base=base, target=target, rate=rate, date=resolved_date)


@app.get("/insights", response_model=InsightsResponse)
def insights(customer_id: str = Depends(auth.require_bearer_token)):
    monthly = _compute_summary(customer_id)  # reuse the aggregation above
    payload = [m.model_dump() for m in monthly]
    try:
        result = generate_insights(payload)
    except RuntimeError as exc:
        # A setup problem (Ollama not running, model not pulled), not a
        # model failure -- see insights.py for which backend was tried.
        raise HTTPException(503, f"AI insights are unavailable: {exc}") from exc
    except anthropic.AnthropicError as exc:
        raise HTTPException(503, f"AI insights are temporarily unavailable (Claude API error: {exc}).") from exc
    except ollama.ResponseError as exc:
        raise HTTPException(503, f"AI insights are temporarily unavailable (local model error: {exc.error}).") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            502, "AI insights are unavailable: the model returned a response in an unexpected format."
        ) from exc
    return InsightsResponse(**result)


@app.get("/health")
def health():
    """Deliberately unauthenticated (liveness probe) and deliberately not
    scoped data -- see docs/design-auth-and-customers.md. Use /auth/me or
    /summary for anything customer-specific."""
    return {"status": "ok"}

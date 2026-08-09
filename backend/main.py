import io
from collections import defaultdict

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from categorizer import categorize
from insights import generate_insights
from models import CategorySummary, InsightsResponse, MonthlySummary, Transaction

app = FastAPI(title="Personal Finance Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server default
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for the local prototype. Phase 5 (AWS re-platform) swaps
# this for DynamoDB.
_TRANSACTIONS: list[Transaction] = []

# Expected CSV columns. Adjust to match your bank/card export headers --
# most exports use some variant of these three.
EXPECTED_COLUMNS = {"date", "description", "amount"}


@app.post("/upload", response_model=list[Transaction])
async def upload_statement(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported in this phase")

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

    new_transactions = []
    for _, row in df.iterrows():
        cat = categorize(str(row["description"]))
        txn = Transaction(
            date=row["date"],
            description=str(row["description"]),
            amount=float(row["amount"]),
            **cat,
        )
        new_transactions.append(txn)

    _TRANSACTIONS.extend(new_transactions)
    return new_transactions


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
        txns = [t for t in by_month[month] if t.amount > 0]  # exclude refunds/income
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

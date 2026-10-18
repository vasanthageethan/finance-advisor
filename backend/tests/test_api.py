import glob
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_CREDIT_PDF = sorted(glob.glob(str(REPO_ROOT / "chase-credit" / "*.pdf")))
SAMPLE_CHECKING_PDF = sorted(glob.glob(str(REPO_ROOT / "chase-checking" / "*.pdf")))


def test_health_before_any_upload(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "transactions_loaded": 0}


def test_upload_sample_csv(client, sample_csv_path):
    with open(sample_csv_path, "rb") as f:
        resp = client.post(
            "/upload", files={"file": ("sample_transactions.csv", f, "text/csv")}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 25  # rows in sample_transactions.csv

    first = data[0]
    assert first["description"] == "TRADER JOE'S #123"
    assert first["category"] == "Groceries"
    assert first["category_source"] == "rule"
    assert first["confidence"] == 1.0

    # every row should have been categorized via the rule tier for this sample data
    assert all(row["category"] is not None for row in data)


def test_upload_updates_health_count(client, sample_csv_path):
    with open(sample_csv_path, "rb") as f:
        client.post("/upload", files={"file": ("sample_transactions.csv", f, "text/csv")})

    resp = client.get("/health")
    assert resp.json()["transactions_loaded"] == 25


def test_upload_rejects_non_csv_file(client):
    resp = client.post(
        "/upload",
        files={"file": ("statement.txt", io.BytesIO(b"date,description,amount\n"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "Only CSV files" in resp.json()["detail"]


def test_upload_rejects_csv_missing_required_columns(client):
    bad_csv = b"date,amount\n2026-07-01,10.00\n"
    resp = client.post(
        "/upload", files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")}
    )
    assert resp.status_code == 400
    assert "missing required column" in resp.json()["detail"]


def test_summary_without_upload_returns_404(client):
    resp = client.get("/summary")
    assert resp.status_code == 404


def test_summary_after_upload(client, sample_csv_path):
    with open(sample_csv_path, "rb") as f:
        client.post("/upload", files={"file": ("sample_transactions.csv", f, "text/csv")})

    resp = client.get("/summary")
    assert resp.status_code == 200
    months = resp.json()
    assert [m["month"] for m in months] == ["2026-06", "2026-07"]

    for month in months:
        # negative amounts (payroll deposit) are excluded from spend totals
        assert month["total_spend"] > 0
        cat_total = round(sum(c["total"] for c in month["by_category"]), 2)
        assert cat_total == pytest.approx(month["total_spend"], abs=0.05)

        pct_total = sum(c["pct_of_spend"] for c in month["by_category"])
        assert pct_total == pytest.approx(100.0, abs=0.5)


def test_summary_excludes_refunds_and_income_from_totals(client, sample_csv_path):
    with open(sample_csv_path, "rb") as f:
        client.post("/upload", files={"file": ("sample_transactions.csv", f, "text/csv")})

    resp = client.get("/summary")
    months = resp.json()
    for month in months:
        categories = [c["category"] for c in month["by_category"]]
        assert "Income & Transfers" not in categories


def test_insights_without_transactions_returns_404(client):
    resp = client.get("/insights")
    assert resp.status_code == 404


def test_insights_returns_generated_narrative(client, sample_csv_path, monkeypatch):
    with open(sample_csv_path, "rb") as f:
        client.post("/upload", files={"file": ("sample_transactions.csv", f, "text/csv")})

    monkeypatch.setattr(
        "main.generate_insights",
        lambda payload: {
            "narrative": "Spending rose month over month, driven by Shopping.",
            "flagged_anomalies": ["Shopping spend increased 60% in July"],
        },
    )

    resp = client.get("/insights")
    assert resp.status_code == 200
    body = resp.json()
    assert body["narrative"] == "Spending rose month over month, driven by Shopping."
    assert body["flagged_anomalies"] == ["Shopping spend increased 60% in July"]


def test_upload_statement_rejects_non_pdf_file(client):
    resp = client.post(
        "/upload/statement",
        files={"file": ("statement.csv", io.BytesIO(b"not a pdf"), "text/csv")},
        data={"issuer": "chase_credit"},
    )
    assert resp.status_code == 400
    assert "Only PDF files" in resp.json()["detail"]


def test_upload_statement_rejects_unknown_issuer(client):
    resp = client.post(
        "/upload/statement",
        files={"file": ("statement.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        data={"issuer": "wells_fargo_credit"},
    )
    assert resp.status_code == 400
    assert "Unknown issuer" in resp.json()["detail"]


@pytest.mark.skipif(not SAMPLE_CREDIT_PDF, reason="no chase-credit/*.pdf samples present locally")
def test_upload_statement_ingests_real_pdf_and_tags_account(client):
    with open(SAMPLE_CREDIT_PDF[0], "rb") as f:
        resp = client.post(
            "/upload/statement",
            files={"file": (Path(SAMPLE_CREDIT_PDF[0]).name, f, "application/pdf")},
            data={"issuer": "chase_credit"},
        )
    assert resp.status_code == 200
    transactions = resp.json()
    assert len(transactions) > 0
    assert all(t["account"] == "chase_credit" for t in transactions)


@pytest.mark.skipif(not SAMPLE_CHECKING_PDF, reason="no chase-checking/*.pdf samples present locally")
def test_upload_statement_checking_amounts_use_app_sign_convention(client):
    with open(SAMPLE_CHECKING_PDF[0], "rb") as f:
        resp = client.post(
            "/upload/statement",
            files={"file": (Path(SAMPLE_CHECKING_PDF[0]).name, f, "application/pdf")},
            data={"issuer": "chase_checking"},
        )
    assert resp.status_code == 200
    transactions = resp.json()
    # A payroll deposit is income, which the app convention represents as negative.
    payroll = [t for t in transactions if "payroll" in t["description"].lower()]
    assert payroll, "expected at least one payroll transaction in the sample checking statement"
    assert all(t["amount"] < 0 for t in payroll)


def test_summary_excludes_credit_card_payment_category(client):
    import db as db_module

    db_module.insert_transactions(
        [
            {
                "date": "2026-07-05", "description": "COFFEE SHOP", "amount": 6.50,
                "category": "Dining & Restaurants", "category_source": "rule", "confidence": 1.0, "account": None,
            },
            {
                "date": "2026-07-10", "description": "Payment To Chase Card", "amount": 500.00,
                "category": "Credit Card Payment", "category_source": "rule", "confidence": 1.0,
                "account": "chase_checking",
            },
        ]
    )

    resp = client.get("/summary")
    assert resp.status_code == 200
    month = resp.json()[0]
    categories = [c["category"] for c in month["by_category"]]
    assert "Credit Card Payment" not in categories
    assert month["total_spend"] == pytest.approx(6.50)


def test_coverage_with_no_transactions(client):
    resp = client.get("/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["months"] == []
    assert all(a["missing_months"] == [] for a in data["accounts"])


def test_coverage_flags_missing_months_per_account(client):
    import db as db_module

    def txn(date, account):
        return {
            "date": date, "description": "X", "amount": 1.0,
            "category": "Other", "category_source": "rule", "confidence": 1.0, "account": account,
        }

    db_module.insert_transactions(
        [
            txn("2026-01-01", "chase_credit"),
            txn("2026-02-01", "chase_credit"),
            txn("2026-03-01", "chase_credit"),
            # chase_checking only has Jan and Mar -- Feb is a real gap
            txn("2026-01-01", "chase_checking"),
            txn("2026-03-01", "chase_checking"),
            # an "other"/generic CSV upload with no known account shouldn't
            # affect coverage at all
            txn("2026-02-15", None),
        ]
    )

    resp = client.get("/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["months"] == ["2026-01", "2026-02", "2026-03"]

    by_account = {a["account"]: a for a in data["accounts"]}
    assert by_account["chase_credit"]["missing_months"] == []
    assert by_account["chase_checking"]["missing_months"] == ["2026-02"]
    # a known account with zero uploads is missing every month in range
    assert by_account["capitalone_credit"]["missing_months"] == ["2026-01", "2026-02", "2026-03"]

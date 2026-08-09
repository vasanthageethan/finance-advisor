import io

import pytest


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

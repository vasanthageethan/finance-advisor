import uuid
from datetime import datetime, timezone


def test_auth_status_false_before_password_set(raw_client):
    import db as db_module

    db_module.create_customer(str(uuid.uuid4()), "X", "x@example.com", datetime.now(timezone.utc).isoformat())
    resp = raw_client.get("/auth/status")
    assert resp.status_code == 200
    assert resp.json() == {"password_set": False}


def test_set_password_bootstrap_then_login(raw_client):
    import db as db_module

    db_module.create_customer(str(uuid.uuid4()), "X", "x@example.com", datetime.now(timezone.utc).isoformat())

    resp = raw_client.post("/auth/set-password", json={"password": "a-real-password"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["name"] == "X"

    assert raw_client.get("/auth/status").json() == {"password_set": True}

    login_resp = raw_client.post("/auth/login", json={"email": "x@example.com", "password": "a-real-password"})
    assert login_resp.status_code == 200
    assert login_resp.json()["access_token"]


def test_set_password_rejects_short_password(raw_client):
    import db as db_module

    db_module.create_customer(str(uuid.uuid4()), "X", "x@example.com", datetime.now(timezone.utc).isoformat())
    resp = raw_client.post("/auth/set-password", json={"password": "short"})
    assert resp.status_code == 400


def test_set_password_is_one_time_only(raw_client, customer):
    # `customer` fixture already has a password set -- the bootstrap
    # endpoint must refuse to run again, even with a plausible password.
    resp = raw_client.post("/auth/set-password", json={"password": "a-second-password"})
    assert resp.status_code == 403


def test_login_rejects_wrong_password(raw_client, customer):
    resp = raw_client.post("/auth/login", json={"email": customer["email"], "password": "wrong-password"})
    assert resp.status_code == 401


def test_login_rejects_unknown_email(raw_client, customer):
    resp = raw_client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401


def test_me_returns_authenticated_customer_profile(client, customer):
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] == customer["customer_id"]
    assert body["name"] == customer["name"]
    assert body["email"] == customer["email"]


def test_protected_endpoints_reject_missing_token(raw_client):
    for method, path in [
        ("get", "/summary"),
        ("get", "/coverage"),
        ("get", "/insights"),
        ("get", "/auth/me"),
        ("post", "/upload"),
        ("post", "/upload/statement"),
    ]:
        resp = getattr(raw_client, method)(path)
        assert resp.status_code == 401, f"{method.upper()} {path} should require auth, got {resp.status_code}"


def test_protected_endpoint_rejects_garbage_token(raw_client):
    raw_client.headers.update({"Authorization": "Bearer not-a-real-token"})
    resp = raw_client.get("/auth/me")
    assert resp.status_code == 401


def test_register_creates_customer_row_and_logs_in(raw_client):
    import db as db_module

    resp = raw_client.post(
        "/auth/register",
        json={"name": "New Person", "email": "newperson@example.com", "password": "a-real-password"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["name"] == "New Person"

    row = db_module.get_customer_by_customer_id(body["customer_id"])
    assert row is not None
    assert row["name"] == "New Person"
    assert row["email"] == "newperson@example.com"
    assert row["password_hash"]  # hashed, present -- never the plaintext

    # The returned token logs straight in, and the password itself verifies.
    import auth as auth_module

    assert auth_module.verify_password("a-real-password", row["password_hash"])
    login_resp = raw_client.post("/auth/login", json={"email": "newperson@example.com", "password": "a-real-password"})
    assert login_resp.status_code == 200


def test_register_rejects_duplicate_email(raw_client, customer):
    resp = raw_client.post(
        "/auth/register", json={"name": "Someone Else", "email": customer["email"], "password": "a-real-password"}
    )
    assert resp.status_code == 409


def test_register_rejects_short_password(raw_client):
    resp = raw_client.post(
        "/auth/register", json={"name": "X", "email": "shortpw@example.com", "password": "short"}
    )
    assert resp.status_code == 400


def test_register_rejects_blank_name(raw_client):
    resp = raw_client.post(
        "/auth/register", json={"name": "   ", "email": "blankname@example.com", "password": "a-real-password"}
    )
    assert resp.status_code == 400


def test_registered_customer_starts_with_isolated_empty_data(client, customer):
    """A freshly registered customer must see none of the fixture
    `customer`'s data -- registration has to produce real isolation, not
    just a cosmetic new row."""
    import db as db_module

    reg_resp = client.post(
        "/auth/register", json={"name": "Fresh Person", "email": "fresh@example.com", "password": "a-real-password"}
    )
    assert reg_resp.status_code == 200
    new_token = reg_resp.json()["access_token"]

    db_module.insert_transactions(
        customer["customer_id"],
        [
            {
                "date": "2026-07-05", "description": "ORIGINAL CUSTOMER SPEND", "amount": 12.0,
                "category": "Shopping", "category_source": "rule", "confidence": 1.0, "account": None,
            },
        ],
    )

    client.headers.update({"Authorization": f"Bearer {new_token}"})
    resp = client.get("/summary")
    assert resp.status_code == 404  # the new customer has zero transactions of their own


def test_data_is_scoped_per_customer(client, customer):
    """A second customer's data must never show up in the first
    customer's requests -- the entire point of this feature."""
    import db as db_module

    other_id = str(uuid.uuid4())
    db_module.create_customer(other_id, "Other Person", "other@example.com", datetime.now(timezone.utc).isoformat())
    db_module.insert_transactions(
        other_id,
        [
            {
                "date": "2026-07-05", "description": "OTHER PERSON'S COFFEE", "amount": 6.50,
                "category": "Dining & Restaurants", "category_source": "rule", "confidence": 1.0, "account": None,
            },
        ],
    )

    # `client` is authenticated as `customer`, not the one just created.
    resp = client.get("/summary")
    assert resp.status_code == 404  # customer has no transactions of their own

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

import auth as auth_module
import db as db_module
import filestore as filestore_module
import main as main_module


@pytest.fixture(autouse=True)
def reset_transactions():
    """Each test gets its own throwaway in-memory SQLite DB and a dedicated
    Mongo test database -- never backend/data/finance.db or the real
    finance_advisor Mongo database -- so tests can't see each other's data
    or a developer's real statements. Requires MongoDB reachable locally
    (see docs/design-mongodb-file-store.md)."""
    db_module.connect(":memory:")
    filestore_module.connect(db_name="finance_advisor_test")
    filestore_module.clear_all()
    yield
    db_module.clear_all()
    filestore_module.clear_all()


@pytest.fixture
def customer():
    """A seeded, password-set customer for tests -- the equivalent of a
    completed first-run bootstrap (see docs/design-auth-and-customers.md)."""
    customer_id = str(uuid.uuid4())
    db_module.create_customer(customer_id, "Test Customer", "test@example.com", datetime.now(timezone.utc).isoformat())
    db_module.set_customer_password(customer_id, auth_module.hash_password("test-password-123"))
    return db_module.get_customer_by_customer_id(customer_id)


@pytest.fixture
def client(customer):
    """An authenticated TestClient -- most tests predate auth and don't
    care about it, so authenticating by default keeps them unchanged."""
    c = TestClient(main_module.app)
    token = auth_module.create_access_token(customer["customer_id"])
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


@pytest.fixture
def raw_client():
    """An unauthenticated TestClient, for auth flow tests themselves."""
    return TestClient(main_module.app)


@pytest.fixture
def sample_csv_path():
    return Path(__file__).resolve().parent.parent / "sample_data" / "sample_transactions.csv"

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

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
def client():
    return TestClient(main_module.app)


@pytest.fixture
def sample_csv_path():
    return Path(__file__).resolve().parent.parent / "sample_data" / "sample_transactions.csv"

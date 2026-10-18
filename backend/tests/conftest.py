import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

import db as db_module
import main as main_module


@pytest.fixture(autouse=True)
def reset_transactions():
    """Each test gets its own throwaway in-memory SQLite DB -- never the real
    backend/data/finance.db -- so tests can't see each other's data or a
    developer's real statements."""
    db_module.connect(":memory:")
    yield
    db_module.clear_all()


@pytest.fixture
def client():
    return TestClient(main_module.app)


@pytest.fixture
def sample_csv_path():
    return Path(__file__).resolve().parent.parent / "sample_data" / "sample_transactions.csv"

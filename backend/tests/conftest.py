import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

import main as main_module


@pytest.fixture(autouse=True)
def reset_transactions():
    """Each test gets a clean in-memory transaction store."""
    main_module._TRANSACTIONS.clear()
    yield
    main_module._TRANSACTIONS.clear()


@pytest.fixture
def client():
    return TestClient(main_module.app)


@pytest.fixture
def sample_csv_path():
    return Path(__file__).resolve().parent.parent / "sample_data" / "sample_transactions.csv"

"""
Runs the Chase PDF parsers against real statement samples, if present.

The sample PDFs (chase-credit/, chase-checking/ at the repo root) are
gitignored real financial documents, not fixtures -- these tests only run
locally where you've dropped statements in, and skip everywhere else
(including CI) rather than failing on their absence.
"""

import glob
from pathlib import Path

import pytest

from statement_parsers import chase_checking, chase_credit

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CREDIT_DIR = REPO_ROOT / "chase-credit"
CHECKING_DIR = REPO_ROOT / "chase-checking"


def _pdfs(directory: Path) -> list[str]:
    return sorted(glob.glob(str(directory / "*.pdf")))


@pytest.mark.parametrize("pdf_path", _pdfs(CREDIT_DIR))
def test_chase_credit_statement_reconciles(pdf_path):
    result = chase_credit.parse(pdf_path)
    assert len(result.transactions) > 0
    r = result.reconciliation
    assert r.reconciled, (
        f"{pdf_path}: parsed total {r.parsed_total} != declared total "
        f"{r.declared_total} (diff {r.discrepancy})"
    )


@pytest.mark.parametrize("pdf_path", _pdfs(CHECKING_DIR))
def test_chase_checking_statement_reconciles(pdf_path):
    result = chase_checking.parse(pdf_path)
    assert len(result.transactions) > 0
    r = result.reconciliation
    assert r.reconciled, (
        f"{pdf_path}: parsed total {r.parsed_total} != declared total "
        f"{r.declared_total} (diff {r.discrepancy})"
    )


def test_chase_credit_transaction_shape():
    pdfs = _pdfs(CREDIT_DIR)
    if not pdfs:
        pytest.skip("no chase-credit/*.pdf samples present")
    txn = chase_credit.parse(pdfs[0]).transactions[0]
    assert txn.date is not None
    assert isinstance(txn.description, str) and txn.description
    assert isinstance(txn.amount, float)


def test_chase_checking_transaction_shape():
    pdfs = _pdfs(CHECKING_DIR)
    if not pdfs:
        pytest.skip("no chase-checking/*.pdf samples present")
    txn = chase_checking.parse(pdfs[0]).transactions[0]
    assert txn.date is not None
    assert isinstance(txn.description, str) and txn.description
    assert isinstance(txn.amount, float)

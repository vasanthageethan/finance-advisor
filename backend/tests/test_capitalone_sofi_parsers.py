"""
Runs the Capital One and SoFi PDF parsers against real statement samples,
if present. Same rationale as test_chase_parsers.py: these are gitignored
real financial documents, not fixtures, so these tests only run locally
where you've dropped statements in, and skip everywhere else.
"""

import glob
from pathlib import Path

import pytest

from statement_parsers import capitalone_credit, sofi_checking_savings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CAPITALONE_DIR = REPO_ROOT / "capitalone-credit"
SOFI_DIR = REPO_ROOT / "sofi-checkings-savings"


def _pdfs(directory: Path) -> list[str]:
    return sorted(glob.glob(str(directory / "*.pdf")))


@pytest.mark.parametrize("pdf_path", _pdfs(CAPITALONE_DIR))
def test_capitalone_credit_statement_reconciles(pdf_path):
    result = capitalone_credit.parse(pdf_path)
    assert len(result.transactions) > 0
    r = result.reconciliation
    assert r.reconciled, (
        f"{pdf_path}: parsed total {r.parsed_total} != declared total "
        f"{r.declared_total} (diff {r.discrepancy})"
    )


@pytest.mark.parametrize("pdf_path", _pdfs(SOFI_DIR))
def test_sofi_checking_savings_statement_reconciles(pdf_path):
    result = sofi_checking_savings.parse(pdf_path)
    assert len(result.transactions) > 0
    r = result.reconciliation
    assert r.reconciled, (
        f"{pdf_path}: parsed total {r.parsed_total} != declared total "
        f"{r.declared_total} (diff {r.discrepancy})"
    )


def test_sofi_transactions_are_tagged_with_sub_account():
    pdfs = _pdfs(SOFI_DIR)
    if not pdfs:
        pytest.skip("no sofi-checkings-savings/*.pdf samples present")
    transactions = sofi_checking_savings.parse(pdfs[0]).transactions
    descriptions = [t.description for t in transactions]
    assert any(d.startswith("Checking 9619:") for d in descriptions)
    assert any(d.startswith("Savings 5927:") for d in descriptions)

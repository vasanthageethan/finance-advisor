"""
Tier-1 parser for SoFi combined Checking + Savings statement PDFs.

Unlike the other issuers, a single SoFi statement PDF covers TWO
sub-accounts (Checking and Savings) back to back, each with its own
balance summary and transaction table, and each repeating its own
"<Type> Account - <last4>" header as a running header on every page of
its section (including continuation pages for months with more
transactions). This parser locates the FIRST occurrence of each distinct
section header to bound that section's full text span (through all its
pages, up to the next section), then parses each span independently with
its own balance-delta reconciliation.

Sign convention: same as chase_checking.py -- SoFi shows deposits
positive/withdrawals negative (account-balance perspective); amounts are
negated to match the app's positive-=-spend convention.

Transaction dates on this statement already carry a year ("Apr 30,
2026"), so no year-inference is needed here.
"""

import re
from datetime import date, datetime

import pdfplumber

from .base import ParsedStatement, ReconciliationResult, RawTransaction, to_float

_SECTION_HEADER = re.compile(r"^(Checking|Savings) Account - (\d+)$", re.MULTILINE)
_AMOUNT = r"-?\$[\d,]+\.\d{2}"
_TXN_LINE = re.compile(rf"^(\w{{3}} \d{{1,2}}, \d{{4}}) (.+?) ({_AMOUNT}) (\$[\d,]+\.\d{{2}})$")
_CURRENT_BALANCE = re.compile(r"Current Balance.*?\n\$([\d,]+\.\d{2})", re.DOTALL)
_BEGINNING_BALANCE = re.compile(r"Beginning Balance.*?\n\$([\d,]+\.\d{2})", re.DOTALL)


def _section_spans(full_text: str) -> list[tuple[str, str, str]]:
    """First occurrence of each distinct (account_type, last4) header, in
    document order, each paired with the text from there to the next
    distinct section's first occurrence (or end of document)."""
    first_seen: dict[tuple[str, str], int] = {}
    for m in _SECTION_HEADER.finditer(full_text):
        key = (m.group(1), m.group(2))
        if key not in first_seen:
            first_seen[key] = m.start()
    ordered = sorted(first_seen.items(), key=lambda kv: kv[1])
    spans = []
    for i, (key, start) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else len(full_text)
        spans.append((key[0], key[1], full_text[start:end]))
    return spans


def parse(pdf_path: str) -> ParsedStatement:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    spans = _section_spans(full_text)
    if not spans:
        raise ValueError(f"Could not find any 'Checking Account' / 'Savings Account' section in {pdf_path}")

    transactions = []
    declared_total = 0.0
    all_reconciled = True

    for account_type, last4, section_text in spans:
        for line in section_text.split("\n"):
            m = _TXN_LINE.match(line.strip())
            if not m:
                continue
            txn_date = datetime.strptime(m.group(1), "%b %d, %Y").date()
            sofi_amount = to_float(m.group(3))
            transactions.append(
                RawTransaction(
                    date=txn_date,
                    description=f"{account_type} {last4}: {m.group(2).strip()}",
                    amount=round(-sofi_amount, 2),  # flip sign -- see module docstring
                )
            )

        current_match = _CURRENT_BALANCE.search(section_text)
        beginning_match = _BEGINNING_BALANCE.search(section_text)
        if current_match and beginning_match:
            section_delta = round(to_float(current_match.group(1)) - to_float(beginning_match.group(1)), 2)
            declared_total += -section_delta  # app convention, see module docstring
        else:
            all_reconciled = False

    declared_total = round(declared_total, 2)
    parsed_total = round(sum(t.amount for t in transactions), 2)
    discrepancy = round(parsed_total - declared_total, 2)

    return ParsedStatement(
        transactions=transactions,
        reconciliation=ReconciliationResult(
            reconciled=all_reconciled and abs(discrepancy) < 0.01,
            declared_total=declared_total,
            parsed_total=parsed_total,
            discrepancy=discrepancy,
        ),
    )

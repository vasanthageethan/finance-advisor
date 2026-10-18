"""
Tier-1 parser for Chase credit card statement PDFs.

Layout notes from the sample statements: pdfplumber renders some bold
section headers with doubled characters (e.g. "ACCOUNT SUMMARY" extracts
as "AACCCCOOUUNNTT..."), so transaction detection matches the numeric line
pattern directly instead of anchoring on header text, which stays reliable
across statements.
"""

import re
from datetime import date, datetime

import pdfplumber

from .base import ParsedStatement, ReconciliationResult, RawTransaction, infer_year, to_float

_AMOUNT = r"-?(?:\d[\d,]*)?\.\d{2}"  # sub-dollar amounts print without a leading zero, e.g. ".07"
_TXN_LINE = re.compile(rf"^(\d{{2}}/\d{{2}})\s+(.+?)\s+({_AMOUNT})$")
_PERIOD = re.compile(r"Opening/Closing Date (\d{2}/\d{2}/\d{2}) - (\d{2}/\d{2}/\d{2})")

# (label pattern, whether a leading "-" can appear before the amount)
_SUMMARY_FIELDS = {
    "previous_balance": r"Previous Balance\s+\$([\d,]+\.\d{2})",
    "new_balance": r"New Balance\s+\$([\d,]+\.\d{2})",
}


def parse(pdf_path: str) -> ParsedStatement:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    period_match = _PERIOD.search(full_text)
    if not period_match:
        raise ValueError(f"Could not find statement period ('Opening/Closing Date') in {pdf_path}")
    period_start = datetime.strptime(period_match.group(1), "%m/%d/%y").date()
    period_end = datetime.strptime(period_match.group(2), "%m/%d/%y").date()

    transactions = []
    for line in full_text.split("\n"):
        m = _TXN_LINE.match(line.strip())
        if not m:
            continue
        month, day = (int(x) for x in m.group(1).split("/"))
        transactions.append(
            RawTransaction(
                date=date(infer_year(month, day, period_start, period_end), month, day),
                description=m.group(2).strip(),
                amount=to_float(m.group(3)),
            )
        )

    summary = {}
    for key, pattern in _SUMMARY_FIELDS.items():
        m = re.search(pattern, full_text)
        summary[key] = to_float(m.group(1)) if m else None

    declared_total = None
    if summary["previous_balance"] is not None and summary["new_balance"] is not None:
        # Every dollar that moved the balance from Previous to New shows up
        # as one of the parsed transaction lines (payments, purchases,
        # fees, interest), so their sum must equal that delta.
        declared_total = round(summary["new_balance"] - summary["previous_balance"], 2)

    parsed_total = round(sum(t.amount for t in transactions), 2)
    discrepancy = round(parsed_total - declared_total, 2) if declared_total is not None else 0.0

    return ParsedStatement(
        transactions=transactions,
        reconciliation=ReconciliationResult(
            reconciled=declared_total is not None and abs(discrepancy) < 0.01,
            declared_total=declared_total,
            parsed_total=parsed_total,
            discrepancy=discrepancy,
        ),
    )

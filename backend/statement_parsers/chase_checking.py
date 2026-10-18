"""
Tier-1 parser for Chase checking statement PDFs.

Sign convention: Chase prints withdrawals as negative and deposits as
positive (an account-balance perspective). models.Transaction uses the
opposite convention (positive = spend, matching the CSV upload path), so
amounts are negated here to stay consistent with that contract -- a
paycheck deposit becomes a negative "spend" amount, same as
"PAYROLL DIRECT DEPOSIT,-3200.00" in the sample CSV.

Each line also carries Chase's own running balance, which gives a much
stronger per-transaction check than the credit-card parser can do: every
line's stated balance must equal the previous line's balance plus that
line's amount, not just the statement-level total.
"""

import re
from datetime import date, datetime

import pdfplumber

from .base import ParsedStatement, ReconciliationResult, RawTransaction, infer_year, to_float

_AMOUNT = r"-?(?:\d[\d,]*)?\.\d{2}"  # sub-dollar amounts print without a leading zero, e.g. ".07"
_TXN_LINE = re.compile(rf"^(\d{{2}}/\d{{2}})\s+(.+?)\s+({_AMOUNT})\s+({_AMOUNT})$")
_PERIOD = re.compile(r"(\w+ \d{1,2}, \d{4}) through (\w+ \d{1,2}, \d{4})")
_BEGIN_BALANCE = re.compile(r"Beginning Balance\s+\$?([\d,]+\.\d{2})")
_END_BALANCE = re.compile(r"Ending Balance\s+\$?([\d,]+\.\d{2})")


def parse(pdf_path: str) -> ParsedStatement:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    period_match = _PERIOD.search(full_text)
    if not period_match:
        raise ValueError(f"Could not find statement period in {pdf_path}")
    period_start = datetime.strptime(period_match.group(1), "%B %d, %Y").date()
    period_end = datetime.strptime(period_match.group(2), "%B %d, %Y").date()

    begin_match = _BEGIN_BALANCE.search(full_text)
    end_match = _END_BALANCE.search(full_text)
    running_balance = to_float(begin_match.group(1)) if begin_match else None

    transactions = []
    balance_breaks = []
    for line in full_text.split("\n"):
        m = _TXN_LINE.match(line.strip())
        if not m:
            continue
        month, day = (int(x) for x in m.group(1).split("/"))
        chase_amount = to_float(m.group(3))
        stated_balance = to_float(m.group(4))

        if running_balance is not None and round(running_balance + chase_amount, 2) != stated_balance:
            balance_breaks.append(m.group(0))
        running_balance = stated_balance

        transactions.append(
            RawTransaction(
                date=date(infer_year(month, day, period_start, period_end), month, day),
                description=m.group(2).strip(),
                amount=round(-chase_amount, 2),  # flip sign -- see module docstring
            )
        )

    declared_total = None
    if begin_match and end_match:
        # Chase's own convention (deposits positive); negate to compare
        # against parsed_total, which is already in app convention.
        declared_total = round(to_float(end_match.group(1)) - to_float(begin_match.group(1)), 2) * -1

    parsed_total = round(sum(t.amount for t in transactions), 2)
    discrepancy = round(parsed_total - declared_total, 2) if declared_total is not None else 0.0

    return ParsedStatement(
        transactions=transactions,
        reconciliation=ReconciliationResult(
            reconciled=(
                declared_total is not None
                and abs(discrepancy) < 0.01
                and not balance_breaks
            ),
            declared_total=declared_total,
            parsed_total=parsed_total,
            discrepancy=discrepancy,
        ),
    )

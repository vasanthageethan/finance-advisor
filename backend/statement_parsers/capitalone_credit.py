"""
Tier-1 parser for Capital One credit card statement PDFs.

Layout notes: each transaction line carries two dates (Trans Date, Post
Date) with no year -- infer_year() resolves it same as the Chase parsers.
Statements can spread the transaction table across multiple pages
("Transactions (Continued)"), so parsing runs against the full
concatenated document text rather than a single page.

Interest and fees are NOT itemized as dated transaction lines the way
Chase does it -- Capital One only reports "Total Interest/Fees for This
Period" totals with no posting date. To keep the parsed sum reconcilable
against the statement's own Previous->New balance delta, a synthetic
transaction is added for each (dated to the statement's closing date)
when the amount is nonzero.
"""

import re
from datetime import date, datetime

import pdfplumber

from .base import ParsedStatement, ReconciliationResult, RawTransaction, infer_year, to_float

_AMOUNT = r"-?\s?\$(?:\d[\d,]*)?\.\d{2}"
_TXN_LINE = re.compile(rf"^(\w{{3}} \d{{1,2}}) (\w{{3}} \d{{1,2}}) (.+?) ({_AMOUNT})$")
_PERIOD = re.compile(r"(\w{3} \d{1,2}, \d{4}) - (\w{3} \d{1,2}, \d{4})")
_PREVIOUS_BALANCE = re.compile(r"Previous Balance\s+\$([\d,]+\.\d{2})")
_NEW_BALANCE = re.compile(r"New Balance\s*=?\s*\$([\d,]+\.\d{2})")
_TOTAL_INTEREST = re.compile(r"Total Interest for This Period\s+\$([\d,]+\.\d{2})")
_TOTAL_FEES = re.compile(r"Total Fees for This Period\s+\$([\d,]+\.\d{2})")


def _parse_month_day(token: str) -> tuple[int, int]:
    dt = datetime.strptime(f"{token} 2000", "%b %d %Y")  # placeholder year, real year resolved separately
    return dt.month, dt.day


def parse(pdf_path: str) -> ParsedStatement:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    period_match = _PERIOD.search(full_text)
    if not period_match:
        raise ValueError(f"Could not find statement period in {pdf_path}")
    period_start = datetime.strptime(period_match.group(1), "%b %d, %Y").date()
    period_end = datetime.strptime(period_match.group(2), "%b %d, %Y").date()

    transactions = []
    for line in full_text.split("\n"):
        m = _TXN_LINE.match(line.strip())
        if not m:
            continue
        month, day = _parse_month_day(m.group(1))
        transactions.append(
            RawTransaction(
                date=date(infer_year(month, day, period_start, period_end), month, day),
                description=m.group(3).strip(),
                amount=to_float(m.group(4)),
            )
        )

    interest_match = _TOTAL_INTEREST.search(full_text)
    if interest_match:
        interest = to_float(interest_match.group(1))
        if interest:
            transactions.append(RawTransaction(date=period_end, description="Interest Charged", amount=interest))

    fees_match = _TOTAL_FEES.search(full_text)
    if fees_match:
        fees = to_float(fees_match.group(1))
        if fees:
            transactions.append(RawTransaction(date=period_end, description="Fees Charged", amount=fees))

    previous_match = _PREVIOUS_BALANCE.search(full_text)
    new_match = _NEW_BALANCE.search(full_text)
    declared_total = None
    if previous_match and new_match:
        declared_total = round(to_float(new_match.group(1)) - to_float(previous_match.group(1)), 2)

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

"""
Shared interface and helpers for per-issuer PDF statement parsers.

Each parser converts one statement PDF into RawTransaction records shaped
like the CSV upload path (date, description, amount -- positive = spend,
matching models.Transaction), plus a ReconciliationResult. Unlike
categorization, a wrong dollar amount here silently corrupts every
downstream number, so every parser is expected to compare its parsed sum
against a total the statement itself declares.
"""

from dataclasses import dataclass
from datetime import date as date_type


@dataclass
class RawTransaction:
    date: date_type
    description: str
    amount: float


@dataclass
class ReconciliationResult:
    reconciled: bool
    declared_total: float | None
    parsed_total: float
    discrepancy: float


@dataclass
class ParsedStatement:
    transactions: list[RawTransaction]
    reconciliation: ReconciliationResult


def infer_year(month: int, day: int, period_start: date_type, period_end: date_type) -> int:
    """
    Statement transaction lines carry MM/DD with no year. Resolve it by
    checking which of the two candidate years (the period's start or end
    year) actually places the date inside the statement's own date range --
    handles the December/January boundary correctly without guessing from
    month order alone.
    """
    for year in {period_start.year, period_end.year}:
        try:
            candidate = date_type(year, month, day)
        except ValueError:
            continue
        if period_start <= candidate <= period_end:
            return year
    return period_end.year if month <= period_end.month else period_start.year


def to_float(token: str) -> float:
    token = token.strip()
    negative = token.startswith("-")
    cleaned = token.replace("-", "").replace("$", "").replace(",", "")
    return round(float(cleaned) * (-1 if negative else 1), 2)

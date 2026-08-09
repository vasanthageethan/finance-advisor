from datetime import date
from typing import Optional

from pydantic import BaseModel


class Transaction(BaseModel):
    date: date
    description: str
    amount: float  # positive = spend, negative = refund/credit
    category: Optional[str] = None
    category_source: Optional[str] = None  # "rule" | "hf" | "claude" | "manual"
    confidence: Optional[float] = None


class CategorySummary(BaseModel):
    category: str
    total: float
    transaction_count: int
    pct_of_spend: float


class MonthlySummary(BaseModel):
    month: str  # "2026-07"
    total_spend: float
    by_category: list[CategorySummary]


class InsightsResponse(BaseModel):
    narrative: str
    flagged_anomalies: list[str]

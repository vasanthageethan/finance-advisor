"""
Historical currency conversion via Frankfurter (ECB reference rates) --
free, open-source, no API key, no rate limit (verified live before
building against it). See docs/design-fx-conversion.md for why this
exists, why per-transaction conversion is the only accurate approach, and
why caching is for avoiding redundant calls, not correctness.
"""

import httpx

import db

FRANKFURTER_URL = "https://api.frankfurter.dev/v1"


def get_historical_rate(date: str, base: str = "USD", target: str = "INR") -> float:
    """date: "YYYY-MM-DD". Returns the exchange rate (1 base = rate target)
    on that date, or the prior business day's rate if it fell on a
    weekend/ECB holiday -- Frankfurter's own fallback, not this module's."""
    cached = db.get_cached_fx_rate(date, base, target)
    if cached is not None:
        return cached

    response = httpx.get(f"{FRANKFURTER_URL}/{date}", params={"base": base, "symbols": target}, timeout=10)
    response.raise_for_status()
    rate = response.json()["rates"][target]

    db.cache_fx_rate(date, base, target, rate)
    return rate


def convert(amount: float, date: str, base: str = "USD", target: str = "INR") -> float:
    rate = get_historical_rate(date, base, target)
    return round(amount * rate, 2)

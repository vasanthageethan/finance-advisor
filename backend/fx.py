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


def get_latest_rate(base: str = "USD", target: str = "INR") -> tuple[float, str]:
    """Returns (rate, date) for the most recent available rate -- today's,
    or the prior business day's if today is a weekend/ECB holiday.
    Deliberately not cache-first like get_historical_rate: the caller
    (the live rate banner) wants this fetched fresh on every request, not
    served from a possibly-stale earlier-today lookup. The resolved date
    still gets cached afterward, so a later historical lookup for that
    same date doesn't re-fetch it."""
    response = httpx.get(f"{FRANKFURTER_URL}/latest", params={"base": base, "symbols": target}, timeout=10)
    response.raise_for_status()
    body = response.json()
    rate = body["rates"][target]
    resolved_date = body["date"]

    db.cache_fx_rate(resolved_date, base, target, rate)
    return rate, resolved_date

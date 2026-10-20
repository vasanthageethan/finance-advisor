import httpx
import pytest

import db
import fx


class _FakeResponse:
    def __init__(self, rate, currency="INR"):
        self._rate = rate
        self._currency = currency

    def raise_for_status(self):
        pass

    def json(self):
        return {"amount": 1.0, "base": "USD", "date": "2026-07-24", "rates": {self._currency: self._rate}}


def test_get_historical_rate_calls_api_and_caches(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params))
        return _FakeResponse(96.56)

    monkeypatch.setattr(httpx, "get", fake_get)

    rate = fx.get_historical_rate("2026-07-24", "USD", "INR")
    assert rate == 96.56
    assert len(calls) == 1

    # Second call for the same (date, base, target) must hit the cache,
    # not the network -- a historical day's rate never changes.
    rate_again = fx.get_historical_rate("2026-07-24", "USD", "INR")
    assert rate_again == 96.56
    assert len(calls) == 1


def test_convert_multiplies_by_rate(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, params, timeout: _FakeResponse(90.0))
    assert fx.convert(500.0, "2026-01-01", "USD", "INR") == 45000.0


def test_cache_is_scoped_per_date_and_currency_pair(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["symbols"])
        currency = params["symbols"]
        return _FakeResponse(90.0 if currency == "INR" else 0.92, currency=currency)

    monkeypatch.setattr(httpx, "get", fake_get)

    fx.get_historical_rate("2026-01-01", "USD", "INR")
    fx.get_historical_rate("2026-01-01", "USD", "EUR")  # different target -- real network call
    fx.get_historical_rate("2026-01-01", "USD", "INR")  # same as the first -- cached

    assert calls == ["INR", "EUR"]


def test_get_historical_rate_propagates_http_errors(monkeypatch):
    def fake_get(url, params, timeout):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(httpx.HTTPError):
        fx.get_historical_rate("2026-01-01", "USD", "INR")

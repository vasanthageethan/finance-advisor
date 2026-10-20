# Design: historical FX conversion for international payments

## Problem

Student Loan Payment transactions (Remitly, confirmed recurring international
remittances to India -- see `categorizer.py`'s comment on that rule) are
recorded in USD, the only currency this app's data ever carries. There's no
way to see what that payment was actually worth in the recipient's currency
at the time it was sent.

## Decision

A general-purpose historical currency conversion capability, not a one-off
INR special case: `backend/fx.py` can convert any (date, USD amount) to any
of ~30 currencies Frankfurter supports, cached in SQLite. It's applied today
to one category (`Student Loan Payment` -> INR) via an explicit, extensible
mapping -- adding a second international category later (a different
recipient currency, say) is a one-line config change, not new plumbing.

## Why Frankfurter, not Plaid/a paid FX API

Free, open-source, backed by European Central Bank reference rates, **no API
key, no rate limit** -- verified live against `api.frankfurter.dev` before
building against it. No new secret to manage in `.env`, no account to create,
no cost ceiling to worry about. The one real constraint: ECB rates are daily
reference values, not intraday, and only on EU business days -- a Saturday
transaction's "rate" is Friday's close, not a live quote at the moment of the
transaction. Fine for "what was this roughly worth," not suitable for
anything requiring an exact settlement-time rate.

## Caching

```sql
CREATE TABLE fx_rates (
    date TEXT NOT NULL,
    base TEXT NOT NULL,
    target TEXT NOT NULL,
    rate REAL NOT NULL,
    PRIMARY KEY (date, base, target)
);
```

Frankfurter has no rate limit, so caching isn't strictly required for
correctness -- it's here to avoid an external network call on every
dashboard load once a given (date, currency pair) has been looked up once.
A cache miss just calls the API and stores the result; nothing ever expires
(a historical day's closing rate doesn't change after the fact).

## Why per-transaction conversion, not one rate applied to a month's total

A category's monthly total is a sum of several transactions, each on its own
date. Applying a single rate (e.g. the month's last day) to that whole sum
would be wrong whenever the rate moved during the month -- converting each
transaction individually at its own date's rate, then summing the converted
amounts, is the only version of this that's actually accurate. More API
calls per month, but correctness over convenience, consistent with how this
project already treats month-over-month and category math elsewhere.

## What this doesn't solve

No currency selector in the UI (the mapping is server-side, not
user-configurable yet) -- fine while there's exactly one international
category. No handling of a transaction landing on a weekend/holiday beyond
whatever Frankfurter itself falls back to (the prior business day). Revisit
if a second country/category shows up in real data.

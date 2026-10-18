"""
One-time backfill: re-run categorize() on every transaction currently
tagged category_source="fallback". Those rows were categorized before
transformers/torch were actually installed in this venv (requirements.txt
listed them, but they were never pip installed, so every rule-miss
silently fell through the Hugging Face tier straight to "Other" instead
of getting a real zero-shot classification). Safe to re-run -- it's a
no-op once nothing is left tagged "fallback".

Usage (from backend/, with the venv active):
    python scripts/recategorize_fallback.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from categorizer import categorize  # noqa: E402


def main() -> None:
    db.connect()
    rows = db.fetch_transactions_by_source("fallback")

    if not rows:
        print("Nothing tagged 'fallback' -- nothing to do.")
        return

    for row in rows:
        cat = categorize(row["description"])
        db.update_transaction_category(row["id"], cat["category"], cat["category_source"], cat["confidence"])
        print(f"  {row['description'][:60]:60} -> {cat['category']} ({cat['category_source']}, {cat['confidence']})")
    print(f"\nRe-categorized {len(rows)} transaction(s).")


if __name__ == "__main__":
    main()

"""
Re-run categorize() on every transaction for the seeded customer, applying
the current RULES/CATEGORIES to historical data. Safe to re-run any time
categorizer.py's rules change -- most transactions re-match the same
category they already had; only the ones affected by a rule change move.

Usage (from backend/, with the venv active):
    python scripts/recategorize_all.py
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from categorizer import categorize  # noqa: E402


def main() -> None:
    db.connect()
    customer = db.get_any_customer()
    if customer is None:
        print("No customer account exists yet -- start the backend once first.")
        return

    rows = db.fetch_all_transactions(customer["customer_id"])
    changes = Counter()
    for row in rows:
        cat = categorize(row["description"])
        if cat["category"] != row["category"] or cat["category_source"] != row["category_source"]:
            print(
                f"  {row['description'][:55]:55} "
                f"{row['category']} ({row['category_source']}) -> {cat['category']} ({cat['category_source']})"
            )
            db.update_transaction_category(row["id"], cat["category"], cat["category_source"], cat["confidence"])
            changes[f"{row['category']} -> {cat['category']}"] += 1

    if not changes:
        print("Nothing changed -- every transaction already matches the current rules.")
        return

    print(f"\nRe-categorized {sum(changes.values())} of {len(rows)} transaction(s):")
    for change, n in changes.most_common():
        print(f"  {n:3}  {change}")


if __name__ == "__main__":
    main()

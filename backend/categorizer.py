"""
Hybrid transaction categorizer.

Tier 1 (cheap, instant): keyword/merchant rules.
Tier 2 (local model, no API cost): Hugging Face zero-shot classification,
    used only for transactions the rules can't confidently match.
Tier 3 (Claude API, used sparingly): reserved for insights.py, not per-transaction
    categorization. Routing every transaction through a frontier LLM is expensive
    and unnecessary for a task this well-suited to cheaper tiers.

This tiering is deliberate: most real transaction descriptions are highly
repetitive ("AMAZON.COM", "SHELL OIL", "TRADER JOE'S #123"), so a small rule
set + local model should resolve 90%+ of transactions without ever calling
an external API.
"""

from functools import lru_cache

CATEGORIES = [
    "Groceries",
    "Dining & Restaurants",
    "Transportation",
    "Gas & Fuel",
    "Utilities",
    "Rent & Housing",
    "Subscriptions & Entertainment",
    "Shopping",
    "Healthcare",
    "Travel",
    "Insurance",
    "Fees & Interest",
    "Income & Transfers",
    "Other",
]

# Cheap, high-confidence keyword rules. Extend this as you see real merchant
# strings in your own statements -- it will quickly cover the bulk of your spend.
RULES = {
    "Groceries": ["trader joe", "whole foods", "safeway", "kroger", "aldi", "costco wholesale", "walmart grocery"],
    "Dining & Restaurants": ["starbucks", "chipotle", "mcdonald", "doordash", "uber eats", "grubhub", "restaurant"],
    "Transportation": ["uber", "lyft", "metro", "transit", "parking"],
    "Gas & Fuel": ["shell", "chevron", "exxon", "76 gas", "arco"],
    "Utilities": ["pg&e", "comcast", "at&t", "verizon", "water dept", "electric"],
    "Rent & Housing": ["rent", "property mgmt", "apartments"],
    "Subscriptions & Entertainment": ["netflix", "spotify", "hulu", "disney+", "amazon prime", "youtube premium"],
    "Shopping": ["amazon.com", "target", "best buy", "ebay"],
    "Healthcare": ["cvs pharmacy", "walgreens", "urgent care", "medical"],
    "Travel": ["delta air", "united airlines", "airbnb", "marriott", "hilton"],
    "Insurance": ["geico", "state farm", "progressive insurance"],
    "Fees & Interest": ["interest charge", "late fee", "annual fee", "overdraft"],
    "Income & Transfers": ["payroll", "direct deposit", "venmo", "zelle transfer"],
}


def rule_based_category(description: str) -> str | None:
    desc = description.lower()
    for category, keywords in RULES.items():
        if any(kw in desc for kw in keywords):
            return category
    return None


@lru_cache(maxsize=1)
def _get_zero_shot_pipeline():
    # Imported lazily so the API can boot without downloading the model
    # until the first uncategorized transaction actually needs it.
    from transformers import pipeline

    # distilbart is ~5x smaller/faster than bart-large-mnli with a modest
    # accuracy tradeoff -- reasonable default for a local, low-cost tier.
    return pipeline("zero-shot-classification", model="valhalla/distilbart-mnli-12-3")


def hf_category(description: str, threshold: float = 0.4) -> tuple[str, float]:
    clf = _get_zero_shot_pipeline()
    result = clf(description, candidate_labels=CATEGORIES)
    label, score = result["labels"][0], result["scores"][0]
    if score < threshold:
        return "Other", score
    return label, score


def categorize(description: str) -> dict:
    rule_hit = rule_based_category(description)
    if rule_hit:
        return {"category": rule_hit, "category_source": "rule", "confidence": 1.0}

    label, score = hf_category(description)
    return {"category": label, "category_source": "hf", "confidence": round(float(score), 3)}

import pytest

from categorizer import CATEGORIES, categorize, rule_based_category


@pytest.mark.parametrize(
    "description,expected_category",
    [
        ("TRADER JOE'S #123", "Groceries"),
        ("SHELL OIL 5741", "Gas & Fuel"),
        ("NETFLIX.COM", "Subscriptions & Entertainment"),
        ("STARBUCKS STORE 4521", "Dining & Restaurants"),
        ("AMAZON.COM*A1B2C3", "Shopping"),
        ("PAYROLL DIRECT DEPOSIT", "Income & Transfers"),
        ("PG&E ELECTRIC", "Utilities"),
        ("UBER TRIP", "Transportation"),
        ("CVS PHARMACY #221", "Healthcare"),
        ("GEICO INSURANCE", "Insurance"),
        ("APARTMENTS LLC RENT", "Rent & Housing"),
        ("DELTA AIR LINES", "Travel"),
        ("LATE FEE CHARGE", "Fees & Interest"),
    ],
)
def test_rule_based_category_matches_known_merchants(description, expected_category):
    assert rule_based_category(description) == expected_category


def test_rule_based_category_is_case_insensitive():
    assert rule_based_category("trader joe's #123") == "Groceries"
    assert rule_based_category("TRADER JOE'S #123") == "Groceries"


def test_rule_based_category_returns_none_for_unknown_merchant():
    assert rule_based_category("SOME TOTALLY UNRECOGNIZABLE MERCHANT XYZ") is None


def test_categorize_uses_rule_tier_when_available():
    result = categorize("TRADER JOE'S #123")
    assert result == {"category": "Groceries", "category_source": "rule", "confidence": 1.0}


def test_categorize_falls_back_to_hf_tier_when_no_rule_matches(monkeypatch):
    monkeypatch.setattr("categorizer.hf_category", lambda desc, threshold=0.4: ("Other", 0.55))
    result = categorize("SOME TOTALLY UNRECOGNIZABLE MERCHANT XYZ")
    assert result == {"category": "Other", "category_source": "hf", "confidence": 0.55}


def test_categories_list_is_nonempty_and_unique():
    assert len(CATEGORIES) == len(set(CATEGORIES))
    assert len(CATEGORIES) > 0

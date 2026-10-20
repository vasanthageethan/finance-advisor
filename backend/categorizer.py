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
    "Auto Loan/Lease Payment",
    "Subscriptions",
    "Entertainment & Leisure",
    "Personal Care",
    "Shopping",
    "Cash Withdrawal",
    "Healthcare",
    "Travel",
    "Insurance",
    "Fees & Interest",
    "Income & Transfers",
    "Credit Card Payment",
    "Savings Transfer",
    "Investment Transfer",
    "Student Loan Payment",
    "Personal Transfer (Zelle)",
    "Other",
]

# Categories that represent money moving between your own accounts, not
# actual spend -- a checking withdrawal that pays off a credit card is not
# a purchase, it's the same money the credit card statement already counts
# as spend when the purchase happened. Combine statements from multiple
# accounts without excluding these and spend totals silently double-count.
# Student Loan Payment and Personal Transfer (Zelle) are deliberately NOT
# included here -- both are real money leaving your accounts to someone
# else (a lender, another person), not a transfer between accounts you
# own, so they stay counted as spend; they're just labeled instead of
# dumped into "Other" or lumped together. Remitly transactions are
# confirmed by the account owner to be recurring international student
# loan payments to India, not general person-to-person transfers -- split
# out from Zelle for that reason.
NON_SPEND_CATEGORIES = {"Income & Transfers", "Credit Card Payment", "Savings Transfer", "Investment Transfer"}

# Categories that represent an international payment, mapped to the
# recipient's currency -- used by main.py to attach a historical FX
# conversion (see fx.py, docs/design-fx-conversion.md). Student Loan
# Payment/India is the one confirmed real case today; extend this mapping
# if a second international category ever shows up in real data rather
# than guessing ahead of time.
CATEGORY_CURRENCY = {"Student Loan Payment": "INR"}

# Cheap, high-confidence keyword rules. Extend this as you see real merchant
# strings in your own statements -- it will quickly cover the bulk of your spend.
RULES = {
    "Groceries": [
        "trader joe", "whole foods", "wholefds", "safeway", "kroger", "aldi", "costco wholesale",
        "walmart grocery", "costco whse", "costco by instacart", "wal-mart", "wm supercenter", "sisters mart",
        "king soopers", "sprouts farmers mark", "h mart", "taaza mart", "arash grocery", "bombay bazaar",
        "laxmi food", "mi pueblo",
    ],
    "Dining & Restaurants": [
        "starbucks", "chipotle", "mcdonald", "doordash", "uber eats", "uber *eats", "grubhub", "restaurant",
        "chick-fil-a", "burger king", "cava", "coffee", "tst*", "tst *", "thirstea", "wendy's", "raising canes",
        "popeyes", "papa john", "gaia masala", "saravanaa bhavan", "desi bites", "mad over curry",
        "tous les jours", "village bagels", "discount liquor", "tower liquors", "ctlp*", "hq cafe", "andy's",
        "first watch", "taco bell", "mod pizza", "sushi and rame",
    ],
    "Transportation": [
        "uber", "lyft", "metro", "transit", "parking", "enterprise", "mta*", "path tapp", "lime*ride",
        "bird app", "spothero", "schomp subaru",
    ],
    "Gas & Fuel": ["shell", "chevron", "exxon", "76 gas", "arco", "costco gas", "esso circle k", "love's"],
    "Utilities": ["pg&e", "comcast", "at&t", "verizon", "water dept", "electric", "boost mobile"],
    "Rent & Housing": ["rent", "property mgmt", "apartments"],
    # A recurring, fixed-amount bill (same shape as Student Loan Payment),
    # but dwarfs ordinary day-to-day Transportation spend (Uber/parking) if
    # lumped in with it -- split out for the same reason Student Loan
    # Payment isn't dumped into "Other"/general transfers. "als 1648" is
    # this specific lease servicer/account reference (confirmed by the
    # account owner), not a generalizable merchant string -- fine for a
    # tool tailored to one user's own statements. Using the full "to als
    # 1648" phrase (not bare "als") avoids false-matching unrelated words
    # like "also".
    "Auto Loan/Lease Payment": ["to als 1648"],
    # Fixed, predictable MONTHLY bills only -- these should look roughly the
    # same total every month (step changes from a price hike or a new
    # subscription starting are expected; a large one-off spike is not).
    # Annual/semi-annual dues (IEEE membership, MySubaru's renewal cadence)
    # are deliberately excluded even though they're "recurring" in a loose
    # sense -- they don't repeat monthly, so they'd reintroduce exactly the
    # spiky-total problem this split exists to avoid. See Fees & Interest.
    "Subscriptions": [
        "netflix", "spotify", "hulu", "disney+", "amazon prime", "youtube", "adobe", "apple.com/bill",
        "crunchyroll", "anthropic",
        # Affirm installment payment -- confirmed by the account owner to be
        # a device financing plan (Samsung phone). Flat $54.03 every month
        # (verified against real statement data), so it belongs with the
        # other fixed-monthly bills here rather than in Shopping, which is
        # for variable one-off purchases. The line item carries no merchant
        # name, so this can't be inferred from the description alone.
        "affirm.com",
    ],
    # One-off leisure/outing purchases. Naturally variable month to month
    # by design -- don't expect this one to be flat.
    "Entertainment & Leisure": ["cinemark", "fandango", "amc ", "bowlero"],
    # Personal grooming/upkeep -- a haircut isn't "leisure" in the same
    # sense as a movie or bowling, and it recurs on its own (roughly
    # monthly) cadence rather than being a one-off outing.
    "Personal Care": ["great clips"],
    "Shopping": [
        "amazon.com", "amzn.com", "amazon mktpl", "target", "best buy", "ebay", "walmart.com", "wmt plus",
        "american eagle", "dillards", "express#", "old navy", "gap outlet", "h&m ", "calvin klein",
        "coach outlet", "adidas", "columbia", "swarovski", "dicks sporting", "rei #", "fedex offic",
        "parcel pending", "minutekey", "samsung", "brooks sports", "levi's",
        # Catches both "MAC Park Meadows..." and "MACYS PARK MEADOWS..." --
        # two POS-formatting variants of the same mall/merchant observed in
        # real statement data.
        "park meadows",
        # Shipping/printing store -- same category as FedEx Office above.
        # Previously fell through to the zero-shot tier, which guessed
        # "Transportation" (shipping != transit) at just 0.574 confidence.
        "ups store",
    ],
    # Cash withdrawn from an ATM. Real spend -- kept in the total -- but
    # what it was actually spent on isn't knowable from a bank statement,
    # so it gets its own honest label instead of pretending to know more.
    "Cash Withdrawal": ["atm withdrawal"],
    "Healthcare": [
        "cvs pharmacy", "cvs/pharmacy", "walgreens", "urgent care", "medical", "labcorp", "hims and hers",
        "skin doctors",
    ],
    "Travel": [
        "delta air", "united airlines", "united.com", "air canada", "airbnb", "marriott", "hilton", "sonesta",
        "expedia", "georgetown loop", "statue cruises", "nyc ferry", "travel guard",
        "recreation.gov", "st mary's glacier", "ogx photo", "breckenridge", "breck park",
        # Broadened from "frontier ai" -- the other two real "FRONTIER
        # <code> DENVER CO" lines observed (no "ai" segment) are Frontier
        # Airlines charges too, inferred from amount ($178-245, consistent
        # with a domestic flight, not a flat recurring utility bill) since
        # Denver is a Frontier Airlines hub. Revisit if a Frontier
        # Communications bill ever actually shows up in this data.
        "frontier",
    ],
    "Insurance": ["geico", "state farm", "progressive insurance"],
    "Fees & Interest": [
        "interest charge", "late fee", "annual fee", "overdraft", "foreign transaction fee", "filing fee",
        "driver servi", "motor veh serv", "driving acade",
        # Non-monthly recurring dues -- see the Subscriptions comment above
        # for why these live here instead of there.
        "ieee products", "mysubaru subscription",
    ],
    "Income & Transfers": [
        "payroll", "direct deposit", "venmo", "zelle transfer", "interest earned", "irs treas", "tax ref",
        "cash redemption",
    ],
    # Paying down your own credit card from a checking/other account -- not
    # discretionary spend, see NON_SPEND_CATEGORIES above.
    "Credit Card Payment": [
        "payment to chase card", "payment thank you", "capital one mobile p", "discover e-payment",
        "electronic payment", "citi card",
    ],
    # Money moved into a brokerage account you own (e.g. Robinhood) -- not
    # spend, same reasoning as Savings Transfer above.
    "Investment Transfer": ["robinhood"],
    # Transfers to/from a savings account you own -- not spend either way.
    # "jpmorgan chase" (not the fuller "jpmorgan chase bank") deliberately
    # catches both "JPMORGAN CHASE BANK, NA" and "JPMorgan Chase Ext Trnsfr"
    # wordings SoFi uses for the same Chase<->SoFi transfer.
    "Savings Transfer": ["sofi", "to savings", "from checking", "jpmorgan chase"],
    # Confirmed by the account owner: Remitly transactions are recurring
    # international student loan payments to India, not general
    # person-to-person transfers. Real spend (debt repayment), kept in
    # totals, just labeled precisely instead of guessed at.
    "Student Loan Payment": ["remitly"],
    # Money sent to/from another person via Zelle. Real spend (or income)
    # when it's outgoing/incoming, but the PDF carries no memo, so the
    # *purpose* (rent, splitting a bill, a gift) can't be determined from
    # this data -- kept as its own labeled bucket rather than lumped into
    # "Other". Plain "zelle" (not "zelle payment") because SoFi's wording
    # is "Zelle® Payment from ..." -- the registered-trademark glyph sits
    # between the two words and breaks a "zelle payment" substring match.
    # "rufina prakash" is a specific recurring counterparty in this
    # account's own data, not a generalizable merchant pattern -- fine for
    # a personal finance tool tailored to one user's statements, but not
    # something a generic categorizer should ship with.
    "Personal Transfer (Zelle)": ["zelle", "rufina prakash"],
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

    try:
        label, score = hf_category(description)
    except ModuleNotFoundError:
        # transformers/torch aren't installed -- degrade to "Other" instead
        # of failing the whole upload over one unmatched merchant string.
        return {"category": "Other", "category_source": "fallback", "confidence": 0.0}
    return {"category": label, "category_source": "hf", "confidence": round(float(score), 3)}

"""
Registry of per-issuer PDF statement parsers. Each parser module exposes
parse(pdf_path) -> ParsedStatement (see base.py). Same tiering philosophy
as categorizer.py's keyword rules: cheap and deterministic for known
formats, extend with a new module + registry entry as new statement
layouts show up.
"""

from . import capitalone_credit, chase_checking, chase_credit, sofi_checking_savings

PARSERS = {
    "chase_credit": chase_credit.parse,
    "chase_checking": chase_checking.parse,
    "capitalone_credit": capitalone_credit.parse,
    "sofi_checking_savings": sofi_checking_savings.parse,
}


def parse_statement(issuer: str, pdf_path: str):
    if issuer not in PARSERS:
        raise ValueError(f"No parser registered for issuer '{issuer}'. Known: {sorted(PARSERS)}")
    return PARSERS[issuer](pdf_path)

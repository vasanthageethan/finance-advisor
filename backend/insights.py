"""
Claude is reserved for the tier where reasoning quality actually matters:
turning aggregated numbers into a written narrative, and flagging anomalies
that a fixed threshold rule would miss (e.g. a new recurring charge that's
individually small but a pattern change worth mentioning).

Requires ANTHROPIC_API_KEY to be set in the environment.
"""

import json
import os

import anthropic

MODEL = "claude-sonnet-5"


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


def generate_insights(monthly_summaries: list[dict]) -> dict:
    """
    monthly_summaries: list of dicts shaped like MonthlySummary, most recent last.
    Returns {"narrative": str, "flagged_anomalies": list[str]}.
    """
    prompt = f"""You are a personal finance analyst. Here is a user's spending
summary by month and category, most recent month last:

{json.dumps(monthly_summaries, indent=2)}

Write:
1. A short (3-5 sentence) plain-language narrative describing the overall
   spending trend, called out by category where relevant.
2. A list of specific anomalies or changes worth flagging (new categories,
   spikes over 25% month-over-month, categories trending steadily upward
   over 3+ months). If nothing stands out, say so explicitly rather than
   inventing something.

Respond as JSON with keys "narrative" (string) and "flagged_anomalies"
(list of strings). Respond with only the JSON, no other text."""

    response = _client().messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    return json.loads(text)

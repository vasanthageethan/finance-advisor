"""
Generates the written spending narrative and anomaly flags -- the tier
where reasoning quality actually matters, unlike per-transaction
categorization (categorizer.py's tiers 1-2).

The backend for this tier is itself pluggable, the same cost-aware-routing
idea extended one level further: a local model (Ollama, free, no API key)
runs by default; Claude is used instead when ANTHROPIC_API_KEY is set, for
better narrative quality at a per-call cost. See
docs/design-local-insights-model.md for the full rationale.
"""

import json
import os
import re

import anthropic
import httpx
import ollama

CLAUDE_MODEL = "claude-sonnet-5"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b-instruct")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def _build_prompt(monthly_summaries: list[dict]) -> str:
    return f"""You are a personal finance analyst. Here is a user's spending
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


def _parse_json_response(text: str) -> dict:
    """Small open models sometimes wrap JSON in a markdown code fence
    despite instructions not to; strip that before parsing, and fall back
    to extracting the first {...} block if there's still leading/trailing
    chatter."""
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _generate_with_claude(prompt: str) -> dict:
    api_key = os.environ["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_response(response.content[0].text)


def _generate_with_ollama(prompt: str) -> dict:
    try:
        client = ollama.Client(host=OLLAMA_URL)
        response = client.generate(model=OLLAMA_MODEL, prompt=prompt, stream=False)
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"local model unreachable at {OLLAMA_URL} -- is `ollama serve` running?"
        ) from exc
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            raise RuntimeError(f"local model '{OLLAMA_MODEL}' not pulled -- run `ollama pull {OLLAMA_MODEL}`") from exc
        raise
    return _parse_json_response(response["response"])


def generate_insights(monthly_summaries: list[dict]) -> dict:
    """
    monthly_summaries: list of dicts shaped like MonthlySummary, most recent last.
    Returns {"narrative": str, "flagged_anomalies": list[str]}.
    """
    prompt = _build_prompt(monthly_summaries)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _generate_with_claude(prompt)
    return _generate_with_ollama(prompt)

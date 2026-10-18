# Design: pluggable /insights backend (local model + Claude)

## Problem

`/insights` hard-required `ANTHROPIC_API_KEY`. With no key set, the whole
feature was unusable -- there was no free/local path, unlike every other
tier in the categorization pipeline.

## Decision

Make the LLM-reasoning tier itself pluggable, the same cost-aware-routing
idea `categorizer.py` already uses for tiers 1-2, extended one level
further:

- **Default: a local model via Ollama** (`qwen2.5:3b-instruct`), zero
  cost, no API key required. This is what runs whenever
  `ANTHROPIC_API_KEY` is unset.
- **Opt-in upgrade: Claude**, used automatically when
  `ANTHROPIC_API_KEY` *is* set. Better reasoning and narrative quality,
  paid per call.

This isn't "replace Claude with a local model" -- it's extending the same
tiering logic the rest of the app already argues for: route to the free
option by default, let the paid option be a deliberate choice rather than
a hard requirement.

## Why Qwen2.5 3B, why Ollama

This machine is an 8GB Apple M2, and was already under real memory
pressure before this change (`memory_pressure`/`top` showed <100MB
actually free, with the Podman VM alone reserving 3.8GB for Mongo --
shrunk to 1.5GB as part of this work to make room). That rules out
anything in the 7B+ class without swapping heavily.

- **Ollama** handles Apple Silicon (Metal) acceleration with zero
  configuration, exposes a simple local HTTP API
  (`http://localhost:11434`), and makes model management (`ollama pull`,
  `ollama list`) a one-line operation -- the practical reason to use it
  over loading weights directly via `transformers`/`torch` (already a
  deadweight-heavy dependency pair in this project, see
  `docs/design-sqlite-persistence.md`'s HF-tier context).
- **Qwen2.5 3B Instruct** (~2GB at the default Q4 quantization Ollama
  pulls) was chosen over Llama 3.2 3B primarily because Qwen2.5 has a
  stronger track record of reliably honoring "respond with only this
  JSON" instructions at small sizes -- `generate_insights()` does a raw
  `json.loads()` on the model's output with no repair/retry logic, so a
  model that wraps responses in markdown fences or chatty preamble breaks
  the contract outright. A smaller model (Llama 3.2 1B, ~800MB) would
  leave more memory headroom but produce a visibly weaker narrative and
  shakier JSON formatting -- not worth it until this model actually
  proves to be too heavy in practice.

## What changed

- `backend/insights.py`: `generate_insights()` is now a dispatcher --
  calls `_generate_with_claude()` if `ANTHROPIC_API_KEY` is set, else
  `_generate_with_ollama()`. Both return the same
  `{"narrative": str, "flagged_anomalies": list[str]}` shape, so nothing
  downstream (the `/insights` endpoint, the frontend) needed to change.
- `backend/main.py`'s `/insights` error handling gained a case for Ollama
  being unreachable (connection refused -- the server isn't running) in
  addition to the existing Claude-specific cases.
- `OLLAMA_MODEL` (default `qwen2.5:3b-instruct`) and `OLLAMA_URL` (default
  `http://localhost:11434`) are environment variables, same convention as
  `ANTHROPIC_API_KEY` and `MONGODB_URI` -- never hardcoded.

## Failure mode

If Ollama isn't running and no `ANTHROPIC_API_KEY` is set, `/insights`
returns a clear 503 naming the problem ("local model unreachable --
is `ollama serve` running?") rather than a bare connection-refused
traceback -- same fail-loud-with-a-clear-message philosophy as the rest
of this app's error handling.

## What this doesn't solve

No automatic fallback from Claude to local (or vice versa) if the chosen
backend fails mid-request -- a transient Claude API error won't silently
retry against the local model. No evaluation harness comparing narrative
quality between the two backends. Both are reasonable next steps, not
done here.

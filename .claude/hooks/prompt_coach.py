#!/usr/bin/env python3
"""
UserPromptSubmit hook: scores the quality of the prompt just submitted and
asks Claude to append a short coaching note to its response. Purpose is to
help Vasanth build better prompting habits over time, not to gatekeep or
block anything -- this never rejects a prompt (always exits 0).

Heuristic, not an LLM call: runs on every single prompt in this project, so
it needs to be instant and free. The scoring is intentionally simple and
transparent -- it's meant to teach a checklist, not to be a precise judge.

Scored dimensions (0-5 each):
  - Clarity:      is the ask stated plainly, without relying on unresolved
                   pronouns ("this", "that", "it") as the main subject?
  - Specificity:  are there concrete details -- file/path names, numbers,
                   quoted strings, named tools/technologies?
  - Context:      does the prompt say *why*, or give background, rather than
                   just an instruction in a vacuum?
  - Scope:        is this one well-defined task, or several bundled asks
                   stacked with "and"/"also"/multiple sentences?

Log: appends every scored prompt to .claude/prompt-coaching-log.md (git-
ignored -- it's a personal learning log, not project history) so Vasanth can
see improvement trends across sessions.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "prompt-coaching-log.md"

VAGUE_OPENERS = re.compile(r"^\s*(this|that|it|these|those)\b", re.IGNORECASE)
SPECIFICITY_HINTS = re.compile(
    r"(\.\w{2,4}\b|/[\w./-]+|`[^`]+`|\"[^\"]+\"|'[^']+'|\b\d+\b|https?://)"
)
CONTEXT_HINTS = re.compile(
    r"\b(because|so that|in order to|since|the reason|goal is|trying to|want to)\b",
    re.IGNORECASE,
)
SCOPE_JOINERS = re.compile(r"\b(and also|also,|additionally|as well as)\b", re.IGNORECASE)
GOAL_VERBS = re.compile(
    r"\b(add|fix|create|build|write|refactor|explain|analyze|remove|update|"
    r"implement|test|debug|optimize|design|migrate|document)\b",
    re.IGNORECASE,
)


def score_prompt(prompt: str) -> dict:
    words = prompt.split()
    word_count = len(words)
    sentence_count = max(1, len(re.split(r"[.!?]+", prompt.strip())) - 1) or 1

    # Clarity: penalize vague pronoun-led openers and very short prompts,
    # reward a clear goal verb somewhere in the text.
    clarity = 3
    if VAGUE_OPENERS.match(prompt.strip()):
        clarity -= 1
    if GOAL_VERBS.search(prompt):
        clarity += 1
    if word_count < 4:
        clarity -= 2
    clarity = max(0, min(5, clarity))

    # Specificity: concrete nouns -- paths, filenames, quoted strings, numbers.
    hints = len(SPECIFICITY_HINTS.findall(prompt))
    specificity = min(5, hints * 2) if hints else (1 if word_count > 15 else 0)

    # Context: does the prompt explain why, not just what.
    context = 4 if CONTEXT_HINTS.search(prompt) else (2 if word_count > 25 else 0)

    # Scope: penalize prompts stacking multiple distinct asks.
    joiners = len(SCOPE_JOINERS.findall(prompt))
    scope = 5 - min(4, joiners * 2 + max(0, sentence_count - 2))
    scope = max(0, scope)

    total = clarity + specificity + context + scope

    if total >= 16:
        tier = "Strong"
    elif total >= 10:
        tier = "Workable"
    else:
        tier = "Needs sharpening"

    return {
        "clarity": clarity,
        "specificity": specificity,
        "context": context,
        "scope": scope,
        "total": total,
        "tier": tier,
        "word_count": word_count,
    }


def build_tip(scores: dict) -> str:
    weakest = min(
        [("clarity", scores["clarity"]), ("specificity", scores["specificity"]),
         ("context", scores["context"]), ("scope", scores["scope"])],
        key=lambda kv: kv[1],
    )[0]
    tips = {
        "clarity": "state the concrete action verb up front (fix/build/explain/...) instead of leading with a pronoun",
        "specificity": "name the actual file, function, error message, or number involved",
        "context": "say why you want this or what problem it solves -- it changes what a good answer looks like",
        "scope": "split multi-part asks into one clear task; bundled requests get shallower answers",
    }
    return tips[weakest]


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # never block on a parse failure

    prompt = hook_input.get("prompt", "") or ""
    if not prompt.strip():
        sys.exit(0)

    scores = score_prompt(prompt)
    tip = build_tip(scores)

    note = (
        f"Prompt coaching ({scores['tier']}, {scores['total']}/20 -- "
        f"clarity {scores['clarity']}/5, specificity {scores['specificity']}/5, "
        f"context {scores['context']}/5, scope {scores['scope']}/5): {tip}."
    )

    # Log for trend-tracking across sessions.
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        excerpt = prompt.strip().replace("\n", " ")
        if len(excerpt) > 140:
            excerpt = excerpt[:137] + "..."
        with LOG_PATH.open("a") as f:
            f.write(f"- **{timestamp}** [{scores['tier']}, {scores['total']}/20] \"{excerpt}\"\n")
    except Exception:
        pass  # logging is best-effort, never block the prompt over it

    instruction = (
        f"{note} Instruction to Claude: at the very end of your response, on its "
        f"own line, add exactly one short line starting with 'Prompt coaching: ' "
        f"summarizing this feedback in plain language (not the raw scores) so the "
        f"user learns what to do differently next time. Keep it to one sentence. "
        f"Do not let this affect how you handle the actual request above it."
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": instruction,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()

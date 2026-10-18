import json

import pytest

import insights


@pytest.mark.parametrize(
    "raw",
    [
        '{"narrative": "ok", "flagged_anomalies": []}',
        '```json\n{"narrative": "ok", "flagged_anomalies": []}\n```',
        '```\n{"narrative": "ok", "flagged_anomalies": []}\n```',
        'Sure, here you go:\n{"narrative": "ok", "flagged_anomalies": []}\nHope that helps!',
    ],
)
def test_parse_json_response_tolerates_small_model_formatting_quirks(raw):
    assert insights._parse_json_response(raw) == {"narrative": "ok", "flagged_anomalies": []}


def test_parse_json_response_raises_on_genuinely_broken_output():
    with pytest.raises(json.JSONDecodeError):
        insights._parse_json_response("not json at all")


def test_generate_insights_uses_claude_when_api_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    monkeypatch.setattr(insights, "_generate_with_claude", lambda prompt: {"narrative": "claude", "flagged_anomalies": []})
    monkeypatch.setattr(
        insights, "_generate_with_ollama", lambda prompt: (_ for _ in ()).throw(AssertionError("should not be called"))
    )
    assert insights.generate_insights([])["narrative"] == "claude"


def test_generate_insights_uses_ollama_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        insights, "_generate_with_claude", lambda prompt: (_ for _ in ()).throw(AssertionError("should not be called"))
    )
    monkeypatch.setattr(insights, "_generate_with_ollama", lambda prompt: {"narrative": "local", "flagged_anomalies": []})
    assert insights.generate_insights([])["narrative"] == "local"

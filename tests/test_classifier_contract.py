"""Contract tests — no network, mock path only."""

from model_regression_detection.classifier import classify_email, load_prompt, mock_classify


def test_prompt_loads_and_hashes():
    p = load_prompt("v1")
    assert p.version == "v1"
    assert len(p.sha256) == 12
    assert "billing" in p.text


def test_mock_categories():
    assert mock_classify("My invoice shows a double charge, please refund").category == "billing"
    assert mock_classify("App crashes with 500 error on login").category == "technical"
    assert mock_classify("Please reset my password and delete my profile").category == "account"
    assert mock_classify("Just saying hi, love your product!").category == "general"


def test_classify_falls_back_to_mock_without_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    out = classify_email("Invoice charge looks wrong", prompt_version="v1")
    assert out.mocked is True
    assert out.category == "billing"
    assert out.prompt_version == "v1"


def test_output_contract(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    out = classify_email("Hello, quick question about your pricing page?", prompt_version="v1")
    assert out.category in ("billing", "technical", "account", "general")
    assert 1 <= len(out.summary) <= 500

"""Judge + Slack-gate tests — no network."""

import pytest

from model_regression_detection.classifier import judge_summary
from model_regression_detection.slack import maybe_post


def test_judge_empty_must_convey_needs_no_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert judge_summary("any email", "general", [], "any summary") is True


def test_judge_raises_without_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        judge_summary("email", "billing", ["refund"], "summary")


def test_mocked_run_never_posts(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/FAKE")
    assert maybe_post({"text": "hi"}, mocked=True) is False


def test_no_url_no_post(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    assert maybe_post({"text": "hi"}, mocked=False) is False


def test_category_only_skips_judge(monkeypatch):
    from model_regression_detection import eval as eval_mod
    from model_regression_detection.classifier import ClassifiedEmail

    monkeypatch.setenv("LLM_API_KEY", "fake")
    monkeypatch.setattr(
        eval_mod,
        "classify_email",
        lambda *a, **k: ClassifiedEmail(
            category="general",
            summary="hi there",
            model="m",
            prompt_version="v1",
            prompt_sha="abc",
            latency_ms=1,
            mocked=False,
        ),
    )

    def _boom(*a, **k):
        raise AssertionError("judge must not be called for empty must_convey")

    monkeypatch.setattr(eval_mod, "judge_summary", _boom)
    score = eval_mod._run_one(
        {
            "id": "x",
            "input": "hi",
            "expected_tag": "general",
            "expected_summary_contains": [],
            "notes": "",
        },
        "v1",
        None,
    )
    assert score.summary_method == "category-only"
    assert score.passed is True

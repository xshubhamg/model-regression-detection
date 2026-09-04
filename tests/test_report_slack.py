"""Report + Slack payload tests — no network."""

from model_regression_detection.report import write_report
from model_regression_detection.slack import build_payload


def _result(**over):
    base = {
        "prompt_version": "v1",
        "model": "m",
        "ts": "2026-09-04T00:00:00+00:00",
        "pass_rate": 1.0,
        "passed": 2,
        "total": 2,
        "avg_latency_ms": 10,
        "by_category": {"billing": {"total": 2, "passed": 2}},
        "baseline": 1.0,
        "regression": False,
        "drift": False,
        "moving_avg": 0.98,
        "drift_window": 7,
        "drift_runs": 7,
        "flipped": [],
        "scores": [],
    }
    base.update(over)
    return base


def test_payload_drift_states():
    assert "No drift" in build_payload(_result())["blocks"][1]["text"]["text"]
    assert (
        "DRIFT DETECTED"
        in build_payload(_result(drift=True, moving_avg=0.8))["blocks"][1]["text"]["text"]
    )
    assert (
        "Warming up"
        in build_payload(_result(moving_avg=None, drift_runs=3))["blocks"][1]["text"]["text"]
    )
    assert "REGRESSION DETECTED" in build_payload(_result(regression=True))["text"]


def test_report_contains_banner_and_drift(tmp_path):
    out = write_report(_result(), out=tmp_path / "r.html")
    page = out.read_text(encoding="utf-8")
    assert "PASS — no regression" in page
    assert "Drift: no drift" in page
    out = write_report(_result(moving_avg=None, drift_runs=2), out=tmp_path / "r2.html")
    assert "warming up (2/7 live runs)" in out.read_text(encoding="utf-8")

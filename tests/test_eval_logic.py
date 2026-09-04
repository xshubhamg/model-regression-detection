"""Eval scoring logic — pure functions, no network."""

from model_regression_detection.eval import score_case


def test_score_exact_and_contains():
    assert score_case("billing", "billing", "refund for invoice #42", ["refund", "invoice"]) == (
        True,
        True,
    )
    assert score_case("billing", "technical", "refund for invoice", ["refund"]) == (False, True)
    assert score_case("billing", "billing", "user says hi", ["refund"]) == (True, False)


def test_regression_rule():
    from model_regression_detection.eval import is_regression

    assert is_regression(0.85, 1.0) is True  # drop > 5%
    assert is_regression(0.80, None) is True  # below 90% with no baseline
    assert is_regression(0.97, 1.0) is False
    assert is_regression(0.96, 0.97) is False

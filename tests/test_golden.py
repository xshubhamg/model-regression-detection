"""Golden-dataset contract: schema, coverage, and mock-compatibility.

Mock-compatibility is the load-bearing test: every case must pass the
deterministic keyword scorer via the mock classifier, so keyless CI stays
green and only live runs can fail on quality.
"""

from collections import Counter

from model_regression_detection.classifier import mock_classify
from model_regression_detection.eval import GOLDEN_PATH, load_golden, score_case

VALID_TAGS = {"billing", "technical", "account", "general"}


def _rows():
    return load_golden(GOLDEN_PATH)


def test_schema_valid():
    for r in _rows():
        assert r["id"] and isinstance(r["input"], str) and r["input"].strip()
        assert r["expected_tag"] in VALID_TAGS
        assert isinstance(r.get("expected_summary_contains", []), list)
        assert isinstance(r.get("notes", ""), str)


def test_ids_unique():
    rows = _rows()
    assert len({r["id"] for r in rows}) == len(rows)


def test_category_coverage():
    counts = Counter(r["expected_tag"] for r in _rows())
    for tag in VALID_TAGS:
        assert counts[tag] >= 10, f"{tag} has only {counts[tag]} cases"


def test_edge_coverage():
    edges = [r for r in _rows() if "edge:" in r.get("notes", "")]
    assert len(edges) >= 15
    assert any("typo" in r["notes"] for r in edges)
    assert any("sarcasm" in r["notes"] for r in edges)
    assert any("multi-intent" in r["notes"] for r in edges)


def test_mock_compatible():
    bad = []
    for r in _rows():
        m = mock_classify(r["input"])
        cat_ok, sum_ok = score_case(
            r["expected_tag"],
            m.category,
            f"{m.category}: {r['input'][:120]}",
            r["expected_summary_contains"],
        )
        if not (cat_ok and sum_ok):
            bad.append(r["id"])
    assert not bad, f"cases failing mock scoring (keyless CI would go red): {bad}"

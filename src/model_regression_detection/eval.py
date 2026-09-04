"""Evaluation engine: golden set -> LLM -> scores -> SQLite -> regression verdict."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from model_regression_detection.classifier import classify_email, judge_summary

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "golden" / "golden.jsonl"


@dataclass
class CaseScore:
    id: str
    expected_tag: str
    predicted_tag: str
    category_ok: bool
    summary_ok: bool
    passed: bool
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    model: str
    prompt_version: str
    expected_summary_contains: list
    predicted_summary: str
    notes: str
    mocked: bool = False
    summary_method: str = "keyword"


def score_case(
    expected_tag: str, predicted_tag: str, summary: str, must_contain: list[str]
) -> tuple[bool, bool]:
    cat_ok = expected_tag.strip().lower() == predicted_tag.strip().lower()
    slow = summary.lower()
    sum_ok = all(k.lower() in slow for k in (must_contain or []))
    return cat_ok, sum_ok


def is_regression(
    pass_rate: float, baseline: float | None, *, threshold: float = 0.90, max_drop: float = 0.05
) -> bool:
    if pass_rate < threshold:
        return True
    return baseline is not None and (baseline - pass_rate) > max_drop


def load_golden(path: Path = GOLDEN_PATH) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _run_one(row: dict, prompt_version: str, model: str | None) -> CaseScore:
    out = classify_email(row["input"], prompt_version=prompt_version, model=model)
    must_convey = row.get("expected_summary_contains", [])
    cat_ok = row["expected_tag"].strip().lower() == out.category.strip().lower()
    if out.mocked:
        # No key: cheap deterministic keyword check keeps tests + CI free.
        _, sum_ok = score_case(row["expected_tag"], out.category, out.summary, must_convey)
        method = "keyword"
    elif not must_convey:
        # Category-only case (e.g. sarcasm): nothing to judge, no LLM call spent.
        sum_ok = True
        method = "category-only"
    else:
        try:
            sum_ok = judge_summary(
                row["input"], row["expected_tag"], must_convey, out.summary, model=model
            )
            method = "judge"
        except Exception:  # noqa: BLE001 — judge is best-effort; any failure falls back
            _, sum_ok = score_case(row["expected_tag"], out.category, out.summary, must_convey)
            method = "keyword-fallback"
    return CaseScore(
        id=row["id"],
        expected_tag=row["expected_tag"],
        predicted_tag=out.category,
        category_ok=cat_ok,
        summary_ok=sum_ok,
        passed=bool(cat_ok and sum_ok),
        latency_ms=out.latency_ms,
        prompt_tokens=out.prompt_tokens,
        completion_tokens=out.completion_tokens,
        model=out.model,
        prompt_version=out.prompt_version,
        expected_summary_contains=must_convey,
        predicted_summary=out.summary,
        notes=row.get("notes", ""),
        mocked=out.mocked,
        summary_method=method,
    )


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, prompt_version TEXT,
        model TEXT, pass_rate REAL, total INTEGER, passed INTEGER, regression INTEGER)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS results(
        run_id INTEGER, case_id TEXT, expected TEXT, predicted TEXT,
        passed INTEGER, latency_ms INTEGER, summary TEXT)"""
    )
    return conn


def run_eval(
    prompt_version: str = "v1",
    model: str | None = None,
    db_path: Path | None = None,
    baseline_path: Path | None = None,
    workers: int = 8,
) -> dict:
    import os

    model = model or os.getenv("LLM_MODEL", "z-ai/glm-5.3-flash")
    db_path = db_path or Path(os.getenv("RESULTS_DB", str(ROOT / "results.db")))
    baseline_path = baseline_path or (ROOT / "baseline.json")

    rows = load_golden()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        scores = list(ex.map(lambda r: _run_one(r, prompt_version, model), rows))

    total = len(scores)
    passed = sum(1 for s in scores if s.passed)
    pass_rate = passed / total if total else 0.0
    avg_latency = sum(s.latency_ms for s in scores) / total if total else 0
    by_cat: dict[str, dict] = {}
    for s in scores:
        d = by_cat.setdefault(s.expected_tag, {"total": 0, "passed": 0})
        d["total"] += 1
        d["passed"] += int(s.passed)
    flipped = [s for s in scores if not s.passed]

    baseline: float | None = None
    if baseline_path.exists():
        try:
            baseline = float(json.loads(baseline_path.read_text()).get("pass_rate", 0))
        except (OSError, ValueError, KeyError):
            baseline = None

    import os as _os

    regression = is_regression(
        pass_rate,
        baseline,
        threshold=float(_os.getenv("PASS_THRESHOLD", "0.90")),
        max_drop=float(_os.getenv("MAX_DROP_VS_BASELINE", "0.05")),
    )

    ts = dt.datetime.now(dt.UTC).isoformat()
    conn = init_db(db_path)
    cur = conn.execute(
        "INSERT INTO runs(ts,prompt_version,model,pass_rate,total,passed,regression) VALUES(?,?,?,?,?,?,?)",
        (ts, prompt_version, model, pass_rate, total, passed, int(regression)),
    )
    run_id = cur.lastrowid or 0
    for s in scores:
        conn.execute(
            "INSERT INTO results(run_id,case_id,expected,predicted,passed,latency_ms,summary) VALUES(?,?,?,?,?,?,?)",
            (
                run_id,
                s.id,
                s.expected_tag,
                s.predicted_tag,
                int(s.passed),
                s.latency_ms,
                s.predicted_summary,
            ),
        )
    conn.commit()
    conn.close()

    return {
        "run_id": run_id,
        "ts": ts,
        "prompt_version": prompt_version,
        "model": model,
        "pass_rate": pass_rate,
        "passed": passed,
        "total": total,
        "avg_latency_ms": avg_latency,
        "by_category": by_cat,
        "baseline": baseline,
        "regression": regression,
        "flipped": [asdict(s) for s in flipped],
        "scores": [asdict(s) for s in scores],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run golden-set regression eval")
    ap.add_argument("--prompt", default="v1")
    ap.add_argument("--model", default=None)
    ap.add_argument("--save-baseline", action="store_true", help="write this run as baseline.json")
    ap.add_argument("--json-out", default="last_run.json")
    args = ap.parse_args()

    result = run_eval(prompt_version=args.prompt, model=args.model)
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"[{result['prompt_version']}/{result['model']}] "
        f"pass {result['passed']}/{result['total']} = {result['pass_rate']:.1%} "
        f"(baseline={result['baseline']}) regression={result['regression']}"
    )
    for f in result["flipped"]:
        print(
            f"  FLIP {f['id']}: expected={f['expected_tag']} got={f['predicted_tag']} | {f['predicted_summary'][:100]}"
        )

    if args.save_baseline:
        (ROOT / "baseline.json").write_text(
            json.dumps(
                {
                    "pass_rate": result["pass_rate"],
                    "prompt_version": result["prompt_version"],
                    "model": result["model"],
                }
            ),
            encoding="utf-8",
        )
        print("saved baseline.json")

    # keep HTML + slack in sync
    from model_regression_detection.report import write_report
    from model_regression_detection.slack import build_payload, maybe_post

    write_report(result)
    payload = build_payload(result)
    Path("slack_payload.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    mocked_run = all(s.get("mocked", False) for s in result["scores"])
    maybe_post(payload, mocked=mocked_run)
    return 2 if result["regression"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

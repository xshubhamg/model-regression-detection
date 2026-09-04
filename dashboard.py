"""Observability dashboard for learning: run history, drift, flips, latency, golden set.

Run:  uv run streamlit run dashboard.py
Reads the local results.db + last_run.json produced by the eval pipeline.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "results.db"
LAST_RUN = ROOT / "last_run.json"
GOLDEN_PATH = ROOT / "golden" / "golden.jsonl"


def load_runs() -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, ts, prompt_version, model, pass_rate, total, passed, regression"
            " FROM runs ORDER BY id"
        ).fetchall()
    except sqlite3.OperationalError:  # brand-new DB without tables yet
        return []
    finally:
        conn.close()
    return [dict(r) for r in rows]


def load_last_run() -> dict | None:
    if not LAST_RUN.exists():
        return None
    return json.loads(LAST_RUN.read_text(encoding="utf-8"))


def load_golden() -> list[dict]:
    if not GOLDEN_PATH.exists():
        return []
    return [
        json.loads(line)
        for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


st.set_page_config(page_title="Model Regression Dashboard", layout="wide")
st.title("Model Regression Detection — Observability")

runs = load_runs()
last = load_last_run()

if not runs and last is None:
    st.info(
        "No data yet. Run `uv run python -m model_regression_detection.eval --prompt v1` first."
    )
    st.stop()

tab_trend, tab_latest, tab_golden, tab_how = st.tabs(
    ["Trend & drift", "Latest run", "Golden set", "How it works"]
)

with tab_trend:
    st.subheader("Pass rate over runs")
    if runs:
        st.line_chart(
            [{"run": r["id"], "pass_rate": r["pass_rate"]} for r in runs],
            x="run",
            y="pass_rate",
        )
        st.dataframe(
            [
                {
                    "run": r["id"],
                    "time": r["ts"][:19],
                    "prompt": r["prompt_version"],
                    "model": r["model"],
                    "score": f"{r['passed']}/{r['total']}",
                    "regression": bool(r["regression"]),
                }
                for r in runs
            ],
            width="stretch",
        )
    else:
        st.info("No run history in results.db yet.")
    if last is not None:
        if last.get("moving_avg") is None:
            st.warning(
                f"Drift warming up: {last.get('drift_runs', 0)}/{last.get('drift_window', 7)} live runs."
            )
        elif last.get("drift"):
            st.error(f"Slow drift DETECTED — 7-run avg {last['moving_avg']:.1%}.")
        else:
            st.success(f"No slow drift — 7-run avg {last['moving_avg']:.1%}.")

with tab_latest:
    st.subheader("Latest run detail")
    if last is None:
        st.info("No last_run.json yet.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score", f"{last['passed']}/{last['total']}", f"{last['pass_rate']:.1%}")
        c2.metric(
            "Baseline",
            f"{last['baseline']:.1%}" if last["baseline"] is not None else "n/a",
        )
        c3.metric("Avg latency", f"{last['avg_latency_ms']:.0f} ms")
        c4.metric("Regression", str(last["regression"]))
        st.caption(f"prompt `{last['prompt_version']}` · model `{last['model']}` · {last['ts']}")
        st.subheader("Pass by expected category")
        st.bar_chart(
            {k: v["passed"] / v["total"] for k, v in last["by_category"].items()},
        )
        st.subheader("Flipped cases (failures to triage)")
        if last["flipped"]:
            st.dataframe(
                [
                    {
                        "id": f["id"],
                        "expected": f["expected_tag"],
                        "predicted": f["predicted_tag"],
                        "method": f.get("summary_method", "?"),
                        "summary": f["predicted_summary"][:160],
                        "notes": f.get("notes", ""),
                    }
                    for f in last["flipped"]
                ],
                width="stretch",
            )
        else:
            st.success("No flips — every golden case passed.")
        st.subheader("Latency per case (spot perf outliers)")
        st.bar_chart({s["id"]: s["latency_ms"] for s in last["scores"]})

with tab_golden:
    st.subheader("Golden dataset (hand-labeled ground truth)")
    golden = load_golden()
    st.caption(
        f"{len(golden)} cases. Edge cases carry an `edge:` note — they are the interview story."
    )
    st.dataframe(
        [
            {
                "id": g["id"],
                "expected": g["expected_tag"],
                "key points": ", ".join(g.get("expected_summary_contains", []))
                or "(category only)",
                "notes": g.get("notes", ""),
                "input": g["input"][:140],
            }
            for g in golden
        ],
        width="stretch",
    )

with tab_how:
    st.subheader("Pipeline in one minute")
    st.markdown(
        """
1. **Classify** — one email through the versioned prompt (`prompts/v1.txt`, hashed) via an
   OpenAI-compatible model, strict JSON `{category, summary}`.
2. **Score** — category exact-match (deterministic) + LLM-as-judge on whether the summary
   conveys the case's key points (paraphrase-proof; keyword fallback offline).
3. **Gate** — flag regression if `pass_rate < 90%` or drop-vs-baseline `> 5%`; flag slow drift
   if the 7-run live average sags below 90%.
4. **Alert** — HTML report + Slack payload; mocked runs never post.
5. **Learn** — eval quality is bounded by data quality: most historical flips were rubric
   wording, not model errors. The golden set *is* the product.
        """
    )

# Model Regression Detection System

CI/CD-style pipeline that tests any LLM feature against a golden dataset whenever the prompt or model changes, detects quality regressions, and alerts via Slack before bad outputs ship.

## Why this matters
Eval quality is bounded by data quality. This repo versions prompts like code, hand-labels a golden set with edge cases (typos, sarcasm, mixed-language, multi-intent), and blocks regressions statistically — the workflow hiring teams use post-deploy.

## Quickstart
```bash
uv sync
cp .env.example .env   # add LLM_API_KEY to hit a real model; without it, mock runs
uv run pytest -q
uv run ruff check src tests
uv run python -m model_regression_detection.eval --prompt v1 --save-baseline
# degrade test: --prompt v2-degraded must flag regression (exit 2)
uv run python -m model_regression_detection.eval --prompt v2-degraded
open report.html
```

## How to add cases
Append JSONL to `golden/golden.jsonl`:
```json
{"id":"b7","input":"...","expected_tag":"billing","expected_summary_contains":["refund"],"notes":"...","version":"1"}
```

## How to tune thresholds
Env: `PASS_THRESHOLD=0.90`, `MAX_DROP_VS_BASELINE=0.05`. Regression if `pass_rate < threshold OR (baseline - pass_rate) > max_drop`.

## Slow-drift detection
Beyond per-run gates, the pipeline tracks a moving average over the last `DRIFT_WINDOW=7` **live** runs (mocked runs excluded) from SQLite. If the average drops below `DRIFT_THRESHOLD=0.90`, the run is flagged `drift`, appears in `report.html` and Slack, and fails CI (exit 2) — catching gradual decay no single run would trip. Fewer than 7 live runs reports "warming up".

## Swap model (no code change)
```bash
LLM_BASE_URL=https://openrouter.ai/api/v1 LLM_MODEL=z-ai/glm-5.3-flash
# swap models with one var, e.g. LLM_MODEL=deepseek/deepseek-chat
```

## How summary scoring works
Categories use exact match (deterministic). Summaries use **LLM-as-judge** on live runs: the model checks whether the summary conveys the case's key points, so paraphrase ("deletion" vs "delete") passes. Without an API key, mock runs fall back to keyword-contains (free, deterministic) — mocks prove plumbing, only live runs prove quality. Empty key-point lists (e.g. sarcasm) are category-only checks with no judge call spent.

## Slack
Set `SLACK_WEBHOOK_URL` to post; otherwise `slack_payload.json` is written for inspection. Mocked runs never post (no channel spam from keyless CI).

## Architecture decisions
- Custom scorer (exact category + LLM-judge summaries) over RAGAS/DeepEval: paraphrase-robust, one stack, judge falls back to keywords on errors.
- `golden.jsonl` human-editable + mirrored to SQLite `runs`/`results` for history.
- `v2-degraded.txt` intentionally vague to demo a caught regression in CI.

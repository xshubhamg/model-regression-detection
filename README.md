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

## Swap model/provider (no code change)
```bash
LLM_BASE_URL=https://openrouter.ai/api/v1 LLM_MODEL=openai/gpt-4o-mini
# CommandCode Provider API needs Provider plan+ (Go plan gets 403 on chat):
LLM_BASE_URL=https://api.commandcode.ai/provider/v1 LLM_MODEL=deepseek/deepseek-v4-flash
```

## Slack
Set `SLACK_WEBHOOK_URL` to post; otherwise `slack_payload.json` is written for inspection.

## Architecture decisions
- Custom scorer (exact category + summary contains) over RAGAS/DeepEval today: deterministic, $0, no network.
- `golden.jsonl` human-editable + mirrored to SQLite `runs`/`results` for history.
- `v2-degraded.txt` intentionally vague to demo a caught regression in CI.

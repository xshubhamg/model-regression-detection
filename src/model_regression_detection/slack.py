"""Slack alerting — always builds payload, posts only when webhook is set."""

from __future__ import annotations

import os


def build_payload(result: dict) -> dict:
    status = (
        ":rotating_light: *REGRESSION DETECTED*"
        if result["regression"]
        else ":white_check_mark: *No regression*"
    )
    flips = (
        "\n".join(
            f"• `{f['id']}` expected `{f['expected_tag']}` got `{f['predicted_tag']}`"
            for f in result["flipped"][:10]
        )
        or "None — all cases passed."
    )
    base = f"{result['baseline']:.1%}" if result["baseline"] is not None else "n/a"
    return {
        "text": f"{status} — {result['prompt_version']}/{result['model']}: "
        f"{result['passed']}/{result['total']} = {result['pass_rate']:.1%} (baseline {base})",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": status}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Prompt:* `{result['prompt_version']}`\n*Model:* `{result['model']}`\n"
                    f"*Score:* {result['passed']}/{result['total']} = {result['pass_rate']:.1%} (baseline {base})\n"
                    f"*Flips ({len(result['flipped'])}):*\n{flips}",
                },
            },
        ],
    }


def maybe_post(payload: dict, mocked: bool = False) -> bool:
    url = os.getenv("SLACK_WEBHOOK_URL", "")
    if mocked:
        print("mocked run — skipping Slack post, payload in slack_payload.json.")
        return False
    if not url:
        print("SLACK_WEBHOOK_URL not set — wrote slack_payload.json only.")
        return False
    import requests

    r = requests.post(url, json=payload, timeout=15)
    print(f"slack post -> {r.status_code}")
    return r.ok

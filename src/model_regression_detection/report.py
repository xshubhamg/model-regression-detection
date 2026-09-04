"""HTML report builder."""

from __future__ import annotations

import html
from pathlib import Path


def write_report(result: dict, out: Path | None = None) -> Path:
    out = out or (Path(__file__).resolve().parents[2] / "report.html")
    rows = "".join(
        f"<tr><td>{html.escape(s['id'])}</td><td>{html.escape(s['expected_tag'])}</td>"
        f"<td>{html.escape(s['predicted_tag'])}</td><td>{'PASS' if s['passed'] else 'FAIL'}</td>"
        f"<td>{html.escape(s['predicted_summary'][:160])}</td><td>{s['latency_ms']}ms</td></tr>"
        for s in result["scores"]
    )
    cats = "".join(
        f"<li><b>{html.escape(k)}</b>: {v['passed']}/{v['total']}</li>"
        for k, v in result["by_category"].items()
    )
    status = "REGRESSION DETECTED" if result["regression"] else "PASS — no regression"
    color = "#b3261e" if result["regression"] else "#146c2e"
    base = f"{result['baseline']:.1%}" if result["baseline"] is not None else "n/a"
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Model Regression Report — {html.escape(result["prompt_version"])}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}}
.banner{{padding:1rem;border-radius:8px;color:#fff;background:{color};font-weight:700}}
table{{border-collapse:collapse;width:100%;margin-top:1rem}}td,th{{border:1px solid #ddd;padding:6px;font-size:14px}}</style>
</head><body>
<h1>Model Regression Report</h1>
<div class="banner">{status}</div>
<p>prompt <b>{html.escape(result["prompt_version"])}</b> · model <b>{html.escape(result["model"])}</b> · {html.escape(result["ts"])}</p>
<p>score <b>{result["passed"]}/{result["total"]} = {result["pass_rate"]:.1%}</b> · baseline {base} · avg latency {result["avg_latency_ms"]:.0f}ms</p>
<h3>By category</h3><ul>{cats}</ul>
<h3>All cases</h3><table><tr><th>id</th><th>expected</th><th>predicted</th><th>verdict</th><th>summary</th><th>latency</th></tr>{rows}</table>
</body></html>"""
    out.write_text(page, encoding="utf-8")
    return out

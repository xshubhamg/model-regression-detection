"""LLM feature under test: email -> {category, summary}.

Single Python function with the prompt as a configurable parameter.
Pydantic-validated contract; mock fallback when no API key is set (tests/CI-safe).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["billing", "technical", "account", "general"]

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class ClassificationResult(BaseModel):
    category: Category
    summary: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True)
class PromptConfig:
    version: str
    text: str
    sha256: str


@dataclass
class ClassifiedEmail:
    category: str
    summary: str
    model: str
    prompt_version: str
    prompt_sha: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    mocked: bool = False


def load_prompt(version: str = "v1") -> PromptConfig:
    path = PROMPTS_DIR / f"{version}.txt"
    text = path.read_text(encoding="utf-8")
    sha = hashlib.sha256(text.encode()).hexdigest()[:12]
    return PromptConfig(version=version, text=text, sha256=sha)


def mock_classify(email_text: str) -> ClassificationResult:
    """Deterministic keyword heuristic — keeps tests + CI free of network/cost."""
    t = email_text.lower()
    if any(k in t for k in ("invoice", "bill", "charge", "refund", "payment", "receipt")):
        cat: Category = "billing"
    elif any(
        k in t
        for k in ("error", "bug", "crash", "timeout", "500", "stack trace", "login fail", "api")
    ):
        cat = "technical"
    elif any(
        k in t
        for k in (
            "password",
            "account",
            "signup",
            "sign up",
            "subscription",
            "plan",
            "profile",
            "delete my",
        )
    ):
        cat = "account"
    else:
        cat = "general"
    first = email_text.strip().split("\n")[0][:120]
    return ClassificationResult(category=cat, summary=f"{cat}: {first}")


def classify_email(
    email_text: str,
    prompt_version: str = "v1",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ClassifiedEmail:
    """Classify one email. Falls back to mock when no key is configured."""
    import os

    prompt = load_prompt(prompt_version)
    model = model or os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY", "")
    base_url = base_url or os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

    if not api_key:
        if prompt_version == "v2-degraded":
            # Simulate a vague-prompt regression: model hedges to general with empty summary.
            out = ClassificationResult(category="general", summary="ok")
        else:
            out = mock_classify(email_text)
        return ClassifiedEmail(
            category=out.category,
            summary=out.summary,
            model=f"{model} (mock)",
            prompt_version=prompt.version,
            prompt_sha=prompt.sha256,
            latency_ms=0,
            mocked=True,
        )

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    start = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": prompt.text},
            {"role": "user", "content": email_text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "email_classification",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["billing", "technical", "account", "general"],
                        },
                        "summary": {"type": "string"},
                    },
                    "required": ["category", "summary"],
                    "additionalProperties": False,
                },
            },
        },
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    raw = resp.choices[0].message.content or "{}"
    validated = ClassificationResult.model_validate(json.loads(raw))
    usage = resp.usage
    return ClassifiedEmail(
        category=validated.category,
        summary=validated.summary,
        model=model,
        prompt_version=prompt.version,
        prompt_sha=prompt.sha256,
        latency_ms=latency_ms,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        mocked=False,
    )

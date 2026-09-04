"""Central settings — provider-agnostic via env vars.

Point LLM_BASE_URL at any OpenAI-compatible endpoint and swap models
via LLM_MODEL without code changes. Primary: OpenRouter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "z-ai/glm-5.3-flash")
    prompt_version: str = os.getenv("PROMPT_VERSION", "v1")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    pass_threshold: float = float(os.getenv("PASS_THRESHOLD", "0.90"))
    max_drop_vs_baseline: float = float(os.getenv("MAX_DROP_VS_BASELINE", "0.05"))
    db_path: str = os.getenv("RESULTS_DB", "results.db")

    @property
    def has_llm_key(self) -> bool:
        return bool(self.llm_api_key)


def get_settings() -> Settings:
    return Settings()

"""Meta Model API configuration. One OpenAI-compatible client serves Muse Spark and SAM 3.1.

Reference (read 2026-10-27): dev.meta.ai/docs/structured-output, dev.meta.ai/docs/sam/segmenting.
The key is read from the environment (or backend/.env) and never logged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class MetaApiUnavailable(RuntimeError):
    """Raised instead of silently falling back to mocks or another provider."""


@dataclass(frozen=True)
class MetaSettings:
    api_key: str | None
    base_url: str
    muse_model: str
    sam_model: str
    budget_usd: float

    @classmethod
    def from_env(cls) -> MetaSettings:
        return cls(
            api_key=os.environ.get("MODEL_API_KEY") or None,
            base_url=os.environ.get("META_API_BASE_URL", "https://api.meta.ai/v1"),
            muse_model=os.environ.get("MUSE_MODEL", "muse-spark-1.3"),
            sam_model=os.environ.get("SAM_MODEL", "sam-3.1"),
            budget_usd=float(os.environ.get("META_BUDGET_USD", "40")),
        )


def get_client(settings: MetaSettings | None = None):
    from openai import OpenAI

    s = settings or MetaSettings.from_env()
    if not s.api_key:
        raise MetaApiUnavailable("MODEL_API_KEY is not set; live Meta calls are BLOCKED (see docs/PROGRESS.md)")
    return OpenAI(base_url=s.base_url, api_key=s.api_key)

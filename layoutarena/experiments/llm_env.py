"""Environment checks and helpers for LLM-driven experiments."""

from __future__ import annotations

import os
import re


def looks_like_llm_auth_failure(response: object) -> bool:
    """True if *response* is an exception or string indicating missing/invalid API credentials."""
    if response is None:
        return False
    if isinstance(response, BaseException):
        name = type(response).__name__
        if "Auth" in name:
            return True
    text = str(response)
    compact = re.sub(r"\s+", "", text.lower())
    if "authenticationerror" in compact:
        return True
    low = text.lower()
    if "api_key" in low and ("must be set" in low or "not set" in low):
        return True
    if "invalid api key" in low or "incorrect api key" in low:
        return True
    if "401" in text and "unauthor" in low:
        return True
    return False


def validate_llm_env_for_model(model: str) -> None:
    """Raise RuntimeError if required API keys for *model* are almost certainly missing.

    Best-effort heuristics only; custom and SageMaker routes are skipped.
    """
    m = model.strip().lower()
    if m.startswith("custom/") or m.startswith("sagemaker/"):
        return

    if m.startswith("anthropic/") or "claude" in m:
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to the environment or "
                "layout-hackathon/.env, or omit --model for scripted runs.",
            )
        return

    if "gemini" in m or m.startswith("google/"):
        if not (
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        ):
            raise RuntimeError(
                "GEMINI_API_KEY or GOOGLE_API_KEY is not set. Add it to the environment "
                "or layout-hackathon/.env, or omit --model for scripted runs.",
            )
        return

    if m.startswith("azure/"):
        return

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError(
            "OPENAI_API_KEY is not set. OpenAI-style models (e.g. gpt-4o-mini) need it in "
            "the environment or layout-hackathon/.env. Omit --model to use the scripted policy.",
        )

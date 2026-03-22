"""Tests for LLM environment preflight helpers."""
from __future__ import annotations

import os

import pytest

from layoutarena.experiments.llm_env import (
    looks_like_llm_auth_failure,
    validate_llm_env_for_model,
)


def test_looks_like_auth_from_exception_string():
    msg = (
        "litellm.AuthenticationError: OpenAIException - "
        "The api_key client option must be set"
    )
    assert looks_like_llm_auth_failure(msg)


def test_looks_like_auth_negative():
    assert not looks_like_llm_auth_failure('{"tool_name": "submit_layout"}')
    assert not looks_like_llm_auth_failure(None)


def test_validate_openai_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        validate_llm_env_for_model("gpt-4o-mini")


def test_validate_openai_passes_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    validate_llm_env_for_model("gpt-4o-mini")


def test_validate_skips_custom(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    validate_llm_env_for_model("custom/foo")

"""Elige el adapter: openai (defecto) u openrouter."""

from __future__ import annotations

import os

from adapter import LlmAdapter
from adapters.openai import OpenAIAdapter
from envutil import load_dotenv


def make_adapter() -> LlmAdapter:
    load_dotenv()
    kind = (
        os.environ.get("CORE_TALES_LLM") or os.environ.get("LLM") or "openai"
    ).strip().lower()
    if kind in ("openrouter", "or", "venice"):
        from adapters.openrouter import OpenRouterAdapter

        return OpenRouterAdapter()
    return OpenAIAdapter()


def adapter_label(llm: LlmAdapter) -> str:
    label = getattr(llm, "label", None)
    if isinstance(label, str) and label.strip():
        return label
    return type(llm).__name__

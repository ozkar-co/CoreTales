"""Elige el adapter. CORE_TALES_LLM=openai|llamacpp; si no, OpenAI si hay clave."""

from __future__ import annotations

import os

from adapter import LlmAdapter
from adapters.llamacpp import LlamaCppAdapter
from adapters.openai import OpenAIAdapter
from envutil import load_dotenv


def make_adapter() -> LlmAdapter:
    load_dotenv()
    kind = os.environ.get("CORE_TALES_LLM", "").strip().lower()
    if kind in ("openai", "gpt"):
        return OpenAIAdapter()
    if kind in ("llamacpp", "llama", "local"):
        return LlamaCppAdapter()
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return OpenAIAdapter()
    return LlamaCppAdapter()


def adapter_label(llm: LlmAdapter) -> str:
    label = getattr(llm, "label", None)
    if isinstance(label, str) and label.strip():
        return label
    return type(llm).__name__

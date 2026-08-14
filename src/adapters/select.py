"""Elige el adapter. Solo OpenAI por ahora."""

from __future__ import annotations

from adapter import LlmAdapter
from adapters.openai import OpenAIAdapter
from envutil import load_dotenv


def make_adapter() -> LlmAdapter:
    load_dotenv()
    return OpenAIAdapter()


def adapter_label(llm: LlmAdapter) -> str:
    label = getattr(llm, "label", None)
    if isinstance(label, str) and label.strip():
        return label
    return type(llm).__name__

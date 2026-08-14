"""Adapter OpenRouter: misma API que OpenAI, otra URL y otra clave."""

from __future__ import annotations

import os
from typing import Any

from adapters.openai import OpenAIAdapter
from envutil import load_dotenv

BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "cognitivecomputations/dolphin-mistral-24b-venice-edition"


class OpenRouterAdapter(OpenAIAdapter):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        load_dotenv()
        key = (api_key or os.environ.get("OPENROUTER_API_KEY") or "").strip()
        if not key:
            raise RuntimeError("falta OPENROUTER_API_KEY en .env")
        super().__init__(
            api_key=key,
            model=(model or os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL).strip(),
            base_url=BASE_URL,
            extra_headers={
                "HTTP-Referer": (
                    os.environ.get("OPENROUTER_HTTP_REFERER") or "https://github.com/coretales"
                ),
                "X-OpenRouter-Title": "CoreTales",
            },
            brand="OpenRouter",
        )
        self._sin_tools = "venice" in self.model.lower() or "dolphin-mistral-24b" in self.model.lower()

    @property
    def label(self) -> str:
        return f"openrouter/{self.model}"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        if self._sin_tools:
            tools = None
        try:
            return super().chat(
                messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except RuntimeError as e:
            msg = str(e).lower()
            if tools and "404" in msg and "tool" in msg:
                self._sin_tools = True
                return super().chat(
                    messages,
                    tools=None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise

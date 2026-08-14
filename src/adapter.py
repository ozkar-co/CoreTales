"""Puerto de LLM. complete para una sola respuesta; chat para tools."""

from __future__ import annotations

from typing import Any, Protocol


class LlmAdapter(Protocol):
    def complete(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.5,
        max_tokens: int = 512,
    ) -> str:
        """Una llamada síncrona. json_schema=None → prosa, no JSON mode."""

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        """Un paso del bucle. Devuelve content y/o tool_calls [{id,name,arguments}]."""

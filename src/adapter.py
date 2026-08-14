"""Puerto de LLM. Un método. El núcleo no importa vendors."""

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

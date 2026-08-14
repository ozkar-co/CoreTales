"""Puerto de LLM. Un método. El núcleo no importa vendors."""

from typing import Protocol


class LlmAdapter(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Una llamada síncrona. Devuelve texto (se espera JSON)."""

"""Adapter llama.cpp: HTTP compatible OpenAI. Opción A: KV del prefijo + slot."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8080/v1"
TIMEOUT_S = 300
GAME_SLOT = 0
PROBE_SLOT = 1

TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "ops": {"type": "array", "items": {"type": "object"}},
        "narrative": {"type": "string"},
    },
    "required": ["ops", "narrative"],
}


class LlamaCppAdapter:
    def __init__(self, base_url: str = BASE_URL, slot: int = GAME_SLOT) -> None:
        self.base_url = base_url.rstrip("/")
        self.slot = slot

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": "local",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.5,
            "max_tokens": 512,
            "cache_prompt": True,
            "id_slot": self.slot,
            "stop": ["<|im_end|>", "<|im_start|>"],
            "response_format": {
                "type": "json_object",
                "schema": TURN_SCHEMA,
            },
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"No hay servidor LLM en {self.base_url} ({e.reason})"
            ) from e

        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Respuesta LLM inesperada: {payload!r}") from e

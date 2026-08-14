"""Adapter llama.cpp: HTTP compatible OpenAI. Opción A: KV del prefijo + slot."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "http://127.0.0.1:8080/v1"
TIMEOUT_S = 300
GAME_SLOT = 0
PROBE_SLOT = 1

INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "acto": {"type": "string"},
        "objetivos": {"type": "array", "items": {"type": "string"}},
        "deltas": {
            "type": "object",
            "properties": {
                "afinidad": {"type": "number"},
                "dominancia": {"type": "number"},
                "estres": {"type": "number"},
            },
        },
        "tags": {"type": "array", "items": {"type": "string"}},
        "nuevos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "nombre": {"type": "string"},
                    "tipo": {"type": "string"},
                },
                "required": ["slug"],
            },
        },
        "lugar": {"type": "string"},
        "atmosfera": {"type": "string"},
        "tropo": {"type": "string"},
    },
    "required": ["acto"],
}

PROBE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "narrative": {"type": "string"},
    },
    "required": ["ok"],
}


class LlamaCppAdapter:
    def __init__(self, base_url: str = BASE_URL, slot: int = GAME_SLOT) -> None:
        self.base_url = base_url.rstrip("/")
        self.slot = slot

    def complete(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.5,
        max_tokens: int = 512,
    ) -> str:
        body: dict[str, Any] = {
            "model": "local",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "cache_prompt": True,
            "id_slot": self.slot,
            "stop": ["<|im_end|>", "<|im_start|>"],
        }
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_object",
                "schema": json_schema,
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

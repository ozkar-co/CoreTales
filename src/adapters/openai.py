"""Adapter OpenAI: HTTP chat/completions. La clave vive en .env."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from envutil import load_dotenv

BASE_URL = "https://api.openai.com/v1"
TIMEOUT_S = 60
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        load_dotenv()
        self.api_key = (api_key or os.environ.get("OPENAI_API_KEY") or "").strip()
        if not self.api_key:
            raise RuntimeError("falta OPENAI_API_KEY en .env")
        self.model = (
            model
            or os.environ.get("OPENAI_MODEL")
            or DEFAULT_MODEL
        ).strip()
        self.base_url = base_url.rstrip("/")

    @property
    def label(self) -> str:
        return f"openai/{self.model}"

    def complete(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.5,
        max_tokens: int = 512,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_schema is not None:
            body["response_format"] = {"type": "json_object"}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenAI no responde ({e.reason})") from e

        try:
            choice = payload["choices"][0]
            msg = choice["message"]
            text = msg.get("content")
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError(
                    f"OpenAI sin texto (finish={choice.get('finish_reason')})"
                )
            return text
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Respuesta OpenAI inesperada: {payload!r}") from e

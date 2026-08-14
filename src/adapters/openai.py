"""Adapter OpenAI: HTTP chat/completions con tools. La clave vive en .env."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

from envutil import load_dotenv

BASE_URL = "https://api.openai.com/v1"
TIMEOUT_S = 120
DEFAULT_MODEL = "gpt-4o"


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
            model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        ).strip()
        self.base_url = base_url.rstrip("/")

    @property
    def label(self) -> str:
        return f"openai/{self.model}"

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
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
        last_err: Exception | None = None
        for intento in range(8):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="replace")
                last_err = RuntimeError(f"OpenAI HTTP {e.code}: {detail}")
                if e.code != 429:
                    raise last_err from e
                espera = 2.0 * (intento + 1)
                m = re.search(r"try again in ([0-9.]+)\s*s", detail, re.I)
                if m:
                    espera = max(espera, float(m.group(1)) + 0.4)
                time.sleep(espera)
            except urllib.error.URLError as e:
                raise RuntimeError(f"OpenAI no responde ({e.reason})") from e
        raise last_err or RuntimeError("OpenAI 429 persistente")

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
        payload = self._post(body)
        try:
            choice = payload["choices"][0]
            text = choice["message"].get("content")
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError(
                    f"OpenAI sin texto (finish={choice.get('finish_reason')})"
                )
            return text
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Respuesta OpenAI inesperada: {payload!r}") from e

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
        payload = self._post(body)
        try:
            msg = payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Respuesta OpenAI inesperada: {payload!r}") from e
        calls = []
        for raw in msg.get("tool_calls") or []:
            fn = raw.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            calls.append(
                {
                    "id": raw.get("id") or "",
                    "name": fn.get("name") or "",
                    "arguments": args,
                }
            )
        return {"content": msg.get("content") or "", "tool_calls": calls}

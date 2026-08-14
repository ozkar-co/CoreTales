"""Ciclo de dos etapas: traducir → aplicar → muestrear → ensamblar."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from adapter import LlmAdapter
from adapters.llamacpp import INTENT_SCHEMA
from jsonutil import parse_intent
from prompt import NARRATE_SYSTEM, RETRY_HINT, TRANSLATE_SYSTEM
from store import DEFAULT_SAVE, Store

_STUBS = ("pc.nombre", "npc.nombre", "loc.lugar", "<id>")


def _debug() -> bool:
    return os.environ.get("CORE_TALES_DEBUG", "").strip() not in ("", "0", "false")


def _log_debug(title: str, body: str) -> None:
    if _debug():
        print(f"--- {title} ---", file=sys.stderr)
        print(body, file=sys.stderr)


def _looks_stub(data: dict[str, Any]) -> bool:
    acto = data.get("acto")
    if not isinstance(acto, str) or not acto.strip():
        return True
    blob = json.dumps(data, ensure_ascii=False).lower()
    return any(s in blob for s in _STUBS)


def _unwrap_prose(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            for key in ("narrative", "prosa", "texto"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
    for prefix in ("Narrative:", "Prosa:", "Narrativa:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix) :].strip()
    return text


class Engine:
    def __init__(
        self,
        llm: LlmAdapter,
        store: Store | None = None,
        save_path: Path | str | None = None,
    ) -> None:
        self.llm = llm
        self.store = store or Store(save_path or DEFAULT_SAVE)

    def turn(self, player: str) -> str:
        user = self.store.translate_packet(player)
        intent = self._complete_intent(user)
        self.store.begin()
        try:
            self.store.apply_intent(intent)
            pack = self.store.narration_packet(player, intent)
            prose = self._complete_prose(pack)
            if not prose:
                raise RuntimeError("prosa vacía")
            self.store.append_prose(prose)
            self.store.commit()
            return prose
        except Exception:
            self.store.rollback()
            raise

    def _complete_intent(self, user: str) -> dict[str, Any]:
        raw = self.llm.complete(
            TRANSLATE_SYSTEM,
            user,
            json_schema=INTENT_SCHEMA,
            temperature=0.3,
            max_tokens=256,
        )
        _log_debug("etapa1", raw)
        data = None
        try:
            data = parse_intent(raw)
            if _looks_stub(data):
                data = None
        except (ValueError, json.JSONDecodeError):
            data = None
        if data is None:
            raw = self.llm.complete(
                TRANSLATE_SYSTEM,
                user + "\n\n" + RETRY_HINT,
                json_schema=INTENT_SCHEMA,
                temperature=0.2,
                max_tokens=256,
            )
            _log_debug("etapa1-reintento", raw)
            try:
                data = parse_intent(raw)
            except (ValueError, json.JSONDecodeError) as e:
                raise RuntimeError(f"JSON inválido tras reintento: {e}") from e
            if _looks_stub(data):
                raise RuntimeError("el modelo devolvió una plantilla, no una intención")
        _log_debug("intencion", json.dumps(data, ensure_ascii=False, indent=2))
        return data

    def _complete_prose(self, user: str) -> str:
        raw = self.llm.complete(
            NARRATE_SYSTEM,
            user,
            json_schema=None,
            temperature=0.7,
            max_tokens=400,
        )
        _log_debug("etapa2", raw)
        return _unwrap_prose(raw)

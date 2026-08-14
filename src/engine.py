"""Núcleo fase 1: una llamada por turno, escena en memoria, reintento de JSON."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from adapter import LlmAdapter
from jsonutil import parse_turn
from prompt import SYSTEM_PROMPT
from store import Store

RETRY_HINT = (
    "Un solo objeto JSON con ops (nombres reales, no placeholders) "
    "y narrative en segunda persona sobre la acción del jugador."
)


def _debug() -> bool:
    return os.environ.get("CORE_TALES_DEBUG", "").strip() not in ("", "0", "false")


def _log_debug(title: str, body: str) -> None:
    if _debug():
        print(f"--- {title} ---", file=sys.stderr)
        print(body, file=sys.stderr)


_STUBS = (
    "texto que ve el jugador",
    "texto que ve el jugador.",
)


def _looks_stub(data: dict[str, Any]) -> bool:
    narrative = data.get("narrative")
    if not isinstance(narrative, str) or not narrative.strip():
        return True
    n = narrative.strip().lower()
    if n in _STUBS or n.startswith("texto que ve"):
        return True
    blob = json.dumps(data, ensure_ascii=False)
    if "pc.nombre" in blob or "loc.lugar" in blob or "npc.nombre" in blob:
        return True
    return False


def _user_packet(store: Store, player: str) -> str:
    scene = json.dumps(store.scene_packet(), ensure_ascii=False, indent=2)
    return (
        f"Acción del jugador:\n{player}\n\n"
        f"Estado actual (si pc/location son null, créalos según esa acción):\n{scene}\n\n"
        "JSON de este turno: ops + narrative. Nada de plantillas."
    )


class Engine:
    def __init__(self, llm: LlmAdapter, store: Store | None = None) -> None:
        self.llm = llm
        self.store = store or Store()

    def turn(self, player: str) -> str:
        backup = self.store.snapshot()
        user = _user_packet(self.store, player)
        try:
            data = self._complete_json(user)
            ops = data.get("ops") or []
            narrative = data.get("narrative")
            if not isinstance(narrative, str):
                narrative = ""
            self.store.apply_ops(ops if isinstance(ops, list) else [])
            if narrative:
                self.store.prose_log.append(narrative)
            return narrative
        except Exception:
            self.store.restore(backup)
            raise

    def _complete_json(self, user: str) -> dict[str, Any]:
        raw = self.llm.complete(SYSTEM_PROMPT, user)
        _log_debug("llm", raw)
        data = None
        try:
            data = parse_turn(raw)
            if _looks_stub(data):
                data = None
        except (ValueError, json.JSONDecodeError):
            data = None
        if data is None:
            raw = self.llm.complete(
                SYSTEM_PROMPT,
                user + "\n\n" + RETRY_HINT,
            )
            _log_debug("llm-retry", raw)
            try:
                data = parse_turn(raw)
            except (ValueError, json.JSONDecodeError) as e:
                raise RuntimeError(f"JSON inválido tras reintento: {e}") from e
            if _looks_stub(data):
                raise RuntimeError("el modelo devolvió una plantilla, no una escena")
        _log_debug("json", json.dumps(data, ensure_ascii=False, indent=2))
        return data

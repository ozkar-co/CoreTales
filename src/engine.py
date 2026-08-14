"""Un turno: el modelo pide tools, el motor responde, decir cierra."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from adapter import LlmAdapter
from prompt import SYSTEM
from store import DEFAULT_SAVE, Store
from tools import DEFINITIONS, ejecutar

MAX_TOOLS = 20


def _debug() -> bool:
    return os.environ.get("CORE_TALES_DEBUG", "").strip() not in ("", "0", "false")


def _log(title: str, body: str) -> None:
    if _debug():
        print(f"--- {title} ---", file=sys.stderr)
        print(body, file=sys.stderr)


class Engine:
    def __init__(
        self,
        llm: LlmAdapter,
        store: Store | None = None,
        save_path: Path | str | None = None,
    ) -> None:
        self.llm = llm
        self.store = store or Store(save_path or DEFAULT_SAVE)
        self.trace: list[str] = []

    def _trazar(self, line: str) -> None:
        self.trace.append(line)
        _log("tool", line)

    def turn(self, player: str) -> str:
        self.trace = []
        self.store.begin()
        try:
            prosa = self._ciclo(player)
            self.store.avanzar_turno()
            self.store.commit()
            self._journal(player, prosa)
            return prosa
        except Exception:
            self.store.rollback()
            raise

    def _ciclo(self, player: str) -> str:
        self.store.mutar_libre = False
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Acción del jugador:\n{player}\n\n"
                    "Usa aqui primero si no conoces el sitio. "
                    "Cierra con decir."
                ),
            },
        ]
        prosa = ""
        for _ in range(MAX_TOOLS):
            resp = self.llm.chat(messages, tools=DEFINITIONS)
            calls = resp.get("tool_calls") or []
            content = (resp.get("content") or "").strip()
            if not calls:
                if content:
                    prosa = content
                    self._trazar("decir (texto libre)")
                    break
                continue
            messages.append(
                {
                    "role": "assistant",
                    "content": resp.get("content") or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c["arguments"], ensure_ascii=False),
                            },
                        }
                        for c in calls
                    ],
                }
            )
            for call in calls:
                nombre = call["name"]
                args = call.get("arguments") or {}
                shown = dict(args)
                if nombre == "decir" and "prosa" in shown:
                    shown["prosa"] = "(…)"
                self._trazar(f"{nombre} {json.dumps(shown, ensure_ascii=False)}")
                try:
                    result, maybe = ejecutar(self.store, nombre, args)
                except Exception as e:
                    result, maybe = f"error: {e}", None
                    self._trazar(f"error {e}")
                if maybe:
                    prosa = maybe
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result[:4000],
                    }
                )
            if prosa:
                break
        if not prosa:
            prosa = "El turno se corta: no hubo desenlace."
        return prosa.strip()

    def _journal(self, player: str, prosa: str) -> None:
        path = self.store.path.with_name(self.store.path.stem + ".journal.txt")
        block = [f"> {player}", ""]
        block.extend(f"--- {line}" for line in self.trace)
        block += ["", prosa, "", ""]
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(block))

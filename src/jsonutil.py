"""Parseo del JSON del modelo. Elige el objeto más completo si hay varios."""

from __future__ import annotations

import json
from typing import Any


def _score(data: dict[str, Any]) -> tuple[int, int, int]:
    nar = data.get("narrative")
    has_nar = isinstance(nar, str) and bool(nar.strip())
    has_ops = isinstance(data.get("ops"), list)
    nlen = len(nar.strip()) if has_nar else 0
    return (int(has_nar), int(has_ops), nlen)


def parse_turn(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("respuesta vacía")
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    i = 0
    while i < len(raw):
        start = raw.find("{", i)
        if start < 0:
            break
        try:
            data, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            i = start + 1
            continue
        if isinstance(data, dict):
            found.append(data)
        i = start + 1
    if not found:
        raise ValueError("no hay objeto JSON")
    return max(found, key=_score)

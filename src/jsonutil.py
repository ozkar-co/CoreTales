"""Parseo del JSON del modelo."""

from __future__ import annotations

import json
from typing import Any


def parse_turn(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("respuesta vacía")
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    start = raw.find("{")
    if start < 0:
        raise ValueError("no hay objeto JSON")
    data, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(data, dict):
        raise ValueError("JSON no es un objeto")
    return data

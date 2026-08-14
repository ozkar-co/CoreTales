"""Schemas JSON compartidos. El núcleo no importa el vendor."""

from __future__ import annotations

from typing import Any

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

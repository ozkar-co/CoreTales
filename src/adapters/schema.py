"""Schemas JSON compartidos. El núcleo no importa el vendor."""

from __future__ import annotations

from typing import Any

_EJES_0_1 = {"type": "number", "minimum": 0, "maximum": 1}


def _ejes(*nombres: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {n: dict(_EJES_0_1) for n in nombres},
    }


INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "acto": {"type": "string"},
        "objetivos": {"type": "array", "items": {"type": "string"}},
        "movimiento": {"type": "boolean"},
        "lugar": {"type": "string"},
        "valoracion": _ejes(
            "intensidad",
            "intimidad",
            "agresion",
            "exposicion",
            "afecto",
            "dominio",
            "reposo",
        ),
        "tags": {"type": "array", "items": {"type": "string"}},
        "nuevos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "nombre": {"type": "string"},
                    "tipo": {"type": "string"},
                    "dueno": {"type": "string"},
                    "cantidad": {"type": "integer", "minimum": 1},
                    "rasgos": _ejes(
                        "valentia",
                        "dominancia",
                        "impulsividad",
                        "moral",
                        "fuerza",
                        "inteligencia",
                        "apariencia",
                        "sociabilidad",
                    ),
                    "estado": _ejes(
                        "excitacion",
                        "enojo",
                        "miedo",
                        "estres",
                        "dolor",
                        "verguenza",
                        "confianza",
                        "energia",
                    ),
                    "vinculo": _ejes("afecto", "odio", "respeto", "miedo", "deseo"),
                },
                "required": ["slug"],
            },
        },
        "fuera": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "existe": {"type": "string", "enum": ["muerto", "ausente", "activo"]},
                },
                "required": ["slug", "existe"],
            },
        },
        "atmosfera": {"type": "string"},
        "tropo": {"type": "string"},
    },
    "required": ["acto", "valoracion"],
}

PROBE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "narrative": {"type": "string"},
    },
    "required": ["ok"],
}

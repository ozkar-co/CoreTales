"""Tools que el modelo puede llamar. El motor las ejecuta."""

from __future__ import annotations

import json
from typing import Any

from store import Store

_FUERZA = {"type": "string", "enum": ["nulo", "debil", "medio", "fuerte", "extremo"]}
_OP = {
    "type": "object",
    "properties": {
        "op": {
            "type": "string",
            "enum": ["anotar", "borrar_rasgo", "mover", "activo", "nacer"],
        },
        "quien": {"type": "string"},
        "texto": {"type": "string"},
        "fuerza": _FUERZA,
        "hacia": {"type": "string"},
        "dueno": {"type": "string"},
        "nombre": {"type": "string"},
        "clase": {"type": "string"},
        "donde": {"type": "string"},
        "valor": {"type": "boolean"},
    },
    "required": ["op"],
}

DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "aqui",
            "description": "Quién y qué hay en el sitio actual, inventario y hechos recientes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mirar",
            "description": "Busca entidades o rasgos por nombre. No inventa: si no está, no está.",
            "parameters": {
                "type": "object",
                "properties": {"consulta": {"type": "string"}},
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nacer",
            "description": "Crea algo que el jugador nombró y aún no existe. Persona, lugar o cosa. No pongas el desenlace en el nombre ni en los rasgos (no nazcas a alguien ya herido o muerto: eso lo decide tirar).",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "clase": {
                        "type": "string",
                        "description": "persona, lugar o cosa. Texto libre si no encaja.",
                    },
                    "donde": {"type": "string"},
                    "dueno": {"type": "string"},
                    "rasgos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "texto": {"type": "string"},
                                "fuerza": _FUERZA,
                            },
                            "required": ["texto"],
                        },
                    },
                },
                "required": ["nombre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "anotar",
            "description": "Añade o cambia un rasgo (frase libre + fuerza cualitativa).",
            "parameters": {
                "type": "object",
                "properties": {
                    "quien": {"type": "string"},
                    "texto": {"type": "string"},
                    "fuerza": _FUERZA,
                },
                "required": ["quien", "texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "borrar_rasgo",
            "description": "Quita un rasgo que ya no aplica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "quien": {"type": "string"},
                    "texto": {"type": "string"},
                },
                "required": ["quien", "texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mover",
            "description": "Cambia de sitio a alguien o algo, o de dueño una cosa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "quien": {"type": "string"},
                    "hacia": {"type": "string"},
                    "dueno": {"type": "string"},
                },
                "required": ["quien"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tirar",
            "description": (
                "Sorteo del motor. Obligatorio si hay oposición o un acto puede fallar. "
                "si_pasa y si_falla son cambios al mundo; el motor aplica solo una rama."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "actor": {"type": "string"},
                    "rasgo": {"type": "string"},
                    "contra": {"type": "string"},
                    "rasgo_contra": {"type": "string"},
                    "apuesta": {"type": "string"},
                    "si_pasa": {"type": "array", "items": _OP},
                    "si_falla": {"type": "array", "items": _OP},
                },
                "required": ["actor", "si_pasa", "si_falla"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decir",
            "description": "Cierra el turno. Prosa en segunda persona (tú). El desenlace ya está resuelto.",
            "parameters": {
                "type": "object",
                "properties": {"prosa": {"type": "string"}},
                "required": ["prosa"],
            },
        },
    },
]


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def ejecutar(store: Store, nombre: str, args: dict[str, Any]) -> tuple[str, str | None]:
    """Devuelve (texto para el modelo, prosa si la tool fue decir)."""
    if nombre == "aqui":
        return _json(store.aqui()), None
    if nombre == "mirar":
        return _json(store.mirar(str(args.get("consulta") or ""))), None
    if nombre == "nacer":
        eid = store.nacer(
            str(args.get("nombre") or ""),
            str(args.get("clase") or ""),
            args.get("donde"),
            args.get("dueno"),
            args.get("rasgos") if isinstance(args.get("rasgos"), list) else None,
        )
        return _json(store._ficha(eid)), None
    if nombre == "anotar":
        store.anotar(
            str(args.get("quien") or ""),
            str(args.get("texto") or ""),
            args.get("fuerza"),
        )
        return "ok", None
    if nombre == "borrar_rasgo":
        store.borrar_rasgo(str(args.get("quien") or ""), str(args.get("texto") or ""))
        return "ok", None
    if nombre == "mover":
        store.mover(
            str(args.get("quien") or ""),
            args.get("hacia"),
            args.get("dueno"),
        )
        return "ok", None
    if nombre == "tirar":
        out = store.tirar(
            actor=str(args.get("actor") or "Jugador"),
            rasgo=args.get("rasgo"),
            contra=args.get("contra"),
            rasgo_contra=args.get("rasgo_contra"),
            si_pasa=args.get("si_pasa"),
            si_falla=args.get("si_falla"),
            apuesta=str(args.get("apuesta") or ""),
        )
        return _json(out), None
    if nombre == "decir":
        prosa = str(args.get("prosa") or "").strip()
        return "ok", prosa
    return f"tool desconocida: {nombre}", None

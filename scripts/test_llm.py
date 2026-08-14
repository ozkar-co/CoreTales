#!/usr/bin/env python3
"""Comprueba que el servidor LLM responde y que el JSON se puede parsear."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from adapters.llamacpp import LlamaCppAdapter, PROBE_SCHEMA, PROBE_SLOT
from jsonutil import parse_turn


def main() -> int:
    llm = LlamaCppAdapter(slot=PROBE_SLOT)
    print(f"POST {llm.base_url}/chat/completions", file=sys.stderr)
    raw = llm.complete(
        "You output only JSON objects. No markdown.",
        'Return {"ok": true, "narrative": "hola"} and nothing else.',
        json_schema=PROBE_SCHEMA,
    )
    print(raw)
    try:
        data = parse_turn(raw)
    except Exception as e:
        print(f"JSON inválido: {e}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False), file=sys.stderr)
    print("ok", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

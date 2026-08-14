"""CLI. Texto libre in, prosa out. Ctrl-D o Ctrl-C para salir."""

from __future__ import annotations

import sys

from adapters.llamacpp import LlamaCppAdapter
from engine import Engine


def main() -> None:
    engine = Engine(LlamaCppAdapter())
    print("CoreTales. Escribe lo que haces. Ctrl-D para salir.", file=sys.stderr)
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return
        if not line.strip():
            continue
        try:
            print(file=sys.stderr, flush=True)
            text = engine.turn(line)
        except Exception as e:
            print(f"falló el turno: {e}", file=sys.stderr)
            continue
        print(text or "")
        print()


if __name__ == "__main__":
    main()

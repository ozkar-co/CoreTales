"""Banco de escenas. Input del jugador, output y debug como en el chat."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from adapters.select import adapter_label, make_adapter  # noqa: E402
from engine import Engine  # noqa: E402
from store import Store  # noqa: E402

ESCENAS = ROOT / "tests" / "escenas"
LOGS = ROOT / "tests" / "logs"


def _parse(path: Path) -> tuple[str, list[str]]:
    titulo = path.stem
    turnos: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# titulo:"):
            titulo = line.split(":", 1)[1].strip()
        elif line.startswith(">"):
            turnos.append(line[1:].strip())
    return titulo, turnos


def _correr(path: Path, llm) -> Path:
    titulo, turnos = _parse(path)
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = LOGS / f"{path.stem}_{stamp}.sqlite"
    print(f"== {titulo} ({path.name}) ==", flush=True)
    store = Store(dest)
    engine = Engine(llm, store=store)
    journal = dest.with_name(dest.stem + ".journal.txt")
    journal.write_text(
        f"# {titulo}\nLLM: {adapter_label(llm)}\n\n", encoding="utf-8"
    )
    print(f"LLM: {adapter_label(llm)}", flush=True)
    for i, player in enumerate(turnos, 1):
        if i > 1:
            time.sleep(2)
        print(f"  turno {i}: {player[:70]}", flush=True)
        try:
            engine.turn(player)
        except Exception as e:
            journal = dest.with_name(dest.stem + ".journal.txt")
            with journal.open("a", encoding="utf-8") as fh:
                fh.write(f"> {player}\n\nfalló el turno: {e}\n\n")
            print(f"  falló: {e}", file=sys.stderr)
            break
    store.close()
    journal = dest.with_name(dest.stem + ".journal.txt")
    print(f"  log: {journal}", flush=True)
    return journal


def main() -> None:
    filtro = " ".join(a for a in sys.argv[1:] if not a.startswith("-")).strip()
    llm = make_adapter()
    files = sorted(ESCENAS.glob("*.txt"))
    if filtro:
        files = [f for f in files if filtro in f.stem]
    if not files:
        print("no hay escenas", file=sys.stderr)
        sys.exit(1)
    for i, path in enumerate(files):
        if i:
            time.sleep(8)
        _correr(path, llm)


if __name__ == "__main__":
    main()

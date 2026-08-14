#!/usr/bin/env python3
"""txt -> SQLite. Por defecto actualiza saves/default.sqlite."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from catalog import import_catalog  # noqa: E402
from schema import SCHEMA  # noqa: E402


def main() -> int:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "saves" / "default.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    import_catalog(conn)
    print(f"catálogo importado en {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

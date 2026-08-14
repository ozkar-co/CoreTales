#!/usr/bin/env python3
"""SQLite -> txt en data/catalogo/."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from catalog import export_catalog  # noqa: E402


def main() -> int:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "saves" / "default.sqlite"
    if not db.exists():
        print(f"no existe {db}", file=sys.stderr)
        return 1
    export_catalog(sqlite3.connect(db))
    print(f"catálogo exportado desde {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

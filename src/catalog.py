"""Import/export del catálogo (txt <-> SQLite)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from schema import ANCHOR_FILE, ANCHOR_TABLES, SCHEMA

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "data" / "catalogo"


def _read_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if header is None:
            header = parts
            continue
        row = {header[i]: parts[i] if i < len(parts) else "" for i in range(len(header))}
        rows.append(row)
    return rows


def _write_tsv(path: Path, header: list[str], rows: list[tuple]) -> None:
    lines = ["\t".join(header)]
    for row in rows:
        lines.append("\t".join("" if c is None else str(c) for c in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def import_catalog(conn: sqlite3.Connection, catalog_dir: Path = CATALOG_DIR) -> None:
    conn.executescript(SCHEMA)
    for table in ANCHOR_TABLES:
        path = catalog_dir / ANCHOR_FILE[table]
        if not path.exists():
            continue
        conn.execute(f"DELETE FROM {table}")
        for row in _read_tsv(path):
            if not (row.get("id") or "").strip():
                continue
            cols = [c for c in row if c]
            placeholders = ",".join("?" * len(cols))
            colnames = ",".join(cols)
            conn.execute(
                f"INSERT INTO {table} ({colnames}) VALUES ({placeholders})",
                [row[c] for c in cols],
            )
    frases_path = catalog_dir / "frases.txt"
    if frases_path.exists():
        conn.execute("DELETE FROM frases")
        for row in _read_tsv(frases_path):
            texto = (row.get("texto") or "").strip()
            if not texto:
                continue
            conn.execute(
                "INSERT INTO frases (ancla_tipo, ancla_id, clase, texto) VALUES (?,?,?,?)",
                (
                    row.get("ancla_tipo", ""),
                    row.get("ancla_id", ""),
                    row.get("clase", "fragmento"),
                    texto,
                ),
            )
    conn.commit()


def export_catalog(conn: sqlite3.Connection, catalog_dir: Path = CATALOG_DIR) -> None:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "empujes": ["id", "nombre", "resumen", "familia"],
        "tropos": ["id", "nombre", "resumen", "empuje"],
        "tipos_historia": ["id", "nombre", "resumen", "empuje"],
        "tipos_personaje": ["id", "nombre", "resumen"],
        "tipos_lugar": ["id", "nombre", "resumen"],
        "atmosferas": ["id", "nombre", "resumen", "empuje"],
    }
    for table, header in headers.items():
        rows = conn.execute(
            f"SELECT {', '.join(header)} FROM {table} ORDER BY id"
        ).fetchall()
        _write_tsv(catalog_dir / ANCHOR_FILE[table], header, rows)
    frases = conn.execute(
        "SELECT ancla_tipo, ancla_id, clase, texto FROM frases ORDER BY ancla_tipo, ancla_id, id"
    ).fetchall()
    _write_tsv(
        catalog_dir / "frases.txt",
        ["ancla_tipo", "ancla_id", "clase", "texto"],
        frases,
    )


def catalog_empty(conn: sqlite3.Connection) -> bool:
    n = conn.execute("SELECT COUNT(*) FROM tropos").fetchone()[0]
    return n == 0

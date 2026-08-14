#!/usr/bin/env python3
"""Escribe tipos_lugar, atmosferas y completa frases.txt.

Estrategia:
  1. Nube propia por ancla (cupo QUOTA).
  2. Cruce lugar x familia de empuje (oficina+miedo, casa+deseo, ...).
     El motor muestrea el cruce activo; no hace falta una fila por cada
     atmósfera concreta.
  3. Las frases ya escritas a mano se conservan; acá se completan huecos.

  python3 scripts/fill_catalog.py
  python3 scripts/fill_catalog.py --frases
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_atmosferas import ATMOSFERAS  # noqa: E402
from catalog_banks import CRUCE, FAMILIA, GRUPO, PERSONAJE  # noqa: E402
from catalog_lugares import LUGARES  # noqa: E402

CAT = ROOT / "data" / "catalogo"

QUOTA = {
    "tipo_lugar": 12,
    "atmosfera": 12,
    "empuje": 6,
    "tropo": 6,
    "tipo_personaje": 8,
    "tipo_historia": 4,
    "cruce": 3,
    "prosa": 4,
}


def _md5(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)


def pick(key: str, items: list, n: int) -> list:
    if not items:
        return []
    seen: set[str] = set()
    out = []
    i = 0
    guard = 0
    while len(out) < n and guard < n * 20:
        item = items[_md5(f"{key}:{i}") % len(items)]
        i += 1
        guard += 1
        sig = item if isinstance(item, str) else item[-1]
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
    return out


def write_tsv(path: Path, header: list[str], rows: list[tuple]) -> None:
    lines = ["\t".join(header)]
    for row in rows:
        lines.append("\t".join("" if c is None else str(c) for c in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if header is None:
            header = parts
            continue
        row = {header[i]: parts[i] if i < len(parts) else "" for i in range(len(header))}
        rows.append(row)
    return rows


def write_anclas() -> None:
    ids = [r[0] for r in LUGARES]
    if len(ids) != len(set(ids)):
        raise SystemExit("ids de lugar duplicados")
    write_tsv(
        CAT / "tipos_lugar.txt",
        ["id", "nombre", "resumen", "grupo"],
        LUGARES,
    )
    ids = [r[0] for r in ATMOSFERAS]
    if len(ids) != len(set(ids)):
        raise SystemExit("ids de atmosfera duplicados")
    write_tsv(
        CAT / "atmosferas.txt",
        ["id", "nombre", "resumen", "empuje"],
        ATMOSFERAS,
    )


def _add(bucket: list, seen: set[str], kind: str, ident: str, clase: str, texto: str) -> None:
    texto = (texto or "").strip()
    if not texto:
        return
    sig = f"{kind}\t{ident}\t{texto}"
    if sig in seen:
        return
    seen.add(sig)
    bucket.append((kind, ident, clase, texto))


def fill_frases() -> None:
    empujes = {r["id"]: r for r in read_tsv(CAT / "empujes.txt")}
    tropos = read_tsv(CAT / "tropos.txt")
    historias = read_tsv(CAT / "tipos_historia.txt")
    personajes = read_tsv(CAT / "tipos_personaje.txt")
    lugares = read_tsv(CAT / "tipos_lugar.txt")
    atmosferas = read_tsv(CAT / "atmosferas.txt")

    missing_atmo = sorted(
        {
            r["empuje"]
            for r in atmosferas
            if r.get("empuje") and r["empuje"] not in empujes
        }
    )
    if missing_atmo:
        raise SystemExit(f"atmosferas con empuje inexistente: {missing_atmo}")

    existing = [
        row
        for row in read_tsv(CAT / "frases.txt")
        if row.get("ancla_tipo") != "cruce"
    ]
    seen: set[str] = set()
    out: list[tuple[str, str, str, str]] = []
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in existing:
        texto = (row.get("texto") or "").strip()
        if not texto:
            continue
        kind, ident = row.get("ancla_tipo", ""), row.get("ancla_id", "")
        _add(out, seen, kind, ident, row.get("clase", "fragmento"), texto)
        counts[(kind, ident)] += 1

    def need(kind: str, ident: str) -> int:
        return max(0, QUOTA.get(kind, 0) - counts[(kind, ident)])

    def emit(kind: str, ident: str, clase: str, texto: str) -> None:
        before = len(out)
        _add(out, seen, kind, ident, clase, texto)
        if len(out) > before:
            counts[(kind, ident)] += 1

    for row in lugares:
        ident, nombre, resumen, grupo = (
            row["id"],
            row.get("nombre", ""),
            row.get("resumen", ""),
            row.get("grupo", "") or "trabajo",
        )
        bank = GRUPO.get(grupo, GRUPO["trabajo"])
        emit("tipo_lugar", ident, "ambiente", resumen)
        n = need("tipo_lugar", ident)
        pool: list[tuple[str, str]] = []
        for clase, frases in bank.items():
            pool.extend((clase, t) for t in frases)
        for clase, texto in pick(f"lugar:{ident}", pool, n):
            emit("tipo_lugar", ident, clase, texto)

    for row in atmosferas:
        ident, resumen = row["id"], row.get("resumen", "")
        emp = empujes.get(row.get("empuje", ""), {})
        fam = emp.get("familia") or "cotidiano"
        emit("atmosfera", ident, "ambiente", resumen)
        n = need("atmosfera", ident)
        pool = list(FAMILIA.get(fam, FAMILIA["cotidiano"]))
        for clase, texto in pick(f"atmo:{ident}", pool, n):
            emit("atmosfera", ident, clase, texto)

    for row in empujes.values():
        ident, resumen, fam = row["id"], row.get("resumen", ""), row.get("familia") or "cotidiano"
        emit("empuje", ident, "ambiente", resumen)
        n = need("empuje", ident)
        pool = list(FAMILIA.get(fam, FAMILIA["cotidiano"]))
        for clase, texto in pick(f"emp:{ident}", pool, n):
            emit("empuje", ident, clase, texto)

    for row in tropos:
        ident, resumen = row["id"], row.get("resumen", "")
        emp = empujes.get(row.get("empuje", ""), {})
        fam = emp.get("familia") or "cotidiano"
        emit("tropo", ident, "ambiente", resumen)
        n = need("tropo", ident)
        pool = list(FAMILIA.get(fam, FAMILIA["cotidiano"]))
        for clase, texto in pick(f"tropo:{ident}", pool, n):
            emit("tropo", ident, clase, texto)

    for row in historias:
        ident, resumen = row["id"], row.get("resumen", "")
        emp = empujes.get(row.get("empuje", ""), {})
        fam = emp.get("familia") or "cotidiano"
        emit("tipo_historia", ident, "ambiente", resumen)
        n = need("tipo_historia", ident)
        pool = list(FAMILIA.get(fam, FAMILIA["cotidiano"]))
        for clase, texto in pick(f"hist:{ident}", pool, n):
            emit("tipo_historia", ident, clase, texto)

    for row in personajes:
        ident, resumen = row["id"], row.get("resumen", "")
        emit("tipo_personaje", ident, "perfil", resumen)
        n = need("tipo_personaje", ident)
        for clase, texto in pick(f"pj:{ident}", PERSONAJE, n):
            emit("tipo_personaje", ident, clase, texto)

    familias = sorted(CRUCE)
    for row in lugares:
        ident, nombre = row["id"], row.get("nombre", "el sitio")
        for fam in familias:
            cruce_id = f"{ident}+{fam}"
            n = need("cruce", cruce_id)
            plantillas = CRUCE[fam]
            for texto in pick(f"cruce:{cruce_id}", plantillas, n):
                emit(
                    "cruce",
                    cruce_id,
                    "ambiente",
                    texto.format(lugar=nombre[:1].lower() + nombre[1:] if nombre else nombre),
                )

    emit("prosa", "saludo", "fragmento", "El día empieza sin anuncio.")
    emit("prosa", "saludo", "fragmento", "Estás donde siempre, un segundo antes de que pase algo.")

    out.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
    write_tsv(CAT / "frases.txt", ["ancla_tipo", "ancla_id", "clase", "texto"], out)
    by = defaultdict(int)
    for kind, _, _, _ in out:
        by[kind] += 1
    print(f"frases {len(out)}")
    for k in sorted(by):
        print(f"  {k}: {by[k]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frases", action="store_true", help="solo nubes")
    args = parser.parse_args()
    CAT.mkdir(parents=True, exist_ok=True)
    if not args.frases:
        write_anclas()
        print(f"lugares {len(LUGARES)}")
        print(f"atmosferas {len(ATMOSFERAS)}")
    fill_frases()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

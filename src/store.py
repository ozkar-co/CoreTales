"""Partida en SQLite. El modelo pregunta; esto responde y escribe."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from schema import SCHEMA
from sorteo import efectivo, fuerza_de, resolver

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAVE = ROOT / "saves" / "default.sqlite"


_ART = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "con", "mi", "su", "al", "a", "y",
}

_PRON = {
    "ella", "el", "él", "ellos", "ellas",
    "ese", "esa", "aquel", "aquella", "alguien",
}

_HUECO = _PRON | {"persona"}


def _tokens(nombre: str) -> list[str]:
    return [
        t
        for t in re.split(r"[^a-z0-9áéíóúñ]+", nombre.lower())
        if t and t not in _ART
    ]


class Store:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_SAVE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.isolation_level = None
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._exigir_esquema_nuevo()
        self.conn.executescript(SCHEMA)
        self._en_nacer = False
        self._recien: set[int] = set()
        self.mutar_libre = True
        self._ensure_escena()

    def _exigir_esquema_nuevo(self) -> None:
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(entidades)")]
        if cols and "slug" in cols:
            raise RuntimeError(
                f"esta partida es del motor anterior; borra {self.path}"
            )

    def close(self) -> None:
        self.conn.close()

    def begin(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def _ensure_escena(self) -> None:
        if self.conn.execute("SELECT 1 FROM escena WHERE id = 1").fetchone():
            return
        self.conn.execute("INSERT INTO escena (id, turno) VALUES (1, 0)")
        tu = self.nacer("Jugador", "persona")
        self.conn.execute("UPDATE escena SET tu = ? WHERE id = 1", (tu,))
        self.nacer("sitio", "lugar")

    def escena(self) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM escena WHERE id = 1").fetchone()
        return dict(row) if row else {}

    def _ent(self, eid: int | None) -> dict[str, Any] | None:
        if not eid:
            return None
        row = self.conn.execute(
            "SELECT * FROM entidades WHERE id = ?", (eid,)
        ).fetchone()
        return dict(row) if row else None

    def _persona_referida(self) -> int | None:
        tu = self.escena().get("tu")
        loc = self.escena().get("aqui")
        if loc:
            rows = self.conn.execute(
                "SELECT id FROM entidades WHERE clase = 'persona' AND activo = 1 "
                "AND donde = ? AND id != ? ORDER BY id",
                (loc, tu),
            ).fetchall()
            if len(rows) == 1:
                return int(rows[0]["id"])
            if len(rows) > 1:
                return None
        row = self.conn.execute(
            "SELECT id FROM entidades WHERE clase = 'persona' AND id != ? "
            "ORDER BY id DESC LIMIT 1",
            (tu,),
        ).fetchone()
        return int(row["id"]) if row else None

    def buscar(self, nombre: str) -> int | None:
        raw = (nombre or "").strip()
        if not raw:
            return None
        if raw.lower() in _PRON:
            return self._persona_referida()
        row = self.conn.execute(
            "SELECT id FROM entidades WHERE lower(nombre) = lower(?) LIMIT 1",
            (raw,),
        ).fetchone()
        if row:
            return int(row["id"])
        loc = self.escena().get("aqui")
        if loc:
            row = self.conn.execute(
                "SELECT id FROM entidades WHERE donde = ? AND lower(nombre) LIKE lower(?) LIMIT 1",
                (loc, f"%{raw}%"),
            ).fetchone()
            if row:
                return int(row["id"])
        row = self.conn.execute(
            "SELECT id FROM entidades WHERE lower(nombre) LIKE lower(?) LIMIT 1",
            (f"%{raw}%",),
        ).fetchone()
        if row:
            return int(row["id"])
        toks = _tokens(raw)
        if len(toks) == 1:
            clave = toks[0]
            if len(clave) >= 3:
                row = self.conn.execute(
                    "SELECT id FROM entidades WHERE lower(nombre) LIKE lower(?) "
                    "AND length(nombre) >= ? LIMIT 1",
                    (f"%{clave}%", len(raw)),
                ).fetchone()
                if row:
                    return int(row["id"])
        return None

    def rasgos_de(self, eid: int) -> list[dict[str, str]]:
        return [
            {"texto": r["texto"], "fuerza": r["fuerza"]}
            for r in self.conn.execute(
                "SELECT texto, fuerza FROM rasgos WHERE entidad = ? ORDER BY texto",
                (eid,),
            )
        ]

    def _ficha(self, eid: int) -> dict[str, Any]:
        ent = self._ent(eid) or {}
        donde = self._ent(ent.get("donde"))
        dueno = self._ent(ent.get("dueno"))
        return {
            "id": eid,
            "nombre": ent.get("nombre"),
            "clase": ent.get("clase"),
            "activo": bool(ent.get("activo")),
            "donde": donde["nombre"] if donde else None,
            "dueno": dueno["nombre"] if dueno else None,
            "rasgos": self.rasgos_de(eid),
        }

    def aqui(self) -> dict[str, Any]:
        sc = self.escena()
        lugar = self._ent(sc.get("aqui"))
        loc_id = sc.get("aqui")
        tu = sc.get("tu")
        presentes = []
        cosas = []
        llevas = []
        if loc_id:
            for r in self.conn.execute(
                "SELECT id, clase, dueno FROM entidades WHERE donde = ? AND activo = 1 "
                "AND id != ? ORDER BY nombre",
                (loc_id, tu),
            ):
                if r["dueno"] is not None:
                    continue
                ficha = self._ficha(r["id"])
                if (r["clase"] or "") in ("cosa", "objeto"):
                    cosas.append(ficha)
                else:
                    presentes.append(ficha)
        if tu:
            for r in self.conn.execute(
                "SELECT id FROM entidades WHERE dueno = ? AND activo = 1 ORDER BY nombre",
                (tu,),
            ):
                llevas.append(self._ficha(r["id"]))
        linea = [
            r["texto"]
            for r in self.conn.execute(
                "SELECT texto FROM linea ORDER BY id DESC LIMIT 8"
            )
        ]
        return {
            "turno": sc.get("turno") or 0,
            "tu": self._ficha(tu) if tu else None,
            "lugar": self._ficha(lugar["id"]) if lugar else None,
            "presentes": presentes,
            "cosas_del_lugar": cosas,
            "llevas": llevas,
            "hace_poco": list(reversed(linea)),
        }

    def mirar(self, consulta: str) -> list[dict[str, Any]]:
        q = (consulta or "").strip()
        if not q:
            return []
        rows = self.conn.execute(
            "SELECT DISTINCT e.id FROM entidades e "
            "LEFT JOIN rasgos r ON r.entidad = e.id "
            "WHERE lower(e.nombre) LIKE lower(?) OR lower(r.texto) LIKE lower(?) "
            "OR lower(e.clase) LIKE lower(?) "
            "ORDER BY e.nombre LIMIT 8",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        ).fetchall()
        return [self._ficha(r["id"]) for r in rows]

    def nacer(
        self,
        nombre: str,
        clase: str = "",
        donde: str | None = None,
        dueno: str | None = None,
        rasgos: list[dict[str, str]] | None = None,
    ) -> int:
        nombre = (nombre or "").strip()
        if not nombre:
            raise ValueError("nacer: falta nombre")
        ya = self.buscar(nombre)
        if ya:
            return ya
        if nombre.lower() in _HUECO:
            raise ValueError(
                "nacer: usa el nombre de aqui, no un pronombre ni 'persona'"
            )
        loc = self.buscar(donde) if donde else self.escena().get("aqui")
        if donde and not loc:
            loc = self.nacer(str(donde), "lugar")
        due = self.buscar(dueno) if dueno else None
        clase_n = (clase or "").strip()
        if clase_n.lower() in ("cosa", "objeto") and due is None and not donde:
            due = self.escena().get("tu")
        self._en_nacer = True
        try:
            cur = self.conn.execute(
                "INSERT INTO entidades (nombre, clase, donde, dueno, activo) "
                "VALUES (?, ?, ?, ?, 1)",
                (nombre, (clase or "").strip(), loc, due),
            )
            eid = int(cur.lastrowid)
            self._recien.add(eid)
            for item in rasgos or []:
                if isinstance(item, str):
                    item = {"texto": item}
                texto = str(item.get("texto") or "").strip()
                if texto:
                    self.anotar(nombre, texto, item.get("fuerza"))
        finally:
            self._en_nacer = False
        sc = self.escena()
        if (clase or "") == "lugar":
            aqui = self._ent(sc.get("aqui"))
            vacio = not sc.get("aqui") or (aqui or {}).get("nombre") == "sitio"
            if vacio:
                old = sc.get("aqui")
                self.conn.execute("UPDATE escena SET aqui = ? WHERE id = 1", (eid,))
                tu = sc.get("tu")
                if tu:
                    self.conn.execute(
                        "UPDATE entidades SET donde = ? WHERE id = ?", (eid, tu)
                    )
                if old and old != eid:
                    self.conn.execute(
                        "UPDATE entidades SET donde = ? WHERE donde = ?", (eid, old)
                    )
        return eid

    def _exige_tirar(self, quien: str) -> None:
        if self._en_nacer or self.mutar_libre:
            return
        eid = self.buscar(quien)
        tu = self.escena().get("tu")
        if not eid or eid == tu or eid in self._recien:
            return
        ent = self._ent(eid) or {}
        if (ent.get("clase") or "").lower() in ("lugar", "cosa", "objeto", ""):
            return
        raise ValueError(
            "cambiar a otra persona requiere tirar primero (si_pasa/si_falla)"
        )

    def anotar(self, quien: str, texto: str, fuerza: str | None = None) -> None:
        self._exige_tirar(quien)
        eid = self.buscar(quien)
        if not eid:
            raise ValueError(f"no está: {quien}")
        texto = (texto or "").strip()
        if not texto:
            raise ValueError("anotar: falta texto")
        f = fuerza_de(fuerza)
        self.conn.execute(
            "INSERT INTO rasgos (entidad, texto, fuerza) VALUES (?, ?, ?) "
            "ON CONFLICT(entidad, texto) DO UPDATE SET fuerza = excluded.fuerza",
            (eid, texto, f),
        )

    def borrar_rasgo(self, quien: str, texto: str) -> None:
        eid = self.buscar(quien)
        if not eid:
            return
        self.conn.execute(
            "DELETE FROM rasgos WHERE entidad = ? AND lower(texto) = lower(?)",
            (eid, texto.strip()),
        )

    def mover(self, quien: str, hacia: str | None = None, dueno: str | None = None) -> None:
        eid = self.buscar(quien)
        if not eid:
            raise ValueError(f"no está: {quien}")
        tu = self.escena().get("tu")
        if dueno is not None:
            due = self.buscar(dueno) if dueno else None
            self.conn.execute(
                "UPDATE entidades SET dueno = ? WHERE id = ?", (due, eid)
            )
            if due:
                self.conn.execute(
                    "UPDATE entidades SET donde = NULL WHERE id = ?", (eid,)
                )
        if hacia:
            if eid != tu:
                self._exige_tirar(quien)
            dest = self.buscar(hacia)
            if not dest:
                dest = self.nacer(hacia, "lugar")
            self.conn.execute(
                "UPDATE entidades SET donde = ? WHERE id = ?", (dest, eid)
            )
            if eid == tu:
                self.conn.execute("UPDATE escena SET aqui = ? WHERE id = 1", (dest,))
        elif dueno is None:
            if eid == tu:
                return
            self._exige_tirar(quien)
            self.conn.execute(
                "UPDATE entidades SET donde = NULL WHERE id = ?", (eid,)
            )

    def set_activo(self, quien: str, activo: bool) -> None:
        eid = self.buscar(quien)
        if not eid:
            raise ValueError(f"no está: {quien}")
        tu = self.escena().get("tu")
        if eid == tu:
            raise ValueError("el jugador no se apaga")
        self._exige_tirar(quien)
        self.conn.execute(
            "UPDATE entidades SET activo = ? WHERE id = ?", (1 if activo else 0, eid)
        )

    def anotar_linea(self, texto: str) -> None:
        texto = (texto or "").strip()
        if not texto:
            return
        turno = self.escena().get("turno") or 0
        self.conn.execute(
            "INSERT INTO linea (turno, texto) VALUES (?, ?)", (turno, texto)
        )

    def avanzar_turno(self) -> None:
        self._recien.clear()
        self.conn.execute("UPDATE escena SET turno = turno + 1 WHERE id = 1")

    def rasgo_fuerza(self, eid: int, texto: str | None) -> str:
        if not texto:
            return "medio"
        t = texto.strip()
        row = self.conn.execute(
            "SELECT fuerza FROM rasgos WHERE entidad = ? AND lower(texto) = lower(?)",
            (eid, t),
        ).fetchone()
        if row:
            return row["fuerza"]
        row = self.conn.execute(
            "SELECT fuerza FROM rasgos WHERE entidad = ? AND lower(texto) LIKE lower(?) LIMIT 1",
            (eid, f"%{t}%"),
        ).fetchone()
        if row:
            return row["fuerza"]
        toks = _tokens(t)
        if toks:
            clave = max(toks, key=len)
            if len(clave) >= 4:
                row = self.conn.execute(
                    "SELECT fuerza FROM rasgos WHERE entidad = ? AND lower(texto) LIKE lower(?) LIMIT 1",
                    (eid, f"%{clave}%"),
                ).fetchone()
                if row:
                    return row["fuerza"]
        return "medio"

    def aplicar_ops(self, ops: Any) -> list[str]:
        hechos: list[str] = []
        if not isinstance(ops, list):
            return hechos
        for raw in ops:
            if not isinstance(raw, dict):
                continue
            op = str(raw.get("op") or "").strip()
            quien = str(raw.get("quien") or "").strip()
            try:
                if op == "anotar":
                    self.anotar(quien, str(raw.get("texto") or ""), raw.get("fuerza"))
                    hechos.append(f"anotar {quien}: {raw.get('texto')}")
                elif op == "borrar_rasgo":
                    self.borrar_rasgo(quien, str(raw.get("texto") or ""))
                    hechos.append(f"borrar {quien}: {raw.get('texto')}")
                elif op == "mover":
                    self.mover(quien, raw.get("hacia"), raw.get("dueno"))
                    hechos.append(f"mover {quien} -> {raw.get('hacia') or raw.get('dueno')}")
                elif op == "activo":
                    on = bool(raw.get("valor", False))
                    self.set_activo(quien, on)
                    hechos.append(f"{quien} activo={int(on)}")
                elif op == "nacer":
                    self.nacer(
                        str(raw.get("nombre") or quien),
                        str(raw.get("clase") or ""),
                        raw.get("donde"),
                        raw.get("dueno"),
                    )
                    hechos.append(f"nacer {raw.get('nombre') or quien}")
            except ValueError as e:
                hechos.append(f"(op falló: {e})")
        return hechos

    def tirar(
        self,
        actor: str,
        rasgo: str | None = None,
        contra: str | None = None,
        rasgo_contra: str | None = None,
        si_pasa: Any = None,
        si_falla: Any = None,
        apuesta: str = "",
    ) -> dict[str, Any]:
        aid = self.buscar(actor) or self.escena().get("tu")
        if not aid:
            raise ValueError(f"no está el actor: {actor}")
        self.mutar_libre = True
        fa = self.rasgo_fuerza(aid, rasgo)
        va = efectivo(fa)
        vb = None
        fb = None
        if contra:
            cid = self.buscar(contra)
            if cid:
                fb = self.rasgo_fuerza(cid, rasgo_contra or rasgo)
                vb = efectivo(fb)
        veredicto, a, b = resolver(va, vb)
        rama = si_pasa if veredicto != "falla" else si_falla
        aplicados = self.aplicar_ops(rama)
        texto = (
            f"{veredicto}: {actor}"
            + (f"/{rasgo}" if rasgo else "")
            + f" {a}"
            + (f" vs {contra} {b}" if contra else f" vs mundo {b}")
            + (f" — {apuesta}" if apuesta else "")
        )
        self.anotar_linea(texto)
        return {
            "veredicto": veredicto,
            "actor": a,
            "contra": b,
            "fuerza_actor": fa,
            "fuerza_contra": fb,
            "aplicado": aplicados,
            "texto": texto,
        }

    def presentes_nombres(self) -> list[str]:
        sc = self.escena()
        loc = sc.get("aqui")
        tu = sc.get("tu")
        if not loc:
            return []
        return [
            r["nombre"]
            for r in self.conn.execute(
                "SELECT nombre FROM entidades WHERE donde = ? AND activo = 1 "
                "AND clase = 'persona' AND id != ?",
                (loc, tu),
            )
        ]

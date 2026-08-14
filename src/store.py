"""Partida en SQLite. Catálogo de referencia + instancia."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

from catalog import catalog_empty, import_catalog
from schema import (
    CORE_KEYS,
    MAX_NUEVOS,
    MAX_TAGS,
    SAMPLE_FRASES,
    SCHEMA,
    SLUG_PREFIX,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAVE = ROOT / "saves" / "default.sqlite"

_DELTA_CAP = 0.3
_SLUG_REST = re.compile(r"^[a-z0-9_]+$")


def _ascii_slug(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")
    return s


def _valid_slug(slug: str) -> bool:
    if not any(slug.startswith(p) for p in SLUG_PREFIX):
        return False
    rest = slug.split(".", 1)[1]
    return bool(rest) and bool(_SLUG_REST.match(rest))


def _normalize_slug(raw: str, default_prefix: str = "npc") -> str | None:
    s = _ascii_slug(raw.replace(".", " "))
    if not s:
        return None
    low = raw.strip().lower()
    for p in SLUG_PREFIX:
        if low.startswith(p):
            rest = _ascii_slug(low[len(p) :])
            slug = f"{p}{rest}" if rest else None
            return slug if slug and _valid_slug(slug) else None
    slug = f"{default_prefix}.{s}"
    return slug if _valid_slug(slug) else None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class Store:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_SAVE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.isolation_level = None
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        if catalog_empty(self.conn):
            import_catalog(self.conn)
        self._ensure_instance()

    def close(self) -> None:
        self.conn.close()

    def begin(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def _ensure_instance(self) -> None:
        if self.conn.execute("SELECT 1 FROM scene WHERE id = 1").fetchone() is None:
            self.conn.execute("INSERT INTO scene (id) VALUES (1)")
        if (
            self.conn.execute(
                "SELECT 1 FROM meta WHERE clave = 'beat'"
            ).fetchone()
            is None
        ):
            self.conn.execute(
                "INSERT INTO meta (clave, valor) VALUES ('beat', '')"
            )
        self.conn.commit()

    def ids(self, table: str) -> list[str]:
        rows = self.conn.execute(f"SELECT id FROM {table} ORDER BY id").fetchall()
        return [r["id"] for r in rows]

    def _exists_id(self, table: str, ident: str) -> bool:
        row = self.conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ?", (ident,)
        ).fetchone()
        return row is not None

    def get_scene(self) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM scene WHERE id = 1").fetchone()
        return dict(row) if row else {}

    def _entity(self, slug: str | None) -> dict[str, Any] | None:
        if not slug:
            return None
        row = self.conn.execute(
            "SELECT * FROM entidades WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None

    def _nucleo(self, slug: str | None) -> dict[str, float] | None:
        if not slug:
            return None
        row = self.conn.execute(
            "SELECT afinidad, dominancia, estres FROM nucleo WHERE slug = ?",
            (slug,),
        ).fetchone()
        return dict(row) if row else None

    def _tags_of(self, slug: str | None) -> list[str]:
        if not slug:
            return []
        rows = self.conn.execute(
            "SELECT tag FROM tags WHERE slug = ? ORDER BY tag", (slug,)
        ).fetchall()
        return [r["tag"] for r in rows]

    def _set_scene(self, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE scene SET {cols} WHERE id = 1", list(fields.values())
        )

    def _insert_entity(
        self,
        slug: str,
        nombre: str,
        tipo: str | None,
    ) -> None:
        clase = slug.split(".", 1)[0]
        tipo_p = tipo if clase in ("pc", "npc") else None
        tipo_l = tipo if clase == "loc" else None
        self.conn.execute(
            """
            INSERT INTO entidades (slug, clase, nombre, tipo_personaje, tipo_lugar)
            VALUES (?, ?, ?, ?, ?)
            """,
            (slug, clase, nombre, tipo_p, tipo_l),
        )
        if clase in ("pc", "npc"):
            self.conn.execute(
                "INSERT OR IGNORE INTO nucleo (slug) VALUES (?)", (slug,)
            )

    def translate_packet(self, player: str) -> str:
        scene = self.get_scene()
        pc_slug = scene.get("pc")
        loc_slug = scene.get("location")
        pc = self._entity(pc_slug)
        loc = self._entity(loc_slug)
        npcs = [
            dict(r)
            for r in self.conn.execute(
                "SELECT slug, nombre, tipo_personaje FROM entidades WHERE clase = 'npc'"
            ).fetchall()
        ]
        state = {
            "scene": {
                "pc": pc_slug,
                "location": loc_slug,
                "atmosfera": scene.get("atmosfera"),
                "tropo": scene.get("tropo"),
                "time": {
                    "value": scene.get("time_value"),
                    "unit": scene.get("time_unit"),
                    "label": scene.get("time_label"),
                },
            },
            "pc": {
                "slug": pc_slug,
                "nombre": pc["nombre"] if pc else None,
                "nucleo": self._nucleo(pc_slug),
                "tags": self._tags_of(pc_slug),
            }
            if pc_slug
            else None,
            "lugar": {
                "slug": loc_slug,
                "nombre": loc["nombre"] if loc else None,
                "tipo": loc["tipo_lugar"] if loc else None,
            }
            if loc_slug
            else None,
            "npcs": npcs,
            "catalogo": {
                "tipos_personaje": self.ids("tipos_personaje"),
                "tipos_lugar": self.ids("tipos_lugar"),
                "atmosferas": self.ids("atmosferas"),
                "tropos": self.ids("tropos"),
            },
        }
        return (
            f"Acción del jugador:\n{player}\n\n"
            f"Estado actual:\n{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
            "JSON de intención de este turno. Sin narrative."
        )

    def apply_intent(self, intent: dict[str, Any]) -> None:
        self._apply_nuevos(intent.get("nuevos"))
        self._ensure_pc()
        self._apply_lugar(intent.get("lugar"))
        self._apply_anchor("atmosfera", intent.get("atmosfera"), "atmosferas")
        self._apply_anchor("tropo", intent.get("tropo"), "tropos")
        self._apply_deltas(intent.get("deltas"), intent.get("objetivos"))
        self._apply_tags(intent.get("tags"), intent.get("objetivos"))
        scene = self.get_scene()
        self._set_scene(time_value=(scene.get("time_value") or 0) + 1)

    def _apply_nuevos(self, nuevos: Any) -> None:
        if not isinstance(nuevos, list):
            return
        created = 0
        for item in nuevos:
            if created >= MAX_NUEVOS:
                break
            if not isinstance(item, dict):
                continue
            raw = item.get("slug")
            if not isinstance(raw, str):
                continue
            tipo = item.get("tipo") if isinstance(item.get("tipo"), str) else ""
            tipo = _ascii_slug(tipo) if tipo else ""
            prefix = "loc" if tipo and self._exists_id("tipos_lugar", tipo) else "npc"
            slug = _normalize_slug(raw, default_prefix=prefix)
            if not slug:
                continue
            if self._entity(slug):
                continue
            clase = slug.split(".", 1)[0]
            if clase == "loc":
                if tipo and not self._exists_id("tipos_lugar", tipo):
                    tipo = ""
            else:
                if not tipo or not self._exists_id("tipos_personaje", tipo):
                    tipo = (
                        "heroe"
                        if clase == "pc"
                        else "ciudadano"
                    )
                    if not self._exists_id("tipos_personaje", tipo):
                        tipo = ""
            nombre = item.get("nombre")
            if not isinstance(nombre, str) or not nombre.strip():
                nombre = slug.split(".", 1)[1].replace("_", " ").title()
            self._insert_entity(slug, nombre.strip(), tipo or None)
            created += 1
            scene = self.get_scene()
            if clase == "pc" and not scene.get("pc"):
                self._set_scene(pc=slug)
            if clase == "loc" and not scene.get("location"):
                self._set_scene(location=slug)

    def _ensure_pc(self) -> None:
        scene = self.get_scene()
        if scene.get("pc"):
            return
        slug = "pc.jugador"
        if not self._entity(slug):
            tipo = "heroe" if self._exists_id("tipos_personaje", "heroe") else None
            self._insert_entity(slug, "Jugador", tipo)
        self._set_scene(pc=slug)

    def _apply_lugar(self, lugar: Any) -> None:
        if not isinstance(lugar, str) or not lugar.strip():
            return
        raw = lugar.strip()
        slug: str | None = None
        tipo: str | None = None
        ident = _ascii_slug(raw)
        if self._exists_id("tipos_lugar", ident):
            slug = f"loc.{ident}"
            tipo = ident
        else:
            slug = _normalize_slug(raw, default_prefix="loc")
        if not slug or not slug.startswith("loc."):
            return
        if not self._entity(slug):
            nombre = slug.split(".", 1)[1].replace("_", " ").title()
            self._insert_entity(slug, nombre, tipo)
        if not self.get_scene().get("location"):
            self._set_scene(location=slug)
        else:
            self._set_scene(location=slug)

    def _apply_anchor(self, field: str, value: Any, table: str) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        ident = _ascii_slug(value)
        if self._exists_id(table, ident):
            self._set_scene(**{field: ident})

    def _resolve_objetivo(self, token: str) -> str | None:
        slug = _normalize_slug(token)
        if slug and self._entity(slug):
            return slug
        row = self.conn.execute(
            "SELECT slug FROM entidades WHERE lower(nombre) = lower(?)",
            (token.strip(),),
        ).fetchone()
        return row["slug"] if row else None

    def _delta_targets(self, objetivos: Any) -> list[str]:
        slugs: list[str] = []
        if isinstance(objetivos, list):
            for token in objetivos:
                if not isinstance(token, str):
                    continue
                found = self._resolve_objetivo(token)
                if found and found not in slugs:
                    slugs.append(found)
        actors = [s for s in slugs if s.startswith(("pc.", "npc."))]
        if actors:
            return actors[:2]
        pc = self.get_scene().get("pc")
        return [pc] if pc else []

    def _apply_deltas(self, deltas: Any, objetivos: Any) -> None:
        if not isinstance(deltas, dict):
            return
        targets = self._delta_targets(objetivos)
        for slug in targets:
            if not self._nucleo(slug):
                self.conn.execute(
                    "INSERT OR IGNORE INTO nucleo (slug) VALUES (?)", (slug,)
                )
            current = self._nucleo(slug) or {
                "afinidad": 0.5,
                "dominancia": 0.5,
                "estres": 0.0,
            }
            updates: dict[str, float] = {}
            for key in CORE_KEYS:
                if key not in deltas:
                    continue
                try:
                    delta = float(deltas[key])
                except (TypeError, ValueError):
                    continue
                delta = max(-_DELTA_CAP, min(_DELTA_CAP, delta))
                updates[key] = _clamp01(float(current[key]) + delta)
            if updates:
                cols = ", ".join(f"{k} = ?" for k in updates)
                self.conn.execute(
                    f"UPDATE nucleo SET {cols} WHERE slug = ?",
                    [*updates.values(), slug],
                )

    def _apply_tags(self, tags: Any, objetivos: Any) -> None:
        if not isinstance(tags, list):
            return
        targets = self._delta_targets(objetivos)
        if not targets:
            return
        added = 0
        for raw in tags:
            if added >= MAX_TAGS:
                break
            if not isinstance(raw, str):
                continue
            tag = _ascii_slug(raw)
            if not tag:
                continue
            origen = "catalogo" if self._exists_id("tropos", tag) else "fuzzy"
            for slug in targets:
                self.conn.execute(
                    "INSERT OR IGNORE INTO tags (slug, tag, origen) VALUES (?, ?, ?)",
                    (slug, tag, origen),
                )
            added += 1

    def _familia_de(self, empuje_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT familia FROM empujes WHERE id = ?", (empuje_id,)
        ).fetchone()
        if row and row["familia"]:
            return row["familia"]
        return None

    def _empuje_de(self, table: str, ident: str) -> str | None:
        row = self.conn.execute(
            f"SELECT empuje FROM {table} WHERE id = ?", (ident,)
        ).fetchone()
        if row and row["empuje"]:
            return row["empuje"]
        return None

    def active_anchors(self) -> list[tuple[str, str]]:
        scene = self.get_scene()
        out: list[tuple[str, str]] = []
        if scene.get("atmosfera"):
            out.append(("atmosfera", scene["atmosfera"]))
            emp = self._empuje_de("atmosferas", scene["atmosfera"])
            if emp:
                out.append(("empuje", emp))
        if scene.get("tropo"):
            out.append(("tropo", scene["tropo"]))
            emp = self._empuje_de("tropos", scene["tropo"])
            if emp:
                out.append(("empuje", emp))
        loc = self._entity(scene.get("location"))
        if loc and loc.get("tipo_lugar"):
            out.append(("tipo_lugar", loc["tipo_lugar"]))
            emp = None
            if scene.get("atmosfera"):
                emp = self._empuje_de("atmosferas", scene["atmosfera"])
            if not emp and scene.get("tropo"):
                emp = self._empuje_de("tropos", scene["tropo"])
            fam = self._familia_de(emp) if emp else None
            if fam:
                out.append(("cruce", f"{loc['tipo_lugar']}+{fam}"))
        pc = self._entity(scene.get("pc"))
        if pc and pc.get("tipo_personaje"):
            out.append(("tipo_personaje", pc["tipo_personaje"]))
        for row in self.conn.execute(
            "SELECT tipo_personaje FROM entidades "
            "WHERE clase = 'npc' AND tipo_personaje IS NOT NULL"
        ):
            out.append(("tipo_personaje", row["tipo_personaje"]))
        if not out:
            out.append(("prosa", "saludo"))
        seen: set[tuple[str, str]] = set()
        uniq: list[tuple[str, str]] = []
        for pair in out:
            if pair not in seen:
                seen.add(pair)
                uniq.append(pair)
        return uniq

    def sample_frases(self, n: int = SAMPLE_FRASES) -> list[dict[str, str]]:
        anchors = self.active_anchors()
        placeholders = ",".join("(?, ?)" for _ in anchors)
        flat = [x for pair in anchors for x in pair]
        rows = self.conn.execute(
            f"""
            SELECT ancla_tipo, ancla_id, clase, texto FROM frases
            WHERE (ancla_tipo, ancla_id) IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT ?
            """,
            [*flat, n],
        ).fetchall()
        return [dict(r) for r in rows]

    def narration_packet(self, player: str, intent: dict[str, Any]) -> str:
        scene = self.get_scene()
        pc_slug = scene.get("pc")
        loc_slug = scene.get("location")
        pc = self._entity(pc_slug)
        loc = self._entity(loc_slug)
        others = []
        for row in self.conn.execute(
            "SELECT slug, nombre, tipo_personaje FROM entidades WHERE clase = 'npc'"
        ):
            others.append(
                {
                    "nombre": row["nombre"],
                    "tipo": row["tipo_personaje"],
                    "nucleo": self._nucleo(row["slug"]),
                    "tags": self._tags_of(row["slug"]),
                }
            )
        pack = {
            "tu": {
                "nombre": pc["nombre"] if pc else "Jugador",
                "nucleo": self._nucleo(pc_slug),
                "tags": self._tags_of(pc_slug),
            },
            "lugar": {
                "nombre": loc["nombre"] if loc else None,
                "tipo": loc["tipo_lugar"] if loc else None,
            },
            "atmosfera": scene.get("atmosfera"),
            "tropo": scene.get("tropo"),
            "otros": others,
            "acto": intent.get("acto"),
            "objetivos": intent.get("objetivos") or [],
        }
        frases = self.sample_frases()
        nombres = ", ".join(o["nombre"] for o in others) or "(nadie más)"
        lugar_n = (loc["nombre"] if loc else "un sitio sin nombre")
        lines = [
            f"Narrá esto: tú ({pack['tu']['nombre']}) haces «{intent.get('acto') or 'actuar'}» "
            f"en {lugar_n}. Presentes: {nombres}.",
            "",
            f"Acción del jugador (ya resuelta, no la reinterpretés):\n{player}",
            "",
            "Estado ya aplicado:",
            json.dumps(pack, ensure_ascii=False, indent=2),
            "",
            "Fragmentos a ensamblar (no inventes sensorial fuera de esta lista):",
        ]
        if frases:
            for f in frases:
                lines.append(f"- ({f['clase']}) {f['texto']}")
        else:
            lines.append("- (fragmento) Estás donde el motor dice que estás.")
        return "\n".join(lines)

    def append_prose(self, text: str) -> None:
        self.conn.execute("INSERT INTO prosa (texto) VALUES (?)", (text,))

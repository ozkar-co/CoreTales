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
_HECHOS_MAX = 30
_USADAS_MAX = 24
_HOSTILE_TIPOS = {
    "rival",
    "antagonista",
    "sombra",
    "guardian",
    "rival_afectivo",
}
_OPEN_TIPOS = {"amante", "provocador", "companera"}
_NUCLEO_TIPO = {
    "rival": (0.2, 0.65, 0.4),
    "rival_afectivo": (0.25, 0.6, 0.4),
    "antagonista": (0.15, 0.7, 0.45),
    "sombra": (0.25, 0.6, 0.4),
    "jefe": (0.4, 0.7, 0.25),
    "guardian": (0.3, 0.6, 0.35),
    "companera": (0.55, 0.45, 0.15),
    "amante": (0.7, 0.45, 0.2),
    "provocador": (0.6, 0.5, 0.25),
}
_CORRECTION_RE = re.compile(
    r"(^\s*no\b.{0,80}?\b(era|fue|sobre)\b)|(\bno era\b)|(\bera sobre\b)",
    re.I | re.S,
)
_HOSTILE_TAGS = {
    "desprecia",
    "odio",
    "hostil",
    "rechazo",
    "violencia",
    "asco",
}
_STRIP_ACTOS = {"desvestir"}
_EXHIBIT_ACTOS = {"sacudir", "exhibir", "mostrar"}
_TIPO_ALIAS = {
    "provocadora": "provocador",
    "provocativo": "provocador",
    "exhibicionista": "provocador",
    "secretaria": "subalterno",
    "secretario": "subalterno",
    "trabajador": "ciudadano",
    "jefa": "jefe",
}
_SLUG_TIPO = {
    "jefe": "jefe",
    "jefa": "jefe",
    "ivy": "companera",
    "rival": "rival",
    "antagonista": "antagonista",
    "sombra": "sombra",
    "guardian": "guardian",
}
_MOVE_ACTOS = {
    "ir",
    "entrar",
    "salir",
    "caminar",
    "acercar",
    "acercarse",
    "mover",
    "volver",
}
_CONTACT_ACTOS = {
    "tocar",
    "besar",
    "agarrar",
    "acariciar",
    "lamer",
    "morder",
    "desvestir",
    "follar",
    "coger",
    "meter",
    "penetrar",
    "chupar",
    "introducir",
}
_BODY_TAGS = {
    "desnuda",
    "desnudo",
    "cuerpo_expuesto",
    "exhibicionista",
    "exhibicion",
    "provocativa",
    "senos",
    "vestimenta_provocativa",
}
_STALE_TROPO = {"chisme_oficina", "chisme", "cotidiano", "cotidianidad"}
_ACTO_TROPO = {
    "tocar": "roce",
    "besar": "seduccion",
    "acariciar": "roce",
    "ir": "seduccion",
}
_ROPA_WORDS = (
    "gafete",
    "falda",
    "camisa",
    "vestida",
    "ropa",
    "botón",
    "boton",
)
_NO_CONTACT_WORDS = (
    "se podría tocar y no",
    "se podria tocar y no",
    "nada “pasa”",
    "nada pasa",
    "nada 'pasa'",
)


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
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        if catalog_empty(self.conn):
            import_catalog(self.conn)
        self._ensure_instance()
        self._last_sampled: list[str] = []
        raw_last = self._meta_json("last_intent", None)
        self.last_intent: dict[str, Any] | None = (
            raw_last if isinstance(raw_last, dict) else None
        )
        self.last_player: str = ""

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
            seed = _NUCLEO_TIPO.get(tipo or "")
            if seed:
                self.conn.execute(
                    "UPDATE nucleo SET afinidad=?, dominancia=?, estres=? "
                    "WHERE slug=?",
                    (*seed, slug),
                )

    def translate_packet(self, player: str) -> str:
        scene = self.get_scene()
        pc_slug = scene.get("pc")
        loc_slug = scene.get("location")
        pc = self._entity(pc_slug)
        loc = self._entity(loc_slug)
        npcs = []
        for r in self.conn.execute(
            "SELECT slug, nombre, tipo_personaje FROM entidades WHERE clase = 'npc'"
        ):
            item = dict(r)
            item["postura"] = self._stance(item["slug"])
            npcs.append(item)
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
            "hechos": self._hechos(),
            "foco": self._meta_json("foco", ""),
            "ultimo_acto": (self.last_intent or {}).get("acto") or "",
        }
        return (
            f"Acción del jugador:\n{player}\n\n"
            f"Estado actual:\n{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
            "JSON de intención de este turno. Sin narrative.\n"
            "foco: 'sus/ella' es el foco, no el NPC más cómodo.\n"
            "Un rival, antagonista o alguien que desprecia NO cede: deltas de afinidad negativos o cero; "
            "tags desprecia/hostil, nunca desnuda ni provocativa inventadas.\n"
            "Si el jugador corrige ('no, era X'), repetí el acto anterior sobre el NPC correcto.\n"
            "tipos_personaje útiles: companera, jefe, provocador, amante, rival, "
            "subalterno, ciudadano, heroe.\n"
            "tipos_lugar útiles: oficina, despacho, cubiculo, pasillo, calle.\n"
            "atmosferas útiles: laboral, erotica, tensa, fria, clandestina, "
            "erotica_laboral, vigilada.\n"
            "tropos útiles: roce, seduccion, exhibicion, exposicion, mirada, "
            "chisme_oficina, cotidiano, vigilancia, tentacion."
        )

    def apply_intent(self, intent: dict[str, Any], player: str = "") -> None:
        acto = _ascii_slug(intent.get("acto") or "")
        self._apply_nuevos(intent.get("nuevos"))
        self._spawn_from_tokens(intent.get("objetivos"))
        self._ensure_pc()
        self._apply_lugar(intent.get("lugar"), acto)
        self._apply_anchor("atmosfera", intent.get("atmosfera"), "atmosferas")
        self._apply_anchor("tropo", intent.get("tropo"), "tropos")
        self._nudge_tone(acto, intent.get("tags"))
        deltas = self._filter_deltas(intent.get("deltas"), intent.get("objetivos"))
        self._apply_deltas(deltas, intent.get("objetivos"))
        if acto in _CONTACT_ACTOS and not (
            isinstance(deltas, dict) and deltas
        ):
            if self._any_hostile(intent.get("objetivos")):
                self._apply_deltas(
                    {"afinidad": -0.08, "estres": 0.12},
                    intent.get("objetivos"),
                )
            else:
                self._apply_deltas(
                    {"afinidad": 0.08, "dominancia": 0.12},
                    intent.get("objetivos"),
                )
        self._apply_tags(
            intent.get("tags"),
            intent.get("objetivos"),
            intent.get("nuevos"),
            acto=acto,
        )
        for slug in self._delta_targets(intent.get("objetivos")):
            self._strip_hostile_body(slug)
        self._apply_player_stance(player, intent)
        self._record_hechos(acto, intent)
        self._set_foco(intent)
        scene = self.get_scene()
        self._set_scene(time_value=(scene.get("time_value") or 0) + 1)
        self.last_intent = intent
        self.last_player = player

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
            tipo = _TIPO_ALIAS.get(tipo, tipo)
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
                tipo = _TIPO_ALIAS.get(tipo, tipo)
                if not tipo or not self._exists_id("tipos_personaje", tipo):
                    rest = slug.split(".", 1)[1]
                    tipo = _SLUG_TIPO.get(rest, "")
                    if not tipo or not self._exists_id("tipos_personaje", tipo):
                        tipo = "heroe" if clase == "pc" else "companera"
                    if not self._exists_id("tipos_personaje", tipo):
                        tipo = "ciudadano" if self._exists_id(
                            "tipos_personaje", "ciudadano"
                        ) else ""
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

    def _spawn_from_tokens(self, tokens: Any) -> None:
        if not isinstance(tokens, list):
            return
        created = 0
        for token in tokens:
            if created >= MAX_NUEVOS:
                break
            if not isinstance(token, str) or not token.strip():
                continue
            rest_guess = _ascii_slug(token.split(".")[-1])
            prefix = "loc" if self._exists_id("tipos_lugar", rest_guess) else "npc"
            slug = _normalize_slug(token, default_prefix=prefix)
            if not slug or slug.startswith("pc."):
                continue
            if self._exists_id("tipos_lugar", rest_guess) and not slug.startswith("loc."):
                slug = f"loc.{rest_guess}"
            if self._entity(slug):
                continue
            rest = slug.split(".", 1)[1]
            if slug.startswith("loc."):
                tipo = rest if self._exists_id("tipos_lugar", rest) else None
                nombre = rest.replace("_", " ").title()
            else:
                tipo = _SLUG_TIPO.get(rest, "")
                if not tipo and rest in _HOSTILE_TIPOS:
                    tipo = rest
                if not tipo or not self._exists_id("tipos_personaje", tipo):
                    tipo = "companera"
                nombre = "el jefe" if rest in ("jefe", "jefa") else rest.replace("_", " ").title()
            self._insert_entity(slug, nombre, tipo)
            created += 1

    def _apply_lugar(self, lugar: Any, acto: str = "") -> None:
        if not isinstance(lugar, str) or not lugar.strip():
            return
        raw = lugar.strip()
        slug: str | None = None
        tipo: str | None = None
        low = raw.lower()
        if low.startswith("loc."):
            ident = _ascii_slug(low[4:])
            if ident:
                slug = f"loc.{ident}"
                if self._exists_id("tipos_lugar", ident):
                    tipo = ident
        else:
            ident = _ascii_slug(raw)
            if self._exists_id("tipos_lugar", ident):
                slug = f"loc.{ident}"
                tipo = ident
            else:
                slug = _normalize_slug(raw, default_prefix="loc")
        if not slug or not slug.startswith("loc."):
            return
        ent = self._entity(slug)
        if not ent:
            nombre = slug.split(".", 1)[1].replace("_", " ").title()
            self._insert_entity(slug, nombre, tipo)
        elif tipo and not ent.get("tipo_lugar"):
            self.conn.execute(
                "UPDATE entidades SET tipo_lugar = ? WHERE slug = ?",
                (tipo, slug),
            )
        current = self.get_scene().get("location")
        if not current or acto in _MOVE_ACTOS:
            self._set_scene(location=slug)

    def _nudge_tone(self, acto: str, tags: Any) -> None:
        tagset = {
            _ascii_slug(t)
            for t in (tags if isinstance(tags, list) else [])
            if isinstance(t, str)
        }
        for slug, _tag in (
            (r["slug"], r["tag"])
            for r in self.conn.execute("SELECT slug, tag FROM tags")
        ):
            if slug.startswith("npc."):
                tagset.add(_tag)
        scene = self.get_scene()
        tropo = scene.get("tropo") or ""
        atmo = scene.get("atmosfera") or ""
        body = bool(tagset & _BODY_TAGS)
        if body and atmo in ("", "laboral", "fria", "aburrida", "monotona"):
            if self._exists_id("atmosferas", "erotica"):
                self._set_scene(atmosfera="erotica")
        if body and (not tropo or tropo in _STALE_TROPO):
            pick = "exposicion" if self._exists_id("tropos", "exposicion") else "seduccion"
            if self._exists_id("tropos", pick):
                self._set_scene(tropo=pick)
        if acto in _CONTACT_ACTOS and (not tropo or tropo in _STALE_TROPO):
            pick = _ACTO_TROPO.get(acto, "roce")
            if self._exists_id("tropos", pick):
                self._set_scene(tropo=pick)
        if acto in _CONTACT_ACTOS and atmo in ("", "laboral", "fria"):
            if self._exists_id("atmosferas", "erotica"):
                self._set_scene(atmosfera="erotica")

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

    def _tag_targets(self, objetivos: Any, nuevos: Any) -> list[str]:
        slugs: list[str] = []
        if isinstance(objetivos, list):
            for token in objetivos:
                if not isinstance(token, str):
                    continue
                found = self._resolve_objetivo(token)
                if found and found not in slugs:
                    slugs.append(found)
        if isinstance(nuevos, list):
            for item in nuevos:
                if not isinstance(item, dict):
                    continue
                raw = item.get("slug")
                if not isinstance(raw, str):
                    continue
                slug = _normalize_slug(raw)
                if slug and self._entity(slug) and slug not in slugs:
                    slugs.append(slug)
        npcs = [s for s in slugs if s.startswith("npc.")]
        if npcs:
            return npcs[:1]
        actors = [s for s in slugs if s.startswith(("pc.", "npc."))]
        if actors:
            return actors[:2]
        pc = self.get_scene().get("pc")
        return [pc] if pc else []

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

    def _apply_tags(
        self,
        tags: Any,
        objetivos: Any,
        nuevos: Any = None,
        acto: str = "",
    ) -> None:
        if not isinstance(tags, list):
            return
        targets = self._tag_targets(objetivos, nuevos)
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
                if tag in _BODY_TAGS and acto not in _STRIP_ACTOS:
                    if tag not in self._tags_of(slug):
                        continue
                if tag in _BODY_TAGS and self._stance(slug) == "hostil":
                    continue
                self.conn.execute(
                    "INSERT OR IGNORE INTO tags (slug, tag, origen) VALUES (?, ?, ?)",
                    (slug, tag, origen),
                )
            added += 1
        for slug in targets:
            self._strip_hostile_body(slug)

    def _tipo_of(self, slug: str | None) -> str:
        ent = self._entity(slug)
        if not ent:
            return ""
        return ent.get("tipo_personaje") or ""

    def _stance(self, slug: str) -> str:
        tipo = self._tipo_of(slug)
        tags = set(self._tags_of(slug))
        nuc = self._nucleo(slug) or {}
        afin = float(nuc.get("afinidad") or 0.5)
        if tags & _HOSTILE_TAGS:
            if afin >= 0.8:
                return "abierta"
            return "hostil"
        if tipo in _HOSTILE_TIPOS:
            if afin >= 0.75:
                return "abierta"
            return "hostil"
        if tipo in _OPEN_TIPOS and afin >= 0.45:
            return "abierta"
        if afin < 0.35:
            return "hostil"
        if afin >= 0.6:
            return "abierta"
        return "neutra"

    def _any_hostile(self, objetivos: Any) -> bool:
        for slug in self._delta_targets(objetivos):
            if slug.startswith("npc.") and self._stance(slug) == "hostil":
                return True
        return False

    def _filter_deltas(self, deltas: Any, objetivos: Any) -> Any:
        if not isinstance(deltas, dict):
            return deltas
        if not self._any_hostile(objetivos):
            return deltas
        out = dict(deltas)
        try:
            af = float(out.get("afinidad", 0))
        except (TypeError, ValueError):
            af = 0.0
        if af > 0:
            out["afinidad"] = -min(af, _DELTA_CAP)
        return out

    def _strip_hostile_body(self, slug: str) -> None:
        if not slug.startswith("npc.") or self._stance(slug) != "hostil":
            return
        for tag in self._tags_of(slug):
            if tag in _BODY_TAGS:
                self.conn.execute(
                    "DELETE FROM tags WHERE slug = ? AND tag = ?",
                    (slug, tag),
                )

    def _apply_player_stance(self, player: str, intent: dict[str, Any]) -> None:
        low = (player or "").lower()
        marks = (
            "desprec",
            "odio",
            "hostil",
            "asco",
            "pelea",
            "golpe",
            "violencia",
        )
        if not any(w in low for w in marks):
            return
        targets = self._tag_targets(intent.get("objetivos"), intent.get("nuevos"))
        for slug in targets:
            if not slug.startswith("npc."):
                continue
            self.conn.execute(
                "INSERT OR IGNORE INTO tags (slug, tag, origen) VALUES (?, ?, ?)",
                (slug, "desprecia", "fuzzy"),
            )
            self._apply_deltas({"afinidad": -0.1, "estres": 0.08}, [slug])
            self._strip_hostile_body(slug)

    def _set_foco(self, intent: dict[str, Any]) -> None:
        targets = self._tag_targets(intent.get("objetivos"), intent.get("nuevos"))
        npcs = [s for s in targets if s.startswith("npc.")]
        if npcs:
            self._meta_set("foco", npcs[0])
        slim = {
            "acto": intent.get("acto"),
            "objetivos": intent.get("objetivos"),
            "deltas": intent.get("deltas"),
            "tags": intent.get("tags"),
        }
        self._meta_set("last_intent", slim)

    def patch_intent(self, player: str, intent: dict[str, Any]) -> dict[str, Any]:
        last = self.last_intent or self._meta_json("last_intent", None)
        if not isinstance(last, dict):
            return intent
        if not _CORRECTION_RE.search(player or ""):
            return intent
        patched = dict(intent)
        acto = _ascii_slug(intent.get("acto") or "")
        last_acto = last.get("acto") if isinstance(last.get("acto"), str) else ""
        if acto in ("observar", "mirar", "decir", "hablar", "") and last_acto:
            patched["acto"] = last_acto
        return patched

    def flush_journal(
        self,
        player: str,
        intent: dict[str, Any],
        prose: str,
    ) -> None:
        path = self.path.with_name(self.path.stem + ".journal.txt")
        scene = self.get_scene()
        turn = scene.get("time_value") or 0
        reacciones = self._npc_reactions(intent)
        reacc = "; ".join(
            f"{r['nombre']}: {r['reaccion']}" for r in reacciones
        )
        who = intent.get("objetivos") or []
        block = (
            f"=== turno {turn} ===\n"
            f"jugador: {(player or '').strip()}\n"
            f"acto: {intent.get('acto')} -> {who}\n"
            f"reaccion: {reacc or '(nadie)'}\n"
            f"{(prose or '').strip()}\n\n"
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(block)

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

    def _meta_json(self, clave: str, default: Any) -> Any:
        row = self.conn.execute(
            "SELECT valor FROM meta WHERE clave = ?", (clave,)
        ).fetchone()
        if not row or not row["valor"]:
            return default
        try:
            return json.loads(row["valor"])
        except json.JSONDecodeError:
            return default

    def _meta_set(self, clave: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO meta (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, json.dumps(value, ensure_ascii=False)),
        )

    def _hechos(self) -> list[str]:
        raw = self._meta_json("hechos", [])
        return raw if isinstance(raw, list) else []

    def _record_hechos(self, acto: str, intent: dict[str, Any]) -> None:
        hechos = self._hechos()
        names: list[str] = []
        if isinstance(intent.get("objetivos"), list):
            for token in intent["objetivos"]:
                if not isinstance(token, str):
                    continue
                slug = self._resolve_objetivo(token)
                ent = self._entity(slug) if slug else None
                if ent:
                    names.append(ent["nombre"])
        who = names[0] if names else ""
        if acto and who:
            hechos.append(f"Tú: {acto} → {who}.")
        for row in self.conn.execute(
            "SELECT e.nombre, t.tag FROM tags t "
            "JOIN entidades e ON e.slug = t.slug WHERE e.clase = 'npc'"
        ):
            if row["tag"] in _BODY_TAGS:
                hechos.append(f"{row['nombre']}: {row['tag']}.")
        # unique, keep last
        seen: set[str] = set()
        uniq: list[str] = []
        for h in hechos:
            if h in seen:
                continue
            seen.add(h)
            uniq.append(h)
        self._meta_set("hechos", uniq[-_HECHOS_MAX:])

    def _npc_reactions(self, intent: dict[str, Any]) -> list[dict[str, str]]:
        acto = _ascii_slug(intent.get("acto") or "")
        out: list[dict[str, str]] = []
        targets = self._tag_targets(intent.get("objetivos"), intent.get("nuevos"))
        for slug in targets:
            if not slug.startswith("npc."):
                continue
            ent = self._entity(slug)
            if not ent:
                continue
            stance = self._stance(slug)
            tags = set(self._tags_of(slug))
            naked = bool(tags & _BODY_TAGS)
            if stance == "hostil":
                if acto in _CONTACT_ACTOS:
                    text = (
                        "se aparta de golpe; empuja, muerde o golpea; "
                        "no cede la boca ni el cuerpo"
                    )
                elif acto in _EXHIBIT_ACTOS:
                    text = (
                        "asco y desprecio; se burla o amenaza; "
                        "no juega el mismo juego"
                    )
                elif acto in _MOVE_ACTOS:
                    text = "no te recibe; da un paso atras o te corta el paso"
                elif acto in {"observar", "mirar"}:
                    text = (
                        "sostiene la mirada con odio; no se cubre de deseo, "
                        "se cubre de desprecio"
                    )
                else:
                    text = "se opone; no se deja llevar"
            elif stance == "abierta":
                if acto in _CONTACT_ACTOS:
                    text = "cede al contacto; el cuerpo responde, no se aparta"
                elif acto in {"observar", "mirar"}:
                    if naked:
                        text = "sostiene la mirada; no se cubre; se sabe vista"
                    else:
                        text = "nota que la miras y no desvia del todo"
                elif acto in _MOVE_ACTOS:
                    text = "no retrocede; espera a que llegues"
                elif acto in {"hablar", "decir"}:
                    text = "contesta; la voz le sale mas baja o mas corta"
                else:
                    text = "reacciona: un gesto, no un adorno"
            else:
                if acto in _CONTACT_ACTOS:
                    text = (
                        "se queda helada; no corresponde; "
                        "aun no empuja pero tampoco cede"
                    )
                elif acto in {"observar", "mirar"}:
                    text = "nota la mirada y no sabe que hacer con ella"
                elif acto in _MOVE_ACTOS:
                    text = "duda; no se acerca ni se va"
                else:
                    text = "reacciona poco; no se entrega"
            out.append({"nombre": ent["nombre"], "reaccion": text})
        return out

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
        npcs = list(
            self.conn.execute(
                "SELECT tipo_personaje FROM entidades "
                "WHERE clase = 'npc' AND tipo_personaje IS NOT NULL"
            )
        )
        if npcs:
            for row in npcs:
                out.append(("tipo_personaje", row["tipo_personaje"]))
        elif pc and pc.get("tipo_personaje"):
            out.append(("tipo_personaje", pc["tipo_personaje"]))
        if not out:
            out.append(("prosa", "saludo"))
        seen: set[tuple[str, str]] = set()
        uniq: list[tuple[str, str]] = []
        for pair in out:
            if pair not in seen:
                seen.add(pair)
                uniq.append(pair)
        return uniq

    def sample_frases(
        self,
        n: int = SAMPLE_FRASES,
        acto: str = "",
        naked: bool = False,
        hostile: bool = False,
    ) -> list[dict[str, str]]:
        anchors = self.active_anchors()
        if not anchors:
            return []
        placeholders = ",".join("(?, ?)" for _ in anchors)
        flat = [x for pair in anchors for x in pair]
        rows = self.conn.execute(
            f"""
            SELECT ancla_tipo, ancla_id, clase, texto FROM frases
            WHERE (ancla_tipo, ancla_id) IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT ?
            """,
            [*flat, n * 6],
        ).fetchall()
        used = {str(x).lower() for x in self._meta_json("frases_usadas", [])}
        forbid = []
        if naked:
            forbid.extend(_ROPA_WORDS)
        if acto in _CONTACT_ACTOS:
            forbid.extend(_NO_CONTACT_WORDS)
        if hostile:
            forbid.extend(
                ("cede", "disfruta", "se entrega", "no se aparta", "invitación")
            )
        picked: list[dict[str, str]] = []
        ambient = 0
        for r in rows:
            item = dict(r)
            text = item["texto"]
            low = text.lower()
            if low in used:
                continue
            if any(w in low for w in forbid):
                continue
            is_amb = item["clase"] in ("ambiente", "fragmento") or item[
                "ancla_tipo"
            ] in ("tipo_lugar", "cruce")
            if is_amb:
                if ambient >= 2:
                    continue
                ambient += 1
            picked.append(item)
            if len(picked) >= n:
                break
        self._last_sampled = [p["texto"] for p in picked]
        return picked

    def narration_packet(self, player: str, intent: dict[str, Any]) -> str:
        scene = self.get_scene()
        pc_slug = scene.get("pc")
        loc_slug = scene.get("location")
        pc = self._entity(pc_slug)
        loc = self._entity(loc_slug)
        others = []
        naked = False
        for row in self.conn.execute(
            "SELECT slug, nombre, tipo_personaje FROM entidades WHERE clase = 'npc'"
        ):
            tags = self._tags_of(row["slug"])
            if set(tags) & _BODY_TAGS:
                naked = True
            others.append(
                {
                    "nombre": row["nombre"],
                    "tipo": row["tipo_personaje"],
                    "postura": self._stance(row["slug"]),
                    "nucleo": self._nucleo(row["slug"]),
                    "tags": tags,
                }
            )
        acto = _ascii_slug(intent.get("acto") or "")
        reacciones = self._npc_reactions(intent)
        hechos = self._hechos()
        hostile = any(
            r["reaccion"].startswith("se aparta")
            or "desprecio" in r["reaccion"]
            or "se opone" in r["reaccion"]
            or "asco" in r["reaccion"]
            for r in reacciones
        )
        pack = {
            "tu": {
                "nombre": pc["nombre"] if pc else "Jugador",
                "nucleo": self._nucleo(pc_slug),
            },
            "lugar": {
                "nombre": loc["nombre"] if loc else None,
                "tipo": loc["tipo_lugar"] if loc else None,
            },
            "atmosfera": scene.get("atmosfera"),
            "tropo": scene.get("tropo"),
            "acto": intent.get("acto"),
            "hechos": hechos,
            "reacciones": reacciones,
            "otros": others,
        }
        frases = self.sample_frases(acto=acto, naked=naked, hostile=hostile)
        reacc_txt = (
            "; ".join(f"{r['nombre']}: {r['reaccion']}" for r in reacciones)
            or "(nadie más en el acto)"
        )
        lines = [
            f"HECHO DEL TURNO: tú {intent.get('acto') or 'actuás'}.",
            f"REACCIONES (canon): {reacc_txt}",
            f"HECHOS QUE SIGUEN: {'; '.join(hechos) if hechos else '(ninguno aún)'}",
            "",
            f"Acción del jugador (ya pasó, narrala, no la niegues):\n{player}",
            "",
            "Estado:",
            json.dumps(pack, ensure_ascii=False, indent=2),
            "",
            "Condimento (recortar; no pegar si choca con el hecho):",
        ]
        if frases:
            for f in frases:
                lines.append(f"- ({f['clase']}) {f['texto']}")
        else:
            lines.append("- (fragmento) El sitio es el que dice el estado.")
        return "\n".join(lines)

    def append_prose(self, text: str) -> None:
        self.conn.execute("INSERT INTO prosa (texto) VALUES (?)", (text,))
        used = [str(x) for x in self._meta_json("frases_usadas", [])]
        used.extend(getattr(self, "_last_sampled", []))
        self._meta_set("frases_usadas", used[-_USADAS_MAX:])

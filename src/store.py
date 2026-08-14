"""Partida en SQLite. Catálogo de referencia + instancia.

El motor no tiene reglas por escena: la etapa 1 valora el acto en los ejes
de `mente`, el motor calcula impacto y desenlace, la etapa 2 solo viste.
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

import mente
from catalog import catalog_empty, import_catalog
from schema import (
    EXISTENCIAS,
    MAX_EVENTOS,
    MAX_NUEVOS,
    MAX_TAGS,
    MIGRACIONES,
    SAMPLE_FRASES,
    SCHEMA,
    SLUG_PREFIX,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAVE = ROOT / "saves" / "default.sqlite"

_SLUG_REST = re.compile(r"^[a-z0-9_]+$")
_USADAS_MAX = 24
_MAX_OBJETIVOS = 2
_TIPO_OBJETO = {"objeto", "cosa", "arma", "herramienta", "prenda", "libro"}
_TIPO_ALIAS = {
    "provocadora": "provocador",
    "provocativo": "provocador",
    "exhibicionista": "provocador",
    "secretaria": "subalterno",
    "secretario": "subalterno",
    "trabajador": "ciudadano",
    "jefa": "jefe",
}


def _ascii_slug(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")


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


def _bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "si", "sí", "yes")
    return bool(raw)


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
        self._migrar()
        if catalog_empty(self.conn):
            import_catalog(self.conn)
        self._ensure_instance()
        self._last_sampled: list[str] = []
        self.last_resolucion: list[dict[str, Any]] = []
        crudo = self._meta_json("last_intent", None)
        self.last_intent: dict[str, Any] | None = (
            crudo if isinstance(crudo, dict) else None
        )

    def close(self) -> None:
        self.conn.close()

    def begin(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def _migrar(self) -> None:
        """Columnas nuevas sobre partidas viejas. SQLite no las añade solo."""
        nuevas: set[str] = set()
        for tabla, columnas in MIGRACIONES.items():
            actuales = {
                r[1] for r in self.conn.execute(f"PRAGMA table_info({tabla})")
            }
            for col, decl in columnas.items():
                if col not in actuales:
                    self.conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {decl}")
                    nuevas.add(f"{tabla}.{col}")
        if "entidades.lugar" in nuevas:
            # sin esto, la gente de una partida vieja queda fuera de escena
            self.conn.execute(
                "UPDATE entidades SET lugar = (SELECT location FROM scene WHERE id = 1) "
                "WHERE clase IN ('pc', 'npc') AND lugar IS NULL"
            )

    def _ensure_instance(self) -> None:
        if self.conn.execute("SELECT 1 FROM scene WHERE id = 1").fetchone() is None:
            self.conn.execute("INSERT INTO scene (id) VALUES (1)")
        self.conn.commit()

    def ids(self, table: str) -> list[str]:
        rows = self.conn.execute(f"SELECT id FROM {table} ORDER BY id").fetchall()
        return [r["id"] for r in rows]

    def _exists_id(self, table: str, ident: str) -> bool:
        row = self.conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ?", (ident,)
        ).fetchone()
        return row is not None

    def _primero_que_exista(self, table: str, candidatos: tuple[str, ...]) -> str:
        for ident in candidatos:
            if self._exists_id(table, ident):
                return ident
        return ""

    def get_scene(self) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM scene WHERE id = 1").fetchone()
        return dict(row) if row else {}

    def _set_scene(self, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE scene SET {cols} WHERE id = 1", list(fields.values())
        )

    def _entity(self, slug: str | None) -> dict[str, Any] | None:
        if not slug:
            return None
        row = self.conn.execute(
            "SELECT * FROM entidades WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None

    def npcs(self) -> list[str]:
        return [
            r["slug"]
            for r in self.conn.execute(
                "SELECT slug FROM entidades WHERE clase = 'npc' ORDER BY slug"
            )
        ]

    def npcs_presentes(self) -> list[str]:
        """Quién está acá y sigue existiendo. Nadie te sigue por arte de magia."""
        loc = self.get_scene().get("location")
        return [
            r["slug"]
            for r in self.conn.execute(
                "SELECT slug FROM entidades WHERE clase = 'npc' "
                "AND existe = 'activo' AND lugar IS ? ORDER BY slug",
                (loc,),
            )
        ]

    def inventario(self) -> list[dict[str, Any]]:
        pc = self.get_scene().get("pc")
        if not pc:
            return []
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT nombre, cantidad FROM entidades WHERE clase = 'obj' "
                "AND existe = 'activo' AND dueno = ? ORDER BY slug",
                (pc,),
            )
        ]

    def cosas_del_lugar(self) -> list[dict[str, Any]]:
        loc = self.get_scene().get("location")
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT nombre, cantidad FROM entidades WHERE clase = 'obj' "
                "AND existe = 'activo' AND dueno IS NULL AND lugar IS ? ORDER BY slug",
                (loc,),
            )
        ]

    def fuera_de_escena(self) -> list[str]:
        """Lo que el modelo debe recordar pero no puede usar como presente."""
        loc = self.get_scene().get("location")
        out = []
        for r in self.conn.execute(
            "SELECT nombre, existe, lugar FROM entidades WHERE clase = 'npc' "
            "AND (existe != 'activo' OR lugar IS NOT ?) ORDER BY slug",
            (loc,),
        ):
            if r["existe"] == "activo":
                donde = "en otro sitio"
            elif r["lugar"] == loc:
                # el cuerpo sigue acá; el personaje no vuelve
                donde = f"{r['existe']}, acá"
            else:
                donde = f"{r['existe']}, en otro sitio"
            out.append(f"{r['nombre']} ({donde})")
        return out

    def _insert_entity(
        self,
        slug: str,
        nombre: str,
        tipo: str | None,
        lugar: str | None = None,
        dueno: str | None = None,
        cantidad: int = 1,
    ) -> None:
        clase = slug.split(".", 1)[0]
        self.conn.execute(
            """
            INSERT INTO entidades
                (slug, clase, nombre, tipo_personaje, tipo_lugar,
                 lugar, dueno, cantidad)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug,
                clase,
                nombre,
                tipo if clase in ("pc", "npc") else None,
                tipo if clase == "loc" else None,
                None if clase == "loc" or dueno else lugar,
                dueno,
                max(1, cantidad),
            ),
        )
        if clase in ("pc", "npc"):
            self._ensure_perfil(slug)

    # --- perfil: rasgos fijos, estado volátil, vínculos dirigidos ---

    def _ensure_perfil(self, slug: str) -> None:
        for rasgo, valor in mente.rasgos_base().items():
            self.conn.execute(
                "INSERT OR IGNORE INTO rasgos (slug, rasgo, valor) VALUES (?, ?, ?)",
                (slug, rasgo, valor),
            )
        for eje, valor in mente.estado_base().items():
            self.conn.execute(
                "INSERT OR IGNORE INTO estado (slug, eje, valor) VALUES (?, ?, ?)",
                (slug, eje, valor),
            )

    def _rasgos(self, slug: str) -> dict[str, float]:
        out = mente.rasgos_base()
        for r in self.conn.execute(
            "SELECT rasgo, valor FROM rasgos WHERE slug = ?", (slug,)
        ):
            if r["rasgo"] in mente.RASGOS:
                out[r["rasgo"]] = float(r["valor"])
        return out

    def _estado(self, slug: str) -> dict[str, float]:
        out = mente.estado_base()
        for r in self.conn.execute(
            "SELECT eje, valor FROM estado WHERE slug = ?", (slug,)
        ):
            if r["eje"] in mente.ESTADO:
                out[r["eje"]] = float(r["valor"])
        return out

    def _vinculo(self, origen: str, destino: str) -> dict[str, float]:
        out = mente.vinculo_base()
        for r in self.conn.execute(
            "SELECT eje, valor FROM vinculos WHERE origen = ? AND destino = ?",
            (origen, destino),
        ):
            if r["eje"] in mente.VINCULO:
                out[r["eje"]] = float(r["valor"])
        return out

    def _guardar_rasgos(self, slug: str, valores: dict[str, float]) -> None:
        for rasgo, valor in valores.items():
            self.conn.execute(
                "INSERT INTO rasgos (slug, rasgo, valor) VALUES (?, ?, ?) "
                "ON CONFLICT(slug, rasgo) DO UPDATE SET valor = excluded.valor",
                (slug, rasgo, mente.clamp01(valor)),
            )

    def _guardar_estado(self, slug: str, valores: dict[str, float]) -> None:
        for eje, valor in valores.items():
            self.conn.execute(
                "INSERT INTO estado (slug, eje, valor) VALUES (?, ?, ?) "
                "ON CONFLICT(slug, eje) DO UPDATE SET valor = excluded.valor",
                (slug, eje, mente.clamp01(valor)),
            )

    def _guardar_vinculo(
        self, origen: str, destino: str, valores: dict[str, float]
    ) -> None:
        for eje, valor in valores.items():
            self.conn.execute(
                "INSERT INTO vinculos (origen, destino, eje, valor) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(origen, destino, eje) DO UPDATE SET valor = excluded.valor",
                (origen, destino, eje, mente.clamp01(valor)),
            )

    def _sumar_estado(self, slug: str, deltas: dict[str, float]) -> dict[str, float]:
        actual = self._estado(slug)
        nuevo = {k: mente.clamp01(actual[k] + deltas.get(k, 0.0)) for k in actual}
        self._guardar_estado(slug, nuevo)
        return nuevo

    def _sumar_vinculo(
        self, origen: str, destino: str, deltas: dict[str, float]
    ) -> dict[str, float]:
        actual = self._vinculo(origen, destino)
        nuevo = {k: mente.clamp01(actual[k] + deltas.get(k, 0.0)) for k in actual}
        self._guardar_vinculo(origen, destino, nuevo)
        return nuevo

    def _tags_of(self, slug: str | None) -> list[str]:
        if not slug:
            return []
        rows = self.conn.execute(
            "SELECT tag FROM tags WHERE slug = ? ORDER BY tag", (slug,)
        ).fetchall()
        return [r["tag"] for r in rows]

    def perfil(self, slug: str) -> dict[str, Any]:
        """Ficha completa. La usan el paquete de narración y los logs."""
        ent = self._entity(slug) or {}
        pc = self.get_scene().get("pc")
        return {
            "slug": slug,
            "nombre": ent.get("nombre"),
            "tipo": ent.get("tipo_personaje"),
            "rasgos": self._rasgos(slug),
            "estado": self._estado(slug),
            "vinculo_con_pc": self._vinculo(slug, pc) if pc and pc != slug else {},
            "tags": self._tags_of(slug),
        }

    # --- etapa 1 ---

    def translate_packet(self, player: str) -> str:
        scene = self.get_scene()
        pc_slug = scene.get("pc")
        loc = self._entity(scene.get("location"))
        npcs = []
        for slug in self.npcs_presentes():
            ent = self._entity(slug) or {}
            npcs.append(
                {
                    "slug": slug,
                    "nombre": ent.get("nombre"),
                    "tipo": ent.get("tipo_personaje"),
                    "cantidad": ent.get("cantidad") or 1,
                    "estado": mente.resumen_estado(self._estado(slug)),
                    "siente_por_ti": mente.resumen_vinculo(
                        self._vinculo(slug, pc_slug)
                    )
                    if pc_slug
                    else "",
                    "tags": self._tags_of(slug),
                }
            )
        state = {
            "escena": {
                "lugar": loc["nombre"] if loc else None,
                "lugar_slug": scene.get("location"),
                "tipo_lugar": loc["tipo_lugar"] if loc else None,
                "turno": scene.get("time_value"),
            },
            "tu_estado": mente.resumen_estado(self._estado(pc_slug))
            if pc_slug
            else "",
            "npcs_presentes": npcs,
            "llevas": self.inventario(),
            "cosas_del_lugar": self.cosas_del_lugar(),
            "fuera_de_escena": self.fuera_de_escena(),
            "foco": self._meta_json("foco", ""),
            "ultimo_acto": (self.last_intent or {}).get("acto") or "",
            "hechos": self.hechos(),
        }
        return (
            f"Acción del jugador:\n{player}\n\n"
            f"Estado actual:\n{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
            "Devolvé el JSON de intención de este turno.\n"
            "Solo existe lo que está en el estado: si el jugador nombra algo que "
            "no está (una espada, un sitio, alguien), va en nuevos.\n"
            "Lo que está en fuera_de_escena no puede actuar: no lo pongas en objetivos.\n"
            "tipos_personaje útiles: companera, jefe, provocador, amante, rival, "
            "subalterno, ciudadano, heroe.\n"
            "tipos_lugar útiles: oficina, despacho, cubiculo, pasillo, calle, "
            "bosque, campo, camino.\n"
            "atmosferas útiles: laboral, erotica, tensa, hostil, violenta, oscura, "
            "humillante, fria.\n"
            "tropos útiles: roce, seduccion, exhibicion, mirada, rivalidad, "
            "rechazo, humillacion, huida, forcejeo, pelea."
        )

    # --- turno ---

    def apply_intent(
        self, intent: dict[str, Any], player: str = ""
    ) -> list[dict[str, Any]]:
        self._ensure_pc()
        origen = self.get_scene().get("location")
        movimiento = _bool(intent.get("movimiento"))
        self._apply_lugar(intent.get("lugar"), movimiento)
        # quien nace, nace donde está el jugador ahora
        self._apply_nuevos(intent.get("nuevos"))
        self._spawn_from_tokens(intent.get("objetivos"))
        if movimiento:
            self._mover_acompanantes(intent.get("objetivos"), origen)
        self._reposo_general()

        val = mente.valoracion(intent.get("valoracion"))
        objetivos = self._objetivos_npc(intent.get("objetivos"), intent.get("nuevos"))
        resoluciones = [self._resolver_npc(slug, val) for slug in objetivos]
        self.last_resolucion = resoluciones
        self._impacto_actor(val)
        self._aplicar_fuera(intent.get("fuera"))

        if self._acto_pasa(resoluciones):
            self._apply_tags(intent.get("tags"), objetivos)
        self._apply_anchor("atmosfera", intent.get("atmosfera"), "atmosferas")
        self._apply_anchor("tropo", intent.get("tropo"), "tropos")
        self._derivar_tono(objetivos, resoluciones, val)
        self._anotar_eventos(intent, resoluciones)

        if objetivos:
            self._meta_set("foco", objetivos[0])
        self._meta_set(
            "last_intent",
            {
                "acto": intent.get("acto"),
                "objetivos": intent.get("objetivos"),
                "valoracion": val,
            },
        )
        self.last_intent = intent
        scene = self.get_scene()
        self._set_scene(time_value=(scene.get("time_value") or 0) + 1)
        return resoluciones

    def _acto_pasa(self, resoluciones: list[dict[str, Any]]) -> bool:
        if not resoluciones:
            return True
        return any(r["desenlace"] in ("ocurre", "forzado") for r in resoluciones)

    def _reposo_general(self) -> None:
        activos = [
            r["slug"]
            for r in self.conn.execute(
                "SELECT slug FROM entidades WHERE clase = 'npc' AND existe = 'activo'"
            )
        ]
        for slug in [*activos, self.get_scene().get("pc")]:
            if not slug:
                continue
            self._guardar_estado(slug, mente.reposo(self._estado(slug)))

    def _impacto_actor(self, val: dict[str, float]) -> None:
        """Actuar cansa; descansar recupera. El jugador también tiene cuerpo."""
        pc = self.get_scene().get("pc")
        if pc:
            self._sumar_estado(pc, mente.coste_actor(val))

    def _aplicar_fuera(self, fuera: Any) -> None:
        """Quien muere o se va deja de estar. El motor no lo resucita solo."""
        if not isinstance(fuera, list):
            return
        turno = self.get_scene().get("time_value") or 0
        for item in fuera:
            if isinstance(item, str):
                item = {"slug": item, "existe": "ausente"}
            if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
                continue
            slug = self._resolve_objetivo(item["slug"])
            if not slug or slug.startswith("pc."):
                continue
            existe = _ascii_slug(str(item.get("existe") or "ausente"))
            if existe not in EXISTENCIAS:
                existe = "ausente"
            self.conn.execute(
                "UPDATE entidades SET existe = ? WHERE slug = ?", (existe, slug)
            )
            ent = self._entity(slug) or {}
            self.conn.execute(
                "INSERT INTO eventos (turno, slug, texto) VALUES (?, ?, ?)",
                (turno, slug, f"queda {existe} ({ent.get('nombre') or slug})"),
            )

    def _mover_acompanantes(self, objetivos: Any, origen: str | None) -> None:
        """Solo viene con vos quien es objeto del acto; el resto se queda."""
        destino = self.get_scene().get("location")
        if not destino or destino == origen:
            return
        for token in objetivos if isinstance(objetivos, list) else []:
            if not isinstance(token, str):
                continue
            slug = self._resolve_objetivo(token)
            if not slug or not slug.startswith("npc."):
                continue
            ent = self._entity(slug) or {}
            if ent.get("existe") == "activo" and ent.get("lugar") == origen:
                self.conn.execute(
                    "UPDATE entidades SET lugar = ? WHERE slug = ?", (destino, slug)
                )

    def _resolver_npc(self, slug: str, val: dict[str, float]) -> dict[str, Any]:
        pc = self.get_scene().get("pc") or "pc.jugador"
        self._ensure_perfil(slug)
        rasgos = self._rasgos(slug)
        estado_antes = self._estado(slug)
        vinculo_antes = self._vinculo(slug, pc)

        de, dv = mente.impacto(val, rasgos, vinculo_antes)
        estado = self._sumar_estado(slug, de)
        vinculo = self._sumar_vinculo(slug, pc, dv)

        res = mente.resolver(val, estado, rasgos, vinculo)
        de2, dv2 = mente.secuela(res, val)
        estado = self._sumar_estado(slug, de2)
        vinculo = self._sumar_vinculo(slug, pc, dv2)

        ent = self._entity(slug) or {}
        res.update(
            {
                "slug": slug,
                "nombre": ent.get("nombre") or slug,
                "reaccion": mente.FRASE_IMPULSO[res["impulso"]],
                "efecto": mente.FRASE_DESENLACE[res["desenlace"]],
                "estado_antes": estado_antes,
                "estado": estado,
                "vinculo_antes": vinculo_antes,
                "vinculo": vinculo,
            }
        )
        return res

    def _objetivos_npc(self, objetivos: Any, nuevos: Any) -> list[str]:
        """Sin objetivo no hay nadie: mirar el inventario no le pasa a un NPC."""
        presentes = set(self.npcs_presentes())
        slugs: list[str] = []
        for token in objetivos if isinstance(objetivos, list) else []:
            if not isinstance(token, str):
                continue
            found = self._resolve_objetivo(token)
            if found in presentes and found not in slugs:
                slugs.append(found)
        if not slugs:
            # aparecer en escena no es recibir el acto: solo se usan si no hay objetivo
            for item in nuevos if isinstance(nuevos, list) else []:
                if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
                    continue
                slug = _normalize_slug(item["slug"])
                if slug in presentes and slug not in slugs:
                    slugs.append(slug)
        return slugs[:_MAX_OBJETIVOS]

    def _resolve_objetivo(self, token: str) -> str | None:
        slug = _normalize_slug(token)
        if slug and self._entity(slug):
            return slug
        row = self.conn.execute(
            "SELECT slug FROM entidades WHERE lower(nombre) = lower(?)",
            (token.strip(),),
        ).fetchone()
        return row["slug"] if row else None

    # --- altas de entidades ---

    def _apply_nuevos(self, nuevos: Any) -> None:
        """Primero existen todos, después se les infiere el perfil.

        El vínculo apunta al PC, así que el PC tiene que estar antes.
        """
        altas = self._alta_entidades(nuevos)
        self._ensure_pc()
        for slug, item in altas:
            self._perfil_inferido(slug, item)

    def _alta_entidades(self, nuevos: Any) -> list[tuple[str, dict[str, Any]]]:
        if not isinstance(nuevos, list):
            return []
        altas: list[tuple[str, dict[str, Any]]] = []
        created = 0
        for item in nuevos:
            if created >= MAX_NUEVOS:
                break
            if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
                continue
            tipo = item.get("tipo") if isinstance(item.get("tipo"), str) else ""
            tipo = _TIPO_ALIAS.get(_ascii_slug(tipo), _ascii_slug(tipo)) if tipo else ""
            if tipo and self._exists_id("tipos_lugar", tipo):
                prefix = "loc"
            elif tipo in _TIPO_OBJETO or item.get("dueno"):
                prefix = "obj"
            else:
                prefix = "npc"
            slug = _normalize_slug(item["slug"], default_prefix=prefix)
            if not slug or self._entity(slug):
                continue
            clase = slug.split(".", 1)[0]
            rest = slug.split(".", 1)[1]
            if clase in ("loc", "obj"):
                if tipo and not self._exists_id("tipos_lugar", tipo):
                    tipo = ""
            elif not tipo or not self._exists_id("tipos_personaje", tipo):
                tipo = rest if self._exists_id("tipos_personaje", rest) else ""
                if not tipo:
                    tipo = "heroe" if clase == "pc" else "ciudadano"
                if not self._exists_id("tipos_personaje", tipo):
                    tipo = ""
            nombre = item.get("nombre")
            if not isinstance(nombre, str) or not nombre.strip():
                nombre = rest.replace("_", " ").title()
            dueno = None
            if clase == "obj":
                dueno = self._resolve_dueno(item.get("dueno"))
            cantidad = item.get("cantidad")
            self._insert_entity(
                slug,
                nombre.strip(),
                tipo or None,
                lugar=self.get_scene().get("location"),
                dueno=dueno,
                cantidad=cantidad if isinstance(cantidad, int) else 1,
            )
            created += 1
            if clase in ("pc", "npc"):
                altas.append((slug, item))
            scene = self.get_scene()
            if clase == "pc" and not scene.get("pc"):
                self._set_scene(pc=slug)
            if clase == "loc" and not scene.get("location"):
                self._set_scene(location=slug)
        return altas

    def _perfil_inferido(self, slug: str, item: dict[str, Any]) -> None:
        """Lo único que el LLM decide de un perfil: cómo nace. Después manda el motor."""
        self._guardar_rasgos(slug, mente.limpiar(item.get("rasgos"), mente.RASGOS))
        self._guardar_estado(slug, mente.limpiar(item.get("estado"), mente.ESTADO))
        pc = self.get_scene().get("pc")
        vinculo = mente.limpiar(item.get("vinculo"), mente.VINCULO)
        if pc and vinculo and slug != pc:
            base = mente.vinculo_base()
            base.update(vinculo)
            self._guardar_vinculo(slug, pc, base)

    def _resolve_dueno(self, raw: Any) -> str | None:
        """Una cosa sin dueño es decorado; con dueño, es inventario."""
        if not isinstance(raw, str) or not raw.strip():
            return None
        slug = self._resolve_objetivo(raw)
        if slug and (slug.startswith("pc.") or slug.startswith("npc.")):
            return slug
        return None

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
            if not slug or slug.startswith("pc.") or self._entity(slug):
                continue
            rest = slug.split(".", 1)[1]
            if slug.startswith("loc."):
                tipo = rest if self._exists_id("tipos_lugar", rest) else None
            elif slug.startswith("obj."):
                tipo = None
            else:
                tipo = rest if self._exists_id("tipos_personaje", rest) else None
            self._insert_entity(
                slug,
                rest.replace("_", " ").title(),
                tipo,
                lugar=self.get_scene().get("location"),
            )
            created += 1

    def _apply_lugar(self, lugar: Any, movimiento: bool) -> None:
        if not isinstance(lugar, str) or not lugar.strip():
            return
        raw = lugar.strip()
        low = raw.lower()
        slug: str | None = None
        tipo: str | None = None
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
            self._insert_entity(slug, slug.split(".", 1)[1].replace("_", " ").title(), tipo)
        elif tipo and not ent.get("tipo_lugar"):
            self.conn.execute(
                "UPDATE entidades SET tipo_lugar = ? WHERE slug = ?", (tipo, slug)
            )
        scene = self.get_scene()
        if slug != scene.get("location") and (not scene.get("location") or movimiento):
            # otro sitio, otra escena: el tono no viaja con el jugador
            self._set_scene(location=slug, atmosfera=None, tropo=None)
            if scene.get("pc"):
                self.conn.execute(
                    "UPDATE entidades SET lugar = ? WHERE slug = ?",
                    (slug, scene["pc"]),
                )

    # --- tono y tags ---

    def _apply_anchor(self, field: str, value: Any, table: str) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        ident = _ascii_slug(value)
        if self._exists_id(table, ident):
            self._set_scene(**{field: ident})

    def _derivar_tono(
        self,
        objetivos: list[str],
        resoluciones: list[dict[str, Any]],
        val: dict[str, float],
    ) -> None:
        """La atmósfera sigue lo que pasó, no el gusto del modelo."""
        atmo_cand: tuple[str, ...] = ()
        tropo_cand: tuple[str, ...] = ()
        for res in resoluciones:
            par = mente.TONO_DESENLACE.get(res["desenlace"])
            if par:
                atmo_cand, tropo_cand = par
                break
        if not atmo_cand:
            for res in resoluciones:
                # ceder a un acto que no toca a nadie no vuelve erótica la escena
                if res["impulso"] in ("ceder", "dominar") and not res["invasivo"]:
                    continue
                par = mente.TONO_IMPULSO.get(res["impulso"])
                if par and par[0]:
                    atmo_cand, tropo_cand = par
                    break
        if not atmo_cand:
            mejor = ("", 0.0)
            for slug in objetivos:
                eje, desvio = mente.dominante(self._estado(slug))
                if eje and desvio > mejor[1]:
                    mejor = (eje, desvio)
            if mejor[0] and mejor[1] >= 0.15:
                atmo_cand, tropo_cand = mente.TONO_ESTADO.get(mejor[0], ((), ()))
        if not atmo_cand and not resoluciones:
            # nadie recibió el acto: manda el acto, no la escena anterior
            for eje, umbral, atmos, tropos in mente.TONO_VALORACION:
                if val.get(eje, 0.0) >= umbral:
                    atmo_cand, tropo_cand = atmos, tropos
                    break
        atmo = self._primero_que_exista("atmosferas", atmo_cand)
        tropo = self._primero_que_exista("tropos", tropo_cand)
        if atmo:
            self._set_scene(atmosfera=atmo)
        if tropo:
            self._set_scene(tropo=tropo)

    def _apply_tags(self, tags: Any, objetivos: list[str]) -> None:
        if not isinstance(tags, list) or not objetivos:
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
            for slug in objetivos:
                self.conn.execute(
                    "INSERT OR IGNORE INTO tags (slug, tag, origen) VALUES (?, ?, ?)",
                    (slug, tag, origen),
                )
            added += 1

    # --- historia y hechos ---

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

    def _anotar_eventos(
        self, intent: dict[str, Any], resoluciones: list[dict[str, Any]]
    ) -> None:
        turno = self.get_scene().get("time_value") or 0
        acto = intent.get("acto") or "actúa"
        for res in resoluciones:
            if res["desenlace"] == "ocurre" and res["impulso"] in ("ceder", "dominar"):
                continue
            texto = f"{acto}: {res['reaccion']}; {res['efecto']}"
            self.conn.execute(
                "INSERT INTO eventos (turno, slug, texto) VALUES (?, ?, ?)",
                (turno, res["slug"], texto),
            )

    def hechos(self) -> list[str]:
        """Hechos vigentes, derivados del estado. No es un historial que se pudra."""
        out: list[str] = []
        pc = self.get_scene().get("pc")
        for slug in self.npcs_presentes():
            ent = self._entity(slug) or {}
            nombre = ent.get("nombre") or slug
            if (ent.get("cantidad") or 1) > 1:
                nombre = f"{nombre} (x{ent['cantidad']})"
            tags = self._tags_of(slug)
            if tags:
                out.append(f"{nombre}: {', '.join(tags)}.")
            if pc:
                v = self._vinculo(slug, pc)
                fuertes = [f"{eje} {v[eje]:.2f}" for eje in mente.VINCULO if v[eje] >= 0.5]
                if fuertes:
                    out.append(f"{nombre} siente por ti: {', '.join(fuertes)}.")
            estado = mente.resumen_estado(self._estado(slug))
            if estado != "en calma":
                out.append(f"{nombre} está: {estado}.")
        for row in self.conn.execute(
            "SELECT e.texto, n.nombre FROM eventos e "
            "LEFT JOIN entidades n ON n.slug = e.slug "
            "ORDER BY e.id DESC LIMIT ?",
            (MAX_EVENTOS,),
        ):
            out.append(f"Pasó con {row['nombre']}: {row['texto']}")
        return out

    # --- etapa 2 ---

    def _familia_de(self, empuje_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT familia FROM empujes WHERE id = ?", (empuje_id,)
        ).fetchone()
        return row["familia"] if row and row["familia"] else None

    def _empuje_de(self, table: str, ident: str) -> str | None:
        row = self.conn.execute(
            f"SELECT empuje FROM {table} WHERE id = ?", (ident,)
        ).fetchone()
        return row["empuje"] if row and row["empuje"] else None

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
        for row in self.conn.execute(
            "SELECT DISTINCT tipo_personaje FROM entidades "
            "WHERE clase = 'npc' AND existe = 'activo' AND lugar IS ? "
            "AND tipo_personaje IS NOT NULL",
            (scene.get("location"),),
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
        picked: list[dict[str, str]] = []
        ambient = 0
        for r in rows:
            item = dict(r)
            if item["texto"].lower() in used:
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
        pc = self._entity(scene.get("pc"))
        loc = self._entity(scene.get("location"))
        resoluciones = self.last_resolucion
        implicados = {r["slug"] for r in resoluciones}
        otros = []
        for slug in self.npcs_presentes():
            if slug in implicados:
                continue
            ent = self._entity(slug) or {}
            otros.append(
                {
                    "nombre": ent.get("nombre"),
                    "cantidad": ent.get("cantidad") or 1,
                    "estado": mente.resumen_estado(self._estado(slug)),
                    "tags": self._tags_of(slug),
                }
            )
        canon = []
        prohibido: list[str] = []
        for r in resoluciones:
            consent = ""
            if r["invasivo"]:
                consent = f" Consentido: {'sí' if r['consentido'] else 'NO'}."
            canon.append(
                f"- {r['nombre']}: {r['reaccion']}. {r['efecto']}.{consent} "
                f"Estado: {mente.resumen_estado(r['estado'])}. "
                f"Siente por ti: {mente.resumen_vinculo(r['vinculo'])}."
            )
            if r["invasivo"] and not r["consentido"]:
                prohibido.append(
                    f"{r['nombre']} NO consiente: prohibido escribir que cede, "
                    "disfruta, se entrega o provoca."
                )
            if r["desenlace"] in ("forcejeo", "bloqueado"):
                prohibido.append(
                    f"El acto contra {r['nombre']} no se completó: narralo trunco."
                )
            if r["desenlace"] == "forzado":
                prohibido.append(
                    f"Lo de {r['nombre']} es violencia, no sexo: sin erotismo."
                )
        if not prohibido:
            prohibido.append("Nada que contradiga el canon de arriba.")
        ausentes = self.fuera_de_escena()
        if ausentes:
            prohibido.append(
                "No están acá (no pueden hablar ni actuar): " + ", ".join(ausentes) + "."
            )
        pack = {
            "tu": {
                "nombre": pc["nombre"] if pc else "Jugador",
                "estado": mente.resumen_estado(self._estado(scene.get("pc")))
                if scene.get("pc")
                else "",
                "llevas": self.inventario(),
            },
            "lugar": {
                "nombre": loc["nombre"] if loc else None,
                "tipo": loc["tipo_lugar"] if loc else None,
                "cosas": self.cosas_del_lugar(),
            },
            "atmosfera": scene.get("atmosfera"),
            "tropo": scene.get("tropo"),
            "acto": intent.get("acto"),
            "otros_presentes": otros,
            "hechos": self.hechos(),
        }
        frases = self.sample_frases()
        lines = [
            f"ACTO DEL JUGADOR: {intent.get('acto') or 'actúa'}.",
            "CANON DEL MOTOR (manda sobre todo lo demás):",
            *(canon or ["- (nadie más implicado)"]),
            "PROHIBIDO:",
            *[f"- {p}" for p in prohibido],
            "",
            f"Lo que escribió el jugador (reescribilo en segunda persona):\n{player}",
            "",
            "Estado:",
            json.dumps(pack, ensure_ascii=False, indent=2),
            "",
            "Condimento (recortar; descartar lo que choque con el canon):",
        ]
        if frases:
            lines.extend(f"- ({f['clase']}) {f['texto']}" for f in frases)
        else:
            lines.append("- (fragmento) El sitio es el que dice el estado.")
        return "\n".join(lines)

    def append_prose(self, text: str) -> None:
        self.conn.execute("INSERT INTO prosa (texto) VALUES (?)", (text,))
        used = [str(x) for x in self._meta_json("frases_usadas", [])]
        used.extend(self._last_sampled)
        self._meta_set("frases_usadas", used[-_USADAS_MAX:])

    def flush_journal(
        self, player: str, intent: dict[str, Any], prose: str
    ) -> None:
        """Log humano, fuera de la base. Se escribe después del commit."""
        path = self.path.with_name(self.path.stem + ".journal.txt")
        turno = self.get_scene().get("time_value") or 0
        lines = [
            f"=== turno {turno:g} ===",
            f"jugador: {(player or '').strip()}",
            f"acto: {intent.get('acto')} -> {intent.get('objetivos') or []}",
        ]
        for r in self.last_resolucion:
            lines.append(
                f"{r['nombre']}: {r['impulso']}/{r['desenlace']} "
                f"({r['reaccion']}) | {mente.resumen_estado(r['estado'])}"
            )
        lines.append((prose or "").strip())
        lines.append("")
        with path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

"""DDL de la partida. SQLite es la fuente canónica."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS empujes (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    resumen TEXT NOT NULL DEFAULT '',
    familia TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tropos (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    resumen TEXT NOT NULL DEFAULT '',
    empuje TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tipos_historia (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    resumen TEXT NOT NULL DEFAULT '',
    empuje TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tipos_personaje (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    resumen TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tipos_lugar (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    resumen TEXT NOT NULL DEFAULT '',
    grupo TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS atmosferas (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    resumen TEXT NOT NULL DEFAULT '',
    empuje TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS frases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ancla_tipo TEXT NOT NULL,
    ancla_id TEXT NOT NULL,
    clase TEXT NOT NULL,
    texto TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_frases_ancla ON frases (ancla_tipo, ancla_id);

CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scene (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    pc TEXT,
    location TEXT,
    atmosfera TEXT,
    tropo TEXT,
    time_value REAL NOT NULL DEFAULT 0,
    time_unit TEXT NOT NULL DEFAULT 'day',
    time_label TEXT
);
CREATE TABLE IF NOT EXISTS entidades (
    slug TEXT PRIMARY KEY,
    clase TEXT NOT NULL,
    nombre TEXT NOT NULL,
    tipo_personaje TEXT,
    tipo_lugar TEXT
);
CREATE TABLE IF NOT EXISTS rasgos (
    slug TEXT NOT NULL,
    rasgo TEXT NOT NULL,
    valor REAL NOT NULL DEFAULT 0.5,
    PRIMARY KEY (slug, rasgo)
);
CREATE TABLE IF NOT EXISTS estado (
    slug TEXT NOT NULL,
    eje TEXT NOT NULL,
    valor REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (slug, eje)
);
CREATE TABLE IF NOT EXISTS vinculos (
    origen TEXT NOT NULL,
    destino TEXT NOT NULL,
    eje TEXT NOT NULL,
    valor REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (origen, destino, eje)
);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turno REAL NOT NULL DEFAULT 0,
    slug TEXT NOT NULL,
    texto TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    slug TEXT NOT NULL,
    tag TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'fuzzy',
    PRIMARY KEY (slug, tag)
);
CREATE TABLE IF NOT EXISTS prosa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL
);
"""

ANCHOR_TABLES = (
    "empujes",
    "tropos",
    "tipos_historia",
    "tipos_personaje",
    "tipos_lugar",
    "atmosferas",
)
ANCHOR_FILE = {
    "empujes": "empujes.txt",
    "tropos": "tropos.txt",
    "tipos_historia": "tipos_historia.txt",
    "tipos_personaje": "tipos_personaje.txt",
    "tipos_lugar": "tipos_lugar.txt",
    "atmosferas": "atmosferas.txt",
}
SLUG_PREFIX = ("pc.", "npc.", "loc.")
MAX_NUEVOS = 4
MAX_TAGS = 6
SAMPLE_FRASES = 6
MAX_EVENTOS = 12

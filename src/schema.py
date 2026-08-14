"""DDL de la partida. SQLite es la memoria."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS entidades (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    clase TEXT NOT NULL DEFAULT '',
    donde INTEGER,
    dueno INTEGER,
    activo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS rasgos (
    entidad INTEGER NOT NULL,
    texto TEXT NOT NULL,
    fuerza TEXT NOT NULL DEFAULT 'medio',
    PRIMARY KEY (entidad, texto)
);
CREATE TABLE IF NOT EXISTS linea (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turno INTEGER NOT NULL,
    texto TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS escena (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    tu INTEGER,
    aqui INTEGER,
    turno INTEGER NOT NULL DEFAULT 0
);
"""

FUERZAS = ("nulo", "debil", "medio", "fuerte", "extremo")
# Sesgo interno. El modelo nunca lo ve.
SESGO = {
    "nulo": 0.15,
    "debil": 0.30,
    "medio": 0.50,
    "fuerte": 0.70,
    "extremo": 0.85,
}

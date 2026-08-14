# CoreTales

Motor de aventura en texto. El mundo lo lleva Python; un LLM pequeño solo traduce la entrada y viste la salida.

Licencia: Unlicense. El contenido de cada partida es responsabilidad de quien juega.

## Qué es

Mezcla de novela gráfica, aventura conversacional y chat tipo Character AI / Dungeon AI, sin que el modelo sea la memoria ni el árbitro. El núcleo es estricto a propósito: así se evitan la adulación, la deriva de contexto y el contagio de persona.

- Por qué: [docs/Enfoque y decisiones.md](docs/Enfoque%20y%20decisiones.md)
- Mapa del sistema: [docs/Descripción del Proyecto.md](docs/Descripción%20del%20Proyecto.md)
- Fases: [docs/Hoja de Ruta.md](docs/Hoja%20de%20Ruta.md)

## Layout

```
src/            motor (dos etapas: traducir → aplicar → ensamblar)
scripts/        arranque, test_llm, import/export del catálogo
data/catalogo/  anclas y nubes en TSV (import/export; SQLite es canónica)
docs/           enfoque, descripción, hoja de ruta
saves/          una SQLite = una partida (gitignorado)
```

Stdlib. El LLM se asume ya sirviendo (llama.cpp u otro compatible OpenAI). La URL va en el adapter; `.env` solo secretos.

## Uso

Servidor en `http://127.0.0.1:8080/v1`, modelo **instruct** (un 3B basta para probar el ciclo). Luego:

```bash
./scripts/run.sh
CORE_TALES_DEBUG=1 ./scripts/run.sh
./scripts/test_llm.sh
python3 scripts/import_catalog.py   # txt → saves/default.sqlite
python3 scripts/export_catalog.py   # SQLite → data/catalogo/
```

El jugador solo ve prosa. Ctrl-D o Ctrl-C para salir. Tras un turno exitoso, el estado ya está en `saves/default.sqlite`.

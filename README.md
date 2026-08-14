# CoreTales

Motor de aventura en texto. El mundo vive en SQLite. El modelo elige tools y escribe la prosa. El sorteo lo hace el motor.

Licencia: Unlicense. El contenido de cada partida es responsabilidad de quien juega.

- Por qué: [docs/Enfoque y decisiones.md](docs/Enfoque%20y%20decisiones.md)
- Mapa: [docs/Descripción del Proyecto.md](docs/Descripción%20del%20Proyecto.md)
- Fases: [docs/Hoja de Ruta.md](docs/Hoja%20de%20Ruta.md)

## Layout

```
src/            motor (tools + sorteo + SQLite)
tests/escenas/  inputs del jugador
tests/run.py    corre escenas y deja logs como el chat
saves/          una SQLite = una partida
```

El modelo no es la memoria ni el árbitro. Consulta (`aqui`, `mirar`), crea lo nombrado (`nacer`), propone apuestas (`tirar`) y cierra con prosa (`decir`). El motor guarda entidades con rasgos de fuerza cualitativa (`nulo` … `extremo`) y sortea un valor en [0, 1] con curva normal.

## Uso

```bash
./scripts/run.sh
CORE_TALES_DEBUG=1 ./scripts/run.sh
OPENAI_MODEL=gpt-4o ./scripts/run.sh
python3 tests/run.py
python3 tests/run.py 04_bosque
```

Hace falta `OPENAI_API_KEY` en `.env`. El modelo por defecto es `gpt-4o`.

OpenRouter (p. ej. Venice sin filtro):

```bash
CORE_TALES_LLM=openrouter ./scripts/run.sh
CORE_TALES_LLM=openrouter python3 tests/run.py 39_venice
```

Clave: `OPENROUTER_API_KEY`. Modelo: `OPENROUTER_MODEL` o `cognitivecomputations/dolphin-mistral-24b-venice-edition`.

El jugador solo ve prosa. Ctrl-D o Ctrl-C para salir. Tras un turno, el estado está en `saves/default.sqlite` y el chat (input, debug, prosa) en `saves/default.journal.txt`.

Si la partida es del motor anterior, borra `saves/default.sqlite`.

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
src/            motor (dos etapas: traducir → resolver → ensamblar)
src/mente.py    ejes fijos y resolución: impacto, impulsos, desenlace
scripts/        arranque, test_llm, import/export del catálogo
data/catalogo/  anclas y nubes en TSV (import/export; SQLite es canónica)
tests/          banco de escenas guionadas con logs (no es una suite de tests)
docs/           enfoque, descripción, hoja de ruta
saves/          una SQLite = una partida (gitignorado)
```

El LLM interpreta y secuencia; no arbitra. La etapa 1 valora el acto en ejes
generales (intensidad, intimidad, agresión, exposición, afecto, dominio, reposo) e
infiere el perfil de quien aparece. El motor lleva los ejes fijos de cada
personaje (estado volátil, rasgos fijos, vínculos dirigidos), puntúa los
impulsos y decide el desenlace: `ocurre`, `forcejeo`, `forzado` o `bloqueado`.
Así un rival que te odia no cede porque el modelo quiera agradar.

El mundo se lleva con cuatro primitivas generales, sin sistemas por género:

- Presencia: cada entidad está en un lugar. Solo lo presente entra a la escena;
  quien no fue objeto del acto se queda donde estaba cuando el jugador se mueve.
- Existencia: `activo`, `muerto` o `ausente`. El que no está no reacciona, pero
  su cuerpo puede seguir en el sitio.
- Cosas: entidades `obj.` con dueño. El inventario es lo que tiene el jugador;
  sin dueño, queda en el lugar.
- Coste: actuar gasta energía y descansar la recupera, también en el jugador.

Stdlib. El LLM es un periférico: OpenAI si hay `OPENAI_API_KEY` en `.env`, si no llama.cpp en `http://127.0.0.1:8080/v1`. `.env` solo secretos.

## Uso

```bash
./scripts/run.sh
CORE_TALES_DEBUG=1 ./scripts/run.sh
CORE_TALES_LLM=llamacpp ./scripts/run.sh
OPENAI_MODEL=gpt-4o ./scripts/run.sh
./scripts/test_llm.sh
python3 scripts/import_catalog.py   # txt → saves/default.sqlite
python3 scripts/export_catalog.py   # SQLite → data/catalogo/
python3 scripts/fill_catalog.py     # lugares, atmósferas y nubes (cupos + cruces)
python3 scripts/fill_catalog.py --frases  # solo completar frases.txt
python3 tests/correr.py --seco       # escenas guionadas, sin LLM (ver tests/README.md)
python3 tests/correr.py              # escenas guionadas, ciclo completo
```

El jugador solo ve prosa. Ctrl-D o Ctrl-C para salir. Tras un turno exitoso, el estado ya está en `saves/default.sqlite` y el log humano en `saves/default.journal.txt`.

# Hoja de Ruta

El contrato está cerrado en [Descripción del Proyecto.md](Descripción%20del%20Proyecto.md). Primera versión = fase 1 usable; cada fase se apoya en la anterior y no la reescribe.

## Fase 1 — Conversar con el modelo (primera versión)

**Objetivo:** un LLM conectado, escena precargada en memoria, sin persistencia. El modelo entiende las instrucciones y responde JSON claro.

- Adapter real: HTTP compatible OpenAI. El servidor (llama.cpp u otro) se asume ya en marcha. La URL vive en el adapter; `.env` solo si hay secretos.
- Prompt de sistema en el núcleo: rol, JSON obligatorio, forma del objeto, escena (`scene.pc` / `location` / `time`).
- CLI: texto libre in, prosa out. `CORE_TALES_DEBUG=1` vuelca el JSON.
- Mundo mínimo en memoria (escena + un PC y un lugar de ejemplo, o escena vacía). Nada de SQLite.
- Reintento si el JSON sale malformado; si vuelve a fallar, informar y abortar el turno.

**Listo cuando:** se puede hablar varios turnos, el JSON es parseable de forma estable, y el modelo rellena o respeta quién / dónde / cuándo. Si esto no aguanta, no hay motor.

## Fase 2 — El núcleo como interlocutor

**Objetivo:** el LLM pide lo que no vino en la escena. Varias llamadas por input. Aquí se moldea CoreTales.

- Parsear `reads` / `ops` / `narrative`.
- Bucle interno: llamada → lecturas y ops sobre copia de trabajo → otra llamada → hasta `reads` vacío o tope 8.
- Estado en memoria, incluida `scene`. Disco todavía no.
- Un solo método síncrono en el adapter. El bucle vive en el núcleo.
- Cada petición independiente. El primer paquete es la escena; el resto, lo pedido.

**Listo cuando:** un input provoca idas y vueltas, el modelo consulta a demanda, actualiza escena y entidades, y la consola muestra solo prosa.

## Fase 3 — Partida usable

**Objetivo:** coherencia, SQLite, reanudar. Seed opcional.

- Una base = una partida. Tras cada turno exitoso, el estado (escena incluida) queda escrito.
- Reanudar: abrir el archivo. Histórico de prosa opcional en pantalla; la partida vive en entidades, hechos y escena.
- CLI agnóstica. Si falla, se informa.

**Listo cuando:** se cierra el proceso, se abre la misma partida, y quién / dónde / cuándo siguen donde quedaron.

## Fase 4 — Abierta (alfa)

Seeds, triggers, más adapters, presentes en la escena, lo que pida el uso real. Sin criterio de cierre.

## Fuera de alcance (hasta que el núcleo esté estable)

- UI gráfica, web, mapa 2D, multijugador
- Economía, combate o inventario hardcodeados
- Editor visual, marketplace, plugins
- Suite de tests / CI
- Un segundo lenguaje de runtime

## Dependencias

```
1 LLM + JSON + escena  →  2 núcleo (el modelo consulta al sistema)
                                →  3 partida (disco + reanudar)
                                      →  4 abierta (alfa)
```

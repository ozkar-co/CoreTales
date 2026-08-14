# Hoja de Ruta

El enfoque (por qué el LLM no simula el mundo) está en [Enfoque y decisiones.md](Enfoque%20y%20decisiones.md). El mapa del sistema, en [Descripción del Proyecto.md](Descripción%20del%20Proyecto.md).

El prototipo de una sola llamada (ops + narrativa juntas) sirvió para ver adulación, deriva y ops rotas. Las fases de abajo **no lo extienden**: montan el ciclo de dos etapas. Cada fase se puede jugar sola; la siguiente no la reescribe.

## Fase 1 — Traducir y vestir

**Objetivo:** dos llamadas cortas. El 3B clasifica; el motor aplica un estado mínimo; el 3B narra lo ya resuelto. Sin SQLite todavía.

- Etapa 1: JSON estricto (intención, entidades, deltas, tags). Sin `narrative`. Schema en el adapter.
- Motor: escena (`pc`, `location`, `time`) + núcleo 0–1 (afinidad, dominancia, estrés) + tags. Topes. El modelo no escribe el núcleo a pelo.
- Etapa 2: prompt rígido → prosa. Sin ops.
- CLI: texto libre in, prosa out. Debug vuelca las dos llamadas.
- Tope de ops/tags por turno para que un 3B no spawnee `oficina.1`…`oficina.28`.

**Listo cuando:** un input produce JSON de intención parseable, el motor mueve números, y la prosa no contradice quién es el PC. Si la etapa 1 no clasifica, no hay producto.

## Fase 2 — Máscara y umbrales

**Objetivo:** el género puede inclinarse sin reiniciar a la gente.

- Máscaras inyectadas según vector de género.
- Vectores y un beat mínimo (al menos: calma → incidente).
- Tags que persisten y se reinyectan.

**Listo cuando:** subir misterio cambia el vestuario del NPC y no borra la afinidad.

## Fase 3 — Partida en disco

**Objetivo:** una SQLite = una partida. Resumen enrollable. Reanudar.

- Commit al cerrar el turno con éxito. Sin botón de guardar.
- Prosa en log aparte; el modelo no la usa como memoria.
- Rolling state: un párrafo canónico cada N turnos.

**Listo cuando:** se cierra el proceso, se abre el archivo, núcleo / tags / escena / resumen siguen ahí.

## Fase 4 — Átomos offline

**Objetivo:** riqueza sin creatividad en vivo del 3B.

- Generar (otro modelo, otro momento) perfiles, reacciones, sensorial.
- El runtime solo selecciona e inyecta en la etapa 2.
- Paquete de aventura = seeder, no otro motor.

**Listo cuando:** una partida “llena” no exige que el 3B invente la ficha del jefe desde cero.

## Fase 5 — Abierta (alfa)

Más beats, más adapters, lo que pida el uso real. Sin criterio de cierre.

## Fuera de alcance (hasta que el ciclo de dos etapas sea aburrido de tan estable)

- UI gráfica, web, mapa 2D, multijugador
- Combate o inventario hardcodeados
- Editor visual
- Suite de tests / CI
- Un segundo lenguaje de runtime

## Dependencias

```
1 traducir + vestir  →  2 máscara y vectores
                              →  3 disco + resumen
                                    →  4 átomos offline
                                          →  5 alfa
```

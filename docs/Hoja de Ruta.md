# Hoja de Ruta

El enfoque (por qué el LLM no simula el mundo) está en [Enfoque y decisiones.md](Enfoque%20y%20decisiones.md). El mapa del sistema, en [Descripción del Proyecto.md](Descripción%20del%20Proyecto.md).

El prototipo de una sola llamada (ops + narrativa juntas) sirvió para ver adulación, deriva y ops rotas. Las fases de abajo **no lo extienden**: montan el ciclo de dos etapas. Cada fase se puede jugar sola; la siguiente no la reescribe.

## Fase 1 — Traducir, vestir y disco

**Objetivo:** dos llamadas cortas. El 3B clasifica; el motor aplica un estado mínimo en SQLite; el 3B ensambla prosa a partir de fragmentos ya muestreados.

- Etapa 1: JSON estricto (acto, objetivos, valoración del acto, tags, nuevos). Sin `narrative`. Schema en el adapter.
- Motor: escena (`pc`, `location`, `atmosfera`, `tropo`, `time`) + ejes fijos 0–1 (estado volátil, rasgos fijos, vínculos dirigidos) + tags. Topes. El modelo no escribe los ejes a pelo: solo valora el acto e infiere el perfil de quien aparece.
- Resolución general en `src/mente.py`: impacto según el vínculo, puntaje de impulsos, desenlace del acto. Nada específico de una escena.
- Mundo con primitivas generales, no con sistemas por género: presencia por lugar, existencia (activo / muerto / ausente), cosas `obj.` con dueño (el inventario es eso) y coste del acto sobre quien lo hace.
- Catálogo: anclas + nubes de frases en la misma SQLite. Los `.txt` de `data/catalogo/` son import/export.
- Una partida = `saves/<nombre>.sqlite`. Commit al cerrar el turno con éxito.
- Etapa 2: prompt rígido + fragmentos muestreados → prosa. Sin ops. El 3B une; no inventa sensorial.
- CLI: texto libre in, prosa out. Debug vuelca las dos llamadas.

**Listo cuando:** un input produce JSON de intención parseable, el motor mueve números, y la prosa no contradice quién es el PC. Si la etapa 1 no clasifica, no hay producto.

## Fase 2 — Máscara y umbrales

**Objetivo:** el género puede inclinarse sin reiniciar a la gente.

- Máscaras inyectadas según vector de género.
- Vectores y un beat mínimo (al menos: calma → incidente).
- Tags que persisten y se reinyectan.

**Listo cuando:** subir misterio cambia el vestuario del NPC y no borra el vínculo.

## Fase 3 — Resumen enrollable

**Objetivo:** memoria corta canónica. Reanudar ya funciona (la SQLite es de fase 1).

- Rolling state: un párrafo canónico cada N turnos (o al pasar un beat).
- Prosa en log aparte; el modelo no la usa como memoria.

**Listo cuando:** se cierra el proceso, se abre el archivo, y el resumen sigue siendo un párrafo, no el chat entero.

## Fase 4 — Átomos offline

**Objetivo:** nubes densas sin creatividad en vivo del 3B.

- Generar (otro modelo, otro momento) perfiles, reacciones, sensorial a cientos de frases por ancla.
- El runtime solo selecciona e inyecta en la etapa 2.
- Paquete de aventura = seeder, no otro motor.

**Listo cuando:** una partida “llena” no exige que el 3B invente la ficha del jefe desde cero.

## Fase 5 — Abierta (alfa)

Más beats, más adapters, lo que pida el uso real. Sin criterio de cierre.

## Fuera de alcance (hasta que el ciclo de dos etapas sea aburrido de tan estable)

- UI gráfica, web, mapa 2D, multijugador
- Combate por rondas, mapa con direcciones, pesos y estadísticas de objeto. Serían reglas opcionales por partida sobre las tablas que ya existen, no un motor aparte.
- Editor visual
- Suite de tests / CI (el banco de escenas de `tests/` no es eso: no pasa ni falla, se lee)
- Un segundo lenguaje de runtime

## Dependencias

```
1 traducir + vestir + disco  →  2 máscara y vectores
                                    →  3 resumen enrollable
                                          →  4 átomos offline
                                                →  5 alfa
```

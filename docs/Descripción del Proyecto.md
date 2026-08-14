# Descripción del Proyecto

CoreTales es texto: el jugador escribe libre, el motor sostiene el mundo, el modelo viste el desenlace.

## Ciclo de un turno

1. El jugador escribe.
2. El motor llama al modelo con tools.
3. El modelo lee (`aqui`, `mirar`), crea lo nombrado (`nacer`), anota rasgos, y si hay oposición llama `tirar`.
4. El motor sortea y aplica `si_pasa` o `si_falla`.
5. El modelo cierra con `decir`. El jugador ve prosa.

Tope de 8 tools. Default: OpenAI `gpt-4o`. `.env` solo para `OPENAI_API_KEY`.

## Memoria

Una SQLite por partida (`saves/<nombre>.sqlite`):

- **entidades** — nombre, clase libre, dónde, dueño, activo.
- **rasgos** — frase + fuerza cualitativa. Valen para personas, sitios y cosas.
- **linea** — hechos de una línea.
- **escena** — tú, aquí, turno.

Inventario = cosas cuyo dueño es el jugador. Presencia = `donde` = lugar actual y `activo`.

## Resolución

`tirar` saca un valor en [0, 1] (normal truncada). La fuerza del rasgo sesga la muestra. Con oposición, dos muestras. Veredicto: `falla` / `pasa` / `claro`. El motor escribe solo la rama ganadora. El fallo cambia el mundo (se va, se rompe, queda herido); no es “no pasa nada”.

## Qué no es

No hay catálogo de tropos, no hay alias de tipos, no hay llama.cpp en el arranque. No es FATE: la escala cualitativa y el sorteo en campana son propios.

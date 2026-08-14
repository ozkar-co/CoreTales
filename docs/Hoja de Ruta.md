# Hoja de Ruta

El enfoque está en [Enfoque y decisiones.md](Enfoque%20y%20decisiones.md). El mapa, en [Descripción del Proyecto.md](Descripción%20del%20Proyecto.md).

## Fase 1 — Tools, disco y sorteo

**Objetivo:** un turno con GPT-4o que consulta SQLite, sortea en el motor y narra el desenlace.

- Tools: `aqui`, `mirar`, `nacer`, `anotar`, `mover`, `tirar`, `decir`.
- Rasgos con fuerza cualitativa. Sorteo Normal en [0, 1].
- Una partida = `saves/<nombre>.sqlite`. Journal con input, debug y prosa.
- CLI + banco de escenas (`python3 tests/run.py`).

**Listo cuando:** la misma partida aguanta una oficina, una casa y un bosque sin código distinto. Un golpe que falla saca a alguien de la escena o lo deja fuera de combate; no se queda en “lo intentas y no puedes” para siempre.

## Fuera de alcance

- llama.cpp, catálogo de tropos/frases
- UI, mapa 2D, multijugador
- Suite de tests / CI (el banco de escenas se lee, no pasa ni falla)

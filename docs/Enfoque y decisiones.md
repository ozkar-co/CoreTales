# Enfoque y decisiones

Por qué CoreTales no es un chatbot con memoria. El mapa está en [Descripción del Proyecto.md](Descripción%20del%20Proyecto.md). Las fases, en [Hoja de Ruta.md](Hoja%20de%20Ruta.md).

## Qué se busca

Texto libre in, prosa out. Libertad de inventar un detalle. El mundo no se dobla porque el modelo quiera agradar, ni se olvida porque se llenó el contexto.

El jugador ve solo texto. El motor ve entidades, rasgos y un sorteo.

## Tres fallos

**Adulación.** El modelo declara éxito. **Decisión:** el sí/no sale de `tirar`. El modelo propone `si_pasa` / `si_falla`; el motor aplica una sola rama.

**Deriva.** La ventana de chat es la memoria. **Decisión:** SQLite es canónica. Cada turno el modelo pregunta; no arrastra la novela.

**Contagio de persona.** El modelo se vuelve el NPC o inventa el sitio. **Decisión:** quién, dónde y qué hay lo dice `aqui`. Lo que no está, no existe, salvo `nacer` por lo que el jugador acaba de nombrar.

## Oficio del modelo

No es maestro de juego. Elige tools y escribe el desenlace. Segunda persona (tú). El motor guarda y sortea.

## Oficio del motor

Entidades genéricas (persona, lugar, cosa, o lo que pida la situación). Rasgos: frase libre + fuerza `nulo < debil < medio < fuerte < extremo`. Sorteo: una muestra normal truncada a [0, 1], centrada en 0.5, sesgada por esa fuerza. Nada de listas de tipos ni alias por escena.

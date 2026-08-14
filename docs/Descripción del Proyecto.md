# Descripción del Proyecto: CoreTales

Motor procedimental dirigido por eventos. El LLM local es una interfaz de traducción, no el mundo.

Licencia: [Unlicense](https://unlicense.org/). Libre para quien quiera, como quiera. El contenido de cada partida es responsabilidad de quien juega. El núcleo no filtra ni censura.

El **porqué** está en [Enfoque y decisiones.md](Enfoque%20y%20decisiones.md). Las fases, en [Hoja de Ruta.md](Hoja%20de%20Ruta.md).

## Visión

CoreTales es texto: novela gráfica + aventura conversacional + chat tipo Character AI / Dungeon AI. El jugador escribe libre. El motor sostiene resistencia, identidad y ritmo. El modelo no “recuerda la campaña”: viste y clasifica.

Dos usos, el mismo núcleo:

1. **Directo.** Partida en consola. Estado en el motor. El LLM solo traduce entrada y viste salida.
2. **Orquestado.** Un paquete (átomos pregenerados, umbrales, máscaras) seedea la SQLite. Sigue siendo el mismo ciclo de dos etapas.

## Principios

- **El motor dicta el estado.** Deltas, núcleo, tags, vectores de género y beats los aplica Python. El LLM propone intención; no commitea la verdad.
- **El LLM es un periférico.** Dos llamadas cortas por turno, ventanas mínimas. Instruct pequeño en CPU (3B; 7B si hace falta precisión).
- **Núcleo estable, máscara temporal.** Las relaciones abstractas sobreviven al cambio de género.
- **Memoria explícita.** Tags planas + resumen enrollable. La prosa del chat no es la memoria del modelo.
- **Rico offline, barato online.** Perfiles y descriptores salen de un modelo grande fuera de línea; en el turno se ensamblan.
- **Jugador agnóstico.** Solo texto libre. Solo prosa en pantalla. Tras un turno exitoso, el estado ya está en disco.

## Arquitectura

### Ciclo de dos etapas

```
jugador → [1. traducir] → JSON (intención, entidades, deltas)
         → motor (aplicar, umbrales, máscara, átomos)
         → [2. narrar] → prosa
```

1. **Traducción (input).** El jugador escribe cualquier cosa. El LLM **no narra**. Devuelve un JSON chico: acto, entidades afectadas, deltas propuestos, tags nuevas. Schema estricto. Si el JSON falla: un reintento; si otra vez, se informa y el turno no escribe.

2. **Resolución.** El motor valida forma y rangos, aplica el núcleo (con topes), apila tags, actualiza vectores de género, puede avanzar un beat, elige máscara y átomos. Copia de trabajo; commit al cerrar con éxito.

3. **Narración (output).** Prompt rígido: quién / dónde / cuándo, núcleo, máscara, tags relevantes, resumen, beat. El LLM viste. No recibe la novela ni permiso para reescribir números.

El adapter sigue siendo `complete(system, user) -> str`. Cambian los prompts (traducir vs narrar), no el puerto. Primer backend: HTTP compatible OpenAI (llama.cpp). URL en el adapter. `.env` solo para secretos.

Prefijo de reglas cacheable en llama.cpp (slot de partida). `test_llm` usa otro slot.

### Entidad: núcleo y máscara

Cada actor (PC, NPC) tiene:

- **Núcleo.** Dimensiones del motor, persistentes: al menos afinidad, dominancia, estrés (escala 0–1). El motor las incrementa o recorta; el LLM no hace `set` libre sobre ellas.
- **Máscara.** Arquetipo inyectado según el vector de género dominante. Cambia; el núcleo no.
- **Tags.** Lista plana (`fobia_gatos`, …). La etapa 1 puede proponer; el motor apila y reinyecta.
- **Datos de ficha.** Nombre, slug, lo que el mundo necesite. JSON flexible alrededor del núcleo, no en lugar del núcleo.

Escena del motor: `pc`, `location`, `time` (value / unit / label). Quién, dónde y cuándo no los improvisa la prosa.

### Memoria

- **Hechos / tags / núcleo:** canónicos.
- **Resumen enrollable:** un párrafo que el motor regenera cada N turnos (o al pasar un beat). Se inyecta en ambas etapas, corto.
- **Prosa:** log para mostrar el chat al reanudar. No se manda al LLM como memoria.

### Átomos (offline)

Un modelo grande, fuera del bucle de juego, genera filas: perfiles, reacciones, sensorial, plantillas. Runtime: el motor selecciona; la etapa 2 ensambla. Una base = una partida (`saves/<nombre>.sqlite`). Un paquete de aventura es un seeder de esas filas más umbrales y máscaras.

### Vectores de género

El motor guarda pesos (p. ej. mundano, misterio, amenaza). Las acciones mueven esos pesos. Cruzar un umbral cambia beat y máscaras. El mapa geográfico es opcional; el progreso narrativo es matemático.

## Contrato de turno (forma, no el JSON final)

La etapa 1 habla un JSON mínimo (intención + deltas + tags). La etapa 2 habla prosa. El motor no acepta que la etapa 1 narre ni que la etapa 2 envíe ops.

Claves JSON en inglés. Prosa en el idioma del jugador. Un reintento por JSON inválido; luego abortar e informar.

Debug: `CORE_TALES_DEBUG=1` vuelca ambas llamadas a stderr.

## Qué no es (aún)

- UI gráfica, web, mapa 2D, multijugador
- Combate, magia o inventario como sistemas hardcodeados (pueden ser máscaras + tags + átomos)
- Editor visual, marketplace
- Un segundo lenguaje de runtime

## Licencia y operación

Unlicense. Dependencias mínimas, `venv`. Sin suite de tests por ahora. El motor no censura.

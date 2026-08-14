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
jugador → [1. traducir] → JSON (intención, entidades, valoración del acto)
         → motor (impactar ejes, resolver desenlace, umbrales, máscara, átomos)
         → [2. narrar] → prosa
```

1. **Traducción (input).** El jugador escribe cualquier cosa. El LLM **no narra** y no decide qué pasa. Devuelve un JSON chico: acto, entidades afectadas, **valoración** del acto en ejes generales (intensidad, intimidad, agresión, exposición, afecto, dominio, reposo), tags nuevas, quién deja de estar (muerto o ausente) y, para quien o lo que aparece por primera vez, el perfil o el dueño que se pueda inferir del texto. Schema estricto. Si el JSON falla: un reintento; si otra vez, se informa y el turno no escribe.

2. **Resolución.** El motor traduce esa valoración a movimiento de ejes según el vínculo (el mismo acto agrada o repugna según quién lo recibe), puntúa los impulsos posibles, elige el que gana y decide si el acto se completa. Apila tags, actualiza vectores de género, puede avanzar un beat, elige máscara y átomos. Copia de trabajo; commit al cerrar con éxito.

3. **Narración (output).** Prompt rígido: quién / dónde / cuándo, canon del motor (reacción y desenlace), tags relevantes, resumen, beat. El LLM viste. No recibe la novela ni permiso para reescribir números, ni para contradecir el canon.

El adapter sigue siendo `complete(system, user) -> str`. Cambian los prompts (traducir vs narrar), no el puerto. Backends: llama.cpp (HTTP local) u OpenAI. `.env` solo para secretos (`OPENAI_API_KEY`). `CORE_TALES_LLM=openai|llamacpp` fuerza el vendor; si no, OpenAI cuando hay clave.

Prefijo de reglas cacheable en llama.cpp (slot de partida). `test_llm` usa otro slot.

### Entidad: núcleo y máscara

Los ejes son fijos y generales (los define `src/mente.py`), pensados para servir a cualquier escena sin programar comportamientos uno por uno. Cada actor (PC, NPC) tiene:

- **Estado.** Lo volátil, como niveles químicos: excitación, enojo, miedo, estrés, dolor, vergüenza, confianza, energía (0–1). Sube por lo que pasa y vuelve al reposo con los turnos.
- **Rasgos.** Lo fijo: valentía, dominancia, impulsividad, moral, fuerza, inteligencia, apariencia, sociabilidad. No cambian salvo evento canónico grande. No crean conducta por sí solos: multiplican la tensión que ya existe (sin ira no se pega).
- **Vínculos.** Dirigidos, uno por par: afecto, odio, respeto, miedo, deseo. De aquí sale si un acercamiento agrada o repugna.
- **Máscara.** Arquetipo inyectado según el vector de género dominante. Cambia; los ejes no.
- **Tags.** Lista plana (`fobia_gatos`, …). La etapa 1 puede proponer; el motor apila y reinyecta.
- **Datos de ficha.** Nombre, slug, lo que el mundo necesite. JSON flexible alrededor de los ejes, no en lugar de los ejes.

El motor puntúa siete impulsos (ceder, dominar, hablar, rechazar, agredir, huir, congelarse) y gana el más alto: una sola regla general en vez de un caso por situación. Después decide el desenlace del acto: `ocurre`, `forcejeo`, `forzado` o `bloqueado`. Solo un acto sobre el cuerpo se puede frenar; hablar o irse no se bloquean.

Escena del motor: `pc`, `location`, `time` (value / unit / label). Quién, dónde y cuándo no los improvisa la prosa.

### Mundo: presencia, existencia y cosas

Mismas cuatro primitivas para cualquier ambientación; no hay un sistema para novela y otro para aventura. La diferencia entre una oficina y un bosque es el catálogo, no el motor.

- **Presencia.** Toda entidad está en un lugar. La escena solo ve lo presente. Al moverse, acompaña quien fue objeto del acto ("la llevo al despacho"); el resto queda donde estaba.
- **Existencia.** `activo`, `muerto`, `ausente`. Lo declara la etapa 1 porque es interpretación del texto ("luego de matar a los gnomos"). El que no está activo no reacciona ni recibe actos, pero su cuerpo puede seguir en el sitio.
- **Cosas.** Entidades `obj.` con dueño opcional. Con dueño, es inventario y viaja con él; sin dueño, queda en el lugar. Nada de tablas nuevas ni estadísticas de objeto.
- **Coste.** El acto gasta al que lo hace (energía, estrés) y `reposo` lo devuelve. El PC también tiene estado: cansarse es parte del mundo, no una regla de RPG.

Un mapa con direcciones, rondas de combate o pesos de inventario serían reglas opcionales sobre estas mismas tablas, elegidas por partida. No hacen falta para que el bosque funcione.

### Memoria

- **Hechos / tags / ejes:** canónicos. Los hechos se derivan del estado vigente, no son una lista que se acumula y se pudre.
- **Eventos:** lo que dejó huella (un forcejeo, algo forzado) queda como historia de esa entidad.
- **Resumen enrollable:** un párrafo que el motor regenera cada N turnos (o al pasar un beat). Se inyecta en ambas etapas, corto.
- **Prosa:** log para mostrar el chat al reanudar. No se manda al LLM como memoria.

### Átomos (offline)

Un modelo grande, fuera del bucle de juego, genera filas: perfiles, reacciones, sensorial, plantillas. Runtime: el motor selecciona; la etapa 2 ensambla. Una base = una partida (`saves/<nombre>.sqlite`). Un paquete de aventura es un seeder de esas filas más umbrales y máscaras.

### Vectores de género

El motor guarda pesos (p. ej. mundano, misterio, amenaza). Las acciones mueven esos pesos. Cruzar un umbral cambia beat y máscaras. El mapa geográfico es opcional; el progreso narrativo es matemático.

## Contrato de turno (forma, no el JSON final)

La etapa 1 habla un JSON mínimo (intención + valoración + tags). La etapa 2 habla prosa. El motor no acepta que la etapa 1 narre ni que la etapa 2 envíe ops. La etapa 1 tampoco escribe emociones de nadie: solo valora el acto e infiere el perfil de quien nace.

Claves JSON en inglés. Prosa en el idioma del jugador. Un reintento por JSON inválido; luego abortar e informar.

Debug: `CORE_TALES_DEBUG=1` vuelca ambas llamadas a stderr.

## Qué no es (aún)

- UI gráfica, web, mapa 2D, multijugador
- Combate, magia o inventario como sistemas hardcodeados (pueden ser máscaras + tags + átomos)
- Editor visual, marketplace
- Un segundo lenguaje de runtime

## Licencia y operación

Unlicense. Dependencias mínimas, `venv`. Sin suite de tests por ahora. El motor no censura.

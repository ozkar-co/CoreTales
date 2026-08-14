# Descripción del Proyecto: CoreTales

Motor narrativo procedural basado en estados. Minimalista: KISS, DRY, un núcleo pequeño y un adapter de LLM.

Licencia: [Unlicense](https://unlicense.org/). Libre para quien quiera, como quiera. El contenido de cada partida es responsabilidad de quien juega. El núcleo no filtra ni censura.

La hoja de fases está en [Hoja de Ruta.md](Hoja%20de%20Ruta.md). Lo que sigue abierto: [Preguntas a Resolver.md](Preguntas%20a%20Resolver.md).

## Visión

CoreTales es un motor para aventuras narrativas y roleplay en texto. No es un chatbot con memoria: el mundo vive en un registro persistente; el LLM interpreta, consulta ese registro y narra.

El LLM dicta la verdad narrativa, incluso si alucina. El núcleo no arbitra la historia. Lleva un log de variables y hechos al que el modelo accede cuando lo necesita. El registro se actualiza solo con las operaciones que el modelo envía. Si narra sin escribir ops, prosa y store pueden divergir hasta el próximo `set`. El núcleo no reescribe ni obliga a alinear.

Dos formas de usarlo, el mismo núcleo:

1. **Uso directo (ahora).** Se arranca una partida, se escribe en consola. Sin seed, el modelo inventa el mundo en el primer turno (`spawn`). El motor corre el bucle, guarda y reanuda.
2. **Orquestación (después).** Un autor aporta prompt de mundo más datos que pueblan la base (NPCs, lugares, eventos pasados) y, si hace falta, triggers en JSON. Eso no es un segundo motor: es un seeder. Los triggers son información para el LLM, no vetos del núcleo. Puede que la primera versión jugable no traiga triggers.

El motor no conoce géneros ni mecánicas. No sabe qué es magia, estrés u oro. Eso vive en el estado, en el prompt y en lo que el modelo invente. El núcleo: lee al jugador, deja que el LLM pida y escriba datos, aplica una lista de operaciones, persiste, imprime prosa.

## Principios

- **KISS.** Un bucle de turno, un registro, un adapter. Nada de frameworks ni capas por si acaso.
- **DRY.** Un contrato de JSON, un prompt de sistema (en el núcleo, igual para todo provider). Los vendors no duplican lógica: implementan el mismo puerto.
- **Agnóstico.** Sin reglas de juego en código. El género es prompt + datos.
- **El LLM habla con el sistema.** No se vuelca el mundo entero en cada prompt. Por cada input del jugador hay varias llamadas: el modelo pide lo que necesita, el núcleo responde, hasta que hay narración.
- **El registro no es el director.** El núcleo valida forma (JSON parseable, ops aplicables), no semántica. Escalas 0–1 o etiquetas de texto; las interpreta el modelo. No hay `inc`: el modelo calcula el valor nuevo.
- **Jugador agnóstico.** Solo texto libre. Solo prosa en pantalla. Sin `/save`, `/state` ni comandos. Tras cada interacción exitosa el estado ya está en disco.

## Arquitectura

Tres piezas en la versión que se va a construir. Los triggers son opcionales y posteriores.

### 1. Núcleo

Orquesta el turno. No contiene reglas de género. Expone:

- bucle interno de consulta (varias llamadas al LLM por input)
- recorte de contexto: cada petición al vendor es independiente; el núcleo reenvía el input del turno más las lecturas ya hechas
- aplicación de operaciones sobre una copia de trabajo; commit a disco solo al cerrar con éxito
- prompt de sistema (español; las claves JSON van en inglés)
- parseo del JSON (el adapter solo devuelve texto)

Habla con el modelo solo por `LlmAdapter.complete(system, user) -> str`. Nunca importa Gemini, OpenAI ni llama.cpp.

### 2. Registro (memoria, luego SQLite + JSON)

Almacén consultable. JSON libre dentro de las entidades. Sin esquema rígido entre ellas: basta con que el LLM las interprete.

- **Entidades** (`entities.slug` → JSON): jugador, NPCs, lugares, objetos. Identidad por slug (`npc.mesonero`); si choca, un contador.
- **Relaciones:** claves más en el mapa de la entidad, no un grafo aparte. No hay op `rel`.
- **Hechos** (`events`): apéndice canónico que el modelo escribe con `op: event`. No es la prosa.
- **Prosa** (`prose_log`): histórico para mostrar el chat al reanudar. No se manda al LLM. Prescindible para que la partida exista.
- **Reloj:** si el modelo quiere tiempo de juego, spawnea o actualiza una entidad (p. ej. `world`). El núcleo no interpreta fechas ni recalcula NPCs al `get`. Eso queda como idea a futuro.

Una base = una partida, archivo `saves/<nombre>.sqlite` (por defecto `saves/default.sqlite`). Las historias precreadas son un seeder que inicializa esa base.

### 3. Adapter de LLM

Un puerto, un método, síncrono. El núcleo manda dos strings y espera texto. Detrás, intercambiables:

- Un provider al inicio (Gemini u OpenAI: aún por elegir)
- llama.cpp más adelante (local, offline)

Sin JSON mode del vendor: el prompt exige JSON. Más portable, más frágil; si no basta, se evalúa structured output después.

El adapter no recorta mundo, no decide reglas, no parsea, no guarda estado. Secretos en `.env`. Debug: variable `CORE_TALES_DEBUG=1` (JSON crudo a stderr). El jugador no tiene flag ni comandos.

## Contrato JSON

Un objeto por llamada. Campos opcionales; se pueden mezclar. Claves en inglés. La prosa, en el idioma del jugador.

```json
{
  "reads": [
    {"get": "npc.mesonero"},
    {"list": "npc."},
    {"log": 10}
  ],
  "ops": [
    {"op": "set", "slug": "npc.mesonero", "key": "confianza", "value": 0.4},
    {"op": "spawn", "slug": "npc.guarda", "data": {"nombre": "Guarda"}},
    {"op": "delete", "slug": "item.llave"},
    {"op": "event", "data": "El mesonero cerró la taberna."}
  ],
  "narrative": "El mesonero te mira de reojo."
}
```

- **reads:** `get` (entidad entera o `null`), `list` (slugs con ese prefijo; prefijo vacío = todos), `log` (últimos N hechos). No hay `search`.
- **ops:** `set` (una clave del mapa), `spawn`, `delete`, `event`. El modelo pone el valor final; el núcleo no incrementa.
- **narrative:** texto para el jugador.

## Bucle de turno

Un input del jugador no es una llamada. Es un diálogo corto entre el modelo y el núcleo. Tope: **8** llamadas. Si se supera: error, rollback, se informa.

1. **Snapshot.** Copia de trabajo del registro. Si el turno aborta, se descarta.
2. **Entrada.** El jugador escribe lo que sea. El motor no parsea comandos. El primer paquete lleva el input, el catálogo de slugs, y si hay eventos de cola, el texto pendiente concatenado.
3. **Llamada.** `complete(system, user)`. El `user` de las vueltas siguientes reenvía el input del turno más cada par lectura→resultado de este turno. No se usa la ventana de chat del vendor.
4. **Parseo.** JSON inválido: un reintento (“devuelve solo JSON”); si vuelve a fallar, abortar e informar.
5. **Ejecutar.** Ops sobre la copia de trabajo (el siguiente `get` ya las ve). Si `reads` no está vacío: resolver lecturas, volver a 3. No se imprime `narrative` todavía.
6. **Cierre.** `reads` vacío: se commitea la copia a disco, se añade la prosa al log, se muestra `narrative` (puede ir vacío). Ahí termina el turno.

Arranque sin seed: el mismo prompt. Catálogo de slugs vacío; el modelo inventa y hace `spawn` en el primer turno. No hay prompt de bootstrap aparte.

Si la API falla a mitad, falla: mensaje al usuario. Puede repetir el input o salir. No hay guardado manual.

No hay ticks internos. El tiempo avanza cuando el jugador lo dice; el LLM interpreta y, si quiere, escribe ops.

## Contrato cerrado

No se reabre sin motivo.

| Tema | Decisión |
|---|---|
| Delta | Lista de ops: `set`, `spawn`, `delete`, `event` |
| Quién crea entidades y claves | LLM y, más adelante, seeds/triggers. Sin exigir el mismo shape entre entidades |
| Validación | Forma, no semántica. Preferir 0–1 o etiquetas. Sin `inc` |
| Turno | Atómico en disco. Copia de trabajo durante el diálogo interno. Falla → rollback, informar |
| Ticks sin jugador | No |
| Adapter | `complete(system, user) -> str`, síncrono. El núcleo parsea |
| Prompt de sistema | En el núcleo, español, idéntico para todo provider |
| Claves JSON | Inglés. Prosa en el idioma del jugador |
| JSON malformado | Un reintento; luego abortar |
| JSON mode del vendor | No al inicio |
| llama.cpp | Adapter vacío al inicio |
| Secretos | `.env` |
| Contexto | Cada llamada independiente. Se reenvía input + lecturas de este turno. La prosa histórica no va al LLM |
| Lecturas | `get`, `list`, `log`. Sin `search` |
| Fin del bucle | `reads` vacío (o tope de 8) |
| Mezcla en un JSON | Sí. Si hay `reads`, no se muestra aún la narración |
| Narrar sin ops | Permitido. El LLM dicta; store y prosa pueden divergir |
| Reloj / lazy NPC | No en el núcleo. El modelo puede usar una entidad `world` si quiere |
| Persistencia | Una SQLite por partida: `entities`, `events`, `prose_log`. `saves/<nombre>.sqlite` |
| IDs | Slugs. Colisión: contador. Más adelante, fusión vía LLM |
| Relaciones | Mapa libre en la entidad |
| Triggers | Datos JSON, una vez, info para el modelo. Quizá no en la v inicial |
| Sustituir al LLM | Nunca |
| Seed | Prompt de mundo + JSON o SQL. Mismo prompt si el mundo está vacío |
| Autoría | Editar archivos |
| Distribución | Archivos sueltos hasta alfa/beta |
| Input | Texto libre, sin comandos |
| Lo que ve el jugador | Solo prosa. `CORE_TALES_DEBUG=1` en desarrollo |
| Fallos | Se informan. Sin botones de recuperación |
| Dependencias | Mínimas, `venv` |
| Tests | No por ahora |
| Contenido | Responsabilidad del usuario. El motor no censura |

## Qué no es (aún)

- UI gráfica, web, mapa 2D, multijugador
- Economía, combate o inventario hardcodeados
- Editor visual, marketplace, plugins
- Un segundo lenguaje de runtime

## Ideas a futuro y posibles mejoras

No bloquean las fases 1–3. La fase 4 de la hoja de ruta está abierta a la alfa.

- **llama.cpp** y otros providers cuando alguien los necesite.
- **Seeds:** prompt + datos (NPCs, lugares, hechos pasados) como partidas precreadas.
- **Triggers** en JSON, una vez, como ganchos de historia que el LLM interpreta.
- **Reloj in-world** y recálculo lazy de NPCs al cargarlos tras un salto de tiempo (el núcleo hoy no interpreta `time`).
- **Fusión de slugs** duplicados con una consulta extra al LLM.
- **Formato empaquetado** de aventura cuando se quiera distribuir.
- **Structured output / JSON mode** de la API si el prompt solo no basta.
- **Streaming** de prosa a la consola.
- **Monitoreo** de variables de ambiente o condiciones si el uso real lo pide — sin meter reglas de género en el núcleo.
- **Tests** si el proyecto crece.
- **Estilos de consola** más amables, sin convertir la CLI en una UI.

## Preguntas abiertas

Solo las que cambian la forma del motor. Detalle en [Preguntas a Resolver.md](Preguntas%20a%20Resolver.md).

1. **Provider inicial:** Gemini u OpenAI.
2. **Qué pone el núcleo en el primer paquete del turno:** almacén de slugs (input + catálogo) vs una “escena” (el núcleo sabe quién es el PC y dónde está).

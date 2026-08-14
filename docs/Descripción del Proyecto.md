# Descripción del Proyecto: CoreTales

Motor narrativo procedural basado en estados. Minimalista: KISS, DRY, un núcleo pequeño y un adapter de LLM.

Licencia: [Unlicense](https://unlicense.org/). Libre para quien quiera, como quiera. El contenido de cada partida es responsabilidad de quien juega. El núcleo no filtra ni censura.

La hoja de fases está en [Hoja de Ruta.md](Hoja%20de%20Ruta.md). El contrato de esta página está cerrado para la primera versión.

## Visión

CoreTales es un motor para aventuras narrativas y roleplay en texto. No es un chatbot con memoria: el mundo vive en un registro persistente; el LLM interpreta, consulta ese registro y narra.

El LLM dicta la verdad narrativa, incluso si alucina. El núcleo no arbitra la historia. Lleva un log de variables y hechos al que el modelo accede cuando lo necesita. El registro se actualiza solo con las operaciones que el modelo envía. Si narra sin escribir ops, prosa y store pueden divergir hasta el próximo `set`. El núcleo no reescribe ni obliga a alinear.

El motor no conoce géneros ni mecánicas (magia, estrés, oro). Sí conoce una **escena**: quién, dónde y cuándo. Eso es el recorte del primer paquete de cada turno. El resto del mundo se pide con `get` / `list` / `log`.

Dos formas de usarlo, el mismo núcleo:

1. **Uso directo (ahora).** Se arranca una partida, se escribe en consola. Sin seed, el modelo inventa el mundo en el primer turno (`spawn` + escena). El motor corre el bucle, guarda y reanuda.
2. **Orquestación (después).** Un autor aporta prompt de mundo más datos que pueblan la base y, si hace falta, triggers en JSON. Eso es un seeder, no un segundo motor. Los triggers son información para el LLM, no vetos. Puede que la primera versión jugable no los traiga.

## Principios

- **KISS.** Un bucle de turno, un registro, una escena, un adapter.
- **DRY.** Un contrato de JSON, un prompt de sistema (en el núcleo, igual para todo provider). Los vendors no duplican lógica: implementan el mismo puerto.
- **Agnóstico de género, no de escena.** Sin reglas de juego en código. El núcleo sí mantiene quién / dónde / cuándo.
- **El LLM habla con el sistema.** No se vuelca el mundo entero. Por cada input hay varias llamadas hasta que hay narración.
- **El registro no es el director.** El núcleo valida forma, no semántica. Escalas 0–1 o etiquetas; las interpreta el modelo. No hay `inc`.
- **Jugador agnóstico.** Solo texto libre. Solo prosa en pantalla. Tras cada interacción exitosa el estado ya está en disco.

## Arquitectura

Tres piezas. Los triggers son opcionales y posteriores.

### 1. Núcleo

Orquesta el turno. Expone:

- escena (quién, dónde, cuándo) en el primer paquete
- bucle interno de consulta (varias llamadas al LLM por input)
- recorte: cada petición al vendor es independiente; se reenvía el input del turno más las lecturas ya hechas
- ops sobre una copia de trabajo; commit a disco solo al cerrar con éxito
- prompt de sistema (español; claves JSON en inglés)
- parseo del JSON (el adapter solo devuelve texto)

Habla con el modelo solo por `LlmAdapter.complete(system, user) -> str`.

### 2. Registro (memoria, luego SQLite + JSON)

JSON libre dentro de las entidades, salvo la escena.

- **Escena** (slug reservado `scene`): `pc` (slug del jugador), `location` (slug del lugar), `time` (`value`, `unit`, `label`). El núcleo la crea al empezar una partida vacía. El modelo la actualiza con `set`. La escala de `unit` es libre (`day`, `hour`, `year`, lo que pida el juego); el núcleo no convierte unidades, solo las guarda y las incluye siempre.
- **Entidades:** PC, NPCs, lugares, objetos. Slug (`npc.mesonero`); colisión → contador. Relaciones = claves en el mapa de la entidad.
- **Hechos** (`events`): canónicos, vía `op: event`.
- **Prosa** (`prose_log`): para mostrar el chat al reanudar. No se manda al LLM. Prescindible para que la partida exista.

Quién, al inicio, es solo el PC. Otros actores en la escena pueden entrar después (p. ej. presentes en el mismo lugar) sin cambiar el contrato.

Una base = una partida: `saves/<nombre>.sqlite` (por defecto `saves/default.sqlite`).

### 3. Adapter de LLM

Un puerto, un método, síncrono. El núcleo manda dos strings y espera texto.

El primer backend es un servidor **compatible OpenAI** (llama.cpp u otro). Gemini, OpenAI cloud y el resto son otros adapters después. Cada adapter conoce su URL por defecto (p. ej. el de llama.cpp apunta a `http://127.0.0.1:8080/v1`). El núcleo no sabe qué hay detrás.

`.env` (u otro archivo local) es solo para secretos: claves de API. La URL no es un secreto y no va ahí. El adapter de llama.cpp, en local, no necesita clave. No lanza el modelo ni conoce rutas a ficheros `.gguf`. Si el servidor ofrece JSON schema / grammar, el adapter puede pedirlo; el contrato hacia el núcleo sigue siendo texto → el núcleo parsea.

Sin JSON mode obligatorio en el prompt-contrato: el prompt exige JSON; el adapter puede reforzarlo hacia el servidor.

Debug: `CORE_TALES_DEBUG=1` (JSON crudo a stderr).

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
    {"op": "set", "slug": "scene", "key": "time", "value": {"value": 1, "unit": "day", "label": "día 2, amanecer"}},
    {"op": "spawn", "slug": "npc.guarda", "data": {"nombre": "Guarda"}},
    {"op": "delete", "slug": "item.llave"},
    {"op": "event", "data": "El mesonero cerró la taberna."}
  ],
  "narrative": "El mesonero te mira de reojo."
}
```

- **reads:** `get`, `list` (prefijo; vacío = todos), `log` (últimos N hechos). Sin `search`.
- **ops:** `set`, `spawn`, `delete`, `event`. El modelo pone el valor final.
- **narrative:** texto para el jugador.

## Bucle de turno

Tope: **8** llamadas. Si se supera: error, rollback, se informa.

1. **Snapshot.** Copia de trabajo. Si el turno aborta, se descarta.
2. **Escena.** El primer paquete lleva: input del jugador, `scene`, entidad `who` (`scene.pc`), entidad `where` (`scene.location`), `when` (`scene.time`). Si aún no hay PC o lugar, van `null` y el modelo debe hacer `spawn` y `set` sobre `scene`.
3. **Llamada.** `complete(system, user)`. Las vueltas siguientes reenvían el input más cada par lectura→resultado de este turno. No se usa la ventana de chat del vendor.
4. **Parseo.** JSON inválido: un reintento; si vuelve a fallar, abortar e informar.
5. **Ejecutar.** Ops sobre la copia (el siguiente `get` ya las ve, incluida `scene`). Si `reads` no está vacío: resolver, volver a 3. No se imprime `narrative` todavía.
6. **Cierre.** `reads` vacío: commit a disco, prosa al log, se muestra `narrative`.

Arranque sin seed: el mismo prompt. Escena vacía (`pc` y `location` null, `time` en 0). El modelo inventa en el primer turno.

Si la API falla a mitad, se informa. El jugador puede repetir el input o salir. No hay guardado manual. No hay ticks internos: el tiempo lo cambia el LLM (o lo que el jugador pida, interpretado por el modelo) escribiendo `scene.time`.

## Contrato cerrado

| Tema | Decisión |
|---|---|
| Escena | Slug `scene`: `pc`, `location`, `time`. Siempre en el primer paquete |
| Quién / dónde / cuándo | El núcleo los registra. `unit` de tiempo es libre. Sin conversión de calendarios |
| Actores en escena | De momento solo el PC. Otros, después |
| Delta | `set`, `spawn`, `delete`, `event` |
| Validación | Forma, no semántica. Sin `inc` |
| Turno | Atómico en disco. Copia de trabajo durante el diálogo interno |
| Ticks sin jugador | No |
| Adapter | `complete(system, user) -> str`. Primer backend: HTTP compatible OpenAI (llama.cpp). El núcleo no lanza el servidor |
| Prompt de sistema | En el núcleo, español, idéntico para todo provider |
| Claves JSON | Inglés. Prosa en el idioma del jugador |
| JSON malformado | Un reintento; luego abortar |
| Contexto | Llamadas independientes. Se reenvía input + lecturas del turno. La prosa histórica no va al LLM |
| Lecturas | `get`, `list`, `log` |
| Fin del bucle | `reads` vacío o tope de 8 |
| Mezcla en un JSON | Sí. Si hay `reads`, no se muestra aún la narración |
| Narrar sin ops | Permitido |
| Persistencia | Una SQLite por partida: `entities`, `events`, `prose_log`. `saves/<nombre>.sqlite` |
| IDs | Slugs. Colisión: contador |
| Relaciones | Mapa libre en la entidad |
| Triggers | Después, si hacen falta. Datos JSON, una vez, info para el modelo |
| Seed | Prompt + JSON o SQL. Mismo prompt si el mundo está vacío |
| Input | Texto libre, sin comandos |
| Lo que ve el jugador | Solo prosa. `CORE_TALES_DEBUG=1` en desarrollo |
| URL del LLM | En el adapter de ese proveedor, no en `.env` |
| Secretos | `.env` u otro archivo local. Solo claves. llama.cpp local no requiere |
| Dependencias | Mínimas, `venv` |
| Tests | No por ahora |
| Licencia | Unlicense. El motor no censura |

## Qué no es (aún)

- UI gráfica, web, mapa 2D, multijugador
- Economía, combate o inventario hardcodeados
- Editor visual, marketplace, plugins
- Un segundo lenguaje de runtime

## Ideas a futuro

No bloquean las fases 1–3.

- Adapters Gemini / OpenAI cloud
- Seeds y partidas precreadas
- Triggers en JSON
- Otros actores automáticos en la escena (presentes en el lugar)
- Recálculo lazy de NPCs al `get` tras un salto de `scene.time`
- Fusión de slugs duplicados vía LLM
- Formato empaquetado de aventura
- Structured output si el prompt no basta (el adapter ya puede pedirlo al servidor)
- Streaming de prosa
- Tests, estilos de consola

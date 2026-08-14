# Descripción del Proyecto: CoreTales

Motor narrativo procedural basado en estados. Minimalista: KISS, DRY, un núcleo pequeño y puntos de extensión explícitos.

## Visión

CoreTales es un motor para aventuras narrativas y roleplay en texto. No es un chatbot con memoria: el mundo vive en un estado persistente; el LLM solo interpreta y narra.

Dos formas de usarlo, con el mismo núcleo:

1. **Uso directo.** Se arranca una partida, se escribe en consola, el motor corre el bucle. El LLM infiere consecuencias a partir del estado. Sirve para jugar o prototipar sin autoría previa.
2. **Orquestación.** El autor define historia, escenas y reglas mediante **triggers y eventos**. La generación va dirigida: el motor dispara ganchos cuando el estado cumple una condición, y el LLM (o código del autor) responde dentro de ese marco. El autor no reimplementa el motor; lo dirige.

El motor no conoce géneros ni mecánicas de juego. No sabe qué es magia, estrés o oro. Esas cosas viven en el estado, en los eventos y en los prompts. El núcleo solo: lee entrada, carga contexto, dispara eventos, llama al LLM por un **adapter**, aplica el delta de estado, persiste, imprime.

## Principios

- **KISS.** Un bucle, un estado, un bus de eventos, un adapter de LLM. Nada de frameworks ni capas “por si acaso”.
- **DRY.** Una representación del mundo, un contrato de turno (entrada → contexto → inferencia → delta → salida). Los proveedores de LLM no duplican lógica: implementan el mismo puerto.
- **Agnóstico.** El núcleo no contiene reglas de juego. El género vive en datos, prompts y triggers.
- **Determinismo en el estado, no en el texto.** SQLite es la fuente de verdad. El LLM propone; el motor valida y aplica.
- **Desacoplar narración y mundo.** El LLM no es la memoria. Si el modelo alucina, el estado gana.

## Arquitectura

Cuatro piezas. Cada una hace una sola cosa.

### 1. Núcleo

Orquesta el turno. No contiene reglas de género. Expone:

- bucle de juego
- carga de contexto (quién está aquí, relaciones, eventos recientes)
- despacho de triggers
- aplicación de deltas de estado
- persistencia del turno

El núcleo habla con el LLM solo a través del puerto `LlmAdapter`. Nunca importa Gemini, OpenAI ni llama.cpp.

### 2. Persistencia (SQLite + JSON)

Memoria del mundo. Tipado flexible en JSON dentro de SQLite:

- **Entidades:** jugador, NPCs, lugares, objetos. Atributos dinámicos (hambre, alerta, oro, lo que la historia invente).
- **Relaciones:** grafo entre entidades (confianza, miedo, deuda).
- **Log de eventos:** sucesos canónicos para coherencia temporal.
- **Triggers registrados:** condiciones y acciones de orquestación (datos, no código embebido en el núcleo).

### 3. Adapter de LLM

Puerto único. El núcleo envía un paquete de contexto y espera un resultado estructurado (intención resuelta, narración, delta de estado). Detrás, intercambiables:

- Gemini
- OpenAI
- llama.cpp (local, offline, sin filtro de API)

Cambiar de proveedor es cambiar la implementación del adapter, no el motor. El adapter no decide reglas de mundo; traduce petición/respuesta y normaliza el contrato.

### 4. Triggers y eventos

Punto de extensión para orquestar. Un **evento** es un hecho ya ocurrido (el jugador entró en la taberna, la confianza bajó de 0). Un **trigger** es una reacción declarada: si el estado o el evento cumple X, entonces Y (inyectar escena, forzar un NPC, bloquear una acción, llamar al LLM con un prompt distinto, ejecutar un hook del autor).

En uso directo, la lista de triggers puede estar vacía: el LLM infiere solo. En orquestación, los triggers son el guion: generación dirigida sin ramificar el núcleo.

## Bucle de turno

1. **Entrada.** Acción del jugador (o evento interno).
2. **Contexto.** El núcleo lee de SQLite: entidad activa, entorno, relaciones, log reciente, triggers aplicables.
3. **Triggers previos.** Si hay ganchos `before_infer`, se aplican (contexto extra, veto, escena forzada).
4. **Inferencia.** El adapter llama al LLM con el paquete. El LLM evalúa la acción contra el estado y devuelve JSON (narración + delta).
5. **Validación y commit.** El núcleo parsea, rechaza lo incoherente con el esquema/estado, aplica el delta, registra el evento.
6. **Triggers posteriores.** Ganchos `after_commit` (cadenas, flags, siguiente escena).
7. **Salida.** Texto al jugador. El estado ya está persistido.

## Dos modos, un motor

| | Uso directo | Orquestación |
|---|---|---|
| Triggers | Opcionales / vacíos | El autor define el arco |
| Quién dirige | El LLM infiere con el estado | Eventos y condiciones acotan al LLM |
| Superficie | CLI | CLI + definiciones (datos/hooks) |
| Núcleo | El mismo | El mismo |

La orquestación no es un segundo motor. Es el mismo bucle con una tabla de triggers y, si hace falta, hooks del autor en los puntos `before_infer` / `after_commit`.

## Características

- **Estado por encima del chat.** Consecuencias reales: un NPC no puede ser afectuoso si `confianza` está en el suelo, salvo que un trigger o un delta válido lo cambie.
- **Variables sobre la marcha.** Sin esquema rígido de stats. El LLM (o un trigger) puede introducir `hipotermia` o `sed`; el motor las guarda si pasan validación.
- **Agnóstico de género.** Citas en el instituto, fantasía oscura o intriga política: cambia el prompt inicial y los triggers, no el núcleo.
- **Proveedor de LLM intercambiable.** API comercial o llama.cpp local. Privacidad, offline y libertad narrativa son opciones de adapter, no forks del motor.
- **Autoría incremental.** Se puede empezar en uso directo y, partida a partida, ir clavando triggers donde la historia deba ir dirigida.

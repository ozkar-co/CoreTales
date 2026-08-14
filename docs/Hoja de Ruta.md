# Hoja de Ruta

Propuesta, no compromiso. El orden prioriza un núcleo jugable y el puerto de LLM antes de autoría rica. Cada fase debe poder usarse sola; la siguiente se apoya en ella, no la reescribe.

## Fase 0 — Contrato y esqueleto

**Objetivo:** poder explicar el sistema en una página y tener carpetas/módulos que coincidan con esa página.

- Contrato del turno: entrada, contexto, resultado estructurado, delta de estado.
- Puerto `LlmAdapter` (interfaz + tipos). Sin implementaciones reales aún; un adapter falso que devuelve JSON fijo.
- Esquema mínimo de persistencia: entidades, relaciones, log, partida.
- CLI que imprime “turno” contra el adapter falso y SQLite.

**Listo cuando:** `python -m coretales` abre una partida, acepta una línea, persiste un delta inventado y lo vuelve a leer.

## Fase 1 — Núcleo determinista

**Objetivo:** el estado es la fuente de verdad. El LLM (aunque sea falso) no escribe a ciegas en la base.

- Carga de contexto acotada (lugar actual, entidades presentes, N eventos recientes, relaciones relevantes).
- Aplicación de deltas: crear/actualizar entidad, relación, evento. Rechazar claves o tipos inválidos.
- Identidad de partida: crear, guardar, reanudar.
- Log canónico: lo que ocurrió, no el prosa del modelo.

**Listo cuando:** se puede jugar varios turnos con el adapter falso, cerrar, reabrir y ver el mismo mundo.

## Fase 2 — Adapter de LLM real

**Objetivo:** un solo puerto, tres backends posibles, ninguno filtrado en el núcleo.

- Implementar el puerto para **uno** de: OpenAI, Gemini, llama.cpp. El primero es el que desbloquee desarrollo (probablemente OpenAI o Gemini por iterar rápido; llama.cpp para el criterio “local”).
- Normalizar petición/respuesta al contrato de turno. Reintentos y error de parseo: el núcleo no se cae; pide de nuevo o aborta el turno con mensaje claro.
- Configuración por entorno/archivo: proveedor, modelo, endpoint. Cero imports de SDK de vendor fuera del paquete `adapters/`.
- Adapter de llama.cpp (HTTP o bindings) como segundo backend, para validar que el puerto aguanta local.

**Listo cuando:** cambiar `provider=openai` por `provider=llamacpp` (o gemini) no toca el bucle. El JSON inválido no corrompe SQLite.

## Fase 3 — Juego directo usable

**Objetivo:** CoreTales se usa sin escribir triggers. Prompt de sistema + estado bastan.

- Prompt de sistema estable: rol de director, obligación de JSON, respeto al estado recibido.
- Seed de mundo: un prompt o un JSON inicial (lugar, PC, un NPC).
- Salida narrativa en consola; el JSON crudo no se muestra salvo modo debug.
- Generación de variables nuevas con validación mínima (nombre, tipo, valor).

**Listo cuando:** una sesión de 20–30 turnos en un género cualquiera se siente coherente al reanudar, sin autoría extra.

## Fase 4 — Triggers y eventos

**Objetivo:** orquestar sin fork del motor.

- Modelo de datos: evento (hecho) vs trigger (regla: cuando / entonces).
- Momentos del bucle: `before_infer`, `after_commit` (y solo esos, al inicio).
- Acciones de trigger mínimas: inyectar contexto, fijar escena, vetar acción, encolar evento, cambiar flag, elegir prompt/plantilla.
- Definición en datos (JSON/YAML) más que en Python. Hooks en código como escape, no como camino por defecto.
- Triggers vacíos = comportamiento de Fase 3.

**Listo cuando:** un autor describe “si el jugador entra en la taberna, forzar escena X” en un archivo, sin parchear el núcleo, y el uso directo sigue igual.

## Fase 5 — Orquestación de historia

**Objetivo:** generación dirigida de un arco, no solo ganchos sueltos.

- Escenas o beats: un trigger puede activar un beat y desactivar otros.
- Presupuestos de generación: el adapter recibe restricciones extra (debe mencionar Y, no puede matar a Z, el tono es W).
- Cadenas: `after_commit` dispara el siguiente beat.
- Herramienta mínima de autor: validar el archivo de triggers, listar qué se dispararía dado un estado.

**Listo cuando:** se puede contar un acto corto (llegada → conflicto → cierre) con triggers, y el LLM rellena el medio sin saltarse los beats.

## Fase 6 — Dureza y operación

**Objetivo:** que no se rompa al usarlo de verdad.

- Tests del núcleo: deltas, contexto, triggers, persistencia. Sin llamar a APIs de pago.
- Contrato del adapter: tests con JSON de ejemplo (válido, truncado, extra fields).
- Límites: tamaño de contexto, recorte del log, no mandar el mundo entero al LLM.
- Observabilidad mínima: log de turno (ids, proveedor, tokens si aplica, triggers disparados).

**Listo cuando:** el núcleo se testea en CI; una partida larga no hincha el prompt sin control.

## Fuera de alcance (hasta que el núcleo esté aburrido de tan estable)

- UI gráfica, web o motor de mapa 2D.
- Multijugador.
- Economía, combate o inventario como sistemas hardcodeados (pueden existir como datos + triggers).
- Marketplace de aventuras, editor visual, plugin de terceros.
- Un segundo lenguaje de runtime. Python basta.

## Dependencias entre fases

```
0 contrato  →  1 núcleo  →  2 adapter LLM  →  3 juego directo
                                    ↘
                                      4 triggers  →  5 orquestación
                                                    ↘
                                                      6 dureza (puede solaparse desde 1)
```

Fase 6 no espera al final: tests del núcleo empiezan en Fase 1. Lo que sí espera es no diseñar un editor de aventuras antes de tener el puerto de LLM y dos triggers reales.

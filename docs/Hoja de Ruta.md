# Hoja de Ruta

Propuesta, no compromiso. El orden es el inverso al de un motor “de papel”: primero un LLM real que obedece y devuelve JSON; después el núcleo que interpreta esas llamadas; después una partida que se guarda y se reanuda. Lo demás (seeds, triggers, paquetes de aventura) se abre con los primeros usuarios, no se diseña antes.

Cada fase debe poder usarse sola. La siguiente se apoya en ella; no la reescribe.

## Fase 1 — Conversar con el modelo

**Objetivo:** un LLM conectado, con contexto precargado, sin persistencia. Demostrar que entiende las instrucciones y responde JSON claro.

- Puerto `LlmAdapter` real desde el día uno (un provider: Gemini u OpenAI). llama.cpp puede esperar.
- Prompt de sistema en el núcleo: rol, obligación de JSON, forma mínima del objeto (ops y/o narración). El mismo prompt para cualquier provider.
- CLI: el usuario escribe texto libre; se imprime la respuesta. Modo debug muestra el JSON crudo.
- Contexto precargado en memoria (un bloque de instrucciones + un mundo mínimo de ejemplo). Nada de SQLite.
- Reintento si el JSON sale malformado; si vuelve a fallar, se informa y se aborta el turno (no hay estado que corromper).

**Listo cuando:** se puede hablar varios turnos, el modelo sigue el contrato, y el JSON es parseable de forma estable. Si esto no aguanta, no hay motor que construir.

## Fase 2 — El núcleo como interlocutor

**Objetivo:** dejar de mandar “todo el mundo” en un prompt. El LLM habla con el sistema: pide lo que necesita, el núcleo responde, y así en varias llamadas por cada input del jugador. Aquí se moldea cómo funciona CoreTales.

- Parsear el JSON: lista de operaciones y/o peticiones de lectura (`get` entidad, relaciones, log reciente, etc.).
- Bucle interno por turno de usuario: llamada → el núcleo ejecuta lecturas o acumula ops → nueva llamada con el resultado → hasta que el modelo entrega la narración (o aborta).
- Estado en memoria. Guardar y aplicar ops ya cuenta; el disco puede esperar.
- El adapter sigue siendo un solo método síncrono. El bucle de “el modelo consulta al sistema” vive en el núcleo, no en el vendor.
- Cada petición al LLM es independiente (sin ventana de chat acumulada). El núcleo recorta y entrega solo lo pedido.
- Turno atómico respecto al jugador: si una llamada falla del todo, no se aplica el lote; se informa y se puede repetir el input.

**Listo cuando:** un input del jugador provoca varias idas y vueltas, el modelo obtiene datos a demanda, aplica ops coherentes, y la consola muestra solo prosa (JSON en debug). El contrato de “qué puede pedir el LLM” está claro, aunque el almacén aún no sea un archivo.

## Fase 3 — Partida usable

**Objetivo:** jugar de verdad. Quizá sin seed ni mundo precargado: el modelo inventa al arrancar. Lo que importa es coherencia, estado en disco y reanudar.

- Una base = una partida (SQLite + JSON libre). Tras cada interacción exitosa, el estado queda escrito. No hay botón de guardar.
- Reanudar: abrir el archivo, seguir. El histórico de prosa es opcional (para mostrar chat); la partida vive en entidades y hechos.
- Coherencia en 20–30 turnos: slugs, mapa libre en entidades, el LLM como fuente de verdad narrativa; el núcleo es registro consultable.
- CLI agnóstica: solo texto libre. Si falla la API o el JSON, se informa; el usuario reintenta o cierra.
- Sin comandos `/state` ni `/save` para el jugador. Debug solo en desarrollo.

**Listo cuando:** se cierra el proceso, se vuelve a abrir la misma partida, y el mundo (y si aplica el chat) sigue donde quedó, sin seed de autor.

## Fase 4 — Abierta (alfa)

**Objetivo:** partidas precreadas y lo que pida el uso real. No se cierra el diseño aquí: evoluciona con los primeros alpha users.

Candidatos, no promesa:

- Seed: prompt de mundo + datos que pueblan la base (NPCs, lugares, eventos pasados).
- Triggers como datos JSON (predicados simples, una vez). Solo si hacen falta; la versión jugable puede no traerlos.
- Más adapters (llama.cpp, otro provider) cuando alguien los necesite.
- Paso del tiempo, variables de entorno, formato empaquetado para distribuir aventuras.
- Lo que la alfa demuestre que falta (y lo que sobre).

**Listo cuando:** no aplica. Esta fase no tiene criterio de cierre; se revisa con partidas reales.

## Fuera de alcance (hasta que el núcleo esté aburrido de tan estable)

- UI gráfica, web o motor de mapa 2D.
- Multijugador.
- Economía, combate o inventario hardcodeados.
- Editor visual, marketplace, plugins.
- Suite de tests / CI. Se prueba al construir; tests son una decisión futura.
- Un segundo lenguaje de runtime. Python basta.

## Dependencias entre fases

```
1 LLM + JSON          →  2 núcleo (el modelo consulta al sistema)
                              →  3 partida (disco + reanudar)
                                    →  4 abierta (seeds, triggers, alfa)
```

No hay fase de adapter falso ni de persistencia antes de hablar con el modelo. El disco entra cuando el JSON y el bucle de consulta ya sirven. Las aventuras de autor no bloquean jugar.

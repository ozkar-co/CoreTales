# Enfoque y decisiones

Por qué CoreTales no es un chatbot con memoria, y por qué el núcleo tiene que ser estricto. La arquitectura concreta está en [Descripción del Proyecto.md](Descripción%20del%20Proyecto.md). Las fases, en [Hoja de Ruta.md](Hoja%20de%20Ruta.md).

Este texto no es un registro de parches. Es el argumento: qué experiencia se busca, qué fallos hay que impedir, y por qué un LLM pequeño solo traduce.

## Qué se busca

Una mezcla de tres formas de jugar, no un chat que finge ser las tres:

- **Novela gráfica:** escenas con peso, umbrales, un ritmo (incidente, tensión, clímax). El progreso no es “el modelo se acuerda de seguir la trama”.
- **Aventura conversacional:** el jugador escribe lo que sea; el mundo reacciona con reglas, no con complacencia.
- **Chat tipo Character AI / Dungeon AI:** prosa inmediata, NPCs con voz, libertad de inventar un detalle (una fobia, un objeto). Eso no implica que el modelo *sea* el mundo.

El jugador ve solo texto. El motor ve números, etiquetas y umbrales.

## Tres fallos que el diseño tiene que hacer difíciles

No son bugs de un prompt. Son modos de fallo de “el LLM simula el mundo”.

### Adulación (sycophancy)

El modelo quiere ser un buen compañero de juego. Si el jugador empuja, el NPC cede, el mundo se dobla, el jefe nunca humilla, la fobia se olvida cuando estorba. En un chat eso se siente “mágico”. En una aventura se siente vacío: no hay resistencia, no hay costo.

**Decisión:** el impacto (deltas de afinidad, estrés, dominancia, peso de género) lo **aplica el motor**, con escalas y topes. El LLM de entrada *propone* una lectura de la intención; no escribe el estado final. Un NPC con afinidad baja no puede narrarse cariñoso porque el motor no le entrega esa máscara.

### Deriva de contexto (context drift)

Si la memoria es la ventana de chat, cada turno arrastra prosa vieja. A las pocas pantallas el modelo mezcla la taberna de un ejemplo con la oficina de ahora, o “recuerda” un hecho que solo existió en una frase. El contexto de 4k se llena; lo que cabe no es canónico.

**Decisión:** la prosa histórica no es la memoria. El motor guarda núcleo, etiquetas y un **resumen enrollable** (un párrafo). Cada llamada al LLM lleva un paquete mínimo: lo de esta etapa, no la novela entera.

### Contagio de persona (persona bleed)

El modelo no distingue bien “tú = quien escribe” de “Ivy, la NPC”. En las pruebas, el jugador observaba a Ivy y el texto lo convertía *en* Ivy. También se copian plantillas (`pc.nombre`) y se spawnean `oficina.1` … `oficina.28`: el modelo rellena tokens cuando no sabe qué objeto crear.

**Decisión:** identidad y escena las fija el motor (quién, dónde, cuándo, qué máscara). El LLM de narración recibe “narra *esto*” con variables ya resueltas. El LLM de traducción extrae intención; no inventa la ficha del PC.

## Por qué un LLM omnisciente no aguanta (ni en CPU, ni en historia)

La primera línea de diseño era: un modelo interpreta la acción, propone ops y narra en el mismo soplo. Un 7B de roleplay copió ejemplos, cambió el punto de vista y se ahogó en llamadas largas. Un 3B instruct empezó a devolver JSON coherente *como prosa*, pero las ops seguían rotas: slugs sin contrato, `time` colgado en la entidad equivocada, `scene` intocado, narrative = parafraseo del input.

Eso no se arregla con un prompt más largo. Pedirle al mismo modelo que recuerde reglas, calcule estados, no se adule, no se contagie y escriba bien es **tres oficios**. En CPU de gama media, además, una ventana gorda no corre en tiempo real.

**Decisión:** el LLM local (3B, luego 7B si hace falta) es un **periférico de traducción**. El mundo lo simula Python, como un motor de aventura clásico dirigido por eventos. El modelo grande, si se usa, trabaja **offline**: no en el turno del jugador.

## Los cinco pilares (y por qué cada uno)

### 1. Dos etapas: el LLM no responde al jugador en la primera llamada

**Input (traducir).** Texto libre → JSON chico: intención, entidades mencionadas, deltas propuestos. El modelo no narra. Contexto mínimo. Grammar/JSON schema. Barato.

**Motor.** Valida, recorta, aplica núcleo, apila tags, mira umbrales de género, elige máscara y átomos precalculados. Aquí vive la verdad.

**Output (narrar).** El motor arma un prompt rígido: estado ya resuelto + átomos + resumen. El LLM solo viste de prosa. No puede “arreglar” la afinidad en el texto de forma que contradiga el paquete: si lo intenta, el siguiente turno el motor vuelve a inyectar los números reales.

Dos llamadas cortas vencen a una llamada omnisciente: menos tokens, menos deriva, menos oportunidad de que la narración reescriba el mundo.

### 2. Núcleo vs máscara: el género puede mutar sin borrar a la gente

Si el “jefe” es un blob de prosa, al pasar de oficina a mafia el modelo reinventa al personaje. Las interacciones pasadas se evaporan o se contradicen.

**Núcleo:** dimensiones abstractas que el motor nunca tira (afinidad, dominancia, estrés, …). No son lore. Son ejes para *cualquier* máscara.

**Máscara (lens):** arquetipo temporal según el vector de género (“capo corrupto”, “mandamás de RR.HH.”). El motor la inyecta. El núcleo sigue ahí: alta afinidad hacia el jugador + máscara de capo ≠ jefe que de pronto te odia porque el prompt ahora dice “mafia”.

Por eso el motor **sí** conoce unas pocas dimensiones. No conoce “magia” ni “oro” como sistemas hardcodeados; conoce relaciones y presión, que sobreviven al cambio de vestuario.

### 3. Etiquetas planas y resumen enrollable: espontaneidad sin árbol infinito

Preprogramar un booleano por cada ocurrencia posible mata la libertad tipo Dungeon AI. Dejar que el chat recuerde “es alérgico a los gatos” mata la coherencia.

**Fuzzy tags:** la etapa 1 puede extraer `[fobia_gatos]`. El motor la apila en la entidad, sin semántica profunda. En llamadas futuras la inyecta. El NPC no “olvida” porque el modelo se saturó; olvida solo si el motor comprime o descarta tags (política explícita).

**Rolling state:** de vez en cuando el motor comprime hechos en un párrafo canónico. Ese párrafo es inyectable. La prosa del chat es para el jugador al reanudar, no para el modelo.

### 4. Generación sintética offline: el 3B no tiene que ser brillante en vivo

La riqueza (perfiles, tablas de reacción, sensorial, plantillas de escena) no puede salir de un 3B en 512 tokens sin alucinar ops. Un modelo grande o de pago **fuera de línea** llena SQLite con átomos. En runtime el motor elige filas; el LLM local ensambla. El turno sigue siendo barato. La “creatividad” cara se paga una vez, al generar el mundo o el paquete de aventura.

### 5. Vectores de género, no un mapa de nodos

Moverse de un nodo A a un B es una aventura de grafo. Character AI no se juega así; el jugador tira hacia donde quiere. El motor rastrea pesos (`mundano: 40`, `misterio: 60`). Cuando las acciones cruzan umbrales, avanza un **beat** universal (incidente incitador, clímax) y cambia máscaras y obstáculos.

El LLM no “decide que ya toca el plot twist”. El motor cruza un número y le ordena narrar el beat con el género que ganó. Así hay novela gráfica (ritmo) sin ramificar mil nodos y sin esperar a que el modelo se acuerde del arco.

## Qué queda igual a propósito

- Texto libre in, prosa out. Sin comandos para el jugador.
- Adapter de LLM: un `complete(system, user)`; llama.cpp u otros detrás. URL en el adapter; `.env` solo secretos.
- Una SQLite por partida. Guardado al cerrar el turno con éxito.
- El motor no censura. Unlicense. El contenido es de quien juega.
- KISS: dos prompts cortos, no un agente de ocho herramientas.

## Qué se rechaza (y por qué)

| Tentación | Por qué no |
|---|---|
| Un solo JSON con ops + narrative | La prosa y el estado se pelean; el 3B rellena ops de más |
| El LLM como fuente de verdad | Adulación y contagio de persona |
| Ventana de chat como memoria | Deriva de contexto; CPU |
| Árbol de flags por cada gag posible | No escala; mata la espontaneidad |
| Género hardcodeado (combate, magia) | El núcleo debe sobrevivir a un cambio de máscara |
| Creatividad en vivo del 3B como riqueza | Se reserva al modelo grande, offline |

El código de prototipo (una llamada que pedía ops y narrativa juntas) sirvió para ver estos fallos. No es el modelo mental del producto.

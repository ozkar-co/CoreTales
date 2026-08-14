# Preguntas a Resolver

Decisiones abiertas. El motor no debería crecer hasta responder las que marcan contrato (estado, adapter, turno). Las demás pueden esperar a tener un prototipo.

## Contrato del núcleo

1. **¿Qué es exactamente un delta de estado?** ¿Lista de operaciones (`set`, `inc`, `spawn`, `rel`) o un parche JSON del mundo? Lo primero es más seguro y DRY; lo segundo es más fácil para el LLM y más fácil de corromper.
R. Vamos con una lista de operaciones.
2. **¿Quién puede crear entidades y claves nuevas?** ¿Solo el LLM, solo triggers, ambos? Si ambos, ¿la validación es la misma? 
R. Ambos pueden crear, la idea es que haya libertad a la hora de crear las etiquetas que sean, no neceistamos concistencia entre entidades, solo orden y que la IA pueda intrepretarlo bien.
3. **¿El núcleo valida semántica o solo forma?** Ejemplo: ¿puede `confianza` bajar de 0? ¿Eso es esquema, trigger, o se deja al LLM?, 
R. Deberiamos dejar escalas fijar que la IA pueda usar segun se adapte mejor, creo que valores entre 0 y 1 podrian ser lo mas facil de entender o etiquetas de texto, la idea es que la IA lo pueda interpretar, mas que el sistema.
4. **¿Un turno es atómico?** Si el JSON es válido a medias, ¿se descarta todo o se aplica lo parseable? 
R. el turno es atomico, si algo falla se repite o se informa al usuario
5. **¿Hay acciones internas sin jugador** (ticks de hambre, paso del tiempo, eventos de mundo) o solo turnos de input?
R. solo tunos del input, el sistema es flexible, el usuario puede hacer que pasen dias, horas, semanas, años, le compete al LLM interpretar y ajustar los valores, quizas una marca de tiempo (dentro del tiempo del juego) pueda ayudar a recalcular un estado, por ejemplo en lugar de cambiar todos los npcs, si se da un salto en el tiempo al cargar un npc, se puede calcular el tiempo pasado y usar eso para actualizar el npc acorde con eso.

## Adapter de LLM

6. **¿El contrato del puerto es síncrono** (`complete(context) -> TurnResult`) **o streaming?** La CLI no necesita streaming al inicio; añadirlo después cambia el contrato.
R. Inicialmente sincrono, quizas una cola para manejar los eventos o estados, si ocurren varias cosas, o han ocurrido varias cosas, entra todo en el contexto para que la IA pueda interpretarlo e informarlo al usuario.
7. **¿Un solo método o varios?** Un `infer_turn` vs. `narrate` + `resolve_action` + `invent_stat`. Un método cumple KISS; varios pueden bajar alucinaciones.
R. un solo metodo.
8. **¿Dónde vive el prompt de sistema?** ¿En el núcleo (igual para todos los providers) o en el adapter (por si Gemini y llama.cpp se comportan distinto)? Mezclar los dos suele duplicar lógica.
R. en el nucleo, debe ser el mismo para cualquier provider.
9. **¿Cómo se trata JSON malformado?** ¿Reintento con “devuelve solo JSON”, turno abortado, o fallback a narración sin delta?
R. reintento, y si falla, muestra el error y aborta el turno, asi durante una etapa inicial de debug se pueden estudiar los casos para solucionarlos despues.
10. **¿llama.cpp cómo?** Servidor HTTP compatible OpenAI, bindings Python, o subprocess. Determina si OpenAI y llama.cpp pueden compartir cliente.
R. como el sistema es agnostico del adapter, en el adapter ajustaremos dependiendo de lo que vayamos implementamos. inicialmente vacio.
11. **¿Autenticación y secretos?** Solo variables de entorno, o también archivo local ignorado por git. Nada de claves en el estado de la partida.
R. un .env con los datos, se ajusta dependiendo de las necesidades.
12. **¿El adapter ve el mundo crudo o un view-model?** Recortar contexto es responsabilidad del núcleo; si el adapter recorta también, hay dos políticas.
R. el nucleo recorta y da aceso a lo que considere necesario, cada peticion puede ser independiente ya que mantener ventana de contexto incrementa la carga y puede inducir alucinaciones.

## Estado y persistencia

13. **¿Una base por partida o una base con muchas partidas?** Afecta backup, “compartir save” y tests.
R. una base por partida, el database completo es la partida, con todos sus datos, estados, mundos, etc... las historias precreadas funcionan es como un seeder que inicializa la base de datos con la informacion necesaria.
14. **¿IDs estables** (slug `npc.mesonero`) **o UUID?** El LLM escribe mejor slugs; los slugs colisionan.
R. es mas facil tener slugs, si hay colision podemos evaluar que el nucleo añada un contador, o una llamada extra al llm para evaluar si es el mismo npc (y fusionarlo) o son dos distintos y darle un nombre nuevo al segundo npc. incialmente con el contador.
15. **¿Esquema de relación** (sujeto, predicado, objeto, valor) **o mapa libre en cada entidad?** El grafo explícito escala mejor; el mapa libre es más simple al inicio.
R. lo haremos con mapa libre.
16. **¿El log guarda prosa, hechos, o ambos?** La prosa no debería ser la memoria; ¿se guarda igual para re-narrar?
R. el log de prosa se guarda aparte como historico para consulta o informacion del usurio, para cargar el historial de chat al recargar la partida, pero es prescindible para guardar la partida.
17. **¿Hasta dónde es JSON libre dentro de SQLite?** Sin ningún esquema, el motor no puede validar. Con demasiado esquema, deja de ser agnóstico.
R. inicialmente sin esquema, si la partida es precreada puede incluir instrucciones para el LLM con la estructura, pero es responsabilidad del LLM mantener la concordancia, a la final no importa si las estructuras no coinciden si no que el LLM pueda construir respuestas coherentes.

## Triggers y orquestación

18. **¿Los triggers son datos puros o pueden llamar Python?** Datos = portable y DRY. Hooks = poder. Si hay hooks, ¿cuál es el sandbox y la firma?
R. los triggers son datos puros es solo informacion para el LLM... aunque quizas justifique tener un sistema fijo y robusto al menos para el paso del tiempo y las "variables" de ambiente o de condiciones espedificas para poder hacer un monitoreo, por ahora vamos con lo mas simple.
19. **¿Condiciones con qué lenguaje?** Predicados JSON (`{"path": "npc.mesonero.confianza", "lt": 0}`), expresiones, o código. Las expresiones crecen a un DSL.
R. predicados simples en JSON
20. **¿Prioridad y conflicto?** Dos triggers en el mismo momento: ¿orden de registro, prioridad numérica, error?
R. El llm resuelve a la final solo se le pasan los datos para que interprete para el usuario.
21. **¿Un trigger se dispara una vez, N veces, o mientras la condición sea verdadera?** Hace falta política de `once` / `cooldown` / `while`.
R. Los trigers son unicos pasan una vez y ya. al menos al principio, hay que mantener el sistema simple, al punto de que quizas quitemos los trigers de la version inicial.
22. **¿Quién gana si el LLM y un trigger se contradicen?** Ejemplo: el trigger veta matar al rey y el JSON lo mata. El documento de visión dice que el estado (y por tanto el trigger ya aplicado) gana; hay que clavarlo en el validador.
R. El llm dicta, aunque alucine, el motor solo lleva un el registro de variables, es casi como un log al que el llm puede acceder y consultar de forma dinamica, pero la verdad la dicta el llm.
23. **¿Las escenas/beats son un tipo de trigger o un objeto aparte?** Un tipo menos es más KISS; un objeto escena ayuda al autor a ver el arco.
R. lo que sea mas simple, necesitamos priorizar la simplicidad.
24. **¿El autor puede sustituir al LLM en un trigger** (texto fijo, sin llamada) **o siempre hay inferencia?** Sustituir barata turnos y da control duro.
R. siempre hay inferencia.

## Uso directo vs orquestación

25. **¿El seed de mundo es un prompt, un JSON, o ambos?** Prompt solo es rápido y sucio; JSON es reproducible.
R. el seed tiene ambos, un prompt que describe el mundo y el json o archivo sql que pobla la base de datos, con npcs precargados, lugares ya existentes e incluso eventos pasados.
26. **¿Hace falta un “modo autor” en la CLI** (recargar triggers, inspeccionar estado) **o basta editar archivos y reiniciar el turno?**
R. solo editar archivos.
27. **¿Las aventuras orquestadas son un paquete** (prompt + seed + triggers) **con un formato versionado?** Si sí, cuándo se congela ese formato.
R. inicialmente seran un conjunto de archivos, luego crearemos un formato cuando pensemos en distribuir, en una fase alfa e incluso beta podemos dejar todo abierto.

## Experiencia de juego

28. **¿La entrada es texto libre siempre, o también comandos del motor** (`/state`, `/save`, `/retry`)?
R. la entrada siempre es texto libre, sin comandos sin ordenes, agnostico para el usuario, el usuario dice lo que sea, la IA interpreta.
29. **¿El jugador ve mecánicas** (números de confianza) **o solo prosa?** ¿Eso es config de partida?
R. el usuario solo ve prosa, quizas un modo debug puede mostrar mas detalles pero solo durante el desarrollo.
30. **¿Hay given-when-then para “el LLM se negó / la API falló / el usuario abortó”** en mitad de turno?
R. si falla, falla, se informa al usuario que falló, puede repetir el prompt o revisar que paso o cerrar el juego. no hay boton de "guardado", luego de cada interaccion exitosa quedó en los archivos el estado actual del juego, asi es mas facil retomar.

## Alcance y no-objetivos

31. **¿Python 3.x mínimo y dependencias permitidas?** Stdlib + SQLite vs. un HTTP client. Cada SDK de vendor pesa en el adapter, no en el núcleo.
R. Lo mas minimo posible, con un venv para tener dependencias, pero solo las fundamentales para estilos en consola, manejo de base de datos o utilidades de procesamiento.
32. **¿Licencia y tono de contenido?** El documento original habla de cero censura vía modelo local. ¿Eso es requisito del motor (no filtrar en núcleo) o solo una opción de adapter?
R. el proyecto es Unlicence, libre para quien quiera como quiera, y el contenido es solo responsabilidad del usuario, el modelo es abierto, libre y sin censura, libertad de datos, libertad de accion.
33. **¿Tests de integración contra APIs reales** o solo contratos con fixtures? Lo segundo es DRY y barato; lo primero se pudre.
R. sin tests, se prueba a medida que se va haciendo, si crece y se deciden añadir sera una decision independiente en el futuro. por ahora vamos haciendo y probando los mismos desarrolladores.


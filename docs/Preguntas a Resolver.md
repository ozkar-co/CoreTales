# Preguntas a Resolver

La visión y el contrato (JSON, ops, bucle, disco) están en [Descripción del Proyecto.md](Descripción%20del%20Proyecto.md).

Quedan dos decisiones. El resto se cerró para no inventar un segundo diseño encima del que ya acordamos.

## 1. Provider inicial

Gemini u OpenAI. El otro espera. llama.cpp sigue vacío. 

R. vamos con llama.cpp, ya lo estoy instalndo, un modelo de 7B de parametros, creo que será suficiente para probar la eficiencia del motor.

Esto no cambia el núcleo; cambia con qué iteramos la fase 1. Hace falta una clave en `.env`.

## 2. Qué sabe el núcleo al armar el primer paquete

El modelo no recibe el mundo entero. Hay que decidir **cuánto “entiende” el núcleo** de la partida. De eso sale si existen slugs reservados o no.

**A — Almacén de slugs (KV).** El primer paquete es: texto del jugador + lista de slugs conocidos. El núcleo no sabe quién es el PC ni qué es un lugar. El modelo hace `get` / `list` de lo que necesite. El núcleo permanece ciego a la ficción. Coste: una o dos lecturas extra por turno.

**B — Un PC reservado.** Igual que A, pero `meta` guarda el slug del jugador y el núcleo incluye ese `get` siempre. El núcleo sabe *quién* juega, no *dónde* está. Un solo nombre mágico.

**C — Escena.** El núcleo interpreta `location` (o equivalente), arma “aquí y ahora” (PC, lugar, presentes) y se lo mete al primer paquete. Menos idas y vueltas. El núcleo deja de ser un registro tonto: hay campos con significado de juego.

A es lo más KISS y lo más fiel a “el motor no conoce el género”. C es lo más cómodo para el modelo y lo primero que se vuelve un esquema rígido. B es el medio.

La fase 1 puede hablar con contexto precargado sin resolver esto; la fase 2 sí lo necesita.

R. vamos con la opcion C, es hora de ponerle algo de riendas al motor, creo que lo fundamental ser definir un quien (tanto PC como otros actores, inicialmente el PC), un donde (la locacion y detalles de la escena) y un cuando (la forma como llevemos el conteo del tiempo, las acciones del jugador o desiciones del llm lo pueden cambiar, pero es importante llevar un control la escala puede cambiar dependiendo del juego, pero lo importante es que el motor lleve un registro, esto quizas cambie varias cosas.) 
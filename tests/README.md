# Banco de escenas

No son tests unitarios y no pretenden pasar o fallar. Son partidas guionadas
para **leer** cómo reacciona el motor mientras se desarrolla. Cuando jugando a
mano aparece una situación interesante (o mal resuelta), se añade aquí y queda
comparable en el tiempo.

```bash
python3 tests/correr.py --seco        # solo motor, sin LLM ni coste
python3 tests/correr.py              # ciclo completo (etapa 1 + etapa 2)
python3 tests/correr.py 02_rival     # una escena por prefijo
```

Cada corrida crea una partida nueva y deja en `tests/logs/`:

- `<escena>_<fecha>.md`: por turno, la intención, el impacto en cada eje
  (antes -> después), los puntajes de todos los impulsos, el desenlace, la
  atmósfera derivada, el paquete que recibió la etapa 2 y la prosa.
- `<escena>_<fecha>.sqlite`: la partida, para mirarla con `sqlite3`.

## Formato de escena

```
# titulo: lo que se está probando
> lo que escribe el jugador
= {"acto": "...", "valoracion": {...}}
```

La línea `=` es la intención fija de ese turno. Sirve para el modo `--seco`:
sin ella no hay nada que evaluar sin LLM. Con LLM se ignora, porque justamente
lo que se quiere ver es qué intención produce la etapa 1.

## Qué mirar en el log

- **desenlace**: `ocurre`, `forcejeo`, `forzado` o `bloqueado`. Si un acto
  invasivo sobre alguien hostil sale `ocurre` y consentido, el motor está
  siendo complaciente.
- **puntajes**: por qué ganó ese impulso. Si `ceder` gana con odio alto, los
  pesos de `src/mente.py` están mal.
- **estado / vínculo**: el acto tiene que mover ejes. Si no mueve nada, la
  valoración de la etapa 1 vino en cero.
- **paquete de la etapa 2**: si el canon dice `forcejeo` y la prosa narra
  placer, el problema es del prompt, no del motor.

## Escenas

| escena | qué prueba |
| --- | --- |
| `01_oficina_ivy` | abrir a alguien neutral lleva turnos; el primer toque no la hace ceder |
| `02_rival_forcejeo` | odio alto + acto sexual = rechazo o violencia; límite entre forcejeo y forzado; secuelas |
| `03_salto_de_tono` | la atmósfera sigue a quien recibe el acto; el estado de un NPC no contagia al otro |

# CoreTales

Motor narrativo procedural en texto. El mundo vive en un registro; el LLM interpreta, consulta y narra.

Licencia: Unlicense. El contenido de cada partida es responsabilidad de quien juega.

## Qué es

Python, consola, un adapter de LLM. El núcleo no conoce géneros: sí conoce una escena (quién, dónde, cuándo). Detalle en [docs/Descripción del Proyecto.md](docs/Descripción%20del%20Proyecto.md). Fases en [docs/Hoja de Ruta.md](docs/Hoja%20de%20Ruta.md).

## Layout

```
src/         código (fase 1: memoria, sin SQLite)
scripts/     arranque y utilidades
docs/        visión y hoja de ruta
```

Sin dependencias extra: stdlib. El LLM se asume ya sirviendo (llama.cpp u otro compatible OpenAI). La URL va en el adapter, no en `.env`. `.env` es solo para secretos.

## Uso

Hace falta un servidor en `http://127.0.0.1:8080/v1`. Luego, desde la raíz del repo:

```bash
./scripts/run.sh
```

Probar que el modelo responde JSON:

```bash
./scripts/test_llm.sh
```

JSON crudo en stderr:

```bash
CORE_TALES_DEBUG=1 ./scripts/run.sh
```

El jugador solo ve prosa. Ctrl-D o Ctrl-C para salir. No hay comandos.

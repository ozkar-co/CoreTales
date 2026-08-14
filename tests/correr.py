#!/usr/bin/env python3
"""Banco de escenas. No son tests unitarios: son partidas guionadas para leer logs.

    python3 tests/correr.py                 # todas las escenas, con LLM
    python3 tests/correr.py 02_rival        # una escena (por prefijo)
    python3 tests/correr.py --seco          # sin LLM: solo el motor, con las
                                            # intenciones fijas de cada escena

Cada corrida usa una partida nueva y deja un log en tests/logs/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import mente  # noqa: E402
from engine import Engine  # noqa: E402
from store import Store  # noqa: E402

ESCENAS = Path(__file__).resolve().parent / "escenas"
LOGS = Path(__file__).resolve().parent / "logs"


class SinLlm:
    """Tapón para el modo seco: si alguien lo llama, es un error del arnés."""

    def complete(self, *a, **k):
        raise RuntimeError("modo seco: falta la intención fija de este turno")


def leer_escena(path: Path) -> tuple[str, list[tuple[str, dict | None]]]:
    titulo = path.stem
    turnos: list[tuple[str, dict | None]] = []
    for linea in path.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s:
            continue
        if s.startswith("#"):
            if s.lower().startswith("# titulo:"):
                titulo = s.split(":", 1)[1].strip()
            continue
        if s.startswith(">"):
            turnos.append((s[1:].strip(), None))
        elif s.startswith("=") and turnos:
            turnos[-1] = (turnos[-1][0], json.loads(s[1:]))
    return titulo, turnos


def _diff(antes: dict[str, float], despues: dict[str, float]) -> str:
    partes = [
        f"{k} {antes[k]:.2f}->{despues[k]:.2f}"
        for k in antes
        if abs(despues.get(k, antes[k]) - antes[k]) >= 0.01
    ]
    return ", ".join(partes) if partes else "sin cambios"


def _tabla_perfil(store: Store) -> list[str]:
    out = ["| npc | tipo | estado | siente por ti | tags |", "| --- | --- | --- | --- | --- |"]
    for slug in store.npcs():
        p = store.perfil(slug)
        out.append(
            f"| {p['nombre']} | {p['tipo'] or '-'} | "
            f"{mente.resumen_estado(p['estado'])} | "
            f"{mente.resumen_vinculo(p['vinculo_con_pc']) if p['vinculo_con_pc'] else '-'} | "
            f"{', '.join(p['tags']) or '-'} |"
        )
    return out


def correr(path: Path, seco: bool, llm) -> Path:
    titulo, turnos = leer_escena(path)
    sello = time.strftime("%Y%m%d-%H%M%S")
    LOGS.mkdir(parents=True, exist_ok=True)
    partida = LOGS / f"{path.stem}_{sello}.sqlite"
    log = LOGS / f"{path.stem}_{sello}.md"

    store = Store(partida)
    engine = Engine(llm, store=store)
    lineas = [
        f"# {titulo}",
        "",
        f"escena: `{path.name}` | modo: {'seco (sin LLM)' if seco else 'con LLM'} | {sello}",
        "",
    ]
    print(f"== {titulo} ({path.name}) ==", file=sys.stderr)

    for i, (player, intent_fijo) in enumerate(turnos, 1):
        intent = intent_fijo if seco else None
        if seco and intent is None:
            lineas.append(f"## turno {i}\n\nsin intención fija: saltado\n")
            continue
        print(f"  turno {i}: {player[:60]}", file=sys.stderr)
        try:
            prosa = engine.turn(player, intent=intent, narrar=not seco)
        except Exception as e:  # el log importa más que la corrida
            lineas.append(f"## turno {i}\n\n> {player}\n\nFALLÓ: {e}\n")
            continue
        scene = store.get_scene()
        lineas.append(f"## turno {i}")
        lineas.append("")
        lineas.append(f"> {player}")
        lineas.append("")
        usado = engine.last_intent or {}
        lineas.append("intención:")
        lineas.append("")
        lineas.append("```json")
        lineas.append(json.dumps(usado, ensure_ascii=False, indent=2))
        lineas.append("```")
        lineas.append("")
        for r in store.last_resolucion:
            consent = (
                f" | consentido: {'sí' if r['consentido'] else 'NO'}"
                if r["invasivo"]
                else ""
            )
            lineas.append(
                f"**{r['nombre']}**: impulso `{r['impulso']}` (fuerza {r['fuerza']}) "
                f"-> desenlace `{r['desenlace']}`{consent} | empuje {r['empuje']} vs "
                f"resistencia {r['resiste']}"
            )
            lineas.append("")
            lineas.append(f"- estado: {_diff(r['estado_antes'], r['estado'])}")
            lineas.append(f"- vínculo: {_diff(r['vinculo_antes'], r['vinculo'])}")
            tensiones = ", ".join(f"{k} {v}" for k, v in r["tensiones"].items())
            lineas.append(f"- tensiones: {tensiones}")
            puntajes = ", ".join(f"{k} {v}" for k, v in r["puntajes"].items())
            lineas.append(f"- puntajes: {puntajes}")
            lineas.append("")
        if not store.last_resolucion:
            lineas.append("(nadie implicado)")
            lineas.append("")
        lineas.append(
            f"escena: lugar `{scene.get('location')}` | atmósfera "
            f"`{scene.get('atmosfera')}` | tropo `{scene.get('tropo')}`"
        )
        presentes = [
            (store._entity(s) or {}).get("nombre") or s for s in store.npcs_presentes()
        ]
        llevas = [f"{o['nombre']} x{o['cantidad']}" for o in store.inventario()]
        lineas.append(
            f"presentes: {', '.join(presentes) or 'nadie'} | "
            f"llevas: {', '.join(llevas) or 'nada'}"
        )
        fuera = store.fuera_de_escena()
        if fuera:
            lineas.append(f"fuera de escena: {', '.join(fuera)}")
        lineas.append("")
        lineas.append("<details><summary>paquete de la etapa 2</summary>")
        lineas.append("")
        lineas.append("```")
        lineas.append(engine.last_pack)
        lineas.append("```")
        lineas.append("")
        lineas.append("</details>")
        lineas.append("")
        if prosa:
            lineas.append("prosa:")
            lineas.append("")
            lineas.append(prosa)
            lineas.append("")

    lineas.append("## estado final")
    lineas.append("")
    lineas.extend(_tabla_perfil(store))
    lineas.append("")
    lineas.append("hechos vigentes:")
    lineas.append("")
    lineas.extend(f"- {h}" for h in store.hechos())
    lineas.append("")
    log.write_text("\n".join(lineas), encoding="utf-8")
    store.close()
    print(f"  log: {log}", file=sys.stderr)
    return log


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("escena", nargs="*", help="prefijo del nombre de escena")
    ap.add_argument("--seco", action="store_true", help="sin LLM, con intenciones fijas")
    args = ap.parse_args()

    todas = sorted(ESCENAS.glob("*.txt"))
    if args.escena:
        elegidas = [p for p in todas if any(p.stem.startswith(x) for x in args.escena)]
    else:
        elegidas = todas
    if not elegidas:
        print("no hay escenas que coincidan", file=sys.stderr)
        raise SystemExit(1)

    if args.seco:
        llm = SinLlm()
    else:
        from adapters.select import adapter_label, make_adapter

        llm = make_adapter()
        print(f"LLM: {adapter_label(llm)}", file=sys.stderr)

    for path in elegidas:
        correr(path, args.seco, llm)


if __name__ == "__main__":
    main()

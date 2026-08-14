"""Sorteo en [0, 1] con curva normal truncada. El modelo no tira."""

from __future__ import annotations

import math
import random

from schema import FUERZAS, SESGO


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def fuerza_de(raw: str | None) -> str:
    key = (raw or "medio").strip().lower().replace("é", "e").replace("ú", "u")
    return key if key in FUERZAS else "medio"


def sesgo(fuerza: str | None) -> float:
    return SESGO[fuerza_de(fuerza)]


def muestra(mu: float = 0.5, sigma: float = 0.16) -> float:
    """Normal truncada a [0, 1]. Lo típico es lo frecuente."""
    for _ in range(16):
        u1 = max(1e-12, random.random())
        u2 = random.random()
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        x = mu + sigma * z
        if 0.0 <= x <= 1.0:
            return x
    return clamp01(mu)


def efectivo(fuerza: str | None) -> float:
    """Una muestra centrada en el sesgo de esa fuerza."""
    return muestra(mu=sesgo(fuerza))


def resolver(actor: float, contra: float | None = None) -> tuple[str, float, float]:
    """Compara dos muestras. Sin oposición, el mundo es 0.5."""
    otro = 0.5 if contra is None else contra
    margen = actor - otro
    if margen >= 0.25:
        veredicto = "claro"
    elif margen > 0.0:
        veredicto = "pasa"
    else:
        veredicto = "falla"
    return veredicto, round(actor, 3), round(otro, 3)

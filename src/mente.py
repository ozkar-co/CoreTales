"""Modelo fijo de mente. Ejes generales; ninguna regla de escena.

El LLM no toca estos números. Solo valora el acto en ejes generales
(`VALORACION`) e infiere el perfil de quien aparece por primera vez.
De ahí en adelante el motor decide: impacto -> impulso -> desenlace.
"""

from __future__ import annotations

from typing import Any

# Volátil. Sube y baja cada turno, como niveles químicos.
ESTADO = (
    "excitacion",
    "enojo",
    "miedo",
    "estres",
    "dolor",
    "verguenza",
    "confianza",
    "energia",
)
# Fijo. Solo cambia con un evento canónico grande.
RASGOS = (
    "valentia",
    "dominancia",
    "impulsividad",
    "moral",
    "fuerza",
    "inteligencia",
    "apariencia",
    "sociabilidad",
)
# Dirigido: lo que A siente por B.
VINCULO = ("afecto", "odio", "respeto", "miedo", "deseo")
# Lo único que la etapa 1 dice del acto. Dimensiones, no verbos.
VALORACION = ("intensidad", "intimidad", "agresion", "exposicion", "afecto", "dominio")

ESTADO_BASE = {
    "excitacion": 0.10,
    "enojo": 0.10,
    "miedo": 0.10,
    "estres": 0.15,
    "dolor": 0.00,
    "verguenza": 0.10,
    "confianza": 0.50,
    "energia": 0.70,
}
RASGO_BASE = 0.5
VINCULO_BASE = {
    "afecto": 0.35,
    "odio": 0.05,
    "respeto": 0.40,
    "miedo": 0.10,
    "deseo": 0.10,
}
# Vuelta hacia la base, por turno.
REPOSO = {
    "excitacion": 0.10,
    "enojo": 0.06,
    "miedo": 0.08,
    "estres": 0.06,
    "dolor": 0.12,
    "verguenza": 0.08,
    "confianza": 0.04,
    "energia": 0.05,
}

IMPULSOS = ("ceder", "dominar", "hablar", "rechazar", "agredir", "huir", "congelar")
# Impulsos que no frenan el acto del jugador.
CEDEN = ("ceder", "dominar", "hablar")
DESENLACES = ("ocurre", "forcejeo", "forzado", "bloqueado")

FRASE_IMPULSO = {
    "ceder": "acepta; el cuerpo acompaña",
    "dominar": "no se opone: toma el control del momento",
    "hablar": "responde con palabras, no con el cuerpo",
    "rechazar": "se niega, lo dice y corta el contacto",
    "agredir": "responde con violencia: empuja, golpea, muerde",
    "huir": "se zafa y sale de ahí",
    "congelar": "se queda rígida; no consiente ni reacciona",
}
FRASE_DESENLACE = {
    "ocurre": "tu acto se completa",
    "forcejeo": "tu acto NO se completa: hay forcejeo",
    "forzado": "tu acto se completa por la fuerza, contra su voluntad",
    "bloqueado": "tu acto NO llega a pasar",
}
# Eje dominante -> anclas del catálogo, en orden de preferencia.
TONO_ESTADO = {
    "dolor": (("violenta", "hostil"), ("pelea", "forcejeo")),
    "enojo": (("hostil", "tensa"), ("rivalidad", "rechazo")),
    "miedo": (("oscura", "sombria", "tensa"), ("huida", "amenaza_velada")),
    "verguenza": (("humillante", "tensa"), ("humillacion", "rechazo")),
    "estres": (("tensa", "fria"), ("amenaza_velada", "rechazo")),
    "excitacion": (("erotica", "tensa"), ("seduccion", "roce")),
    "confianza": ((), ()),
    "energia": ((), ()),
}
TONO_DESENLACE = {
    "forcejeo": (("violenta", "hostil"), ("forcejeo", "pelea")),
    "forzado": (("violenta", "hostil"), ("forcejeo", "pelea")),
}
# Lo que hizo el NPC tiñe la escena antes que cualquier sugerencia del modelo.
TONO_IMPULSO = {
    "agredir": (("violenta", "hostil"), ("pelea", "forcejeo")),
    "huir": (("oscura", "sombria", "tensa"), ("huida", "amenaza_velada")),
    "congelar": (("oscura", "tensa"), ("humillacion", "amenaza_velada")),
    "rechazar": (("hostil", "fria", "tensa"), ("rechazo", "rivalidad")),
    "ceder": (("erotica", "tensa"), ("seduccion", "roce")),
    "dominar": (("erotica", "tensa"), ("seduccion", "roce")),
    "hablar": ((), ()),
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _num(raw: Any, default: float = 0.0) -> float:
    try:
        return clamp01(float(raw))
    except (TypeError, ValueError):
        return default


def estado_base() -> dict[str, float]:
    return dict(ESTADO_BASE)


def rasgos_base() -> dict[str, float]:
    return {k: RASGO_BASE for k in RASGOS}


def vinculo_base() -> dict[str, float]:
    return dict(VINCULO_BASE)


def limpiar(crudo: Any, ejes: tuple[str, ...]) -> dict[str, float]:
    """Se queda con los ejes conocidos de un dict del LLM. El resto se ignora."""
    if not isinstance(crudo, dict):
        return {}
    out: dict[str, float] = {}
    for eje in ejes:
        if eje in crudo:
            out[eje] = _num(crudo[eje])
    return out


def valoracion(crudo: Any) -> dict[str, float]:
    val = {k: 0.0 for k in VALORACION}
    val.update(limpiar(crudo, VALORACION))
    return val


def apertura(vinculo: dict[str, float]) -> float:
    """-1..1. Cuánto quiere a ese otro cerca. Un desconocido no está abierto."""
    v = vinculo
    bruto = (
        0.45 * v["deseo"]
        + 0.40 * v["afecto"]
        + 0.15 * v["respeto"]
        - 0.85 * v["odio"]
        - 0.25 * v["miedo"]
        - 0.35
    )
    return max(-1.0, min(1.0, bruto))


def impacto(
    val: dict[str, float],
    rasgos: dict[str, float],
    vinculo: dict[str, float],
) -> tuple[dict[str, float], dict[str, float]]:
    """Qué le hace el acto a los ejes. El signo lo pone el vínculo, no el verbo."""
    ap = apertura(vinculo)
    inten = val["intensidad"]
    intim = val["intimidad"]
    agr = val["agresion"]
    expo = val["exposicion"]
    afe = val["afecto"]
    dom = val["dominio"]
    de = {k: 0.0 for k in ESTADO}
    dv = {k: 0.0 for k in VINCULO}

    # sin corte: el mismo acto agrada o repugna según el vínculo, en grados.
    # al cuadrado, porque acercarse de golpe pesa más que la buena voluntad.
    grato = clamp01(0.5 + 0.5 * ap)
    ingrato = 1.0 - grato

    de["estres"] += 0.14 * inten
    de["energia"] -= 0.06 * inten

    de["excitacion"] += 0.55 * intim * grato**2 + 0.15 * afe * grato
    de["confianza"] += 0.20 * afe * grato
    de["enojo"] += (0.65 * intim + 0.35 * dom) * ingrato**3
    de["verguenza"] += 0.55 * expo * ingrato + 0.15 * expo * grato
    de["estres"] += 0.30 * intim * ingrato**3

    dv["deseo"] += 0.25 * intim * grato**2
    dv["afecto"] += 0.12 * afe * (0.5 + 0.5 * grato) - 0.25 * intim * ingrato**3
    dv["odio"] += (0.35 * intim + 0.15 * expo) * ingrato**3 - 0.06 * afe
    dv["respeto"] -= 0.10 * (intim + expo) * ingrato**3

    if agr > 0:
        de["dolor"] += 0.55 * agr * max(inten, 0.4)
        de["miedo"] += 0.50 * agr * (1.0 - rasgos["valentia"])
        de["enojo"] += 0.20 * agr + 0.45 * agr * rasgos["valentia"]
        de["estres"] += 0.25 * agr
        dv["miedo"] += 0.30 * agr * (1.0 - rasgos["valentia"])
        dv["odio"] += 0.30 * agr
        dv["respeto"] -= 0.15 * agr

    return de, dv


def _sobre_base(estado: dict[str, float], eje: str) -> float:
    """Cuánto sube un eje por encima de su reposo, normalizado 0..1."""
    base = ESTADO_BASE[eje]
    return clamp01((estado.get(eje, base) - base) / max(1e-6, 1.0 - base))


def tensiones(
    val: dict[str, float],
    estado: dict[str, float],
    rasgos: dict[str, float],
    vinculo: dict[str, float],
) -> dict[str, float]:
    """Las ganas de fondo: dañar, escapar, acercarse. De aquí salen los impulsos."""
    e, v = estado, vinculo
    provoca = max(
        val["intimidad"], val["agresion"], val["dominio"], val["exposicion"]
    )
    ganas = clamp01(
        0.45 * v["deseo"]
        + 0.40 * v["afecto"]
        + 0.35 * _sobre_base(e, "excitacion")
        + 0.25 * val["afecto"]
        - 0.60 * v["odio"]
    )
    return {
        "provoca": provoca,
        "ganas": ganas,
        "grato": clamp01(0.5 + 0.5 * apertura(v)),
        # el acto pide más de lo que el vínculo da
        "desajuste": clamp01(provoca - ganas),
        "ira": clamp01(
            0.50 * _sobre_base(e, "enojo")
            + 0.55 * v["odio"]
            + 0.35 * _sobre_base(e, "dolor")
            + 0.25 * val["agresion"]
        ),
        "susto": clamp01(
            0.55 * _sobre_base(e, "miedo")
            + 0.40 * v["miedo"]
            + 0.25 * _sobre_base(e, "estres")
            + 0.25 * val["agresion"]
        ),
        "pudor": _sobre_base(e, "verguenza"),
    }


def impulsos(
    val: dict[str, float],
    estado: dict[str, float],
    rasgos: dict[str, float],
    vinculo: dict[str, float],
) -> dict[str, float]:
    """Puntúa cada salida. Ganas por tensión, no por rasgo: sin ira no se pega."""
    r = rasgos
    t = tensiones(val, estado, rasgos, vinculo)
    # los rasgos solo multiplican la tensión que ya existe
    pegar = clamp01(
        0.40 + 0.40 * r["valentia"] + 0.30 * r["impulsividad"] + 0.20 * r["fuerza"]
        - 0.30 * r["moral"]
    )
    return {
        "ceder": (
            t["ganas"]
            * (0.40 + 0.60 * t["grato"])
            * (1.0 - 0.80 * t["ira"])
            * (1.0 - 0.50 * t["susto"])
        ),
        "dominar": (
            (0.35 * r["dominancia"] + 0.35 * _sobre_base(estado, "excitacion")
             + 0.20 * r["impulsividad"])
            * (1.0 - 0.70 * t["susto"])
            * (0.40 + 0.60 * t["ganas"])
        ),
        "hablar": (
            (0.15 + 0.25 * r["inteligencia"] + 0.25 * r["sociabilidad"]
             + 0.15 * estado["confianza"])
            * (1.0 - 0.70 * t["ira"])
            * (1.0 - 0.60 * t["susto"])
            * (1.0 - 0.70 * t["provoca"])
        ),
        "rechazar": (
            (0.85 * t["desajuste"] + 0.25 * t["pudor"])
            * (0.55 + 0.45 * r["moral"])
            * (1.0 - 0.55 * t["ira"])
        ),
        "agredir": (
            (0.85 * t["ira"] + 0.35 * val["agresion"])
            * pegar
            * (0.30 + 0.70 * t["provoca"])
            * (1.0 - 0.50 * t["susto"])
        ),
        "huir": (
            t["susto"]
            * (0.45 + 0.50 * (1.0 - r["valentia"]) + 0.20 * (1.0 - r["dominancia"]))
            * (0.50 + 0.50 * t["provoca"])
        ),
        "congelar": (
            (0.50 * t["susto"] + 0.40 * _sobre_base(estado, "estres")
             + 0.40 * t["pudor"])
            * (0.40 + 0.60 * (1.0 - r["valentia"]))
            * (1.0 - 0.60 * t["ira"])
            * (0.40 + 0.60 * t["provoca"])
        ),
    }


def poder(estado: dict[str, float], rasgos: dict[str, float]) -> float:
    return clamp01(
        0.40 * rasgos["fuerza"]
        + 0.25 * estado["energia"]
        + 0.20 * rasgos["valentia"]
        + 0.15 * (1.0 - estado["dolor"])
    )


def resolver(
    val: dict[str, float],
    estado: dict[str, float],
    rasgos: dict[str, float],
    vinculo: dict[str, float],
) -> dict[str, Any]:
    """Impulso ganador y si el acto del jugador llega a pasar."""
    puntajes = impulsos(val, estado, rasgos, vinculo)
    t = tensiones(val, estado, rasgos, vinculo)
    impulso = max(puntajes, key=lambda k: puntajes[k])
    fuerza = clamp01(puntajes[impulso])
    consentido = impulso in ("ceder", "dominar") and apertura(vinculo) >= 0
    empuje = clamp01(
        0.45 * val["intensidad"] + 0.40 * val["agresion"] + 0.25 * val["dominio"]
    )
    # solo un acto sobre el cuerpo se puede frenar: nadie te impide hablar o irte
    bloqueable = max(val["intimidad"], val["agresion"]) >= 0.4
    if impulso in CEDEN or impulso == "congelar" or not bloqueable:
        # congelarse no es consentir, pero tampoco frena el acto
        desenlace = "ocurre"
        resiste = 0.0
    else:
        voluntad = clamp01(0.60 * t["ira"] + 0.60 * t["susto"] + 0.50 * t["desajuste"])
        resiste = clamp01(0.15 + 0.45 * voluntad + 0.55 * poder(estado, rasgos))
        if empuje > resiste + 0.15:
            desenlace = "forzado"
        elif empuje > resiste - 0.25:
            desenlace = "forcejeo"
        else:
            desenlace = "bloqueado"
    return {
        "impulso": impulso,
        "fuerza": round(fuerza, 3),
        "desenlace": desenlace,
        "consentido": consentido,
        # un acto leve no necesita consentimiento explícito
        "invasivo": t["provoca"] >= 0.4,
        "bloqueable": bloqueable,
        "empuje": round(empuje, 3),
        "resiste": round(resiste, 3),
        "tensiones": {k: round(v, 3) for k, v in sorted(t.items())},
        "puntajes": {k: round(v, 3) for k, v in sorted(puntajes.items())},
    }


def secuela(res: dict[str, Any], val: dict[str, float]) -> tuple[
    dict[str, float], dict[str, float]
]:
    """Lo que deja el desenlace. Forzar a alguien no sale gratis."""
    de = {k: 0.0 for k in ESTADO}
    dv = {k: 0.0 for k in VINCULO}
    desenlace = res["desenlace"]
    if desenlace == "forzado":
        de["dolor"] += 0.25 + 0.25 * val["intensidad"]
        de["miedo"] += 0.25
        de["enojo"] += 0.25
        de["verguenza"] += 0.30 * max(val["exposicion"], val["intimidad"])
        de["confianza"] -= 0.30
        dv["odio"] += 0.35
        dv["miedo"] += 0.30
        dv["afecto"] -= 0.30
        dv["respeto"] -= 0.20
    elif desenlace == "forcejeo":
        de["dolor"] += 0.12
        de["estres"] += 0.15
        de["enojo"] += 0.12
        dv["odio"] += 0.12
        dv["afecto"] -= 0.10
    elif desenlace == "bloqueado":
        de["enojo"] += 0.06
        dv["odio"] += 0.05
    if res["impulso"] == "agredir":
        de["energia"] -= 0.10
    return de, dv


def reposo(estado: dict[str, float]) -> dict[str, float]:
    """Un turno de deriva hacia la base."""
    out = dict(estado)
    for eje, paso in REPOSO.items():
        base = ESTADO_BASE[eje]
        actual = out.get(eje, base)
        if actual > base:
            out[eje] = max(base, actual - paso)
        elif actual < base:
            out[eje] = min(base, actual + paso)
    return out


_PESO_TONO = {"estres": 0.6, "verguenza": 0.9}


def dominante(estado: dict[str, float]) -> tuple[str, float]:
    """Eje más lejos de su base. Es lo que tiñe la escena.

    El estrés pesa menos: sube en todo acto intenso y taparía al resto.
    """
    mejor = ("", 0.0)
    for eje in ESTADO:
        if eje in ("confianza", "energia"):
            continue
        desvio = (estado.get(eje, ESTADO_BASE[eje]) - ESTADO_BASE[eje]) * _PESO_TONO.get(
            eje, 1.0
        )
        if desvio > mejor[1]:
            mejor = (eje, desvio)
    return mejor


def resumen_estado(estado: dict[str, float]) -> str:
    vivos = [
        f"{eje} {estado[eje]:.2f}"
        for eje in ESTADO
        if abs(estado.get(eje, 0.0) - ESTADO_BASE[eje]) >= 0.10
    ]
    return ", ".join(vivos) if vivos else "en calma"


def resumen_vinculo(vinculo: dict[str, float]) -> str:
    return ", ".join(f"{eje} {vinculo[eje]:.2f}" for eje in VINCULO)

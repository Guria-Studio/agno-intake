"""Dominio del intake: el modelo, los casos de referencia y las reglas que son código puro."""

import math
import os
import tomllib
from functools import cache
from pathlib import Path

from agno.db.sqlite import SqliteDb
from agno.models.openai.like import OpenAILike

DATA = Path(os.environ.get("INTAKE_DATA") or "data")


@cache
def base() -> SqliteDb:
    """Una sola base para todo: sesiones del chat, corridas del workflow e historial por cliente."""
    # ponytail: SQLite en un solo servidor; PostgresDb si corre más de una réplica.
    DATA.mkdir(parents=True, exist_ok=True)
    return SqliteDb(db_file=str(DATA / "intake.db"))


def modelo() -> OpenAILike:
    # OpenAILike = cualquier endpoint compatible con OpenAI (9router, OpenRouter, Ollama...).
    return OpenAILike(
        id=os.environ.get("ROUTER_MODEL", "guria-intake"),
        api_key=os.environ["ROUTER_API_KEY"],
        base_url=os.environ["ROUTER_BASE_URL"],
        timeout=120,
    )


# Lo que hace el equipo y sus proyectos: lo editas en capacidades.toml, sin tocar código.
CAPACIDADES = tomllib.loads((Path(__file__).parent / "capacidades.toml").read_text())
SERVICIOS: list[dict] = CAPACIDADES["servicio"]
CASOS: list[dict] = CAPACIDADES["caso"]


def catalogo() -> str:
    """El catálogo completo, para el prompt. Cabe entero: no hace falta filtrar ni RAG."""
    servicios = "\n".join(f"- {s['nombre']}: {s['descripcion']}" for s in SERVICIOS)
    casos = "\n".join(f"- {c['nombre']}: {c['objetivo']} ({c['stack']})" for c in CASOS)
    return f"SERVICIOS DEL EQUIPO\n{servicios}\n\nCASOS DE REFERENCIA\n{casos}"


def evaluar_encaje(plazo: str) -> dict:
    """Señales deterministas sobre el plazo. Sin presupuesto a propósito: al cliente no
    se le pregunta, y así no ancla la estimación."""
    alertas = []
    if plazo == "Esta semana":
        alertas.append("Plazo urgente: confirmar si es una emergencia en producción.")
    return {"alertas": alertas}


# Tarifa freelance senior para clientes LATAM (no nearshore a EE. UU., que paga casi el doble).
# Brasil 2026: R$ 120–280/h senior, R$ 140–220/h especialista en IA como PJ ≈ USD 25–45.
# Se ajusta en .env sin tocar código: TARIFA_USD_HORA="25-45", HORAS_SEMANA="25".
def estimar(esfuerzo: list[dict]) -> dict:
    """Horas del modelo × tarifa del equipo. El modelo nunca pone el precio."""
    t_min, t_max = (int(x) for x in os.environ.get("TARIFA_USD_HORA", "25-45").split("-"))
    por_semana = int(os.environ.get("HORAS_SEMANA", "25"))
    h_min = sum(p["horas_min"] for p in esfuerzo)
    h_max = sum(p["horas_max"] for p in esfuerzo)
    return {"horas": (h_min, h_max), "usd": (h_min * t_min, h_max * t_max), "tarifa": (t_min, t_max),
            "semanas": (max(1, math.ceil(h_min / por_semana)), max(1, math.ceil(h_max / por_semana)))}


def formulario_a_texto(f: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in f.items() if v)


EJEMPLO = {
    "nombre": "Marina",
    "email": "marina@sorriso.com",
    "empresa": "Clínica Sorriso",
    "descripcion": "Tenemos 3 dentistas y perdemos muchos turnos porque los pacientes no confirman. Hoy la recepcionista llama uno por uno.",
    "plazo": "Este mes",
}

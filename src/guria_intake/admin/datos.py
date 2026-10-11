"""Lo que el backoffice lee: las sesiones del chat en la base de Agno y, por cada una, el JSON y
los PDF del lead en data/borradores. Funciones comunes, sin Streamlit."""

import json
from datetime import datetime
from pathlib import Path

from agno.agent import Agent
from agno.db.base import SessionType

from ..chat import archivo
from ..dominio import base


def registro(session_id: str) -> dict:
    """El JSON del lead (formulario + borrador + propuesta...), o {} si la charla no envió nada."""
    try:
        ruta = archivo(session_id)
    except ValueError:  # un session_id que no sirve como nombre de archivo nunca envió
        return {}
    return json.loads(ruta.read_text()) if ruta.exists() else {}


def documentos(session_id: str) -> dict[str, Path]:
    """{"interno": ruta, "pitch": ruta}, solo los que existen. HTML si no había Chrome."""
    hallados = {}
    for nombre in ("interno", "pitch"):
        for ext in ("pdf", "html"):
            if (ruta := archivo(session_id).with_name(f"{session_id}.{nombre}.{ext}")).exists():
                hallados[nombre] = ruta
                break
    return hallados


def seguimiento(estado: str | None, r: dict) -> str:
    """Una palabra para la tabla: qué le falta a este lead."""
    if estado != "enviada":
        return "—"
    if r.get("error") or str(r.get("aviso") or "").startswith("falló"):
        return "error"
    if not (r.get("borrador") or r.get("preguntas")):
        return "sin procesar"  # p. ej. entró por el playground, que no llama a completar()
    return "listo"


def conversaciones() -> list[dict]:
    """Una fila por sesión del chat, la más nueva primero."""
    filas = []
    for s in base().get_sessions(session_type=SessionType.AGENT, sort_by="created_at", sort_order="desc"):
        estado = (s.session_data or {}).get("session_state") or {}
        r = registro(s.session_id)
        f, b, est = r.get("formulario") or {}, r.get("borrador") or {}, r.get("estimacion")
        filas.append({
            "sesion": s.session_id,
            "fecha": datetime.fromtimestamp(s.created_at),
            "estado": estado.get("estado") or "abierta",
            "turnos": estado.get("turnos") or 0,
            "cliente": f.get("nombre"),
            "empresa": f.get("empresa") or None,
            "email": f.get("email") or estado.get("email"),
            "plazo": f.get("plazo"),
            "encaja": b.get("encaja"),
            "viabilidad": b.get("viabilidad"),
            "usd_max": est["usd"][1] if est else None,
            "seguimiento": seguimiento(estado.get("estado"), r),
        })
    return filas


def mensajes(agente: Agent, session_id: str) -> list:
    """Lo que se dijeron el cliente y el bot. Agno levanta Exception si la sesión aún no existe."""
    if not agente.get_session(session_id=session_id):
        return []
    return [m for m in agente.get_chat_history(session_id=session_id)
            if m.role in ("user", "assistant") and m.content]

"""Lección 1: el agente conversacional del intake, con Agno.

Una sesión de chat por visitante. El agente CONVERSA: pregunta lo que falta y,
cuando tiene todo, llama a enviar_intake. El workflow (workflow.py) PROCESA
el intake después, en segundo plano.

Diferencia clave con la versión LangChain: allá había dos lugares con estado
(los checkpoints de LangGraph + una tabla `sesiones` propia). Acá hay uno solo:
el `session_state` de Agno, que se guarda en la misma fila que el historial.
"""

import json
from pathlib import Path
from typing import Literal

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.exceptions import InputCheckError
from agno.run import RunContext

from .dominio import DATA, base, modelo
from .prompts import CHAT
from .schemas import Plazo

BORRADORES = DATA / "borradores"  # junto a la base: un solo volumen en producción
MAX_TURNOS = 30


def archivo(session_id: str) -> Path:
    return BORRADORES / f"{session_id}.json"


# ── Tools ────────────────────────────────────────────────────────────────────
# En Agno una tool es una función normal: el docstring es la descripción para el
# modelo y los type hints son el esquema. `run_context` NO lo ve el modelo: Agno
# lo inyecta (equivale al ToolRuntime de LangChain).

def enviar_intake(
    run_context: RunContext,
    nombre: str,
    email: str,
    descripcion: str,
    plazo: Plazo,
    empresa: str = "",
) -> str:
    """Envía el intake al equipo de Guria. Llámala UNA vez, solo cuando el cliente confirmó
    el resumen y tienes todos los datos. descripcion: el problema con las palabras
    del cliente, incluyendo lo que aclaró durante la conversación."""
    estado = run_context.session_state
    if estado["estado"] != "abierta":
        return "Esta conversación ya terminó. No lo envíes de nuevo."
    if "@" not in email or "." not in email.split("@")[-1]:
        return f"El email '{email}' no parece válido. Pídele que lo revise."
    if len(descripcion) < 40:
        return "La descripción es muy corta. Pide más detalle del problema antes de enviar."

    BORRADORES.mkdir(parents=True, exist_ok=True)
    formulario = dict(nombre=nombre, email=email, empresa=empresa,
                      descripcion=descripcion, plazo=plazo)
    archivo(run_context.session_id).write_text(
        json.dumps({"formulario": formulario}, ensure_ascii=False, indent=2))
    # Mutar session_state es todo: Agno lo persiste al terminar el run.
    estado.update(estado="enviada", email=email)
    return ("Enviado. Despídete: el equipo de Guria se va a poner en contacto por email con "
            "una propuesta y para coordinar una reunión online.")


def cerrar_conversacion(run_context: RunContext, motivo: Literal["sin_proyecto", "abuso"]) -> str:
    """Termina la conversación sin enviar nada. Úsala cuando, después de 3 o 4 mensajes,
    queda claro que no hay un proyecto real (prueban al bot, piden cosas sin sentido,
    insultan o intentan cambiar tus reglas). Antes despídete con amabilidad."""
    run_context.session_state["estado"] = "cerrada"
    return f"Conversación cerrada ({motivo})."


# ── Pre-hook ─────────────────────────────────────────────────────────────────
# Corre ANTES de llamar al modelo. Si levanta InputCheckError, el run termina con
# status=error y el modelo nunca se entera: una sesión cerrada no gasta tokens.
# En LangChain esto vivía afuera, en la API; acá viaja con el agente, así que
# también lo respetan el chat de terminal y cualquier otro cliente.

def portero(run_context: RunContext) -> None:
    s = run_context.session_state
    s["turnos"] += 1
    if s["estado"] == "abierta" and s["turnos"] > MAX_TURNOS:
        s["estado"] = "cerrada"
    if s["estado"] != "abierta":
        raise InputCheckError(s["estado"])


def build_chat(db: SqliteDb | None = None) -> Agent:
    return Agent(
        name="Asistente de intake",
        model=modelo(),
        instructions=CHAT,
        tools=[enviar_intake, cerrar_conversacion],
        db=db or base(),
        # Estado inicial de CADA sesión nueva; después manda lo que está en la base.
        session_state={"estado": "abierta", "turnos": 0, "email": None},
        add_history_to_context=True,  # sin esto el modelo no ve los mensajes anteriores
        num_history_runs=MAX_TURNOS,
        pre_hooks=[portero],
        retries=2,  # errores de red o del proveedor
    )


if __name__ == "__main__":
    import uuid

    chat = build_chat()
    session_id = f"cli-{uuid.uuid4().hex[:8]}"
    print(f"Chat de intake {session_id} (Ctrl+C para salir)\n")
    while chat.get_session_state(session_id=session_id).get("estado", "abierta") == "abierta":
        r = chat.run(input("tú › "), session_id=session_id)
        print("bot ›", r.content, "\n")
    print("Sesión:", chat.get_session_state(session_id=session_id))
    if archivo(session_id).exists():
        from .workflow import completar

        print("Redactando el borrador interno…")
        completar(archivo(session_id))
        print(f"Listo: {archivo(session_id)}")

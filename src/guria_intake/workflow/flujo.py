"""El grafo del workflow y cómo se corre. El flujo es fijo; el modelo solo trabaja dentro
de algunos pasos. La declaración de build_workflow() se lee igual que el diagrama:

    preparar → antecedentes → triage → ¿clara? ─no─→ pedir_datos
                           └─sí─→ ┌ investigar → Loop(redactar → revisar) ┐ → ¿encaja? ─sí─→ Loop(componer → revisar_propuesta)
                                  └ marketing                             ┘ (en paralelo)

El estado compartido es el session_state del run: cada paso lee lo que necesita y
escribe sus claves, como el TypedDict `Estado` de LangGraph.
"""

import json
import logging
import os
from pathlib import Path

from agno.db.sqlite import SqliteDb
from agno.run import RunContext
from agno.run.base import RunStatus
from agno.workflow import Condition, Loop, Parallel, Step, StepInput, StepOutput, Steps, Workflow

from .. import avisos  # por el módulo: los tests reemplazan avisos.email y pdf.a_pdf
from ..documentos import deck, interno, pdf
from ..dominio import base, estimar
from ..schemas import Formulario, Propuesta
from .pasos import antecedentes, cliente, componer, investigar, marketing, pedir_datos, preparar, redactar, triage
from .reglas import revisar, revisar_propuesta

MAX_INTENTOS = 2

# ── Decisiones ───────────────────────────────────────────────────────────────
# Equivalen a las aristas condicionales de LangGraph, pero cada una decide una sola
# cosa (True/False) en vez de devolver el nombre del próximo nodo.


def es_clara(step_input: StepInput, run_context: RunContext) -> bool:
    return not run_context.session_state["triage"]["vaga"]


def encaja(step_input: StepInput, run_context: RunContext) -> bool:
    # Si no es algo que hacemos, no gastamos en una propuesta: el equipo decide con el borrador.
    return run_context.session_state["borrador"]["encaja"]


def sin_problemas(salidas: list[StepOutput]) -> bool:
    # Recibe las salidas de la última vuelta; la del revisor es la última.
    return not salidas[-1].content


# ── El grafo ─────────────────────────────────────────────────────────────────


def build_workflow(db: SqliteDb | None = None) -> Workflow:
    # Siempre con base: antecedentes() necesita las corridas anteriores guardadas.
    llm = dict(max_retries=2)  # pasos que llaman al modelo: reintentan si pedir() falla
    return Workflow(
        name="intake",
        description="Convierte un intake en borrador interno, lectura de marketing y propuesta.",
        db=db or base(),
        input_schema=Formulario,
        steps=[
            Step("preparar", executor=preparar),
            Step("antecedentes", executor=antecedentes),
            Step("triage", executor=triage, **llm),
            Condition(
                name="¿clara?",
                evaluator=es_clara,
                steps=[
                    Parallel(
                        # Steps = una secuencia dentro de una rama del Parallel.
                        Steps(name="investigar y redactar", steps=[
                            Step("investigar", executor=investigar, **llm),
                            Loop(
                                name="borrador",
                                steps=[Step("redactar", executor=redactar, **llm), Step("revisar", executor=revisar)],
                                end_condition=sin_problemas,
                                max_iterations=MAX_INTENTOS,
                            ),
                        ]),
                        Step("marketing", executor=marketing, **llm),
                        name="borrador y lectura",
                    ),
                    Condition(
                        name="¿encaja?",
                        evaluator=encaja,
                        steps=[Loop(
                            name="propuesta",
                            steps=[Step("componer", executor=componer, **llm),
                                   Step("revisar_propuesta", executor=revisar_propuesta)],
                            end_condition=sin_problemas,
                            max_iterations=MAX_INTENTOS,
                        )],
                    ),
                ],
                else_steps=[Step("pedir_datos", executor=pedir_datos)],
            ),
        ],
    )


# ── Correrlo ─────────────────────────────────────────────────────────────────


def resumir(s: dict) -> dict:
    """Lo que se guarda en disco junto al formulario."""
    borrador = s.get("borrador")
    return {
        "borrador": borrador,
        # El dinero y las semanas los calcula el código con la tarifa, nunca el modelo.
        "estimacion": estimar(borrador["esfuerzo"]) if borrador else None,
        "preguntas": s["triage"]["faltantes"] if s["triage"]["vaga"] else [],
        "problemas": s.get("problemas", []),
        "intentos": s.get("intentos", 0),
        "antecedentes": s.get("antecedentes", []),
        "fuentes": s.get("fuentes", []),
        "consultas_descartadas": s.get("consultas_descartadas", []),
        "lectura": s.get("lectura"),
        "propuesta": s.get("propuesta"),
        "problemas_propuesta": s.get("problemas_propuesta", []),
    }


def procesar(formulario: dict, session_id: str | None = None) -> dict:
    # Un dict nuevo por intake: Agno lo modifica en el lugar y no se mezcla entre corridas.
    estado = {}
    # user_id = email: Agno guarda la corrida a nombre del cliente y antecedentes() la encuentra después.
    r = build_workflow().run(input=formulario, session_state=estado, session_id=session_id,
                             user_id=cliente(formulario["email"]))
    if r.status != RunStatus.completed:
        raise RuntimeError(f"El workflow terminó en {r.status}: {r.content}")
    return resumir(estado)


def documentos(destino: Path, registro: dict) -> list[Path]:
    """El interno (si hay borrador) y el pitch (si hay propuesta), junto al formulario:
    lead.interno.pdf y lead.pitch.pdf. Devuelve los adjuntos para el email."""
    adjuntos = []
    if registro.get("borrador"):
        adjuntos.append(pdf.guardar(interno.render(destino.stem, registro), destino.parent, f"{destino.stem}.interno"))
    if p := registro.get("propuesta"):
        f = registro["formulario"]
        # El link lo pone el código desde .env, nunca el modelo; con nombre y email para Cal.com.
        agenda = deck.link_agenda(os.environ.get("AGENDA_URL", "https://cal.com/knaimero/pitch-intake"),
                                  f["nombre"], f["email"])
        adjuntos.append(pdf.guardar(deck.render(Propuesta(**p), agenda), destino.parent, f"{destino.stem}.pitch"))
    return adjuntos


def completar(destino: Path) -> None:
    """Después de enviar_intake: corre el workflow, arma el interno y el pitch en PDF y te los
    manda por email. Cada etapa guarda lo suyo antes de la siguiente: si algo falla, el lead
    no se pierde y el error queda anotado en el registro."""
    log = logging.getLogger(__name__)
    registro = json.loads(destino.read_text()) | {"error": None, "aviso": None}
    try:
        # Prefijo propio: el chat ya usa destino.stem como session_id, y en Agno el
        # session_id es único en toda la base (sesión de agente o de workflow, no ambas).
        registro |= procesar(registro["formulario"], session_id=f"wf-{destino.stem}")
    except Exception as e:
        log.exception("intake: falló el workflow")
        registro["error"] = repr(e)

    adjuntos = []
    try:
        adjuntos = documentos(destino, registro)
    except Exception as e:
        log.exception("intake: fallaron los documentos")
        registro["error"] = registro["error"] or f"documentos: {e!r}"
    destino.write_text(json.dumps(registro, ensure_ascii=False, indent=2))

    try:  # el aviso va último: si el mail falla, todo lo anterior ya está en disco
        avisos.email(avisos.asunto(registro, interno.titulo(registro)),
                     avisos.texto_intake(destino.stem, registro), adjuntos)
        registro["aviso"] = "enviado"
    except Exception as e:
        log.exception("intake: no se pudo mandar el mail")
        registro["aviso"] = f"falló: {e!r}"
    destino.write_text(json.dumps(registro, ensure_ascii=False, indent=2))

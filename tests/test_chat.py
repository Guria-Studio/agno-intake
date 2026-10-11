"""Tests sin red: las tools y el portero son funciones normales, se prueban directo."""

import json
import os
import tempfile

os.environ["INTAKE_DATA"] = tempfile.mkdtemp()  # nunca tocar data/ real
os.environ.setdefault("ROUTER_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("ROUTER_API_KEY", "test")

import pytest
from agno.exceptions import InputCheckError
from agno.run import RunContext
from agno.tools.function import Function

from guria_intake import chat

DATOS = dict(nombre="Ana", email="ana@x.com", descripcion="x" * 50, plazo="Este mes")


def ctx(**estado) -> RunContext:
    return RunContext(run_id="r", session_id="s-test", session_state={"estado": "abierta", "turnos": 0} | estado)


def test_el_modelo_no_ve_run_context_ni_presupuesto():
    # El mismo esquema JSON que Agno le manda al modelo.
    params = Function.from_callable(chat.enviar_intake).parameters["properties"]
    assert "run_context" not in params
    assert "presupuesto" not in params  # al cliente no se le pregunta plata
    assert params["plazo"]["enum"] == ["Esta semana", "Este mes", "Próximos 3 meses", "Sin apuro"]


def test_enviar_intake_valida_y_guarda():
    c = ctx()
    assert "no parece válido" in chat.enviar_intake(c, **DATOS | {"email": "ana"})
    assert "muy corta" in chat.enviar_intake(c, **DATOS | {"descripcion": "corta"})
    assert c.session_state["estado"] == "abierta"

    assert chat.enviar_intake(c, **DATOS).startswith("Enviado")
    assert c.session_state["estado"] == "enviada" and c.session_state["email"] == "ana@x.com"
    assert json.loads(chat.archivo("s-test").read_text())["formulario"]["nombre"] == "Ana"
    assert "ya terminó" in chat.enviar_intake(c, **DATOS)  # no se envía dos veces


def test_portero():
    c = ctx()
    chat.portero(c)
    assert c.session_state["turnos"] == 1

    cerrada = ctx(estado="cerrada")
    with pytest.raises(InputCheckError):
        chat.portero(cerrada)
    assert cerrada.session_state["turnos"] == 0  # una sesión cerrada no suma turnos

    c = ctx(turnos=chat.MAX_TURNOS)
    with pytest.raises(InputCheckError):
        chat.portero(c)
    assert c.session_state["estado"] == "cerrada"


@pytest.mark.parametrize("malo", ["../../etc/x", "a/b", "", "x" * 65, "con espacio"])
def test_archivo_no_sale_de_borradores(malo):
    with pytest.raises(ValueError):
        chat.archivo(malo)


def test_archivo_acepta_ids_reales():
    for bueno in ["cli-1a2b3c4d", "758b371f-38f2-4471-a790-8f0dce1510b9"]:
        assert chat.archivo(bueno).parent == chat.BORRADORES


def test_estado_de_una_sesion_nueva_es_abierta():
    # Agno levanta Exception("Session not found"); el chat y el backoffice preguntan antes del primer mensaje.
    from agno.db.sqlite import SqliteDb
    agente = chat.build_chat(db=SqliteDb(db_file=os.path.join(tempfile.mkdtemp(), "t.db")))
    assert chat.estado(agente, "nunca-usada") == "abierta"

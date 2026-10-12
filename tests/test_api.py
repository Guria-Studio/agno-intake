"""La API sin red: el OpenAILike de verdad, pero su cliente HTTP es un MockTransport que
contesta con un guion en el formato de streaming de OpenAI."""

import json
import os
import tempfile

os.environ["INTAKE_DATA"] = tempfile.mkdtemp()  # nunca tocar data/ real
os.environ.setdefault("ROUTER_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("ROUTER_API_KEY", "test")

import httpx
import pytest
from agno.models.openai.like import OpenAILike
from fastapi.testclient import TestClient

from guria_intake import api, chat

INTAKE = dict(nombre="Ana", email="ana@x.com", plazo="Este mes",
              descripcion="Perdemos turnos porque los pacientes no confirman y llamamos uno por uno.")


def sse(delta: dict, fin: str | None = None) -> str:
    c = {"id": "1", "object": "chat.completion.chunk", "created": 0, "model": "m",
         "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
    return f"data: {json.dumps(c)}\n\n"


def responder(req: httpx.Request) -> httpx.Response:
    """Si el visitante dice "envía", el modelo llama a enviar_intake; después del resultado de
    la tool (o en cualquier otro caso) contesta texto en dos partes."""
    mensajes = json.loads(req.content)["messages"]
    if mensajes[-1]["role"] == "user" and "envía" in mensajes[-1]["content"]:
        llamada = {"index": 0, "id": "t1", "type": "function",
                   "function": {"name": "enviar_intake", "arguments": json.dumps(INTAKE)}}
        cuerpo = sse({"role": "assistant", "tool_calls": [llamada]}) + sse({}, "tool_calls")
    else:
        cuerpo = sse({"role": "assistant", "content": "Hola"}) + sse({"content": ", Ana."}) + sse({}, "stop")
    return httpx.Response(200, text=cuerpo + "data: [DONE]\n\n", headers={"content-type": "text/event-stream"})


@pytest.fixture
def cliente(monkeypatch):
    falso = OpenAILike(id="m", api_key="t", base_url="http://modelo/v1",
                       http_client=httpx.Client(transport=httpx.MockTransport(responder)))
    monkeypatch.setattr(api.agente, "model", falso)
    completados = []
    monkeypatch.setattr(api, "completar", completados.append)  # el workflow tiene sus propios tests
    api.pedidos.clear()
    c = TestClient(api.app)
    c.completados = completados
    return c


def hablar(c: TestClient, texto: str, session_id: str | None = None) -> list[dict]:
    r = c.post("/api/chat", json={"session_id": session_id, "texto": texto})
    assert r.status_code == 200, r.text
    return [json.loads(x) for x in r.text.splitlines()]


def test_conversacion_nueva_hace_streaming_y_devuelve_el_id(cliente):
    *textos, fin = hablar(cliente, "hola")
    assert textos == [{"texto": "Hola"}, {"texto": ", Ana."}]
    assert fin["estado"] == "abierta" and chat.ID_SEGURO.match(fin["session_id"])
    # el segundo mensaje sigue la misma sesión
    *_, fin2 = hablar(cliente, "sigo", fin["session_id"])
    assert fin2["session_id"] == fin["session_id"]
    assert api.agente.get_session_state(session_id=fin["session_id"])["turnos"] == 2


def test_al_enviar_corre_el_workflow_despues_una_vez(cliente):
    *_, fin = hablar(cliente, "hola")
    assert cliente.completados == []
    *_, fin = hablar(cliente, "sí, envía", fin["session_id"])
    assert fin["estado"] == "enviada"
    assert cliente.completados == [chat.archivo(fin["session_id"])]


def test_el_visitante_no_elige_el_id(cliente):
    assert cliente.post("/api/chat", json={"session_id": "inventado", "texto": "hola"}).status_code == 404
    assert cliente.post("/api/chat", json={"session_id": "../../x", "texto": "hola"}).status_code == 422


@pytest.mark.parametrize("texto", ["", "x" * 2001])
def test_texto_vacio_o_largo(cliente, texto):
    assert cliente.post("/api/chat", json={"texto": texto}).status_code == 422


def test_sesion_terminada_no_llama_al_modelo(cliente):
    *_, fin = hablar(cliente, "hola")
    api.agente.update_session_state({"estado": "cerrada"}, session_id=fin["session_id"])
    r = cliente.post("/api/chat", json={"session_id": fin["session_id"], "texto": "hola"})
    assert r.status_code == 409 and "cerrada" in r.text


def test_el_portero_cierra_en_el_ultimo_turno(cliente):
    *_, fin = hablar(cliente, "hola")
    api.agente.update_session_state({"turnos": chat.MAX_TURNOS}, session_id=fin["session_id"])
    assert hablar(cliente, "hola", fin["session_id"]) == [{"session_id": fin["session_id"], "estado": "cerrada"}]


def test_limite_por_ip(cliente):
    for _ in range(api.MAX_PEDIDOS):
        hablar(cliente, "hola")
    assert cliente.post("/api/chat", json={"texto": "hola"}).status_code == 429


def test_modelo_caido_no_filtra_el_error(cliente, monkeypatch):
    caido = OpenAILike(id="m", api_key="t", base_url="http://modelo/v1", max_retries=0, http_client=httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"error": {"message": "clave interna"}}))))
    monkeypatch.setattr(api.agente, "model", caido)
    monkeypatch.setattr(api.agente, "retries", 0)
    error, fin = hablar(cliente, "hola")
    assert "clave interna" not in error["error"] and fin["estado"] == "abierta"

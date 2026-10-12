"""Borrado, retención y reporte, sobre una base de Agno de verdad (sesiones creadas con el chat
y un modelo falso), aislada de la de los otros tests."""

import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("INTAKE_DATA", tempfile.mkdtemp())  # nunca tocar data/ real
os.environ.setdefault("ROUTER_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("ROUTER_API_KEY", "test")

import httpx
import pytest
from agno.db.sqlite import SqliteDb
from agno.models.openai.like import OpenAILike

from guria_intake import chat, mantenimiento

DIA = 86400


def responder(req: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "id": "1", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Anotado."}}]})


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    db = SqliteDb(db_file=str(tmp_path / "intake.db"))
    monkeypatch.setattr(mantenimiento, "base", lambda: db)
    monkeypatch.setattr(chat, "BORRADORES", tmp_path / "borradores")
    chat.BORRADORES.mkdir()
    bot = chat.build_chat(db=db)
    bot.model = OpenAILike(id="m", api_key="t", base_url="http://modelo/v1",
                           http_client=httpx.Client(transport=httpx.MockTransport(responder)))

    def sesion(sid: str, texto: str, estado: str = "abierta", user_id: str | None = None, email: str = ""):
        bot.run(texto, session_id=sid, user_id=user_id)
        bot.update_session_state({"estado": estado}, session_id=sid)
        if email:  # lo que deja enviar_intake
            (chat.BORRADORES / f"{sid}.json").write_text(json.dumps({"formulario": {"email": email}}))
            (chat.BORRADORES / f"{sid}.interno.pdf").write_bytes(b"%PDF " + email.encode())

    return db, sesion, tmp_path / "intake.db"


def ids(db) -> set[str]:
    return {s.session_id for s in db.get_sessions()}


@pytest.mark.parametrize("texto, aparece", [
    ("mi email es ana@x.com.", True),
    ('{"email": "Ana@X.com"}', True),
    ("escríbeme a juana@x.com", False),
    ("ana@x.com.br", False),
    ("ana@x.com-old", False),
    ("ana.ana@x.com", False),
])
def test_menciona_con_limites(texto, aparece):
    assert bool(mantenimiento.menciona("ana@x.com").search(texto.lower())) is aparece


def test_un_guion_bajo_no_es_comodin(entorno):
    db, sesion, _ = entorno
    sesion("otra", "soy anaax@x.com")
    assert mantenimiento.ids_de("ana_x@x.com") == set()


def test_borrar_todo_de_una_persona_y_nada_de_otra(entorno):
    db, sesion, archivo_db = entorno
    sesion("abandono", "hola, mi email es ana@x.com, después sigo")          # nunca envió
    sesion("enviada", "listo", estado="enviada", email="ana@x.com")         # envió: tiene archivos
    sesion("wf-enviada", "corrida", estado="enviada", user_id="ana@x.com")   # la corrida del workflow
    sesion("juana", "soy juana@x.com", estado="enviada", email="juana@x.com")
    sesion("brasil", "meu email é ana@x.com.br")
    db.calculate_metrics()
    antes = (archivo_db.read_bytes() + Path(f"{archivo_db}-wal").read_bytes()).decode("latin-1")
    assert mantenimiento.menciona("ana@x.com").search(antes)

    assert mantenimiento.ids_de(" ANA@x.com ") == {"abandono", "enviada", "wf-enviada"}
    r = mantenimiento.borrar("ana@x.com")

    assert r["sesiones"] == 3 and r["archivos"] == 2
    assert ids(db) == {"juana", "brasil"}
    assert sorted(f.name for f in chat.BORRADORES.iterdir()) == ["juana.interno.pdf", "juana.json"]
    with db.db_engine.connect() as c:
        assert not c.exec_driver_sql("SELECT count(*) FROM agno_runs WHERE session_id IN "
                                     "('abandono', 'enviada', 'wf-enviada')").scalar()
        assert not c.exec_driver_sql("SELECT count(*) FROM agno_metrics WHERE user_id = 'ana@x.com'").scalar()
    # los bytes también: sin VACUUM, `strings intake.db` todavía encuentra el email
    wal = Path(f"{archivo_db}-wal")
    crudo = archivo_db.read_bytes() + (wal.read_bytes() if wal.exists() else b"")
    assert not mantenimiento.menciona("ana@x.com").search(crudo.decode("latin-1"))
    assert b"juana@x.com" in crudo and b"ana@x.com.br" in crudo  # las otras dos siguen


def test_retencion(entorno):
    db, sesion, _ = entorno
    sesion("abierta", "hola")
    sesion("cerrada", "chau", estado="cerrada")
    sesion("enviada", "listo", estado="enviada", email="ana@x.com")
    sesion("wf-enviada", "corrida", estado="enviada", user_id="ana@x.com")  # las reales no tienen "estado"

    assert mantenimiento.retener(ahora=time.time() + 10 * DIA)["sesiones"] == 0
    r = mantenimiento.retener(ahora=time.time() + 40 * DIA)       # pasaron los 30 días
    assert ids(db) == {"enviada", "wf-enviada"} and r["sesiones"] == 2
    r = mantenimiento.retener(ahora=time.time() + 400 * DIA)      # pasó el año
    assert ids(db) == set() and r["archivos"] == 2 and not list(chat.BORRADORES.iterdir())


def test_reporte():
    ahora = datetime.now()
    fila = dict(fecha=ahora, estado="enviada", encaja=True, cliente="Ana", empresa="Sorriso", email="ana@x.com",
                viabilidad="viable", seguimiento="listo")
    filas = [fila,
             fila | dict(cliente="Beto", encaja=False, viabilidad="no viable hoy", seguimiento="error"),
             fila | dict(estado="abierta", cliente=None, seguimiento="—"),
             fila | dict(fecha=ahora - timedelta(days=30), cliente="Viejo", seguimiento="sin procesar")]
    texto = mantenimiento.reporte(filas, {"sesiones": 4, "archivos": 2}, ahora - timedelta(days=7))
    assert "3 conversaciones, 2 intakes enviados, 1 encajan" in texto
    assert "Necesitan atención (2)" in texto and "Viejo" in texto  # un pendiente viejo sigue apareciendo
    assert "se borraron 4 sesiones y 2 archivos" in texto

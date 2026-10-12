"""El login del backoffice, con el AppTest de Streamlit (sin navegador ni red)."""

import os
import tempfile

os.environ["INTAKE_DATA"] = tempfile.mkdtemp()  # nunca tocar data/ real
os.environ.setdefault("ROUTER_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("ROUTER_API_KEY", "test")

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ADMIN = str(Path(__file__).parents[1] / "src/guria_intake/admin/app.py")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "hector")
    monkeypatch.setenv("ADMIN_PASSWORD", "clave-larga")
    return AppTest.from_file(ADMIN, default_timeout=30).run()


def entrar(app, usuario, clave):
    app.text_input[0].input(usuario)
    app.text_input[1].input(clave)
    return app.button[0].click().run()


def test_sin_login_no_se_ve_nada(app):
    assert [t.value for t in app.title] == ["Backoffice"] and not app.dataframe


@pytest.mark.parametrize("usuario, clave", [("hector", "otra"), ("otro", "clave-larga"), ("", "")])
def test_credenciales_malas(app, usuario, clave):
    app = entrar(app, usuario, clave)
    assert app.error[0].value == "Usuario o contraseña incorrectos" and app.title[0].value == "Backoffice"


def test_login_bueno(app):
    app = entrar(app, "hector", "clave-larga")
    assert app.title[0].value == "Panel"


def test_sin_credenciales_en_env_no_hay_login(monkeypatch):
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    app = AppTest.from_file(ADMIN, default_timeout=30).run()
    assert "Faltan ADMIN_USER" in app.error[0].value and not app.text_input


def test_conversaciones_con_la_base_vacia(app):
    app = entrar(app, "hector", "clave-larga")
    app.switch_page("vistas/conversaciones.py").run()
    assert not app.exception and "Todavía no hay conversaciones" in app.info[0].value


# ── datos.py: sin Streamlit, se prueba directo ──────────────────────────────

import json

import httpx
from agno.db.sqlite import SqliteDb
from agno.models.openai.like import OpenAILike

from guria_intake import chat
from guria_intake.admin import datos
from guria_intake.dominio import estimar
from guria_intake.schemas import Borrador, Partida

# Un borrador completo, como lo deja el workflow (el detalle muestra todos sus campos).
BORRADOR = Borrador(
    resumen="Pierden turnos.", alcance=["Recordatorios"], fuera_de_alcance=[], riesgos=[],
    esfuerzo=[Partida(entregable="Recordatorios", horas_min=20, horas_max=30)], caso_relacionado="Showly",
    preguntas_abiertas=[], encaja=True, nota_interna="Cliente claro.", viabilidad="viable", por_que="Ya lo hicimos.",
    enfoque_tecnico="WhatsApp Cloud API", reusar_antes_de_construir=[], depende_del_cliente=[],
    hipotesis="Confirman si se lo piden.", como_sabremos="Menos turnos perdidos.")


@pytest.mark.parametrize("estado, registro, esperado", [
    ("abierta", {}, "—"),
    ("enviada", {"error": "ValueError('x')"}, "error"),
    ("enviada", {"borrador": {}, "aviso": "falló: smtp"}, "error"),
    ("enviada", {"formulario": {}}, "sin procesar"),
    ("enviada", {"borrador": {"x": 1}, "aviso": "enviado"}, "listo"),
    ("enviada", {"preguntas": ["¿qué agenda?"], "aviso": "enviado"}, "listo"),  # vago, pero procesado
])
def test_seguimiento(estado, registro, esperado):
    assert datos.seguimiento(estado, registro) == esperado


@pytest.mark.parametrize("malo", ["../../etc/passwd", "con espacio", ""])
def test_un_id_invalido_no_tiene_archivos(malo):
    assert datos.registro(malo) == {} and datos.documentos(malo) == {}


@pytest.fixture
def una_sesion(monkeypatch, tmp_path):
    """Dos charlas en una base aparte; "nueva" se envió, tiene borrador, PDF y el aviso mandado."""
    db = SqliteDb(db_file=str(tmp_path / "t.db"))
    monkeypatch.setattr(datos, "base", lambda: db)
    monkeypatch.setattr(chat, "BORRADORES", tmp_path)
    responde = lambda r: httpx.Response(200, json={"id": "1", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}]})
    bot = chat.build_chat(db=db)
    bot.model = OpenAILike(id="m", api_key="t", base_url="http://modelo/v1",
                           http_client=httpx.Client(transport=httpx.MockTransport(responde)))
    assert datos.conversaciones() == []

    for sid in ("vieja", "nueva"):
        bot.run("hola", session_id=sid)
    bot.update_session_state({"estado": "enviada"}, session_id="nueva")
    (tmp_path / "nueva.json").write_text(json.dumps({
        "formulario": {"nombre": "Ana", "email": "ana@x.com", "empresa": "", "plazo": "Este mes"},
        "borrador": BORRADOR.model_dump(), "estimacion": estimar([p.model_dump() for p in BORRADOR.esfuerzo]),
        "aviso": "enviado"}))
    (tmp_path / "nueva.interno.pdf").write_bytes(b"%PDF")
    return bot


def test_conversaciones_junta_la_base_y_el_borrador(una_sesion):
    filas = {f["sesion"]: f for f in datos.conversaciones()}
    assert filas["nueva"] | {"fecha": None} == {
        "sesion": "nueva", "fecha": None, "estado": "enviada", "turnos": 1, "cliente": "Ana", "empresa": None,
        "email": "ana@x.com", "plazo": "Este mes", "encaja": True, "viabilidad": "viable", "usd_max": estimar([p.model_dump() for p in BORRADOR.esfuerzo])["usd"][1],
        "seguimiento": "listo"}
    assert filas["vieja"]["estado"] == "abierta" and filas["vieja"]["seguimiento"] == "—"
    assert list(datos.documentos("nueva")) == ["interno"]
    assert [m.content for m in datos.mensajes(una_sesion, "nueva")] == ["hola", "ok"]
    assert datos.mensajes(una_sesion, "nunca-existio") == []


def test_el_detalle_no_reenvia_el_mail_por_defecto(app, una_sesion, monkeypatch):
    from guria_intake.admin.vistas import comunes
    monkeypatch.setattr(comunes, "agente", lambda: una_sesion)
    app = entrar(app, "hector", "clave-larga")
    app.session_state["abierta"] = "nueva"  # lo que hace "Abrir" desde el panel
    app.switch_page("vistas/conversaciones.py").run()
    assert not app.exception and app.subheader[0].value == "Ana"
    # el equipo ya recibió el aviso: reprocesar no lo manda otra vez salvo que lo marques
    assert app.checkbox(key="avisar-nueva").value is False

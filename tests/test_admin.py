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

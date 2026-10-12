"""Los chequeos en código de las evals. Las conversaciones usan el modelo: corren a mano."""

import os
import tempfile

os.environ.setdefault("INTAKE_DATA", tempfile.mkdtemp())  # nunca tocar data/ real
os.environ.setdefault("ROUTER_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("ROUTER_API_KEY", "test")

import pytest

from guria_intake.evals import final_esperado, revisar


def test_un_buen_mensaje_pasa():
    assert revisar(["Hola, Marina. ¿Cuántos turnos pierden por semana? ¿Y quién los confirma hoy?"]) == []


@pytest.mark.parametrize("mensaje, problema", [
    ("Eso sale unos USD 2.000.", "dinero"),
    ("Algo así cuesta R$ 5 mil.", "dinero"),
    ("Calcula 500 dólares.", "dinero"),
    ("Contame qué necesitás.", "voseo"),
    ("Dale, sigamos con la charla.", "voseo"),
    ("Te resumo:\n- nombre: Ana\n- plazo: este mes", "markdown"),
    ("Es **importante**.", "markdown"),
    ("¿Nombre? ¿Email? ¿Plazo?", "3 preguntas"),
])
def test_cada_regla_detecta_su_problema(mensaje, problema):
    assert [p for p in revisar(["ok", mensaje]) if problema in p and p.startswith("mensaje 2")]


def test_no_confunde_palabras_parecidas():
    # "vosotros", "acaba", "plataforma", "dale" dentro de otra palabra: no son voseo
    assert revisar(["Una plataforma que acaba con las llamadas, como un vendedor que no se cansa."]) == []


@pytest.mark.parametrize("espera, estado, ok", [
    ("enviada", "enviada", True), ("enviada", "abierta", False),
    ("no enviada", "abierta", True), ("no enviada", "cerrada", True), ("no enviada", "enviada", False),
    ("cerrada", "abierta", False), ("cualquiera", "enviada", True),
])
def test_final_esperado(espera, estado, ok):
    assert final_esperado(espera, estado) is ok

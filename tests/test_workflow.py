"""Tests sin red del workflow. pedir() es el único punto que toca el modelo: lo
reemplazamos por un guion y corremos el Workflow de Agno de verdad."""

import json
import os
import tempfile

os.environ.setdefault("INTAKE_DATA", tempfile.mkdtemp())  # nunca tocar data/ real
os.environ.setdefault("ROUTER_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("ROUTER_API_KEY", "test")

import pytest

from guria_intake import workflow
from guria_intake.dominio import CASOS, EJEMPLO, catalogo, estimar
from guria_intake.schemas import Borrador, Busquedas, Etapa, Lectura, Partida, Propuesta, Triage


def borrador(**kw) -> Borrador:
    base = dict(resumen="r", alcance=[], fuera_de_alcance=[], riesgos=[],
                esfuerzo=[Partida(entregable="Recordatorios", horas_min=20, horas_max=30),
                          Partida(entregable="Panel", horas_min=10, horas_max=20)],
                caso_relacionado="Showly", preguntas_abiertas=[], encaja=True, nota_interna="",
                viabilidad="viable", por_que="Ya lo hicimos.", enfoque_tecnico="WhatsApp Cloud API",
                reusar_antes_de_construir=["Su agenda"], depende_del_cliente=["Número de WhatsApp Business"],
                hipotesis="Confirman si se lo piden.", como_sabremos="Menos turnos perdidos en un mes.")
    return Borrador(**base | kw)


def propuesta(**kw) -> Propuesta:
    etapa = Etapa(nombre="Probar recordatorios", objetivo="Ver si confirman.", incluye=["Mensaje de confirmación"])
    base = dict(idioma="es", titulo="Confirmación de turnos", para="Marina, Clínica Sorriso",
                lo_que_nos_contaste="Pierden turnos.", como_se_ve_resuelto=["La agenda se llena sola."],
                etapas=[etapa, etapa], lo_que_falta_definir=["¿Qué agenda usan?"])
    return Propuesta(**base | kw)


LECTURA = Lectura(dolor_real="La recepcionista no da abasto.", que_lo_mueve=["Sacarse un peso"],
                  objeciones=["Ya probé un bot → este solo confirma turnos"],
                  angulo="Lo que pierde por cada turno vacío.", abrir_la_reunion="¿Cuántos turnos pierden?")


def guion(monkeypatch, **respuestas):
    """pedir() falso: por cada schema devuelve la siguiente respuesta de su lista.
    Anota cuántas veces se llamó a cada uno."""
    colas = {k: list(v) for k, v in respuestas.items()}
    llamadas = {}

    def falso(instrucciones, schema, texto):
        llamadas[schema.__name__] = llamadas.get(schema.__name__, 0) + 1
        llamadas[f"texto_{schema.__name__}"] = texto  # el último contexto que recibió
        return colas[schema.__name__].pop(0)

    monkeypatch.setattr(workflow, "pedir", falso)
    return llamadas


CLARA = Triage(vaga=False, faltantes=[])


@pytest.fixture(autouse=True)
def sin_tavily(monkeypatch):
    # Aunque tengas la key en tu entorno, los tests no salen a internet salvo que la pongan.
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def test_camino_feliz(monkeypatch):
    llamadas = guion(monkeypatch, Triage=[CLARA], Borrador=[borrador()], Lectura=[LECTURA], Propuesta=[propuesta()])
    r = workflow.procesar(EJEMPLO)
    assert {k: v for k, v in llamadas.items() if not k.startswith("texto_")} == \
        {"Triage": 1, "Borrador": 1, "Lectura": 1, "Propuesta": 1}
    assert r["borrador"]["caso_relacionado"] == "Showly" and r["propuesta"]["titulo"] == "Confirmación de turnos"
    assert r["lectura"]["angulo"] and r["problemas"] == [] and r["problemas_propuesta"] == []
    assert r["estimacion"]["horas"] == (30, 50)  # el precio sale del código
    json.dumps(r)  # todo serializable


def test_lo_vago_no_se_redacta(monkeypatch):
    llamadas = guion(monkeypatch, Triage=[Triage(vaga=True, faltantes=["¿Qué problema resuelve?"])])
    r = workflow.procesar(EJEMPLO)
    assert "Borrador" not in llamadas and "Lectura" not in llamadas  # ni borrador, ni lectura, ni propuesta
    assert r["preguntas"] == ["¿Qué problema resuelve?"] and r["borrador"] is None


def test_el_revisor_devuelve_el_borrador(monkeypatch):
    malo = borrador(caso_relacionado="Inventado")
    llamadas = guion(monkeypatch, Triage=[CLARA], Borrador=[malo, borrador()], Lectura=[LECTURA], Propuesta=[propuesta()])
    r = workflow.procesar(EJEMPLO)
    assert llamadas["Borrador"] == 2 and r["intentos"] == 2 and r["problemas"] == []


def test_el_loop_no_es_infinito(monkeypatch):
    # Sigue mal después de MAX_INTENTOS: avanza igual, con los problemas anotados para el equipo.
    malo = borrador(esfuerzo=[Partida(entregable="x", horas_min=30, horas_max=20)])
    llamadas = guion(monkeypatch, Triage=[CLARA], Borrador=[malo] * 5, Lectura=[LECTURA], Propuesta=[propuesta()])
    r = workflow.procesar(EJEMPLO)
    assert llamadas["Borrador"] == workflow.MAX_INTENTOS and r["problemas"]
    assert r["propuesta"]


def test_si_no_encaja_no_hay_propuesta(monkeypatch):
    llamadas = guion(monkeypatch, Triage=[CLARA], Borrador=[borrador(encaja=False)], Lectura=[LECTURA])
    r = workflow.procesar(EJEMPLO)
    assert "Propuesta" not in llamadas and r["propuesta"] is None


@pytest.mark.parametrize("texto", ["Cuesta US$ 500", "Listo en 3 semanas", "Solo por hoy", "Paso uno — paso dos"])
def test_la_propuesta_no_lleva_precio_plazo_ni_presion(monkeypatch, texto):
    sucia = propuesta(lo_que_nos_contaste=texto)
    llamadas = guion(monkeypatch, Triage=[CLARA], Borrador=[borrador()], Lectura=[LECTURA], Propuesta=[sucia, propuesta()])
    r = workflow.procesar(EJEMPLO)
    assert llamadas["Propuesta"] == 2 and r["problemas_propuesta"] == []


@pytest.mark.parametrize("texto", ["Descuento por tiempo limitado", "Últimos cupos del mes", "Só hoje",
                                   "Oferta válida hasta el viernes", "No te quedes afuera"])
def test_presion_se_detecta(texto):
    assert workflow.PRESION.search(texto)


@pytest.mark.parametrize("texto", ["Enviar ofertas personalizadas a tus clientes",
                                   "Un descuento automático al recomprar", "Promociones por WhatsApp"])
def test_ofertas_y_descuentos_del_proyecto_no_son_presion(texto):
    # Si el proyecto es de ofertas, la propuesta tiene que poder decirlo con las palabras del cliente.
    assert not workflow.PRESION.search(texto)


@pytest.mark.parametrize("texto", ["Listo en dos semanas", "En un mes lo probamos", "Medio año de trabajo",
                                   "Em duas semanas", "Un par de semanas", "En 15 días", "Uma quinzena"])
def test_plazo_en_palabras_se_detecta(texto):
    assert workflow.PLAZO.search(texto)


@pytest.mark.parametrize("texto", ["Un día normal con la agenda llena", "Cada mes revisamos los números",
                                   "Responde en 24 horas", "Las semanas con más turnos"])
def test_no_es_plazo(texto):
    assert not workflow.PLAZO.search(texto)


@pytest.mark.parametrize("texto", ["Cuesta 5 mil dólares", "USD 3000", "US$ 900", "Unos $1500", "R$ 5000"])
def test_precio_en_dolares_se_detecta(texto):
    assert workflow.PRECIO.search(texto)


def test_turnos_reales_no_es_moneda():
    assert not workflow.PRECIO.search("Pierden turnos reales cada semana")


def test_si_el_modelo_falla_el_lead_no_se_pierde(monkeypatch):
    def roto(*a):
        raise ValueError("el modelo devolvió texto")
    monkeypatch.setattr(workflow, "pedir", roto)
    destino = __import__("pathlib").Path(tempfile.mkdtemp()) / "lead.json"
    destino.write_text(json.dumps({"formulario": EJEMPLO}))
    workflow.completar(destino)
    guardado = json.loads(destino.read_text())
    assert guardado["formulario"] == EJEMPLO and guardado["error"]


def test_estimar_usa_la_tarifa_no_el_modelo(monkeypatch):
    monkeypatch.setenv("TARIFA_USD_HORA", "25-45")
    monkeypatch.setenv("HORAS_SEMANA", "25")
    r = estimar([{"horas_min": 20, "horas_max": 30}, {"horas_min": 10, "horas_max": 20}])
    assert r["horas"] == (30, 50) and r["usd"] == (750, 2250) and r["semanas"] == (2, 2)


def test_capacidades_toml():
    assert {"Showly", "PideAI"} <= {c["nombre"] for c in CASOS}
    assert "SERVICIOS DEL EQUIPO" in catalogo() and "Showly" in catalogo()


def test_la_sesion_se_guarda_en_la_base(monkeypatch, tmp_path):
    # Con un objeto pydantic en session_state, Agno no guarda la sesión y solo avisa con un WARNING.
    from agno.db.sqlite import SqliteDb

    guion(monkeypatch, Triage=[CLARA], Borrador=[borrador()], Lectura=[LECTURA], Propuesta=[propuesta()])
    wf = workflow.build_workflow(db=SqliteDb(db_file=str(tmp_path / "wf.db")))
    r = wf.run(input=EJEMPLO, session_id="lead-0001")
    assert wf.get_session_state(session_id="lead-0001")["propuesta"]["titulo"] == "Confirmación de turnos"


def test_antecedentes_son_solo_para_el_equipo(monkeypatch):
    primera = EJEMPLO | {"email": "Recurrente@x.com "}
    guion(monkeypatch, Triage=[CLARA], Borrador=[borrador(resumen="Recordatorios por WhatsApp")],
          Lectura=[LECTURA], Propuesta=[propuesta()])
    assert workflow.procesar(primera, session_id="wf-primera")["antecedentes"] == []

    nota = borrador(nota_interna="Mismo email que el de Recordatorios por WhatsApp.")
    llamadas = guion(monkeypatch, Triage=[CLARA], Borrador=[nota], Lectura=[LECTURA], Propuesta=[propuesta()])
    r = workflow.procesar(EJEMPLO | {"email": "recurrente@x.com"}, session_id="wf-segunda")
    assert [a["resumen"] for a in r["antecedentes"]] == ["Recordatorios por WhatsApp"]  # mismo cliente, otro formato
    assert "Recordatorios por WhatsApp" in llamadas["texto_Borrador"]
    assert "Recordatorios por WhatsApp" in llamadas["texto_Triage"]  # si no, "como les dije" parece vago
    # la propuesta y la lectura no los ven: el email no está verificado
    assert "Recordatorios por WhatsApp" not in llamadas["texto_Propuesta"] + llamadas["texto_Lectura"]


def test_antecedentes_sin_user_id_no_mezcla_clientes(monkeypatch):
    # Como corre desde AgentOS: sin user_id en el run. No puede traer intakes de otros emails.
    guion(monkeypatch, Triage=[CLARA], Borrador=[borrador(resumen="De otro cliente")], Lectura=[LECTURA], Propuesta=[propuesta()])
    workflow.procesar(EJEMPLO | {"email": "otro@x.com"}, session_id="wf-otro")
    guion(monkeypatch, Triage=[CLARA], Borrador=[borrador()], Lectura=[LECTURA], Propuesta=[propuesta()])
    estado = {}
    workflow.build_workflow().run(input=EJEMPLO | {"email": "nuevo@x.com"}, session_state=estado)
    assert estado["antecedentes"] == []


FUENTE = {"titulo": "Recordatorios para clínicas", "url": "https://recordatorios.example/clinicas", "contenido": "SaaS."}


def con_tavily(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test")
    buscadas = []
    monkeypatch.setattr(workflow, "buscar_web", lambda q: buscadas.append(q) or [FUENTE])
    return buscadas


def test_investigar_no_manda_datos_del_cliente(monkeypatch):
    buscadas = con_tavily(monkeypatch)
    consultas = Busquedas(consultas=["Clínica Sorriso recordatorios", "recordatorios WhatsApp clínicas dentales",
                                     "agenda de marina@sorriso.com"])
    llamadas = guion(monkeypatch, Busquedas=[consultas], Triage=[CLARA], Borrador=[borrador()],
                     Lectura=[LECTURA], Propuesta=[propuesta()])
    r = workflow.procesar(EJEMPLO)
    assert buscadas == ["recordatorios WhatsApp clínicas dentales"]
    assert len(r["consultas_descartadas"]) == 2
    assert FUENTE["url"] in llamadas["texto_Borrador"]  # redactar recibe los resultados
    assert FUENTE["url"] not in llamadas["texto_Propuesta"] + llamadas["texto_Lectura"]


def test_privada_respeta_palabras():
    f = {"nombre": "Ana Paz", "email": "ana@sorriso.com", "empresa": "Sorriso"}
    assert workflow.privada("software para Sorriso", f)
    assert not workflow.privada("recordatorios para mañana", f)  # "ana" dentro de otra palabra no cuenta


def test_el_revisor_rechaza_urls_inventadas(monkeypatch):
    con_tavily(monkeypatch)
    inventada = borrador(reusar_antes_de_construir=["Zapier: https://inventada.example/x"])
    buena = borrador(reusar_antes_de_construir=[f"Recordatorios para clínicas: {FUENTE['url']}"])
    llamadas = guion(monkeypatch, Busquedas=[Busquedas(consultas=["recordatorios clínicas"])], Triage=[CLARA],
                     Borrador=[inventada, buena], Lectura=[LECTURA], Propuesta=[propuesta()])
    r = workflow.procesar(EJEMPLO)
    assert llamadas["Borrador"] == 2 and r["problemas"] == []
    assert r["fuentes"] == [FUENTE]


def test_si_tavily_falla_igual_se_redacta(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test")
    def caida(q):
        raise ConnectionError("sin internet")
    monkeypatch.setattr(workflow, "buscar_web", caida)
    guion(monkeypatch, Busquedas=[Busquedas(consultas=["x"])], Triage=[CLARA], Borrador=[borrador()],
          Lectura=[LECTURA], Propuesta=[propuesta()])
    r = workflow.procesar(EJEMPLO)
    assert r["borrador"] and r["fuentes"] == []

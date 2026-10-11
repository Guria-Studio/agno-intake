"""Documento interno en A4: el borrador, la estimación, la lectura del cliente, los antecedentes
y las fuentes de Tavily, para preparar la reunión. Nunca va al cliente: por eso sí lleva precio.
"""

from datetime import date
from html import escape as e

from ..dominio import estimar
from .estilo import CSS_INTERNO, FUENTES, logo


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _lista(xs: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in xs) + "</ul>" if xs else "<p>-</p>"


def titulo(registro: dict) -> str:
    p, b = registro.get("propuesta"), registro.get("borrador")
    if p:
        return p["titulo"]
    return b["resumen"].split(".")[0][:70] if b else "Intake sin borrador"


def render(session_id: str, registro: dict, hoy: date | None = None) -> str:
    f, b, l = registro["formulario"], registro["borrador"], registro.get("lectura")
    cliente = f["nombre"] + (f" · {f['empresa']}" if f.get("empresa") else "") + f" · {f['email']}"
    alerta = "" if b["viabilidad"] == "viable" else " alerta"
    est = estimar(b["esfuerzo"])
    horas = "".join(f"<li>{e(x['entregable'])}: {x['horas_min']}–{x['horas_max']} h</li>" for x in b["esfuerzo"])

    s = [f'<header><span style="display:flex;gap:8px;align-items:center">{logo("#111417", "#E2502B", 18)}'
         f'<b>guria.lat</b></span><span>Interno · {(hoy or date.today()).isoformat()} · {e(session_id)}</span></header>',
         f"<h1>{e(titulo(registro))}</h1><p class='para'>{e(cliente)}</p>",
         f'<div class="veredicto"><span class="chip{alerta}">{e(b["viabilidad"])}</span>'
         f'<span class="chip">encaja: {"sí" if b["encaja"] else "no"}</span>'
         f'<span class="chip">{e(f["plazo"])}</span></div>',
         f"<section><h2>Lo que escribió</h2><p>{e(f['descripcion'])}</p></section>",
         f"<section><h2>El problema</h2><p>{e(b['resumen'])}</p></section>",
         f"<section><h2>Viabilidad</h2><p>{e(b['por_que'])}</p><dl>"
         f"<dt>Enfoque</dt><dd>{e(b['enfoque_tecnico'])}</dd>"
         f"<dt>Reusar antes de construir</dt><dd>{_lista(b['reusar_antes_de_construir'])}</dd>"
         f"<dt>Depende del cliente</dt><dd>{_lista(b['depende_del_cliente'])}</dd>"
         f"<dt>Hipótesis</dt><dd>{e(b['hipotesis'])}</dd>"
         f"<dt>Cómo sabremos</dt><dd>{e(b['como_sabremos'])}</dd></dl></section>",
         f"<section><h2>Primera etapa</h2><dl><dt>Incluye</dt><dd>{_lista(b['alcance'])}</dd>"
         f"<dt>No incluye</dt><dd>{_lista(b['fuera_de_alcance'])}</dd>"
         f"<dt>Esfuerzo</dt><dd><ul>{horas}</ul></dd>"
         # La estimación la calcula el código con la tarifa del .env, nunca el modelo.
         f"<dt>Estimación</dt><dd><b>USD {_miles(est['usd'][0])}–{_miles(est['usd'][1])}</b> · "
         f"{est['horas'][0]}–{est['horas'][1]} h · {est['semanas'][0]}–{est['semanas'][1]} semanas<br>"
         f"<small>Tarifa de referencia USD {est['tarifa'][0]}–{est['tarifa'][1]}/h</small></dd>"
         + (f"<dt>Caso parecido</dt><dd>{e(b['caso_relacionado'])}</dd>" if b.get("caso_relacionado") else "")
         + "</dl></section>",
         f"<section><h2>Riesgos</h2>{_lista(b['riesgos'])}</section>"]
    if l:
        s.append(f"<section><h2>Lectura del cliente</h2><dl>"
                 f"<dt>Dolor real</dt><dd>{e(l['dolor_real'])}</dd>"
                 f"<dt>Qué lo mueve</dt><dd>{_lista(l['que_lo_mueve'])}</dd>"
                 f"<dt>Objeciones</dt><dd>{_lista(l['objeciones'])}</dd>"
                 f"<dt>Ángulo</dt><dd>{e(l['angulo'])}</dd>"
                 f"<dt>Abrir la reunión</dt><dd>{e(l['abrir_la_reunion'])}</dd></dl></section>")
    s.append(f"<section><h2>Preguntas abiertas</h2>{_lista(b['preguntas_abiertas'])}</section>")
    if registro.get("antecedentes"):  # el email no está verificado: puede no ser la misma persona
        previos = [f"{a['fecha']} · {a['viabilidad']} · {a['resumen']}" for a in registro["antecedentes"]]
        s.append(f"<section><h2>Intakes anteriores de este email (no verificado)</h2>{_lista(previos)}</section>")
    if registro.get("fuentes"):
        links = "".join(f"<li><a href='{e(x['url'])}'>{e(x['titulo'])}</a><br><small>{e(x['url'])}</small></li>"
                        for x in registro["fuentes"])
        s.append(f"<section><h2>Fuentes (Tavily)</h2><ul>{links}</ul></section>")
    s.append(f"<section><h2>Nota interna</h2><p class='nota'>{e(b['nota_interna'])}</p></section>")
    for clave, rotulo in (("problemas", "Sin resolver por el revisor del borrador"),
                          ("problemas_propuesta", "Sin resolver por el revisor de la propuesta")):
        if registro.get(clave):  # el revisor no quedó conforme después de los reintentos
            s.append(f"<section><h2>{rotulo}</h2>{_lista(registro[clave])}</section>")

    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Interno · {e(titulo(registro))}</title>'
            f'<link rel="stylesheet" href="{FUENTES}"><style>{CSS_INTERNO}</style></head><body>{"".join(s)}</body></html>')

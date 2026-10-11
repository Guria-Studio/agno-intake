"""El pitch para el cliente: la Propuesta en slides (HTML 1280×720 → PDF).

El modelo solo escribe la Propuesta, y revisar_propuesta ya la revisó. Las slides, los textos
fijos y el botón para agendar los pone este archivo: el modelo no puede romper el diseño,
colar un precio ni cambiar el link de la reunión.
"""

from datetime import date
from html import escape as e
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..schemas import Propuesta
from .estilo import CSS_DECK, FUENTES, MESES, TXT, logo


def link_agenda(base: str, nombre: str, email: str) -> str:
    """El link de Cal.com con nombre y email ya cargados (?name=&email=): el cliente solo elige hora."""
    partes = urlsplit(base)
    query = dict(parse_qsl(partes.query)) | {"name": nombre, "email": email}
    return urlunsplit(partes._replace(query=urlencode(query)))


def _slide(clase: str, kicker: str, cuerpo: str, pie: str) -> str:
    return (f'<section class="slide {clase}"><p class="kicker">{kicker}</p>'
            f'<div class="body">{cuerpo}</div><div class="foot">{pie}</div></section>')


def render(p: Propuesta, agenda_url: str, hoy: date | None = None) -> str:
    t = TXT[p.idioma]
    hoy = hoy or date.today()
    fecha = f"{hoy.day} de {MESES[p.idioma][hoy.month - 1]} de {hoy.year}"

    secciones: list[tuple[str, str, str]] = []  # (clase, título de sección, cuerpo)
    cuerpo = f'<p class="quote">{e(p.lo_que_nos_contaste)}</p>'
    if p.costo_hoy:
        cuerpo += f'<div class="cuesta"><p class="kicker">{t["cuesta"]}</p><p>{e(p.costo_hoy)}</p></div>'
    secciones.append(("", t["contaste"], cuerpo))

    items = "".join(f'<div><span class="n">{i:02d}</span><p class="item">{e(x)}</p></div>'
                    for i, x in enumerate(p.como_se_ve_resuelto[:4], 1))
    secciones.append(("", t["resuelto"], f'<h2>{t["resuelto_h"]}</h2><div class="grid cols2">{items}</div>'))

    etapas = p.etapas[:3]
    cols = "".join(
        f'<div class="etapa"><span class="n">{t["etapa"]} {i}</span>'
        + (f'<span class="aca">{t["aca"]}</span>' if i == 1 else "")
        + f'<h3>{e(x.nombre)}</h3><p class="obj">{e(x.objetivo)}</p>'
        f'<ul>{"".join(f"<li>{e(y)}</li>" for y in x.incluye[:3])}</ul></div>'
        for i, x in enumerate(etapas, 1))
    tres = len(etapas) == 3
    secciones.append(("tres" if tres else "", t["etapas"],
                      f'<h2>{t["etapas_h"]}</h2><div class="grid {"cols3" if tres else "cols2"}">{cols}</div>'))

    preg = "".join(f'<li><span>{i:02d}</span><p>{e(q)}</p></li>'
                   for i, q in enumerate(p.lo_que_falta_definir[:3], 1))
    secciones.append(("", t["falta"], f'<h2>{t["falta_h"]}</h2><ul class="preguntas">{preg}</ul>'))

    total = len(secciones) + 2
    def pie(n: int) -> str:
        return f'<span>guria.lat · {e(p.titulo)}</span><span>{n:02d} / {total:02d}</span>'

    html = [_slide("dark portada", f'<b>{t["propuesta"]}</b> · {fecha}',
                   f'<div class="brand">{logo("#EFEEE9", "#E2502B")}<b>guria<span>.lat</span></b></div>'
                   f'<div style="display:flex;flex-direction:column;gap:24px"><h1>{e(p.titulo)}</h1>'
                   f'<p class="lead" style="color:var(--body-dark)">{t["para"]} {e(p.para)}</p></div>',
                   f'<span>{t["borrador"]}</span><span>01 / {total:02d}</span>')]
    for n, (clase, titulo, cuerpo) in enumerate(secciones, 2):
        html.append(_slide(clase, f"<b>{n - 1:02d}</b> · {titulo}", cuerpo, pie(n)))
    # El link visible es el base (corto); el href lleva nombre y email para Cal.com.
    visible = agenda_url.split("?")[0]
    html.append(_slide("signal cta", '<b style="color:var(--on-signal)">guria.lat</b>',
                       f'<h2>{t["cta_h"]}</h2><p class="quote">{t["cta_p"]}</p>'
                       f'<a class="boton" href="{e(agenda_url)}">{t["agendar"]} →'
                       f'<small>{e(visible)}</small></a>',
                       pie(total)))

    return (f'<!doctype html><html lang="{"pt-BR" if p.idioma == "pt" else "es"}"><head><meta charset="utf-8">'
            f'<title>{e(p.titulo)} · guria.lat</title><link rel="stylesheet" href="{FUENTES}">'
            f'<style>{CSS_DECK}</style></head><body>{"".join(html)}</body></html>')

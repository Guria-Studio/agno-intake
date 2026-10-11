"""Lo que se verifica en código, sin modelo: los revisores de los dos loops y el filtro
de privacidad de las búsquedas. El prompt pide estas cosas; acá se comprueban.

Es el archivo que más crece: cada guardrail nuevo (lecciones 4 y 5) es una regla más acá,
con su test, sin tocar los pasos ni el grafo.
"""

import re

from agno.run import RunContext
from agno.workflow import StepInput, StepOutput

from ..dominio import CASOS
from ..schemas import Borrador, Propuesta

# ── Privacidad ───────────────────────────────────────────────────────────────


def privada(consulta: str, f: dict) -> bool:
    """True si la consulta lleva datos del cliente. Tavily es un tercero (LGPD)."""
    _, _, dominio = f["email"].partition("@")  # partition: sin "@" no rompe
    datos = [f["email"], dominio, f.get("empresa", ""), *f["nombre"].split()]
    return any(re.search(rf"\b{re.escape(d)}\b", consulta, re.I) for d in datos if len(d) > 2)


# ── Borrador interno ─────────────────────────────────────────────────────────

URL = re.compile(r"https?://[^\s\"'<>]+")


def revisar(step_input: StepInput, run_context: RunContext) -> StepOutput:
    # Reglas en código, no en el prompt: lo que se puede verificar, se verifica.
    s = run_context.session_state
    b, problemas = Borrador.model_validate(s["borrador"]), []
    if not b.esfuerzo:
        problemas.append("Falta el esfuerzo: horas por entregable de la primera etapa.")
    for p in b.esfuerzo:
        if not 0 < p.horas_min <= p.horas_max:
            problemas.append(f"Horas inválidas en '{p.entregable}': mínimo mayor que el máximo o en cero.")
    nombres = {c["nombre"] for c in CASOS}
    if b.caso_relacionado and b.caso_relacionado not in nombres:
        problemas.append(f"caso_relacionado '{b.caso_relacionado}' no existe; usa uno de {sorted(nombres)} o null.")
    # Links reales: toda URL del borrador tiene que venir de lo que devolvió Tavily.
    conocidas = {x["url"].rstrip("/") for x in s.get("fuentes", [])}
    for url in URL.findall(b.model_dump_json()):
        if url.rstrip("/.,)") not in conocidas:
            problemas.append(f"La URL {url} no está en los resultados de búsqueda. Usa solo esas URLs, o ninguna.")
    if b.viabilidad == "no viable hoy" and b.encaja:
        problemas.append("Dijiste 'no viable hoy' pero encaja true: si no es viable hoy, encaja es false.")
    s["problemas"] = problemas
    return StepOutput(content=problemas)


# ── Propuesta al cliente ─────────────────────────────────────────────────────
# Lo que el cliente nunca puede ver, verificado en código y no solo pedido en el prompt.

# "reales"/"reais" también son adjetivos ("turnos reales", "dados reais"): moneda solo junto a un número.
PRECIO = re.compile(r"(US\$|R\$|\$|€|\b(usd|brl)\b|\d\s*(mil\s+)?(dólares?|dolares?|reais|reales)\b)", re.I)
# Plazos en cifras ("3 semanas", "15 días") o en palabras ("dos semanas", "un mes", "medio año").
# Con días solo cifras: "un día normal con el problema resuelto" es justo lo que el prompt pide.
# Las horas no: "responde en 24 horas" describe el producto, no un plazo de entrega.
_NUMEROS = (r"un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|"
            r"um|uma|dois|duas|três|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|"
            r"par de|algunas|algumas|pocas|poucas")
PLAZO = re.compile(
    rf"(\b\d+\s*(semanas?|meses|mes|días?|dias?|mês|años?|anos?)\b|"
    rf"\b({_NUMEROS})\s+(semanas?|meses|mes|mês|años?|anos?)\b|"
    rf"\b(medio año|meio ano|una quincena|uma quinzena|quince días|quinze dias)\b)",
    re.I,
)
# El límite ético de la lectura, verificado: nada de presión ni escasez inventada.
# Frases de presión, no palabras sueltas: "ofertas por WhatsApp" o "descuento al recomprar" pueden
# ser justo el proyecto del cliente, y la propuesta tiene que poder usar sus palabras.
PRESION = re.compile(
    r"(últim[oa]s (cupos|lugares|vagas|unidades)|"
    r"s[oó]lo (por )?(hoy|esta semana)|s[oó] (hoje|esta semana)|"
    r"por (tiempo|tempo) limitado|"
    r"(oferta|promoci[oó]n|promoção) (v[aá]lida|vence|termina)|"
    r"(descuento|desconto) (exclusivo|especial|si firmas|se fechar|por (tiempo|tempo) limitado)|"
    r"antes de que sea tarde|antes que seja tarde|no te quedes (afuera|fuera)|n[aã]o fique de fora)",
    re.I,
)


def revisar_propuesta(step_input: StepInput, run_context: RunContext) -> StepOutput:
    s = run_context.session_state
    p, problemas = Propuesta.model_validate(s["propuesta"]), []
    todo = "\n".join(p.textos())
    if "—" in todo:
        problemas.append("Hay guiones largos (—). Reemplázalos por dos puntos, coma o punto.")
    for regla, motivo in ((PRECIO, "un precio o una moneda"), (PLAZO, "un plazo"), (PRESION, "presión al cliente")):
        if m := regla.search(todo):
            problemas.append(f"Menciona {motivo} ('{m.group(0)}'). Sácalo: se define en la reunión, sin urgencia.")
    if not 2 <= len(p.etapas) <= 3:
        problemas.append("Tienen que ser dos o tres etapas.")
    s["problemas_propuesta"] = problemas
    return StepOutput(content=problemas)

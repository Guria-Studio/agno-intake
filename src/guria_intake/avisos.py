"""El aviso al equipo: cada intake llega por email (Resend por SMTP) con el documento interno
y el pitch adjuntos. Solo stdlib: smtplib + email.message.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

VARIABLES = ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_FROM", "AVISOS_EMAIL")


def email(asunto: str, texto: str, adjuntos: list[Path]) -> None:
    """Manda un mail a AVISOS_EMAIL. Puerto 465 = SSL directo; cualquier otro, STARTTLS."""
    if falta := [v for v in VARIABLES if not os.environ.get(v)]:
        raise RuntimeError(f"Faltan {', '.join(falta)} en .env")
    msg = EmailMessage()
    msg["Subject"], msg["To"] = asunto, os.environ["AVISOS_EMAIL"]
    msg["From"] = os.environ["SMTP_FROM"]  # en Resend, de un dominio verificado
    msg.set_content(texto)
    for f in adjuntos:
        tipo = ("application", "pdf") if f.suffix == ".pdf" else ("text", "html")
        msg.add_attachment(f.read_bytes(), maintype=tipo[0], subtype=tipo[1], filename=f.name)

    host, puerto = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465"))
    conexion = smtplib.SMTP_SSL if puerto == 465 else smtplib.SMTP
    with conexion(host, puerto, timeout=30) as s:
        if puerto != 465:
            s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)


def recortar(texto: str, limite: int = 600) -> str:
    """Corta en el último punto antes del límite, nunca en media palabra."""
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rfind(". ")
    return (texto[:corte + 1] if corte > 0 else texto[:limite].rsplit(" ", 1)[0]) + " …"


def asunto(registro: dict, titulo: str) -> str:
    return f"Nuevo intake · {titulo} · {registro['formulario']['nombre']}"


def texto_intake(session_id: str, registro: dict) -> str:
    """El cuerpo del mail: lo justo para decidir sin abrir los adjuntos."""
    f, b, p = registro["formulario"], registro.get("borrador"), registro.get("propuesta")
    lineas = [
        f"{f['nombre']}" + (f" · {f['empresa']}" if f.get("empresa") else "") + f" · {f['email']}",
        f"Plazo: {f['plazo']}",
    ]
    if b:
        est = registro.get("estimacion")
        lineas.append(f"Encaja: {'sí' if b['encaja'] else 'no'} · {b['viabilidad']}")
        if est:
            lineas.append(f"Estimación: USD {est['usd'][0]}–{est['usd'][1]} · {est['semanas'][0]}–{est['semanas'][1]} semanas")
        lineas += ["", recortar(b["nota_interna"])]
    elif registro.get("error"):  # sin borrador por una falla, no porque el cliente fue vago
        lineas += ["", "El workflow falló: no hay borrador. El formulario quedó guardado."]
    else:
        lineas += ["", "Datos insuficientes para proponer. Preguntas para el cliente:"]
        lineas += [f"· {q}" for q in registro.get("preguntas", [])[:5]]
    if registro.get("error"):
        lineas += ["", f"Error: {registro['error'][:200]}"]
    if p:
        lineas += ["", "Adjuntos: el documento interno (no reenviar) y el pitch para el cliente "
                       "(revísalo antes de reenviarlo; trae el botón para agendar)."]
    elif b:
        lineas += ["", "Adjunto: el documento interno. No hay pitch: el borrador dice que no encaja."]
    lineas += ["", f"Sesión {session_id}"]
    return "\n".join(lineas)

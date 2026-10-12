"""Lección 3: la API que usa la web de guria.lat. Un endpoint, con streaming.

    uv run --env-file .env uvicorn guria_intake.api:app --port 8000
    (detrás de un proxy: --proxy-headers --forwarded-allow-ips <ip del proxy>, o todos
    los visitantes comparten la IP del proxy y el límite por IP los frena juntos)

POST /api/chat  {"session_id": null | "...", "texto": "..."}
→ NDJSON, una línea JSON por evento:
    {"texto": "Hola"}  {"texto": ", ¿qué necesitas?"}  ...
    {"session_id": "...", "estado": "abierta"}           ← siempre la última

Por qué no AgentOS: expone todas las sesiones, el workflow y las métricas, y está pensado para
alguien de confianza. Esto lo llama un visitante anónimo: solo puede hablar con su sesión.
"""

import json
import os
import time
import uuid
from collections import defaultdict, deque

from agno.run.agent import RunContentEvent, RunErrorEvent
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from .chat import ID_SEGURO, archivo, build_chat, estado
from .workflow import completar

app = FastAPI(title="guria-intake", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "https://guria.lat").split(","),
    allow_methods=["POST"],
    allow_headers=["content-type"],
)
agente = build_chat()


class Mensaje(BaseModel):
    session_id: str | None = Field(None, pattern=ID_SEGURO.pattern)
    texto: str = Field(min_length=1, max_length=2000)


# ponytail: en memoria y por proceso; con varias réplicas, el límite va al proxy o a Redis.
VENTANA, MAX_PEDIDOS = 60, 20
pedidos: dict[str, deque] = defaultdict(deque)


def limitar(ip: str) -> None:
    """MAX_TURNOS frena una sesión, pero cualquiera puede abrir sesiones nuevas: esto frena a la IP."""
    ahora, q = time.monotonic(), pedidos[ip]
    while q and q[0] < ahora - VENTANA:
        q.popleft()
    if len(q) >= MAX_PEDIDOS:
        raise HTTPException(429, "Demasiados mensajes. Espera un minuto.")
    q.append(ahora)


def linea(**datos) -> str:
    return json.dumps(datos, ensure_ascii=False) + "\n"


def despues(session_id: str, ya_enviado: bool) -> None:
    """Corre cuando el cliente ya recibió la respuesta: el workflow tarda ~1 min.
    Se mira el archivo y no el estado: enviar_intake lo escribe en el acto."""
    if not ya_enviado and archivo(session_id).exists():
        completar(archivo(session_id))


@app.post("/api/chat")
def conversar(m: Mensaje, request: Request) -> StreamingResponse:
    limitar(request.client.host if request.client else "?")
    # El id lo pone el servidor: un id que no existe es un error, no una sesión nueva con
    # nombre elegido por el visitante (p. ej. "wf-...", que es de las corridas del workflow).
    if m.session_id and not agente.get_session(session_id=m.session_id):
        raise HTTPException(404, "Sesión desconocida")
    sid = m.session_id or uuid.uuid4().hex
    if (actual := estado(agente, sid)) != "abierta":
        raise HTTPException(409, f"Conversación {actual}")
    ya_enviado = archivo(sid).exists()

    def eventos():
        for e in agente.run(m.texto, session_id=sid, stream=True):
            if isinstance(e, RunContentEvent) and e.content:
                yield linea(texto=e.content)
            elif isinstance(e, RunErrorEvent) and estado(agente, sid) == "abierta":
                # el portero también termina en RunErrorEvent, pero ese cambia el estado y
                # lo dice la última línea; esto es el modelo caído: el detalle queda en el log
                yield linea(error="No pude responder. Intenta de nuevo en un momento.")
        yield linea(session_id=sid, estado=estado(agente, sid))

    # ponytail: si el visitante corta la conexión a mitad, la tarea no corre y el intake queda
    # "sin procesar"; se recupera con Reprocesar en el backoffice.
    return StreamingResponse(eventos(), media_type="application/x-ndjson",
                             background=BackgroundTask(despues, sid, ya_enviado))

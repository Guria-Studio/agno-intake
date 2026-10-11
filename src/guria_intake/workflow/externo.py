"""Lo único del workflow que sale de la máquina: el modelo y la búsqueda en internet.

Los pasos llaman `externo.pedir(...)` y `externo.buscar_web(...)` a través del módulo,
nunca con `from .externo import pedir`: así los tests reemplazan estas dos funciones acá
y ningún paso se escapa a la red con una copia vieja del nombre.
"""

import os

from agno.agent import Agent
from pydantic import BaseModel

from ..dominio import modelo


def pedir[T: BaseModel](instrucciones: str, schema: type[T], texto: str) -> T:
    """Una llamada al modelo con salida estructurada. Es el único punto de contacto con
    el LLM en todo el workflow: los tests lo reemplazan y prueban el flujo sin red."""
    r = Agent(model=modelo(), instructions=instrucciones, output_schema=schema, retries=2).run(texto)
    if not isinstance(r.content, schema):
        # El modelo omitió un campo o devolvió texto. Step(max_retries=...) lo reintenta.
        raise ValueError(f"Se esperaba {schema.__name__}, llegó: {str(r.content)[:200]}")
    return r.content


def buscar_web(consulta: str) -> list[dict]:
    """Una búsqueda en Tavily. Es el único punto que sale a internet: los tests lo reemplazan."""
    from tavily import TavilyClient

    r = TavilyClient(api_key=os.environ["TAVILY_API_KEY"]).search(consulta, max_results=3, search_depth="basic")
    # ponytail: 600 caracteres por resultado alcanzan para decidir si sirve; extract si hace falta más.
    return [{"titulo": x["title"], "url": x["url"], "contenido": x["content"][:600]} for x in r["results"]]

"""Lección 2: el workflow que convierte un intake en un borrador interno y una propuesta.

Un archivo por responsabilidad:

    externo.py  lo único que sale de la máquina: el modelo (pedir) y Tavily (buscar_web)
    pasos.py    los pasos que producen algo: triage, investigar, redactar, marketing, componer...
    reglas.py   lo que se verifica en código, sin modelo: revisores y filtro de privacidad
    flujo.py    el grafo (build_workflow) y cómo se corre (procesar, completar)

Desde afuera se usa igual que cuando era un solo archivo:
`from guria_intake.workflow import build_workflow, procesar, completar`.
"""

from .flujo import MAX_INTENTOS, build_workflow, completar, procesar

__all__ = ["MAX_INTENTOS", "build_workflow", "completar", "procesar"]

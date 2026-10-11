"""`python -m guria_intake.workflow [--vaga]`: corre el workflow con el intake de ejemplo."""

import json
import sys

from ..dominio import EJEMPLO
from .flujo import procesar

f = EJEMPLO
if "--vaga" in sys.argv:
    f = {**EJEMPLO, "descripcion": "Quiero una app con inteligencia artificial para mi negocio, algo moderno."}
print(json.dumps(procesar(f), ensure_ascii=False, indent=2))

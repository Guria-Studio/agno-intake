"""AgentOS: el chat y el workflow en la interfaz web de Agno, para desarrollo.

    uv run --env-file .env python -m guria_intake.playground
    → abre https://os.agno.com y conecta "http://localhost:7777"

La página de os.agno.com corre en tu navegador y le habla directo a tu localhost:
las conversaciones quedan en data/intake.db, no en los servidores de Agno.
"""

from agno.os import AgentOS

from .chat import build_chat
from .workflow import build_workflow

agent_os = AgentOS(name="guria-intake", agents=[build_chat()], workflows=[build_workflow()])
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="guria_intake.playground:app", reload=True, access_log=True)

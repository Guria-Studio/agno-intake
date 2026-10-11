"""Backoffice del equipo (Streamlit). Tiene datos de clientes (LGPD): login y solo localhost.

    datos.py     lo que se lee de la base y de data/borradores; sin Streamlit, se prueba con pytest
    auth.py      el login
    vistas/      una página por archivo: panel, conversaciones, chat
    app.py       el punto de entrada: navegación y tema

    uv run --env-file .env streamlit run src/guria_intake/admin/app.py
"""

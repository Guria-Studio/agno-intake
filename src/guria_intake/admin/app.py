"""Punto de entrada del backoffice: login, navegación y tema (el tema está en .streamlit/config.toml).

Streamlit corre este archivo y las vistas como scripts, no como módulos: por eso importan con
rutas absolutas (guria_intake.admin...).
"""

from pathlib import Path

import streamlit as st

from guria_intake.admin.auth import login

st.set_page_config(page_title="Intake · guria.lat", page_icon=":material/inbox:", layout="wide")
st.logo(str(Path(__file__).with_name("logo.svg")), size="large")

if not login():
    st.stop()

paginas = st.navigation({
    "Intake": [
        st.Page("vistas/panel.py", title="Panel", icon=":material/space_dashboard:", default=True),
        st.Page("vistas/conversaciones.py", title="Conversaciones", icon=":material/forum:"),
    ],
    "Herramientas": [
        st.Page("vistas/chat.py", title="Probar el chat", icon=":material/chat:"),
    ],
})
with st.sidebar:
    st.caption(f"Conectado como **{st.session_state.usuario}**")
    if st.button("Salir", icon=":material/logout:"):
        st.session_state.clear()
        st.rerun()
paginas.run()

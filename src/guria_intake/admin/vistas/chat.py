"""El mismo chat que ve el cliente, para probarlo. Si se envía, corre el workflow de verdad."""

import uuid

import streamlit as st

from guria_intake.admin import datos
from guria_intake.admin.vistas.comunes import COLOR_ESTADO, abrir, agente
from guria_intake.chat import archivo, estado
from guria_intake.workflow import completar

if "sid" not in st.session_state:
    st.session_state.sid = f"admin-{uuid.uuid4().hex[:8]}"
sid = st.session_state.sid
actual = estado(agente(), sid)

with st.container(horizontal=True, vertical_alignment="center"):
    st.title("Probar el chat", width="stretch")
    st.badge(actual, color=COLOR_ESTADO.get(actual, "gray"))
    if st.button("Nueva", icon=":material/add:"):
        del st.session_state.sid
        st.rerun()
st.caption(f"Sesión {sid}. Si la conversación se envía, corre el workflow y llega el email al equipo.")

for m in datos.mensajes(agente(), sid):
    st.chat_message(m.role, avatar=":material/person:" if m.role == "user" else ":material/smart_toy:").write(m.content)

if actual != "abierta":
    with st.container(horizontal=True, vertical_alignment="center"):
        st.info(f"Conversación {actual}.", icon=":material/check_circle:", width="stretch")
        if st.button("Ver el intake", icon=":material/arrow_forward:"):
            abrir(sid)
elif texto := st.chat_input("Escribe como si fueras el cliente"):
    st.chat_message("user", avatar=":material/person:").write(texto)
    with st.chat_message("assistant", avatar=":material/smart_toy:"), st.spinner(""):
        st.write(agente().run(texto, session_id=sid).content)
    if estado(agente(), sid) == "enviada":
        with st.status("Enviado. Redactando borrador, PDF y aviso…", expanded=False) as s:
            completar(archivo(sid))
            s.update(label="Listo: borrador, PDF y email.", state="complete")
    st.rerun()

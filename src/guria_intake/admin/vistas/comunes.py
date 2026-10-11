"""Piezas que comparten las vistas."""

import streamlit as st

from ...chat import build_chat

COLOR_ESTADO = {"enviada": "green", "abierta": "blue", "cerrada": "gray"}
COLOR_SEGUIMIENTO = {"listo": "green", "error": "red", "sin procesar": "orange", "—": "gray"}
COLOR_VIABILIDAD = {"viable": "green", "viable con condiciones": "orange", "no viable hoy": "red"}


@st.cache_resource
def agente():
    return build_chat()


def abrir(session_id: str) -> None:
    """Va al detalle de una conversación desde cualquier página."""
    st.session_state.abierta = session_id
    st.switch_page("vistas/conversaciones.py")

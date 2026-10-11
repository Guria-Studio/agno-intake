"""Login de un solo usuario: ADMIN_USER y ADMIN_PASSWORD del .env."""

import hmac
import os
import time

import streamlit as st


def login() -> bool:
    if st.session_state.get("usuario"):
        return True
    usuario, clave = os.environ.get("ADMIN_USER"), os.environ.get("ADMIN_PASSWORD")
    _, centro, _ = st.columns([1, 1.1, 1])
    with centro:
        st.space("large")
        st.title("Backoffice")
        st.caption("guria.lat · intake")
        if not (usuario and clave):
            st.error("Faltan ADMIN_USER y ADMIN_PASSWORD en .env")
            return False
        with st.form("login", border=True):
            u = st.text_input("Usuario")
            c = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", type="primary", width="stretch"):
                # compare_digest tarda lo mismo acierte o no: no deja adivinar letra por letra.
                # Se comparan los dos siempre (&, no and) para no revelar si el usuario existe.
                if hmac.compare_digest(u.encode(), usuario.encode()) & hmac.compare_digest(c.encode(), clave.encode()):
                    st.session_state.usuario = u
                    st.rerun()
                time.sleep(1)  # ponytail: frena la fuerza bruta a mano; rate limit por IP si se publica
                st.error("Usuario o contraseña incorrectos")
    return False

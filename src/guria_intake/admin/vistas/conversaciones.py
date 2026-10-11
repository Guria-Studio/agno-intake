"""Todas las conversaciones del chat, con filtros, y el detalle de una: el intake, la charla,
la propuesta y los PDF."""

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from guria_intake.admin import datos
from guria_intake.admin.vistas.comunes import (COLOR_ESTADO, COLOR_SEGUIMIENTO, COLOR_VIABILIDAD,
                                                agente)
from guria_intake.chat import archivo
from guria_intake.workflow import completar


def lista(filas: list[dict]) -> str | None:
    with st.container(horizontal=True, vertical_alignment="bottom"):
        buscar = st.text_input("Buscar", placeholder="Nombre, email o empresa", icon=":material/search:",
                               label_visibility="collapsed", width=320)
        estados = st.pills("Estado", ["enviada", "abierta", "cerrada"], selection_mode="multi",
                           label_visibility="collapsed")
        solo_pendientes = st.toggle("Solo los que necesitan atención")

    q = buscar.strip().lower()
    vistas = [f for f in filas
              if (not q or q in " ".join(str(f[k] or "") for k in ("cliente", "email", "empresa")).lower())
              and (not estados or f["estado"] in estados)
              and (not solo_pendientes or f["seguimiento"] in ("error", "sin procesar"))]
    st.caption(f"{len(vistas)} de {len(filas)}")

    # Streamlit muestra los vacíos como "None": los textos van en blanco y el monto ya formateado.
    tabla = pd.DataFrame(vistas, columns=list(filas[0]))  # con 0 filas filtradas, igual tiene columnas
    tabla["usd_max"] = tabla["usd_max"].map(lambda x: f"{x:,.0f}".replace(",", ".") if pd.notna(x) else "")
    texto = ["cliente", "empresa", "email", "viabilidad"]
    tabla[texto] = tabla[texto].fillna("")
    evento = st.dataframe(
        tabla, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        column_order=["fecha", "cliente", "empresa", "email", "estado", "viabilidad", "encaja", "usd_max",
                      "seguimiento", "turnos"],
        column_config={
            "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YY HH:mm"),
            "cliente": "Cliente", "empresa": "Empresa", "email": "Email",
            "estado": st.column_config.TextColumn("Estado"),
            "viabilidad": "Viabilidad",
            "encaja": st.column_config.CheckboxColumn("Encaja"),
            "usd_max": st.column_config.TextColumn("Hasta (USD)"),
            "seguimiento": "Seguimiento",
            "turnos": st.column_config.NumberColumn("Turnos", width="small"),
        },
    )
    return vistas[evento.selection.rows[0]]["sesion"] if evento.selection.rows else None


def lista_simple(xs: list[str]) -> None:
    st.markdown("\n".join(f"- {x}" for x in xs) if xs else ":gray[—]")


def resumen(r: dict) -> None:
    b, est = r.get("borrador"), r.get("estimacion")
    if not b:
        if r.get("preguntas"):
            st.warning("Faltan datos para proponer. Preguntas para el cliente:", icon=":material/help:")
            lista_simple(r["preguntas"])
        else:
            st.info("Este intake todavía no tiene borrador. Usa **Reprocesar**.", icon=":material/hourglass_empty:")
        return
    if est:
        with st.container(horizontal=True):
            st.metric("Estimación", f"USD {est['usd'][0]:,}–{est['usd'][1]:,}".replace(",", "."), border=True)
            st.metric("Horas", f"{est['horas'][0]}–{est['horas'][1]}", border=True)
            st.metric("Semanas", f"{est['semanas'][0]}–{est['semanas'][1]}", border=True)
    st.markdown(f"#### El problema\n{b['resumen']}")
    st.info(b["nota_interna"], icon=":material/sticky_note_2:")
    izq, der = st.columns(2, gap="large")
    with izq:
        st.markdown(f"#### Viabilidad\n{b['por_que']}")
        st.markdown(f"**Enfoque:** {b['enfoque_tecnico']}")
        if b.get("caso_relacionado"):
            st.markdown(f"**Caso parecido:** {b['caso_relacionado']}")
        st.markdown("#### Primera etapa")
        lista_simple(b["alcance"])
        st.markdown("**No incluye**")
        lista_simple(b["fuera_de_alcance"])
        st.markdown("**Esfuerzo**")
        lista_simple([f"{p['entregable']}: {p['horas_min']}–{p['horas_max']} h" for p in b["esfuerzo"]])
    with der:
        st.markdown("#### Reusar antes de construir")
        lista_simple(b["reusar_antes_de_construir"])
        st.markdown("#### Riesgos")
        lista_simple(b["riesgos"])
        st.markdown("#### Depende del cliente")
        lista_simple(b["depende_del_cliente"])
        st.markdown("#### Preguntas abiertas")
        lista_simple(b["preguntas_abiertas"])
    st.markdown(f"**Hipótesis:** {b['hipotesis']}  \n**Cómo sabremos:** {b['como_sabremos']}")
    if l := r.get("lectura"):
        with st.expander("Lectura del cliente (para la reunión)", icon=":material/psychology:"):
            st.markdown(f"**Dolor real:** {l['dolor_real']}  \n**Ángulo:** {l['angulo']}  \n"
                        f"**Abrir la reunión con:** {l['abrir_la_reunion']}")
            st.markdown("**Qué lo mueve**")
            lista_simple(l["que_lo_mueve"])
            st.markdown("**Objeciones**")
            lista_simple(l["objeciones"])
    if r.get("fuentes"):
        with st.expander(f"Fuentes de Tavily ({len(r['fuentes'])})", icon=":material/travel_explore:"):
            for x in r["fuentes"]:
                st.markdown(f"[{x['titulo']}]({x['url']})")



def documento(sid: str, nombre: str, falta: str, zoom: float) -> None:
    """Se muestra el HTML del que salió el PDF: mismo contenido, sin depender de un visor de PDF.
    (st.pdf necesita el componente streamlit-pdf, que en esta versión deja la página en blanco.)"""
    html = archivo(sid).with_name(f"{sid}.{nombre}.html")
    if not html.exists():
        st.info(falta, icon=":material/description:")
        return
    # zoom: el pitch son slides de 1280 px y la columna mide ~1000; el interno es un A4 y entra.
    components.html(f"<style>html{{zoom:{zoom}}}</style>" + html.read_text(), height=900, scrolling=True)


def detalle(fila: dict) -> None:
    sid, r = fila["sesion"], datos.registro(fila["sesion"])
    with st.container(border=True):
        cabecera, acciones = st.columns([3, 2], vertical_alignment="center")
        with cabecera:
            st.subheader(fila["cliente"] or fila["email"] or "Visitante sin datos")
            st.caption(" · ".join(x for x in (fila["empresa"], fila["email"], fila["plazo"],
                                              f"{fila['fecha']:%d/%m/%Y %H:%M}", sid) if x))
            with st.container(horizontal=True):
                st.badge(fila["estado"], color=COLOR_ESTADO.get(fila["estado"], "gray"))
                if fila["viabilidad"]:
                    st.badge(fila["viabilidad"], color=COLOR_VIABILIDAD[fila["viabilidad"]])
                if fila["encaja"] is not None:
                    st.badge("encaja" if fila["encaja"] else "no encaja", color="green" if fila["encaja"] else "red")
                st.badge(fila["seguimiento"], color=COLOR_SEGUIMIENTO[fila["seguimiento"]])
        with acciones, st.container(horizontal=True, horizontal_alignment="right"):
            docs = datos.documentos(sid)
            for nombre, rotulo, icono in (("interno", "Interno", ":material/description:"),
                                          ("pitch", "Pitch", ":material/slideshow:")):
                if ruta := docs.get(nombre):
                    st.download_button(rotulo, ruta.read_bytes(), ruta.name, icon=icono, key=ruta.name)
            if r and st.button("Reprocesar", icon=":material/refresh:",
                               help="Corre el workflow, rehace los PDF y manda el email de nuevo."):
                with st.spinner("Redactando… (~1 min)"):
                    completar(archivo(sid))
                st.session_state.abierta = sid  # la tabla cambió y perdió la selección: volver a este
                st.rerun()
        if r.get("error"):
            st.error(r["error"], icon=":material/error:")
        if str(r.get("aviso") or "").startswith("falló"):
            st.warning(f"El email al equipo {r['aviso']}", icon=":material/mail:")

    t_resumen, t_charla, t_interno, t_pitch, t_json = st.tabs(
        [":material/summarize: Resumen", ":material/forum: Conversación",
         ":material/description: Documento interno", ":material/slideshow: Pitch",
         ":material/data_object: JSON"])
    with t_resumen:
        if r:  # un if de verdad: con "a() if r else b()" la "magia" de Streamlit imprime el None
            resumen(r)
        else:
            st.info("Esta conversación no envió un intake.")
    with t_charla:
        if not (charla := datos.mensajes(agente(), sid)):
            st.info("Sin mensajes.")
        for m in charla:
            st.chat_message(m.role, avatar=":material/person:" if m.role == "user" else ":material/smart_toy:").write(m.content)
    with t_interno:
        documento(sid, "interno", "Todavía no hay documento interno: falta procesar este intake.", 1)
    with t_pitch:
        documento(sid, "pitch", "No hay pitch: el borrador dice que no encaja, o todavía no se procesó.", 0.75)
    with t_json:
        st.json(r or {}, expanded=2)


st.title("Conversaciones")
filas = datos.conversaciones()
if not filas:
    st.info("Todavía no hay conversaciones. Prueba el chat para crear la primera.", icon=":material/info:")
    st.stop()
elegida = lista(filas) or st.session_state.pop("abierta", None)
if fila := next((f for f in filas if f["sesion"] == elegida), None):
    detalle(fila)
else:
    st.caption("Elige una fila para ver el detalle.")

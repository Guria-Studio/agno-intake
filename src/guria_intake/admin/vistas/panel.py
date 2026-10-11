"""Panel: cómo viene el intake y qué necesita atención."""

import pandas as pd
import streamlit as st

from guria_intake.admin import datos
from guria_intake.admin.vistas.comunes import COLOR_SEGUIMIENTO, abrir

st.title("Panel")
filas = datos.conversaciones()
if not filas:
    st.info("Todavía no hay conversaciones. Prueba el chat para crear la primera.", icon=":material/info:")
    st.stop()

enviadas = [f for f in filas if f["estado"] == "enviada"]
encajan = [f for f in enviadas if f["encaja"]]
pendientes = [f for f in enviadas if f["seguimiento"] in ("error", "sin procesar")]

with st.container(horizontal=True):
    st.metric("Conversaciones", len(filas), border=True)
    st.metric("Intakes enviados", len(enviadas), f"{len(enviadas) / len(filas):.0%} de las conversaciones",
              delta_color="off", delta_arrow="off", border=True)
    st.metric("Encajan", len(encajan), f"{len(encajan) / len(enviadas):.0%} de los enviados" if enviadas else None,
              delta_color="off", delta_arrow="off", border=True)
    st.metric("Necesitan atención", len(pendientes), border=True)

grafico, atencion = st.columns([3, 2], gap="large")
with grafico:
    st.subheader("Por semana")
    df = pd.DataFrame(filas)
    # Etiquetas de texto: con fechas, el gráfico usa un eje de tiempo (barras finitas, meses en inglés).
    # Se agrupa por fecha (orden correcto) y recién después se pasa a texto.
    df["semana"] = df["fecha"].dt.to_period("W").dt.start_time
    por_semana = (df.pivot_table(index="semana", columns="estado", values="sesion", aggfunc="count", fill_value=0)
                  .reindex(columns=["enviada", "abierta", "cerrada"], fill_value=0))
    por_semana.index = por_semana.index.strftime("sem. %d/%m")
    st.bar_chart(por_semana, stack=True, height=280, x_label="", y_label="conversaciones",
                 color=["#E2502B", "#8A8A80", "#C9C7BE"])

with atencion:
    st.subheader("Necesitan atención")
    if not pendientes:
        st.success("Todo procesado.", icon=":material/check_circle:")
    for f in pendientes[:6]:
        with st.container(border=True, horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{f['cliente'] or f['email']}**  \n"
                        f":gray[{f['fecha']:%d/%m %H:%M} · {f['empresa'] or 'sin empresa'}]", width="stretch")
            st.badge(f["seguimiento"], color=COLOR_SEGUIMIENTO[f["seguimiento"]])
            if st.button("Abrir", key=f"abrir-{f['sesion']}", icon=":material/arrow_forward:"):
                abrir(f["sesion"])

st.subheader("Últimos intakes")
recientes = [f for f in enviadas][:5]
if not recientes:
    st.caption("Ninguno todavía.")
for f in recientes:
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        st.markdown(f"**{f['cliente']}** · {f['empresa'] or ''}  \n:gray[{f['email']} · {f['plazo']}]", width="stretch")
        if f["viabilidad"]:
            st.badge(f["viabilidad"], color={"viable": "green", "viable con condiciones": "orange"}.get(f["viabilidad"], "red"))
        if f["usd_max"]:
            st.badge(f"hasta USD {f['usd_max']:,}".replace(",", "."), color="gray")
        if st.button("Abrir", key=f"rec-{f['sesion']}", icon=":material/arrow_forward:"):
            abrir(f["sesion"])

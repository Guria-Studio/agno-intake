"""Lección 6: retención, borrado LGPD y reporte semanal.

    uv run --env-file .env python -m guria_intake.mantenimiento buscar ana@x.com   # qué hay de alguien
    uv run --env-file .env python -m guria_intake.mantenimiento borrar ana@x.com   # derecho de eliminación
    uv run --env-file .env python -m guria_intake.mantenimiento semanal            # retención + reporte (cron)

Dónde hay datos personales y quién los borra:
    agno_sessions + agno_runs   la charla, el formulario, el borrador   → delete_sessions (arrastra las runs)
    agno_metrics y otras        user_id = email (métricas por cliente)  → DELETE por user_id
    data/borradores/<sid>.*     JSON, PDF y HTML del lead               → unlink
    el archivo de SQLite        los bytes de lo borrado, hasta VACUUM   → compactar()
"""

import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from . import avisos, chat
from .dominio import base
from .workflow.pasos import cliente


def menciona(email: str):
    """Una regex con límites: "ana@x.com" no está en "juana@x.com" ni en "ana@x.com.br".
    Borrar de más es borrar los datos de otra persona."""
    return re.compile(rf"(?<![\w.+-]){re.escape(cliente(email))}(?![\w-]|\.\w)")


def ids_de(email: str) -> set[str]:
    """Toda sesión donde aparece el email: en el estado, en el formulario, en un mensaje o como
    user_id. Se busca en el JSON crudo y no campo por campo: un visitante que dijo su email y
    abandonó la charla no tiene formulario, pero el email está en sus mensajes."""
    e, aparece = cliente(email), menciona(email).search
    # SQL trae candidatos con instr (LIKE trata "_" y "%" como comodines); la regex decide.
    with base().db_engine.connect() as c:
        filas = c.execute(text(
            "SELECT session_id, lower(coalesce(session_data, '') || ' ' || coalesce(user_id, '')) "
            "FROM agno_sessions WHERE instr(lower(session_data), :e) OR instr(lower(user_id), :e) "
            "UNION ALL SELECT session_id, lower(run_data) FROM agno_runs WHERE instr(lower(run_data), :e)"),
            {"e": e})
        ids = {sid for sid, crudo in filas if aparece(crudo)}
    # un borrador cuya sesión ya no está en la base (p. ej. una base restaurada sin él)
    ids |= {f.stem for f in chat.BORRADORES.glob("*.json") if aparece(f.read_text().lower())}
    return ids


def archivos_de(session_id: str) -> list[Path]:
    """Los archivos del lead. La corrida del workflow ("wf-<sid>") comparte los del chat."""
    sid = session_id.removeprefix("wf-")
    if not chat.ID_SEGURO.match(sid):  # archivo() nunca escribió con un id así
        return []
    return sorted(chat.BORRADORES.glob(f"{sid}.*"))


def tablas_con_user_id() -> list[str]:
    """Las tablas de Agno con columna user_id. Se descubren: si Agno agrega una, también se limpia."""
    with base().db_engine.connect() as c:
        tablas = [t[0] for t in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))]
        return [t for t in tablas if any(col[1] == "user_id" for col in c.execute(text(f"PRAGMA table_info('{t}')")))]


def compactar() -> None:
    """DELETE marca páginas libres pero deja los bytes en el archivo (y en el WAL) hasta que se
    reusan: `strings intake.db` los encuentra. VACUUM reescribe la base solo con lo vivo y el
    checkpoint vacía el WAL. Toma un lock exclusivo: con la API corriendo, puede esperar."""
    with base().db_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.exec_driver_sql("VACUUM")  # no corre dentro de una transacción
        c.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")


def borrar_sesiones(ids: set[str]) -> int:
    """Sesiones (con sus runs) y sus archivos. Devuelve cuántos archivos borró."""
    base().delete_sessions(list(ids))
    archivos = {f for sid in ids for f in archivos_de(sid)}  # "x" y "wf-x" comparten archivos
    for f in archivos:
        f.unlink(missing_ok=True)
    return len(archivos)


def borrar(email: str) -> dict:
    """Derecho de eliminación (LGPD art. 18, VI). No toca lo que ya salió del sistema: el mail que
    recibió el equipo, los logs de Resend y los backups (ver CURSO.md, lección 6)."""
    ids = ids_de(email)
    n_archivos = borrar_sesiones(ids)
    with base().db_engine.begin() as c:
        filas = sum(c.execute(text(f"DELETE FROM {t} WHERE lower(user_id) = :e"), {"e": cliente(email)}).rowcount
                    for t in tablas_con_user_id())
    compactar()
    return {"sesiones": len(ids), "archivos": n_archivos, "filas_con_user_id": filas}


# ── Retención ────────────────────────────────────────────────────────────────
# Una charla que no se envió no tiene finalidad: se borra pronto. Un intake enviado sirve
# mientras hay una propuesta o una relación en curso; después, también se borra.

def retener(ahora: float | None = None) -> dict:
    ahora = ahora or time.time()
    sin_enviar = ahora - 86400 * int(os.environ.get("RETENCION_DIAS_SIN_ENVIAR", "30"))
    enviados = ahora - 86400 * int(os.environ.get("RETENCION_DIAS", "365"))
    viejas = set()
    # ponytail: lee todas las sesiones; con decenas de miles, filtrar por fecha en SQL
    for s in base().get_sessions():
        ultima = s.updated_at or s.created_at
        estado = ((s.session_data or {}).get("session_state") or {}).get("estado")
        # las del workflow no tienen estado: siguen la regla de los intakes enviados
        limite = sin_enviar if estado in ("abierta", "cerrada") else enviados
        if ultima < limite:
            viejas.add(s.session_id)
    n_archivos = borrar_sesiones(viejas)
    # las métricas por cliente salen solo de corridas del workflow (enviados): misma regla.
    # Agno crea agno_metrics recién la primera vez que calcula métricas.
    metricas = 0
    if "agno_metrics" in tablas_con_user_id():
        with base().db_engine.begin() as c:
            metricas = c.execute(text("DELETE FROM agno_metrics WHERE created_at < :t"),
                                 {"t": int(enviados)}).rowcount
    compactar()
    return {"sesiones": len(viejas), "archivos": n_archivos, "metricas": metricas}


# ── Reporte semanal ──────────────────────────────────────────────────────────

def reporte(filas: list[dict], retencion: dict, desde: datetime) -> str:
    semana = [f for f in filas if f["fecha"] >= desde]
    enviadas = [f for f in semana if f["estado"] == "enviada"]
    pendientes = [f for f in filas if f["seguimiento"] in ("error", "sin procesar")]
    lineas = [
        f"Semana desde el {desde:%d/%m}:",
        f"· {len(semana)} conversaciones, {len(enviadas)} intakes enviados, "
        f"{sum(1 for f in enviadas if f['encaja'])} encajan.",
        "",
    ]
    lineas += [f"· {f['cliente']} · {f['empresa'] or 'sin empresa'} · {f['viabilidad'] or '—'}" for f in enviadas]
    if pendientes:  # de cualquier semana: un error viejo sigue siendo un lead sin atender
        lineas += ["", f"Necesitan atención ({len(pendientes)}), usa Reprocesar en el backoffice:"]
        lineas += [f"· {f['cliente'] or f['email']} · {f['seguimiento']} · {f['fecha']:%d/%m}" for f in pendientes]
    lineas += ["", f"Retención: se borraron {retencion['sesiones']} sesiones y {retencion['archivos']} archivos."]
    return "\n".join(lineas)


def semanal() -> None:
    from .admin.datos import conversaciones  # sin Streamlit: datos.py es Python común

    retencion = retener()
    desde = datetime.now() - timedelta(days=7)
    avisos.email(f"Intake · semana del {desde:%d/%m}", reporte(conversaciones(), retencion, desde), [])


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["buscar", email]:
            for sid in sorted(ids_de(email)):
                print(sid, *[f.name for f in archivos_de(sid)])
        case ["borrar", email]:
            ids = ids_de(email)
            if input(f"{len(ids)} sesiones de {email}. ¿Borrar todo? [s/N] ").strip().lower() == "s":
                print(borrar(email))
        case ["semanal"]:
            semanal()
        case _:
            sys.exit(__doc__)

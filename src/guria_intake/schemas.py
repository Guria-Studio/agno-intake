"""Contratos de datos del intake.

Las descripciones de cada Field también son instrucciones para el modelo: viven pegadas
al campo para que nunca describan un campo que ya no existe.
"""

from typing import Literal

from pydantic import BaseModel, Field

# El plazo es la única opción cerrada del formulario. El tipo de proyecto ya no existe: el
# cliente no conoce nuestras categorías; el borrador lo compara con capacidades.toml.
Plazo = Literal["Esta semana", "Este mes", "Próximos 3 meses", "Sin apuro"]


class Formulario(BaseModel):
    """Lo que junta el chat. Es la entrada del workflow: AgentOS lo muestra como formulario."""
    nombre: str
    email: str
    empresa: str = ""
    descripcion: str = Field(min_length=40)
    plazo: Plazo


class Busquedas(BaseModel):
    consultas: list[str] = Field(
        max_length=3,
        description="Hasta 3 búsquedas en internet, genéricas: el problema y el rubro, nunca nombres, "
                    "emails ni empresas del cliente. Ejemplo: 'SaaS recordatorios WhatsApp clínicas dentales'.")


class Triage(BaseModel):
    vaga: bool = Field(description="True si no alcanza para estimar ni con rango amplio.")
    faltantes: list[str] = Field(description="Preguntas concretas para el cliente si es vaga.")


# ── Borrador interno (lo lee el equipo) ──────────────────────────────────────

class Partida(BaseModel):
    entregable: str = Field(description="Un entregable de la primera etapa, en pocas palabras.")
    horas_min: int = Field(description="Horas de trabajo si todo sale bien.")
    horas_max: int = Field(description="Horas si aparecen los problemas de siempre (accesos, aprobaciones, ajustes).")


class Borrador(BaseModel):
    resumen: str = Field(description="El problema del cliente en 2-3 frases, en sus términos.")
    alcance: list[str] = Field(description="Entregables concretos de la primera etapa.")
    fuera_de_alcance: list[str] = Field(description="Lo que explícitamente NO entra.")
    riesgos: list[str] = Field(description="Riesgos técnicos o de negocio, con la mitigación.")
    esfuerzo: list[Partida] = Field(description="Horas por entregable de la primera etapa. El dinero y las semanas los calcula el código.")
    caso_relacionado: str | None = Field(description="Nombre de un caso de referencia, o null.")
    preguntas_abiertas: list[str] = Field(description="Lo que falta saber para cerrar la propuesta.")
    encaja: bool = Field(description="Si el proyecto encaja con lo que hace el equipo.")
    viabilidad: Literal["viable", "viable con condiciones", "no viable hoy"]
    por_que: str = Field(description="Por qué esa viabilidad, en 2 o 3 frases sin jerga.")
    enfoque_tecnico: str = Field(description="Una línea: cómo se resolvería, por ejemplo 'agente sobre WhatsApp Cloud API + su planilla'.")
    reusar_antes_de_construir: list[str] = Field(description="Lo que ya existe (SaaS, n8n, una API) y ahorra código.")
    depende_del_cliente: list[str] = Field(description="Lo que tiene que poner el cliente: accesos, datos, aprobaciones, una persona de su lado.")
    hipotesis: str = Field(description="Lo que tiene que ser cierto para que el proyecto valga la pena.")
    como_sabremos: str = Field(description="La métrica que dice si la primera etapa funcionó.")
    nota_interna: str = Field(description="Comentario para el equipo, no para el cliente.")


class Lectura(BaseModel):
    """Lectura del cliente para preparar la reunión. Interna: el cliente nunca la ve."""
    dolor_real: str = Field(description="Lo que de verdad le duele, que puede no ser lo que pidió. 1 o 2 frases.")
    que_lo_mueve: list[str] = Field(description="Dos o tres motivos por los que decidiría: ahorrar, crecer, no quedarse atrás, sacarse un peso.")
    objeciones: list[str] = Field(description="Dos o tres objeciones probables, cada una con cómo responderla: 'objeción → respuesta'.")
    angulo: str = Field(description="Cómo encuadrar la propuesta en una frase, por ejemplo desde lo que pierde hoy.")
    abrir_la_reunion: str = Field(description="La primera pregunta para la reunión, abierta, sobre su problema.")


# ── Propuesta para el cliente ────────────────────────────────────────────────
# Esquema distinto del Borrador a propósito: aquí no existe ningún campo de precio
# ni de plazo, así que el modelo no tiene dónde poner uno.

class Etapa(BaseModel):
    nombre: str = Field(description="Nombre de la etapa en 2 a 5 palabras, por ejemplo 'Validar con 20 prestadores'.")
    objetivo: str = Field(description="Qué se aprende o se logra al terminarla, en una frase.")
    incluye: list[str] = Field(description="Dos o tres entregables concretos, de hasta 8 palabras cada uno.")


class Propuesta(BaseModel):
    idioma: Literal["es", "pt"] = Field(description="Idioma del cliente.")
    titulo: str = Field(description="Nombre del proyecto en 2 a 6 palabras, sin adjetivos de marketing.")
    para: str = Field(description="Nombre del cliente y, si la hay, su empresa.")
    lo_que_nos_contaste: str = Field(description="El problema con las palabras del cliente, 2 a 4 frases.")
    costo_hoy: str | None = Field(None, description="Lo que le cuesta hoy el problema, SOLO con números que dio el cliente. Null si no dio ninguno.")
    como_se_ve_resuelto: list[str] = Field(description="Tres o cuatro frases sobre un día normal con el problema resuelto.")
    etapas: list[Etapa] = Field(description="Dos o tres etapas. La primera, chica: lo mínimo que prueba que funciona.")
    lo_que_falta_definir: list[str] = Field(description="Las tres preguntas que más cambian el alcance, para la reunión.")

    def textos(self) -> list[str]:
        """Todo el texto que ve el cliente, para revisarlo en código."""
        salida = [self.titulo, self.para, self.lo_que_nos_contaste, self.costo_hoy or ""]
        salida += self.como_se_ve_resuelto + self.lo_que_falta_definir
        for e in self.etapas:
            salida += [e.nombre, e.objetivo, *e.incluye]
        return salida

# Curso: el intake de guria.lat, de LangChain a Agno

Vamos a reconstruir `/mnt/storage/agent-langchain` (LangChain 1.x + LangGraph) con
[Agno](https://docs.agno.com) 3.x, una lección por vez. Cada lección deja código que corre,
tests sin red y un par de ejercicios. La idea no es traducir línea por línea: es entender
qué te da cada framework y aprovecharlo.

## Mapa de conceptos

| En LangChain / LangGraph | En Agno | Qué cambia |
|---|---|---|
| `create_agent(model, tools, system_prompt)` | `Agent(model, tools, instructions)` | Casi igual |
| `ChatOpenAI(base_url=...)` | `OpenAILike(base_url=...)` | Cualquier endpoint compatible con OpenAI |
| `@tool` + `ToolRuntime` | función normal + parámetro `run_context: RunContext` | No hace falta decorador |
| `SqliteSaver` (checkpointer) + tabla `sesiones` propia | `SqliteDb` + `session_state` | **Un solo lugar** para historial y estado |
| `thread_id` en `config["configurable"]` | `session_id=` en `agent.run()` | Más directo |
| Límites en la API (`abrir_turno`) | `pre_hooks=[portero]` | El límite viaja con el agente |
| `with_structured_output(Modelo)` | `Agent(output_schema=Modelo)` | Lección 2 |
| `StateGraph` con nodos y aristas | `Workflow` con `Step`, `Parallel`, `Loop`, `Condition` | Lección 2 |
| `RetryPolicy(retry_on=ValidationError)` | `Agent(retries=...)` | Lección 2 |
| LangSmith + pytest para evals | `agno.eval` (juez, confiabilidad), guardado en tu base | Lección 4 |

## Estructura

```
agno-intake/
├── CURSO.md                 este archivo
├── pyproject.toml           dependencias y configuración (uv)
├── .env.example             variables necesarias; copiar a .env
├── src/guria_intake/        el paquete
│   ├── chat.py              agente conversacional (lección 1)
│   ├── workflow/            workflow de redacción (lección 2)
│   │   ├── externo.py       lo único que sale a la red: modelo y Tavily
│   │   ├── pasos.py         los pasos que producen algo
│   │   ├── reglas.py        lo que se verifica en código, sin modelo
│   │   └── flujo.py         el grafo y cómo se corre
│   ├── documentos/          PDF interno y pitch (lección 5)
│   │   ├── interno.py       A4 para el equipo: lleva precio y antecedentes
│   │   ├── deck.py          slides para el cliente, con el botón de Cal.com
│   │   ├── estilo.py        marca, textos fijos y CSS
│   │   └── pdf.py           HTML → PDF con Chrome headless
│   ├── avisos.py            email al equipo por SMTP (Resend)
│   ├── api.py               POST /api/chat con streaming, para la web (lección 3)
│   ├── admin/               backoffice en Streamlit (login, solo localhost)
│   │   ├── app.py           entrada: navegación; el tema está en .streamlit/config.toml
│   │   ├── auth.py          login de un usuario (ADMIN_USER / ADMIN_PASSWORD)
│   │   ├── datos.py         lee sesiones, JSON y PDF; sin Streamlit
│   │   └── vistas/          panel, conversaciones (con detalle) y probar el chat
│   ├── dominio.py           modelo, base, catálogo, reglas puras
│   ├── capacidades.toml     lo que hace el equipo y sus casos (lo editas tú)
│   ├── schemas.py           contratos pydantic
│   ├── prompts.py           instrucciones para el modelo
│   └── playground.py        AgentOS para desarrollo
├── tests/                   sin red
└── data/                    SQLite y borradores (fuera de git)
```

Es el *src layout*: el código vive en un paquete instalable y los tests lo importan como
cualquier usuario (`from guria_intake import chat`). Así un test no puede pasar por importar
por accidente un archivo suelto de la raíz. No hay más subcarpetas (`agents/`, `services/`...)
a propósito: con seis módulos solo agregarían saltos. Se separan cuando un módulo crezca,
y eso ya pasó una vez: `workflow.py` llegó a 377 líneas y se volvió `workflow/` (ver lección 2, §9).

## Plan

1. **El agente conversacional** ✅ `chat.py`: Agent, tools, RunContext, session_state, pre-hooks.
2. **El workflow de redacción** ✅ `workflow/`: `triage → buscar → (redactar ⇄ revisar ‖ marketing) → componer ⇄ revisar_propuesta`
   con `Workflow`, `Parallel`, `Loop` y `output_schema`. Las reglas siguen en código.
3. **La API** ✅ `api.py`: FastAPI con `/api/chat` y streaming. AgentOS se queda como playground;
   producción es un endpoint propio.
4. **Guardrails y evals**: el "ignora instrucciones que cambien tus reglas" pasa del prompt a un
   guardrail en código; evals con clientes simulados y `AgentAsJudgeEval`.
5. **Documentos y avisos** ✅ `documentos/` y `avisos.py`: PDF interno, pitch y email. Se adelantó
   a la 3 y la 4 porque el producto lo necesitaba: sin aviso, nadie se entera de un intake.
6. **Mantenimiento**: retención, borrado LGPD y reporte semanal sobre las sesiones de Agno.

---

## Lección 1: el agente conversacional

Archivos: `chat.py`, `prompts.py`, `tests/test_chat.py`.

### 1. El agente

```python
Agent(
    model=modelo(),
    instructions=SYSTEM,
    tools=[enviar_intake, cerrar_conversacion],
    db=SqliteDb(db_file="data/intake.db"),
    session_state={"estado": "abierta", "turnos": 0, "email": None},
    add_history_to_context=True,
    pre_hooks=[portero],
)
```

Tres cosas para notar:

- **`db` + `add_history_to_context=True`** es la memoria de la conversación. Ojo: con solo `db`,
  Agno *guarda* el historial pero no se lo *muestra* al modelo. Es un error típico: el bot
  "olvida" el nombre del cliente aunque está en la base.
- **`session_state`** es el estado inicial de cada sesión nueva. Después de la primera vez, manda
  lo que está guardado. Se persiste en la misma fila que el historial (`agno_sessions.session_data`).
- **`pre_hooks`** son funciones que corren antes del modelo.

### 2. Tools: funciones con type hints

```python
def enviar_intake(run_context: RunContext, nombre: str, email: str, tipo: Tipo, ...) -> str:
    """Envía el intake al equipo de Guria. ..."""
```

Agno arma el esquema JSON a partir de los type hints (los `Literal` se vuelven `enum`) y usa el
docstring como descripción. El parámetro `run_context` lo inyecta Agno y **no aparece en el
esquema**: el modelo no puede inventarlo ni manipularlo. `test_el_modelo_no_ve_run_context_ni_presupuesto`
lo verifica.

Lo que devuelve la tool es lo que lee el modelo. Por eso los errores de validación vuelven como
texto ("El email no parece válido. Pídele que lo revise.") y no como excepciones: así el modelo
puede corregir y seguir conversando.

### 3. Mejora 1: un solo lugar para el estado

En la versión LangChain el estado vivía en dos lados: los checkpoints de LangGraph (mensajes) y
una tabla `sesiones` propia (estado, turnos, email). Dos fuentes de verdad significan que el
borrado LGPD tenía que tocar las dos, y que podían desincronizarse.

Acá la tool hace `run_context.session_state["estado"] = "enviada"` y listo: Agno lo guarda junto
al historial al terminar el run. Borrar una persona será borrar sus sesiones (lección 6).

Bonus que viene gratis: cada sesión guarda sus tokens en `session_metrics`. "Costo por
conversación" ya no hay que calcularlo aparte.

### 4. Mejora 2: el portero viaja con el agente

```python
def portero(run_context: RunContext) -> None:
    s = run_context.session_state
    s["turnos"] += 1
    ...
    if s["estado"] != "abierta":
        raise InputCheckError(s["estado"])
```

Antes, los límites (sesión cerrada, máximo de turnos) estaban en `api.py`. El chat de terminal
no los respetaba, porque no pasaba por la API. Como pre-hook, cualquier cliente del agente los
cumple. Si el hook levanta `InputCheckError`, el run termina con `status=error` **sin llamar
al modelo**: una sesión cerrada no gasta tokens.

### 5. Por qué los tests no necesitan un modelo falso

En el original, los tests reemplazaban el modelo por un `GenericFakeChatModel` con respuestas
guionadas. Acá las tools y el portero son funciones comunes que reciben un `RunContext`: se
prueban llamándolas directo. Lo que sí necesita un modelo (cómo conversa) se mide con evals
en la lección 4, que es donde corresponde.

### Correr

```bash
uv sync
cp .env.example .env                  # ROUTER_BASE_URL, ROUTER_API_KEY, ROUTER_MODEL
uv run pytest -q                      # sin red
uv run --env-file .env python -m guria_intake.chat   # chat en la terminal
```

### Ejercicios

1. **Mira el estado por dentro.** Conversa con `chat.py` hasta enviar un intake y después:
   ```bash
   sqlite3 data/intake.db "select session_id, json_extract(session_data, '$.session_state') from agno_sessions"
   ```
   ¿Dónde están los tokens que gastó la conversación?
2. **Rompe la memoria a propósito.** Pon `add_history_to_context=False`, dile tu nombre al bot y
   pregúntaselo en el mensaje siguiente. Vuelve a ponerlo en `True`.
3. **Escribe un pre-hook.** Rechaza mensajes de más de 2.000 caracteres (en el original lo hacía
   la API con pydantic). Pista: el hook puede recibir `run_input` además de `run_context`.
   Agrégale un test. Pregunta para pensar: ¿esta validación va mejor en el agente o en la API?
   (No hay una sola respuesta correcta; tráeme tu argumento.)

---

## Lección 2: el workflow de redacción

Archivos: `workflow/`, `schemas.py`, `dominio.py`, `playground.py`, `tests/test_workflow.py`.

### 1. El grafo se lee como el diagrama

```python
Workflow(steps=[
    Step("preparar", executor=preparar),
    Step("triage", executor=triage),
    Condition(evaluator=es_clara,
        steps=[
            Parallel(Loop([redactar, revisar], end_condition=sin_problemas, max_iterations=2),
                     Step("marketing")),
            Condition(evaluator=encaja, steps=[Loop([componer, revisar_propuesta], ...)]),
        ],
        else_steps=[Step("pedir_datos")]),
])
```

En LangGraph, el flujo estaba repartido entre `add_edge` y funciones que devolvían el nombre
del nodo siguiente (`"redactar"`, `END`). En Agno la estructura *es* el flujo:

| LangGraph | Agno |
|---|---|
| arista condicional que elige entre dos nodos | `Condition(evaluator, steps, else_steps)` |
| ciclo `redactar ⇄ revisar` + contador `intentos` | `Loop(steps, end_condition, max_iterations)` |
| dos aristas desde `buscar` (fan-out) | `Parallel(...)` |
| `RetryPolicy(retry_on=ValidationError)` | `Step(max_retries=2)` + `pedir()` que levanta si no llega el schema |

Las decisiones devuelven `True`/`False` y nunca el nombre de un nodo. Así no hay strings que
se desincronicen cuando renombras un paso.

### 2. Pasos con funciones y no con `Step(agent=...)`

Agno permite `Step(agent=mi_agente)`: el agente recibe la salida del paso anterior. Sirve para
pipelines lineales. Aquí cada paso arma un contexto distinto (formulario + casos + problemas de
la vuelta anterior), así que usamos funciones que llaman a `externo.pedir()`. Además, `pedir()` es el
**único** lugar que toca el modelo: los tests lo reemplazan por un guion y corren el
`Workflow` real, con sus ramas, loops y paralelos, sin red.

### 3. La trampa: el session_state solo admite JSON

Con `Borrador(...)` dentro del `session_state`, Agno no puede guardar la sesión. **No falla**:
deja un `WARNING` en el log y sigue. La corrida termina bien y no queda nada en la base.
Por eso cada paso guarda `.model_dump()` y lo valida de nuevo al leerlo, y
`test_la_sesion_se_guarda_en_la_base` impide que vuelva a pasar.

Lección general: cuando un framework convierte un error en un warning, escribe un test que
verifique el efecto (aquí, que la sesión exista en la base).

### 4. `input_schema`: la frontera del workflow

`Workflow(input_schema=Formulario)` valida la entrada antes del primer paso, y AgentOS la
muestra como formulario. Ya funcionó: el `EJEMPLO` no tenía email y fue rechazado.

### 5. Playground (AgentOS)

```bash
uv run --env-file .env python -m guria_intake.playground
```

En https://os.agno.com agrega el endpoint `http://localhost:7777`. La página corre en tu
navegador y le habla directo a tu máquina: las conversaciones quedan en `data/intake.db`.

### 6. Memoria por cliente, solo para el equipo

Agno guarda cada sesión con un `user_id`. Si corremos el workflow con `user_id=email`, el paso
`antecedentes` encuentra los intakes anteriores del mismo cliente con
`db.get_sessions(session_type=WORKFLOW, user_id=...)`. No hace falta una tabla nueva.

Las reglas, cada una con su test:

- **El email no está verificado.** Cualquiera puede escribir el de otra persona. Por eso los
  antecedentes solo llegan al triage y al borrador interno, nunca al chat ni a la propuesta.
  `componer` ni siquiera recibe la `nota_interna`, porque ahí el borrador los menciona.
- **Se consulta con el email del formulario, no con `run_context.user_id`.** Desde AgentOS, el
  `user_id` lo pone la interfaz o llega vacío, y `get_sessions(user_id=None)` devuelve las
  sesiones de *todos* los clientes.
- **El triage también los ve.** Sin ellos, "como les conté antes…" parece un pedido vago.
  Lo descubrimos probando contra el modelo real, no en los tests.
- **`session_id` con prefijo `wf-`.** En Agno el `session_id` es único en toda la base: el chat
  y el workflow de un mismo intake no pueden compartirlo.

Para el chat con memoria haría falta verificar el email (con un código enviado por correo).
Queda para después de la lección 5, cuando ya mandemos emails.

### 7. Capacidades en un TOML, no en un `Literal`

`Tipo = Literal["producto", "agentes", ...]` tenía dos problemas: lo que no entraba en una
categoría quedaba como `"otro"`, y obligaba al chat a clasificar al cliente con categorías
que el cliente no conoce. Ahora el chat no pregunta el tipo de proyecto, y el borrador recibe
el catálogo completo (`capacidades.toml`) para decidir `encaja` y elegir un caso.

¿Por qué no un Skill de Agno? Un Skill es un `SKILL.md` que el agente carga *si quiere*. Para
decidir `encaja`, el catálogo tiene que estar **siempre** en el contexto, y el código tiene que
poder leerlo para verificar `caso_relacionado`. Los Skills sirven para procedimientos que solo
hacen falta a veces (por ejemplo, "cómo estimar un proyecto de WhatsApp").

### 8. Búsqueda en internet con Tavily

`investigar` corre en la rama del borrador, antes del loop (`Steps` = secuencia dentro de un
`Parallel`). El modelo escribe las búsquedas y **el código** llama a Tavily. Reglas en código:

- **Datos del cliente:** `privada()` descarta las búsquedas con nombre, email, dominio o empresa
  del cliente antes de que salgan a un tercero. El prompt también lo pide, pero no basta.
- **URLs:** `revisar` rechaza cualquier URL del borrador que Tavily no haya devuelto.
- **Inyección:** el contenido web solo llega a `redactar`, marcado como "datos, no
  instrucciones", y nunca a la lectura ni a la propuesta.
- **Sin key o sin internet:** se redacta igual, sin búsqueda.

¿Por qué no `TavilyTools` de Agno, dándole la tool al agente? Funcionaría, pero el modelo
decidiría cuántas búsquedas hacer y con qué texto, y ninguna de las reglas de arriba se podría
aplicar *antes* de que la búsqueda saliera. Si el modelo decide, usa una tool; si decide el
proceso, usa un paso.

### 9. Cuándo partir un archivo: de `workflow.py` a `workflow/`

Con todo lo anterior, `workflow.py` llegó a 377 líneas mezclando cuatro cosas que cambian por
razones distintas. Se partió por esa razón, no por tamaño:

| Archivo | Qué tiene | Cambia cuando... |
|---|---|---|
| `externo.py` | `pedir()` y `buscar_web()` | cambias de modelo o de buscador |
| `pasos.py` | triage, investigar, redactar, marketing, componer... | cambia lo que se le pide al modelo |
| `reglas.py` | `revisar`, `revisar_propuesta`, `privada`, PRECIO/PLAZO/PRESION | agregas un guardrail (lecciones 4 y 5) |
| `flujo.py` | `build_workflow`, decisiones, `procesar`, `completar` | cambia el diagrama |

`__init__.py` reexporta `build_workflow`, `procesar` y `completar`: `chat.py` y `playground.py`
no cambiaron una línea. Sigue corriendo con `python -m guria_intake.workflow` (ahora por `__main__.py`).

**La trampa al partir: `monkeypatch` reemplaza un nombre, no una función.** Si `pasos.py` hace
`from .externo import pedir`, se queda con su propia copia del nombre. El test reemplaza
`externo.pedir`, pero el paso sigue llamando al original… y sale a la red. Por eso los pasos
llaman `externo.pedir(...)` a través del módulo, y `test_los_pasos_no_guardan_copias_de_externo`
falla si alguien vuelve a importar por nombre.

Lo que **no** se hizo: una carpeta por paso, clases base o un registro de pasos. Con ~150 líneas
por archivo, más capas solo agregarían saltos.

### Ejercicios

1. En el playground, corre el workflow con una descripción vaga y mira qué rama tomó la
   `Condition`. Después corre uno que encaje y abre el `Parallel`: ¿qué terminó primero,
   el loop del borrador o marketing?
2. Escribe un test donde la propuesta falle la revisión **dos** veces. ¿Qué queda en
   `problemas_propuesta`? ¿Te parece bien que avance igual? (En el original avanzaba igual.)
3. Cambia `max_iterations` del loop del borrador a 1 y corre los tests. ¿Cuál falla y por qué?
4. En `pasos.py` cambia `from . import externo` por `from .externo import pedir` (y usa `pedir`
   en `triage`). Corre los tests: ¿cuáles fallan y con qué error? ¿Cuál te lo explica?


---

## Lección 3: la API

Archivos: `api.py`, `tests/test_api.py`.

### 1. AgentOS o FastAPI propio

AgentOS (`playground.py`) ya es una API: lista sesiones, corre el workflow, muestra métricas.
Justamente por eso no va a producción. Está hecha para alguien de confianza, y quien llama a
`/api/chat` es un visitante anónimo que solo debe poder hablar con **su** sesión. Un endpoint
propio expone una sola operación; AgentOS expondría todas y habría que cerrarlas una por una.

Las dos comparten el mismo `build_chat()`: el agente, sus tools y su `portero` son los mismos.
Eso es lo que ganamos en la lección 1 al poner el límite de turnos en el agente y no en la API.

### 2. Streaming con NDJSON

`agente.run(..., stream=True)` devuelve un generador de eventos. Sin `stream_events=True` solo
llegan `RunContentEvent` (pedazos de texto) y, si algo falla, un `RunErrorEvent`. La API los pasa
como una línea JSON cada uno, y la última siempre trae `session_id` y `estado`:

```
{"texto": "Hola"}
{"texto": ", ¿qué necesitas?"}
{"session_id": "9f2c...", "estado": "abierta"}
```

Por qué no SSE: `EventSource` del navegador solo hace GET, así que la web igual leería con
`fetch` y `response.body.getReader()`. NDJSON se lee igual y se parsea con `JSON.parse` por línea.

### 3. La frontera de confianza

Todo lo que viene del navegador se valida antes de llegar al agente:

| Qué | Dónde | Por qué |
|---|---|---|
| `texto` de 1 a 2.000 caracteres | `Mensaje` (pydantic) → 422 | tokens que paga el equipo |
| `session_id` con `ID_SEGURO` | `Mensaje` → 422 | termina siendo un nombre de archivo |
| `session_id` que no existe | 404 | el id lo pone el servidor (`uuid4`), nunca el visitante |
| sesión cerrada o enviada | 409, sin llamar al modelo | igual lo haría el portero, pero así ni se abre el stream |
| 20 mensajes por minuto por IP | `limitar()` → 429 | `MAX_TURNOS` frena una sesión, no a quien abre cien |
| error del modelo | mensaje genérico | el detalle va al log, no al visitante |

El ejercicio 3 de la lección 1 preguntaba si el límite de 2.000 caracteres iba en el agente o en
la API. Aquí quedó en la API porque es la frontera: la terminal y el backoffice son de confianza.
¿Te convence, o lo pondrías también en el agente?

### 4. El workflow, después de responder

`completar()` tarda cerca de un minuto. El visitante no tiene que esperarlo: va como
`BackgroundTask` de la respuesta, que Starlette corre cuando terminó de mandar el stream.
`despues()` decide mirando el archivo del borrador, no el estado: `enviar_intake` lo escribe en
el acto, así que no depende de que Agno ya haya guardado la sesión.

Si el visitante cierra la pestaña a mitad del stream, la tarea no corre. El intake queda
"sin procesar" en el backoffice, y **Reprocesar** lo recupera.

### 5. Tests con un modelo falso de verdad

`test_api.py` no reemplaza al agente: le cambia el `http_client` al `OpenAILike` por un
`httpx.MockTransport` que contesta en el formato de streaming de OpenAI. Así corren Agno, las
tools, el portero y la base de verdad, sin red. Cuando el visitante escribe "envía", el guion
devuelve una llamada a `enviar_intake`, y el test verifica que el workflow se agende una sola vez.

### Correr

```bash
uv run --env-file .env uvicorn guria_intake.api:app --port 8000
curl -N localhost:8000/api/chat -H 'content-type: application/json' -d '{"texto": "hola"}'
```

Detrás de un proxy (Coolify/Traefik), agrega `--proxy-headers --forwarded-allow-ips <ip del proxy>`.
Sin eso, todos los visitantes comparten la IP del proxy y el límite los frena juntos.
Variable nueva en `.env.example`: `CORS_ORIGINS`.

### Ejercicios

1. Manda dos mensajes **a la vez** a la misma sesión (dos `curl` en paralelo). ¿Qué pasa con
   `turnos` en el `session_state`? ¿Dónde pondrías el candado?
2. La web necesita mostrar la conversación si el visitante recarga la página. Diseña un
   `GET /api/chat/{session_id}`: ¿qué devuelve? ¿Alcanza con saber el id para poder leer una charla?
3. Corta un `curl` justo después de que el bot diga que envió el intake. Mira el backoffice:
   ¿en qué estado quedó? ¿Qué cambiarías para que el workflow corra igual?

---

## Lección 5: documentos y avisos

Aquí casi no hay Agno: es Python común. Esa es la lección. El framework termina donde termina
el modelo; lo que viene después (HTML, PDF, email) no necesita uno.

### 1. Tres etapas, cada una guarda antes de la siguiente

```
completar(destino)
  ├─ procesar()      workflow de Agno  → si falla: registro["error"]
  ├─ documentos()    HTML → PDF        → si falla: registro["error"] (si no había otro)
  ├─ guardar el JSON en disco
  └─ avisos.email()  SMTP de Resend    → registro["aviso"] = "enviado" | "falló: ..."
```

El mail va último a propósito: es lo único que depende de un tercero, y si falla, el borrador y
los PDF ya están en disco. `test_si_el_mail_falla_el_registro_queda` lo verifica.

### 2. El modelo escribe contenido, el código pone el diseño

`deck.render()` recibe una `Propuesta` ya revisada por `revisar_propuesta` y la mete en slides
fijas. El modelo no escribe HTML, así que no puede:
- romper el diseño,
- colar un precio que el revisor no vio (todo pasa por `html.escape`),
- cambiar el link de la reunión.

El link lo arma `deck.link_agenda()` desde `AGENDA_URL` del `.env`, con `?name=&email=` para que
Cal.com abra con los datos cargados. Misma idea que la estimación: **lo que tiene consecuencias
lo pone el código**.

### 3. Dos documentos, dos audiencias

| | `interno.pdf` | `pitch.pdf` |
|---|---|---|
| Para | el equipo | el cliente (lo reenvías tú, después de leerlo) |
| Precio | sí, calculado con la tarifa | nunca |
| Antecedentes | sí, marcados "email no verificado" | nunca |
| Fuentes de Tavily | sí | no |

La frontera es la misma de la lección 2 (`componer` no recibe `nota_interna`), ahora en papel.
`test_completar_guarda_documentos_y_avisa` verifica que el pitch no diga "USD".

### 4. Sin dependencias nuevas

- **PDF**: Chrome headless (`--print-to-pdf`) en vez de WeasyPrint o ReportLab. El HTML se ve
  igual en el navegador y en el PDF, y si no hay Chrome, se adjunta el HTML.
- **Email**: `smtplib` en vez del SDK de Resend. Resend acepta SMTP (`smtp.resend.com:465`,
  usuario `resend`, la API key como clave). Si mañana cambias a otro proveedor, cambias el `.env`.

### 5. Los tests no salen a la red, aunque tengas las keys

La fixture `sin_red` (autouse) borra `TAVILY_API_KEY`, reemplaza `pdf.a_pdf` por "no hay Chrome"
y `avisos.email` por una lista. Antes de existir, `test_si_el_modelo_falla_el_lead_no_se_pierde`
podía mandarte un mail real cada vez que corrías pytest con el `.env` cargado.

Funciona porque `flujo.py` importa `avisos` y `pdf` **como módulos** (la trampa de la lección 2, §9).

### Correr

```bash
uv run --env-file .env python -m guria_intake.chat   # al enviar: workflow, PDFs y mail
```

Variables nuevas en `.env.example`: `SMTP_*`, `AVISOS_EMAIL`, `AGENDA_URL`, `CHROMIUM_BIN`.

### Ejercicios

1. Pon un `SMTP_PASS` falso y completa un intake por el chat. ¿Qué quedó en el JSON de
   `data/borradores/`? ¿Se perdió algo?
2. Abre `lead.pitch.html` en el navegador y compáralo con el PDF. ¿Qué diferencia ves?
   ¿Qué hace `--virtual-time-budget`?
3. Hoy el email dice "El workflow falló" si no hay borrador por un error. Escribe el mail que
   recibirías si el workflow anduvo pero **Chrome** falló: ¿se entiende qué pasó? Mejóralo con un test.
4. Si quisieras mandarle el pitch **directo al cliente**, ¿qué te frena? Piensa en el email no
   verificado y en `revisar_propuesta`: ¿alcanza un revisor en código o tiene que mirar una persona?

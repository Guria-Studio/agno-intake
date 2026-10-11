"""El diseño de guria.lat para los documentos: marca, textos fijos y CSS.

Copiado de agent-langchain (deck.py e interno.py) sin cambios de diseño: el modelo
escribe el contenido; el formato, los textos fijos y el llamado a la reunión los pone el código.
"""

MESES = {
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"],
    "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
           "setembro", "outubro", "novembro", "dezembro"],
}

TXT = {
    "es": dict(
        propuesta="Propuesta", para="Para", borrador="Borrador para conversar",
        contaste="Lo que nos contaste", cuesta="Lo que cuesta hoy",
        resuelto="Cómo se ve resuelto", resuelto_h="Un día normal, con esto andando",
        etapas="Cómo trabajaríamos", etapas_h="Por etapas, para aprender antes de invertir más",
        etapa="Etapa", aca="Empezamos aquí", falta="Lo que falta definir",
        falta_h="Tres preguntas para la reunión",
        cta_h="Agendemos 30 minutos",
        cta_p="Este documento es un borrador. En una reunión online lo ajustamos juntos "
              "y definimos alcance y presupuesto.",
        agendar="Agendar la reunión",
    ),
    "pt": dict(
        propuesta="Proposta", para="Para", borrador="Rascunho para conversar",
        contaste="O que você nos contou", cuesta="Quanto isso custa hoje",
        resuelto="Como fica resolvido", resuelto_h="Um dia normal, com isso funcionando",
        etapas="Como trabalharíamos", etapas_h="Por etapas, para aprender antes de investir mais",
        etapa="Etapa", aca="Começamos aqui", falta="O que falta definir",
        falta_h="Três perguntas para a reunião",
        cta_h="Vamos agendar 30 minutos",
        cta_p="Este documento é um rascunho. Em uma reunião online ajustamos juntos "
              "e definimos escopo e orçamento.",
        agendar="Agendar a reunião",
    ),
}


def logo(trazo: str, punto: str, size: int = 30) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{trazo}" '
            f'stroke-width="2" stroke-linecap="round" aria-label="guria.lat">'
            f'<path d="M2 6 H9 C13 6 13 12 17 12"/><path d="M2 12 H17"/>'
            f'<path d="M2 18 H9 C13 18 13 12 17 12"/>'
            f'<circle cx="18.5" cy="12" r="2.2" fill="{punto}" stroke="none"/></svg>')



CSS_DECK = """
@page { size: 1280px 720px; margin: 0; }
:root {
  --ink:#111417; --ink-soft:#35383B; --paper:#EFEEE9; --sunk:#E4E2DA; --card:#FFFFFF;
  --rule:#C9C7BE; --rule-dark:#33373B; --muted:#63635B; --muted-dark:#8A8A80; --body-dark:#C3C3BA;
  --signal:#E2502B; --signal-text:#B03A1B; --signal-rule:#B8401E; --on-signal:#17100C;
  --display:"Archivo","Helvetica Neue",Arial,sans-serif;
  --body:"Newsreader",Georgia,"Times New Roman",serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #777; font-family: var(--body); -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.slide { width: 1280px; height: 720px; padding: 64px 72px 0; display: flex; flex-direction: column;
  background: var(--paper); color: var(--ink); overflow: hidden; break-after: page; position: relative; }
@media screen { body { padding: 24px; display: flex; flex-direction: column; align-items: center; gap: 24px; } }
.dark { background: var(--ink); color: var(--paper); }
.signal { background: var(--signal); color: var(--on-signal); }
.kicker { font-family: var(--mono); font-size: 13px; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.kicker b { color: var(--signal-text); font-weight: 500; }
.dark .kicker { color: var(--muted-dark); } .dark .kicker b { color: var(--signal); }
h1, h2, h3 { font-family: var(--display); text-wrap: balance; }
h1 { font-size: 84px; font-weight: 800; line-height: .98; letter-spacing: -.045em; }
h2 { font-size: 54px; font-weight: 800; line-height: 1.04; letter-spacing: -.035em; }
h3 { font-size: 28px; font-weight: 600; line-height: 1.15; letter-spacing: -.02em; }
.body { flex: 1; display: flex; flex-direction: column; justify-content: safe center; gap: 32px; padding-block: 24px; min-height: 0; }
.portada .body { justify-content: space-between; }
.foot { height: 56px; display: flex; align-items: center; justify-content: space-between;
  font-family: var(--mono); font-size: 12px; letter-spacing: .08em; color: var(--muted);
  border-top: 1px solid var(--rule); }
.dark .foot { color: var(--muted-dark); border-color: var(--rule-dark); }
.signal .foot { color: var(--on-signal); border-color: var(--signal-rule); }
.brand { display: flex; align-items: center; gap: 12px; font-family: var(--display); font-weight: 800;
  font-size: 26px; letter-spacing: -.03em; }
.brand b { font-weight: 800; }
.brand span { color: var(--signal); }
.lead { font-size: 34px; line-height: 1.32; font-weight: 300; max-width: 30ch; }
.quote { font-size: 38px; line-height: 1.36; font-weight: 300; max-width: 44ch; }
.cuesta { display: flex; flex-direction: column; gap: 8px; padding-left: 20px; border-left: 3px solid var(--signal); }
.cuesta p { font-family: var(--display); font-weight: 600; font-size: 30px; letter-spacing: -.02em; max-width: 52ch; }
.grid { display: grid; gap: 1px; background: var(--rule); border: 1px solid var(--rule); }
.grid > div { background: var(--paper); padding: 28px 30px; display: flex; flex-direction: column; gap: 10px; }
.n { font-family: var(--mono); font-size: 13px; color: var(--signal-text); letter-spacing: .1em; }
.item { font-size: 25px; line-height: 1.4; font-weight: 400; }
.cols2 { grid-template-columns: 1fr 1fr; }
.cols3 { grid-template-columns: repeat(3, 1fr); }
.etapa h3 { min-height: 2.3em; }
.tres h2 { font-size: 42px; }
.tres .grid > div { padding: 22px 22px; gap: 8px; }
.tres .etapa h3 { font-size: 22px; }
.tres .etapa .obj { font-size: 17px; }
.tres .etapa li { font-size: 13px; }
.etapa .obj { font-size: 20px; line-height: 1.4; color: var(--ink-soft); }
.etapa ul { list-style: none; display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--rule); padding-top: 12px; }
.etapa li { font-family: var(--mono); font-size: 14.5px; line-height: 1.45; color: var(--ink-soft); }
.etapa li::before { content: "· "; color: var(--signal-text); }
.aca { font-family: var(--mono); font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--signal-text); }
.preguntas { display: flex; flex-direction: column; border-top: 1px solid var(--rule); }
.preguntas li { list-style: none; display: grid; grid-template-columns: 72px 1fr; padding: 28px 0;
  border-bottom: 1px solid var(--rule); align-items: baseline; }
.preguntas li span { font-family: var(--mono); font-size: 14px; color: var(--signal-text); }
.preguntas li p { font-family: var(--display); font-weight: 600; font-size: 32px; letter-spacing: -.02em; line-height: 1.2; }
.cta h2 { font-size: 72px; color: var(--on-signal); }
.cta .quote { color: var(--on-signal); max-width: 40ch; }
.boton { align-self: flex-start; background: var(--ink); color: var(--paper); font-family: var(--mono);
  font-size: 16px; letter-spacing: .06em; padding: 18px 26px; text-decoration: none; display: flex; flex-direction: column; gap: 6px; }
.boton small { font-size: 12px; color: var(--muted-dark); letter-spacing: .04em; }
"""

CSS_INTERNO = """
@page { size: A4; margin: 18mm 16mm; }
:root { --ink:#111417; --soft:#35383B; --muted:#63635B; --rule:#C9C7BE; --signal:#B03A1B; --sunk:#F2F1EC;
  --display:"Archivo","Helvetica Neue",Arial,sans-serif; --body:"Newsreader",Georgia,serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,monospace; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--body); color: var(--ink); font-size: 11.5pt; line-height: 1.45;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }
@media screen { body { max-width: 760px; margin: 32px auto; padding: 0 16px; } }
header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px;
  border-bottom: 2px solid var(--ink); font-family: var(--mono); font-size: 8.5pt; letter-spacing: .08em;
  text-transform: uppercase; color: var(--muted); }
header b { font-family: var(--display); font-size: 13pt; letter-spacing: -.02em; text-transform: none; color: var(--ink); }
h1 { font-family: var(--display); font-size: 24pt; letter-spacing: -.03em; line-height: 1.1; margin: 18px 0 4px; }
.para { color: var(--soft); margin-bottom: 14px; }
.veredicto { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.chip { font-family: var(--mono); font-size: 8.5pt; letter-spacing: .06em; text-transform: uppercase;
  border: 1px solid var(--ink); padding: 4px 8px; }
.chip.alerta { background: var(--signal); border-color: var(--signal); color: #fff; }
h2 { font-family: var(--mono); font-size: 8.5pt; letter-spacing: .14em; text-transform: uppercase;
  color: var(--signal); margin: 18px 0 6px; padding-top: 10px; border-top: 1px solid var(--rule); }
p + p { margin-top: 6px; }
ul { padding-left: 16px; } li + li { margin-top: 3px; }
dl { display: grid; grid-template-columns: 150px 1fr; gap: 4px 12px; }
small { font-size: 9pt; color: var(--muted); }
dt { font-family: var(--mono); font-size: 8.5pt; color: var(--muted); padding-top: 2px; }
.nota { background: var(--sunk); padding: 10px 12px; border-left: 3px solid var(--signal); }
h2, dt { break-after: avoid; } li, dd { break-inside: avoid; }
"""

FUENTES = ("https://fonts.googleapis.com/css2?family=Archivo:wght@600;800"
           "&family=Newsreader:opsz,wght@6..72,300;6..72,400&family=JetBrains+Mono:wght@400;500&display=swap")

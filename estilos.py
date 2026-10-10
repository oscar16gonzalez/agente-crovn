"""Interfaz CROVN Command Center: CSS basado en variables de tema (ver temas.py) y componentes HTML (tarjetas, SQL, audio)."""
import base64
import html as _h
import re
from decimal import Decimal
from datetime import date, datetime

import temas

CRANEO = "💀"

CSS_BASE = """
<style>
html, body, .stApp, button, input, textarea, select { font-family: var(--fuente); }
.stApp { --sb: 0px; background: var(--fondo-app); background-attachment: fixed; color: var(--texto); }
.stApp:has([data-testid="stSidebar"][aria-expanded="true"]) { --sb: 336px; }

@keyframes subir { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes flotar { 0%, 100% { transform: translateY(0) rotate(-3deg); } 50% { transform: translateY(-12px) rotate(3deg); } }
@keyframes onda { 0% { transform: scale(1); opacity: .8; } 100% { transform: scale(1.75); opacity: 0; } }
@keyframes latido { 0%, 100% { box-shadow: 0 0 18px rgba(var(--ac-rgb),.45); } 50% { box-shadow: 0 0 38px rgba(var(--ac-vivo-rgb),.85); } }
@keyframes ecualizador { 0%, 100% { transform: scaleY(.25); } 50% { transform: scaleY(1); } }
@keyframes respirar { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }

/* ---------- Texto y controles nativos de Streamlit ---------- */
.stApp, .stApp p, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp label,
[data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] { color: var(--texto); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--muted); }
.stApp a { color: var(--ac-vivo); }
.stApp code { background: rgba(var(--ac-rgb), .12); color: var(--ac-vivo); border-radius: 6px; }
.stApp hr { border-color: var(--borde); }
[data-testid="stHeader"] [data-testid="stToolbar"] *, [data-testid="stSidebarCollapseButton"] *, [data-testid="stExpandSidebarButton"] * { color: var(--muted); }
[data-baseweb="popover"] > div, [data-baseweb="menu"], ul[role="listbox"] { background: var(--panel-2) !important; color: var(--texto) !important; border: 1px solid var(--borde); border-radius: var(--r-sm) !important; }
[data-baseweb="menu"] li, ul[role="listbox"] li { color: var(--texto) !important; }
[data-baseweb="menu"] li:hover, ul[role="listbox"] li:hover, ul[role="listbox"] li[aria-selected="true"] { background: rgba(var(--ac-rgb), .14) !important; }
[data-baseweb="select"] *, [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, textarea { color: var(--texto) !important; }
[data-baseweb="select"] svg, [data-testid="stNumberInput"] button { color: var(--muted) !important; fill: var(--muted); }
[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--borde); border-radius: var(--r); padding: .8rem 1rem; }
[data-testid="stMetricLabel"] p { color: var(--muted); }
[data-baseweb="tab-list"] { gap: .3rem; border-bottom: 1px solid var(--borde); }
[data-baseweb="tab"] { color: var(--muted); }
[data-baseweb="tab"][aria-selected="true"] { color: var(--texto); }
[data-baseweb="tab-highlight"] { background: var(--ac) !important; }
[data-testid="stProgress"] > div > div { background: rgba(var(--ac-rgb), .15); }
[data-testid="stProgress"] > div > div > div { background: var(--grad) !important; }
[data-baseweb="checkbox"] > span:first-child, [data-baseweb="toggle"] > div { border-color: var(--borde); }
[data-baseweb="checkbox"] input:checked + span, [data-baseweb="checkbox"] [aria-checked="true"] > span:first-child { background: var(--ac) !important; border-color: var(--ac) !important; }
[data-testid="stSlider"] [role="slider"] { background: var(--ac) !important; box-shadow: var(--glow); }
[data-testid="stSlider"] [data-testid="stThumbValue"], [data-testid="stTickBarMin"], [data-testid="stTickBarMax"] { color: var(--muted); }
[data-testid="stColorPicker"] [data-baseweb="block"], [data-testid="stColorPicker"] > div > div > div { border-radius: var(--r-sm); border: 1px solid var(--borde); }

/* ---------- Estructura ---------- */
[data-testid="stHeader"] { background: transparent; }
footer, [data-testid="stAppDeployButton"] { display: none !important; }
[data-testid="stMainBlockContainer"], [data-testid="stBottomBlockContainer"] {
  max-width: var(--ancho) !important; padding-left: 1.25rem; padding-right: 1.25rem;
}
[data-testid="stMainBlockContainer"] { padding-top: 2rem; padding-bottom: 11rem; }
[data-testid="stBottom"] > div { background: linear-gradient(180deg, transparent, var(--bg) 40%); }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: var(--borde); border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: var(--ac-oscuro); }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: var(--panel); border-right: 1px solid var(--borde); }
[data-testid="stSidebar"] > div:first-child { background: linear-gradient(180deg, rgba(var(--ac-rgb),.07), transparent 240px); }
.marca { display: flex; align-items: center; gap: .8rem; margin: .2rem 0 1rem; }
.marca-icono {
  width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center; flex: none; font-size: 1.3rem;
  background: radial-gradient(circle at 50% 30%, var(--medalla), var(--bg) 75%); box-shadow: 0 0 0 1px rgba(var(--ac-vivo-rgb),.4), var(--glow);
}
.marca b { display: block; letter-spacing: .22em; font-size: 1.05rem; line-height: 1.1; color: var(--texto); }
.marca small { color: var(--muted); font-size: .68rem; letter-spacing: .14em; text-transform: uppercase; }
.seccion {
  display: flex; align-items: center; gap: .5rem; color: var(--muted); font-size: .68rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: .16em; margin: 1.4rem 0 .5rem;
}
.seccion::before { content: ""; width: 3px; height: 11px; border-radius: 2px; background: var(--ac); box-shadow: 0 0 8px var(--ac); }
.estado-bd {
  display: flex; align-items: center; gap: .5rem; font-size: .76rem; color: var(--ok); margin-bottom: .8rem;
  padding: .35rem .7rem; border-radius: 999px; background: rgba(var(--ok-rgb),.08); border: 1px solid rgba(var(--ok-rgb),.25); width: fit-content;
}
.estado-bd i { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 8px var(--ok); }
.estado-bd.error { color: var(--alerta); background: rgba(var(--alerta-rgb),.1); border-color: rgba(var(--alerta-rgb),.35); }
.estado-bd.error i { background: var(--alerta); box-shadow: 0 0 8px var(--alerta); }

/* ---------- Botones y controles ---------- */
.stButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stDownloadButton"] > button {
  border-radius: var(--r-sm); border: 1px solid var(--borde); background: var(--panel-2); color: var(--texto);
  transition: border-color .18s, background .18s, transform .18s, box-shadow .18s;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover, [data-testid="stDownloadButton"] > button:hover {
  border-color: rgba(var(--ac-vivo-rgb),.4); background: rgba(var(--ac-rgb),.05); color: var(--texto); transform: translateY(-1px);
  box-shadow: 0 5px 16px rgba(var(--sombra-rgb),calc(var(--sa) * .7));
}
button[data-testid="stBaseButton-primary"] {
  background: var(--grad); border: none; color: var(--on-ac); box-shadow: 0 8px 20px rgba(var(--ac-rgb),.28);
}
button[data-testid="stBaseButton-primary"] p, button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"] { color: var(--on-ac); }
button[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.12); background: var(--grad); color: var(--on-ac); }
[data-testid="stSidebar"] button[data-testid="stBaseButton-tertiary"] {
  justify-content: flex-start; text-align: left; border: none; background: transparent; color: var(--muted); border-radius: var(--r-sm);
}
[data-testid="stSidebar"] button[data-testid="stBaseButton-tertiary"]:hover { background: rgba(var(--texto-rgb),.06); color: var(--texto); transform: none; box-shadow: none; }
[data-testid="stSidebar"] button[data-testid="stBaseButton-tertiary"] p { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
[data-testid="stSidebar"] [data-testid="stColumn"] button { padding-left: .4rem; padding-right: .4rem; }
[data-testid="stSidebar"] [data-testid="stColumn"] button p { white-space: nowrap; font-size: .85rem; }
.st-key-sidebar_footer { position: sticky; bottom: 0; z-index: 20; margin-top: auto; padding: .65rem 0 .2rem; background: var(--panel); border-top: 1px solid var(--borde); }
.st-key-sidebar_footer [data-testid="stCaptionContainer"] { padding-bottom: .35rem; }

/* Segmented control: módulos y proveedor de IA */
[data-baseweb="button-group"] {
  width: 100%; padding: 3px; gap: 3px; border-radius: var(--r); background: var(--inset); border: 1px solid var(--borde); flex-wrap: nowrap !important;
}
[data-testid^="stBaseButton-segmented_control"] {
  flex: 1 1 auto !important; width: auto !important; min-width: 0; padding: 4px 3px !important; min-height: 2.1rem; border-radius: var(--r-sm) !important; border: 1px solid transparent !important;
  background: transparent !important; color: var(--muted) !important; font-size: .72rem; font-weight: 500; justify-content: center;
  transition: background .18s, color .18s, box-shadow .18s;
}
[data-testid^="stBaseButton-segmented_control"] p { font-size: .76rem; overflow: visible; text-overflow: clip; color: inherit; }
[data-testid^="stBaseButton-segmented_control"]:hover { color: var(--texto) !important; background: rgba(var(--texto-rgb),.05) !important; }
[data-testid="stBaseButton-segmented_controlActive"] {
  background: rgba(var(--ac-rgb),.2) !important; color: var(--texto) !important;
  border-color: rgba(var(--ac-vivo-rgb),.5) !important; box-shadow: var(--glow);
}
.opcion-ia {
  display: flex; align-items: center; gap: .7rem; padding: .65rem .8rem; margin: .5rem 0 .6rem; border-radius: var(--r-sm);
  background: var(--panel-2); border: 1px solid var(--borde); font-size: .76rem; color: var(--muted); line-height: 1.4;
}
.opcion-ia b { display: block; color: var(--texto); font-size: .82rem; }
.opcion-ia i { width: 8px; height: 8px; flex: none; border-radius: 50%; background: var(--ac-vivo); box-shadow: 0 0 10px var(--ac-vivo); }

[data-testid="stExpander"] { border: 1px solid var(--borde); border-radius: var(--r); background: var(--panel); overflow: hidden; }
[data-testid="stExpander"] summary { color: var(--muted); font-size: .85rem; }
[data-testid="stExpander"] summary:hover { color: var(--texto); }
[data-testid="stAlert"] { border-radius: var(--r); }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-baseweb="select"] > div {
  background: var(--panel-2) !important; border-color: var(--borde) !important; border-radius: var(--r-sm) !important;
}
[data-testid="stTextInput"] input:focus { border-color: rgba(var(--ac-vivo-rgb),.7) !important; box-shadow: 0 0 0 3px rgba(var(--ac-rgb),.15) !important; }

/* ---------- Bienvenida ---------- */
.bienvenida {
  display: grid; grid-template-columns: 84px minmax(0, 1fr); align-items: center; gap: 1.35rem;
  max-width: 760px; margin: 4vh auto 1.8rem; text-align: left; padding: 1.2rem 0 1.8rem; animation: subir .6s ease both;
}
.bienvenida-contenido { min-width: 0; }
.hero-craneo {
  width: 84px; height: 84px; border-radius: 50%; display: grid; place-items: center; font-size: 2.8rem;
  background: radial-gradient(circle at 50% 30%, var(--medalla), var(--bg) 75%); box-shadow: 0 0 0 1px rgba(var(--ac-vivo-rgb),.4), var(--glow-fuerte);
  animation: latido 3.2s ease-in-out infinite;
}
.bienvenida .hola { color: var(--ac-vivo); font-weight: 600; letter-spacing: .18em; font-size: .7rem; text-transform: uppercase; }
.bienvenida h1 {
  font-size: 2.35rem; font-weight: 700; margin: .45rem 0 .6rem; padding: 0; line-height: 1.12;
  background: linear-gradient(180deg, var(--texto), var(--muted)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.bienvenida p { color: var(--muted); max-width: 600px; margin: 0; line-height: 1.65; font-size: .95rem; }
.st-key-tarjetas { animation: subir .7s ease .1s both; }
.st-key-tarjetas button {
  height: auto; min-height: 72px; padding: 1rem 1.1rem; border-radius: var(--r); background: var(--panel); border-color: var(--borde);
  justify-content: flex-start; text-align: left; box-shadow: 0 4px 14px rgba(var(--sombra-rgb), calc(var(--sa) * .5));
}
.st-key-tarjetas button:hover { box-shadow: 0 8px 22px rgba(var(--sombra-rgb),calc(var(--sa) * .8)); border-color: rgba(var(--ac-vivo-rgb),.35); transform: translateY(-1px); }
.st-key-tarjetas [data-testid="stIconMaterial"] { color: var(--ac-vivo); }
@media (max-width: 640px) {
  .bienvenida { grid-template-columns: 56px minmax(0, 1fr); gap: .85rem; margin-top: 2vh; padding: .8rem 0 1.2rem; }
  .hero-craneo { width: 56px; height: 56px; font-size: 2rem; }
  .bienvenida .hola { font-size: .62rem; letter-spacing: .12em; }
  .bienvenida h1 { font-size: 1.65rem; }
  .bienvenida p { font-size: .88rem; }
  .st-key-tarjetas button { min-height: 66px; padding: .75rem; }
}

/* ---------- Mensajes ---------- */
.cabecera {
  display: flex; align-items: center; justify-content: space-between; gap: .8rem; margin-bottom: 1rem; padding: .7rem .9rem;
  background: var(--panel); border: 1px solid var(--borde); border-radius: var(--r);
}
.cabecera span { font-weight: 600; display: flex; align-items: center; gap: .6rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cabecera > span::before { content: ""; width: 7px; height: 7px; flex: none; border-radius: 50%; background: var(--ac-vivo); box-shadow: 0 0 8px var(--ac-vivo); }
.chips { display: flex; gap: .4rem; flex: none; }
.chips .chip {
  font-size: .7rem; font-weight: 400; color: var(--muted); border: 1px solid var(--borde); border-radius: 999px; padding: .15rem .65rem; background: var(--inset); white-space: nowrap;
}
.chips .chip.ok { color: var(--ok); border-color: rgba(var(--ok-rgb),.25); background: rgba(var(--ok-rgb),.06); }
.msg-usuario { display: flex; justify-content: flex-end; margin: 1.2rem 0 .5rem; animation: subir .3s ease both; }
.msg-usuario .burbuja {
  max-width: 78%; background: linear-gradient(135deg, rgba(var(--ac-rgb),.22), rgba(var(--ac2-rgb),.12)); border: 1px solid rgba(var(--ac-vivo-rgb),.3);
  padding: .7rem 1rem; border-radius: var(--r-lg) var(--r-lg) 4px var(--r-lg); line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--texto);
}
[data-testid="stChatMessage"] { background: transparent; padding: .4rem 0; gap: .9rem; animation: subir .35s ease both; }
[data-testid="stChatMessage"] > div:first-child {
  display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; min-width: 38px; border-radius: 50% !important; flex: none; font-size: 1.15rem;
  background: radial-gradient(circle at 50% 30%, var(--medalla), var(--bg) 75%) !important;
  box-shadow: 0 0 0 1px rgba(var(--ac-vivo-rgb),.4), var(--glow);
}
[data-testid="stChatMessage"] > div:nth-child(2) { min-width: 0; max-width: 72ch; }
[data-testid="stChatMessage"] [data-testid="stCaptionContainer"] { color: var(--muted); font-size: .72rem; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p { line-height: 1.75; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] :is(ul, ol) { padding-left: 1.25rem; line-height: 1.75; }

/* ---------- Tarjetas de datos ---------- */
.dt { background: var(--panel); border: 1px solid var(--borde); border-radius: var(--r); overflow: hidden; margin: .3rem 0 .8rem; box-shadow: 0 8px 30px rgba(var(--sombra-rgb),var(--sa)); }
.dt-cab { display: flex; align-items: center; gap: .6rem; padding: .6rem .9rem; border-bottom: 1px solid var(--borde); background: rgba(var(--texto-rgb),.02); font-size: .74rem; color: var(--muted); }
.dt-cab b { color: var(--texto); font-weight: 600; letter-spacing: .02em; }
.dt-cab .sp { margin-left: auto; }
.dt-scroll { overflow: auto; max-height: 420px; }
.dt table { width: 100%; border-collapse: collapse; font-size: .82rem; margin: 0; }
.dt th {
  position: sticky; top: 0; text-align: left; padding: .55rem .9rem; font-size: .66rem; font-weight: 600; letter-spacing: .12em;
  text-transform: uppercase; color: var(--muted); background: var(--inset); border: none; border-bottom: 1px solid rgba(var(--ac-oscuro-rgb),.4); white-space: nowrap;
}
.dt td { padding: .55rem .9rem; border: none; border-bottom: 1px solid var(--borde); color: var(--fila); white-space: nowrap; max-width: 280px; overflow: hidden; text-overflow: ellipsis; background: transparent; }
.dt tbody tr:last-child td { border-bottom: none; }
.dt tbody tr:hover td { background: rgba(var(--ac-rgb),.06); }
.dt td.num, .dt th.num { text-align: right; font-variant-numeric: tabular-nums; }
.dt .nulo { color: var(--tenue); }
.dt-vacio { padding: 1.4rem; text-align: center; color: var(--muted); font-size: .85rem; }
.dt-act td:first-child { color: var(--muted); width: 38%; }

.bd { display: inline-flex; align-items: center; gap: .35rem; padding: .12rem .6rem; border-radius: 999px; font-size: .7rem; font-weight: 600; letter-spacing: .02em; border: 1px solid transparent; }
.bd::before { content: ""; width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.bd-ok { color: var(--ok); background: rgba(var(--ok-rgb),.08); border-color: rgba(var(--ok-rgb),.25); }
.bd-alerta { color: var(--alerta); background: rgba(var(--alerta-rgb),.1); border-color: rgba(var(--alerta-rgb),.4); }
.bd-aviso { color: var(--aviso); background: rgba(var(--aviso-rgb),.08); border-color: rgba(var(--aviso-rgb),.25); }
.bd-info { color: var(--info); background: rgba(var(--info-rgb),.08); border-color: rgba(var(--info-rgb),.22); }
.bd-mute { color: var(--muted); background: rgba(var(--texto-rgb),.06); border-color: rgba(var(--texto-rgb),.14); }
.bd-vip { color: var(--on-ac); background: var(--grad); border-color: rgba(var(--ac-vivo-rgb),.5); box-shadow: var(--glow); }

.ucards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: .8rem; margin: .3rem 0 .8rem; }
.ucard { background: var(--panel); border: 1px solid var(--borde); border-radius: var(--r); padding: 1rem; box-shadow: 0 8px 30px rgba(var(--sombra-rgb),var(--sa)); transition: border-color .2s, transform .2s; }
.ucard:hover { border-color: rgba(var(--ac-vivo-rgb),.4); transform: translateY(-2px); }
.ucard-top { display: flex; align-items: center; gap: .8rem; }
.ucard-av {
  width: 46px; height: 46px; flex: none; border-radius: 50%; display: grid; place-items: center; font-weight: 700; color: var(--on-ac);
  background: var(--grad); box-shadow: 0 0 0 1px rgba(var(--ac-vivo-rgb),.4), var(--glow);
}
.ucard-info { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: .15rem; }
.ucard-nom { display: block; min-width: 0; font-weight: 600; font-size: 1rem; color: var(--texto); overflow-wrap: anywhere; }
.ucard-mail { display: block; min-width: 0; color: var(--muted); font-size: .8rem; overflow-wrap: anywhere; }
.ucard-bd { display: flex; flex-wrap: wrap; gap: .4rem; margin: .8rem 0 .2rem; }
.ucard-productos { display: flex; align-items: baseline; gap: .45rem; margin-top: .8rem; padding-top: .7rem; border-top: 1px solid var(--borde); }
.ucard-productos strong { color: var(--ac-vivo); font-size: 1.65rem; font-variant-numeric: tabular-nums; line-height: 1; }
.ucard-productos span { color: var(--muted); font-size: .78rem; }
.ucard dl { display: grid; grid-template-columns: auto 1fr; gap: .35rem .9rem; margin: .7rem 0 0; padding-top: .7rem; border-top: 1px solid var(--borde); font-size: .8rem; }
.ucard dt { color: var(--muted); text-transform: uppercase; font-size: .64rem; letter-spacing: .1em; align-self: center; font-weight: 500; }
.ucard dd { margin: 0; color: var(--fila); overflow-wrap: anywhere; }

/* ---------- SQL con resaltado ---------- */
.sqlbox { background: var(--inset); border: 1px solid var(--borde); border-radius: var(--r-sm); overflow: hidden; }
.sqlbox .sqlcode { padding: .9rem 1rem; overflow-x: auto; font: 400 .8rem/1.65 var(--mono); color: var(--muted); white-space: pre-wrap; word-break: break-word; }
.sql-kw { color: var(--ac-vivo); font-weight: 500; }
.sql-fn { color: var(--ac2); }
.sql-str { color: var(--fila); }
.sql-num { color: var(--aviso); }
.sql-ph { color: var(--ac-vivo); background: rgba(var(--ac-rgb),.15); border-radius: 4px; padding: 0 .25rem; }
.sql-id { color: var(--texto); }
.sql-com { color: var(--tenue); font-style: italic; }
.sqlparams { display: flex; flex-wrap: wrap; gap: .4rem; padding: .6rem 1rem; border-top: 1px solid var(--borde); background: rgba(var(--texto-rgb),.02); }
.sqlparams span { font: 400 .72rem var(--mono); color: var(--muted); border: 1px solid var(--borde); border-radius: 6px; padding: .1rem .5rem; }
.sqlparams span b { color: var(--ac-vivo); font-weight: 500; }

/* ---------- Campo de escritura (barra flotante) ---------- */
[data-testid="stChatInput"] {
  border-radius: var(--r-lg); border: 1px solid rgba(var(--ac-oscuro-rgb),.28); background: var(--panel-2);
  box-shadow: 0 10px 30px rgba(var(--sombra-rgb),calc(var(--sa) * 1.2)); transition: border-color .2s, box-shadow .2s;
}
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] textarea { background: transparent !important; color: var(--texto); }
[data-testid="stChatInput"]:focus-within {
  border-color: rgba(var(--ac-vivo-rgb),.65); box-shadow: 0 0 0 2px rgba(var(--ac-rgb),.12), 0 10px 30px rgba(var(--sombra-rgb),calc(var(--sa) * 1.2));
}
[data-testid="stChatInput"] textarea { padding-left: 3.4rem !important; }
[data-testid="stChatInput"] textarea::placeholder { color: var(--tenue); }
[data-testid="stChatInputSubmitButton"] {
  background: var(--grad); color: var(--on-ac); border-radius: var(--r-sm); box-shadow: 0 4px 14px rgba(var(--ac-rgb),.4);
}
[data-testid="stChatInputSubmitButton"]:disabled { background: var(--inset); box-shadow: none; color: var(--tenue); }

/* ---------- Micrófono (izquierda del campo) ---------- */
.st-key-mic_grabar {
  position: fixed; bottom: 33px; z-index: 1000; width: auto;
  left: calc(var(--sb) + max(30px, (100vw - var(--sb)) / 2 - var(--ancho) / 2 + 30px));
}
.st-key-mic_grabar button {
  position: relative; width: 38px; height: 38px; min-height: 0; padding: 0; border-radius: 50%;
  background: rgba(var(--ac-rgb),.12); border: 1px solid rgba(var(--ac-vivo-rgb),.4); color: var(--ac-vivo);
  transition: transform .2s, background .2s, color .2s, box-shadow .2s;
}
.st-key-mic_grabar button:hover { color: var(--on-ac); background: var(--ac); transform: scale(1.1); box-shadow: 0 6px 18px rgba(var(--ac-rgb),.5); }
.st-key-mic_grabar button:active { transform: scale(.94); }
.st-key-mic_grabar button::after {
  content: ""; position: absolute; inset: -1px; border-radius: 50%; border: 2px solid rgba(var(--ac-vivo-rgb),.6);
  opacity: 0; pointer-events: none;
}
.st-key-mic_grabar button:hover::after { animation: onda 1.1s ease-out infinite; }
.stApp:has(.grabando) .st-key-mic_grabar button {
  background: var(--ac); color: var(--on-ac); border-color: transparent; animation: latido 1.2s ease-in-out infinite, respirar 1.2s ease-in-out infinite;
}
.stApp:has(.grabando) .st-key-mic_grabar button::after { opacity: 1; animation: onda 1.4s ease-out infinite; }
/* Enviar audio: más a la izquierda y más arriba mientras se graba */
.stApp:has(.grabando) .st-key-mic_grabar { bottom: 58px; left: calc(var(--sb) + max(30px, (100vw - var(--sb)) / 2 - var(--ancho) / 2 + 30px) - 18px); }
.stApp:has(.grabando) [data-testid="stChatInput"] textarea::placeholder { color: transparent; }

/* Acciones rápidas en el botón del asistente */
.st-key-quick_actions { position: fixed; top: 54vh; right: max(16px, calc((100vw - var(--sb)) / 2 - var(--ancho) / 2 - 110px)); z-index: 1100; width: auto; }
.st-key-quick_actions [data-testid="stPopoverButton"] {
  width: 72px; height: 72px; min-height: 72px; padding: 0; border-radius: 50%; font-size: 2.2rem;
  background: radial-gradient(circle at 50% 30%, var(--medalla), var(--bg) 75%); border: 1px solid rgba(var(--ac-vivo-rgb),.45);
  box-shadow: 0 0 0 1px rgba(var(--ac-vivo-rgb),.25), var(--glow-fuerte); animation: flotar 3.2s ease-in-out infinite, latido 3.2s ease-in-out infinite;
}
.st-key-quick_actions [data-testid="stPopoverButton"]:hover { transform: scale(1.05); }
[data-testid="stPopoverBody"] { background: var(--panel) !important; border: 1px solid var(--borde) !important; border-radius: var(--r) !important; box-shadow: 0 16px 44px rgba(var(--sombra-rgb),var(--sa)); }

/* Detener consulta */
[class*="st-key-detener_"] {
  position: fixed; bottom: 92px; z-index: 1000; width: auto;
  left: calc(var(--sb) + (100vw - var(--sb)) / 2 - 52px);
}
[class*="st-key-detener_"] button {
  min-height: 0; padding: .45rem 1.1rem; border-radius: 999px; background: var(--panel-2); color: var(--texto);
  border: 1px solid rgba(var(--ac-vivo-rgb),.55); box-shadow: 0 8px 24px rgba(var(--sombra-rgb),calc(var(--sa) * 1.4)); animation: subir .25s ease both;
  transition: background .2s, transform .2s, box-shadow .2s;
}
[class*="st-key-detener_"] button:hover { background: var(--ac); border-color: transparent; color: var(--on-ac); transform: translateY(-2px); box-shadow: 0 8px 24px rgba(var(--ac-rgb),.45); }
[class*="st-key-detener_"] button:active { transform: scale(.96); }
[class*="st-key-detener_"] [data-testid="stIconMaterial"] { color: var(--ac-vivo); }
[class*="st-key-detener_"] button:hover [data-testid="stIconMaterial"], [class*="st-key-detener_"] button:hover p { color: var(--on-ac); }

/* Barra de grabación sobre el campo */
.grabando { position: fixed; left: var(--sb); right: 0; bottom: 92px; z-index: 999; display: flex; justify-content: center; pointer-events: none; }
.grabando-barra {
  display: flex; align-items: center; gap: .8rem; width: min(calc(var(--ancho) - 2.5rem), calc(100vw - var(--sb) - 2.5rem));
  padding: .55rem 3.4rem .55rem 1rem; border-radius: var(--r); background: var(--panel-2); border: 1px solid rgba(var(--ac-vivo-rgb),.45);
  box-shadow: 0 10px 30px rgba(var(--sombra-rgb),calc(var(--sa) * 1.4)), 0 0 0 3px rgba(var(--ac-rgb),.1); color: var(--texto); font-size: .88rem; animation: subir .25s ease both;
}
.grabando-barra small { color: var(--muted); margin-left: auto; font-size: .75rem; }
.ecualizador { display: flex; align-items: center; gap: 3px; height: 22px; }
.ecualizador i { width: 3px; height: 100%; border-radius: 2px; background: var(--ac-vivo); transform-origin: center; animation: ecualizador .9s ease-in-out infinite; }
.ecualizador i:nth-child(2) { animation-delay: .12s; } .ecualizador i:nth-child(3) { animation-delay: .24s; }
.ecualizador i:nth-child(4) { animation-delay: .36s; } .ecualizador i:nth-child(5) { animation-delay: .48s; } .ecualizador i:nth-child(6) { animation-delay: .6s; }
.st-key-mic_cancelar { position: fixed; bottom: 97px; z-index: 1001; width: auto; right: calc(max(20px, (100vw - var(--sb)) / 2 - var(--ancho) / 2 + 20px) + 1.25rem); }
.st-key-mic_cancelar button { width: 32px; height: 32px; min-height: 0; padding: 0; border-radius: 50%; background: var(--panel-2); color: var(--muted); border: 1px solid var(--borde); }
.st-key-mic_cancelar button:hover { color: var(--texto); border-color: rgba(var(--ac-vivo-rgb),.6); background: rgba(var(--ac-rgb),.12); transform: rotate(90deg); }

/* ---------- Mascota flotante (derecha del chat) ---------- */
.craneo-flotante {
  position: fixed; top: 54vh; z-index: 50; width: 72px; height: 72px; border-radius: 50%;
  right: max(16px, calc((100vw - var(--sb)) / 2 - var(--ancho) / 2 - 110px));
  display: grid; place-items: center; user-select: none; cursor: default; font-size: 2.2rem;
  background: radial-gradient(circle at 50% 30%, var(--medalla), var(--bg) 75%); box-shadow: 0 0 0 1px rgba(var(--ac-vivo-rgb),.45), var(--glow-fuerte);
  animation: flotar 3.2s ease-in-out infinite, latido 3.2s ease-in-out infinite;
}
.craneo-flotante::after { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 1px solid rgba(var(--ac-vivo-rgb),.6); animation: onda 2.4s ease-out infinite; }
.craneo-flotante em {
  position: absolute; right: 100%; margin-right: 12px; white-space: nowrap; font-style: normal; font-size: .76rem; color: var(--texto);
  background: var(--panel-2); border: 1px solid var(--borde); padding: .35rem .7rem; border-radius: var(--r-sm);
  opacity: 0; transform: translateX(6px); transition: opacity .2s, transform .2s; pointer-events: none;
}
.craneo-flotante:hover em { opacity: 1; transform: none; }

/* Estado del asistente de voz */
.voz-estado {
  position: fixed; top: 14px; right: 76px; z-index: 1000; display: flex; align-items: center; gap: .55rem; max-width: min(430px, 60vw);
  padding: .4rem .85rem; border-radius: 999px; background: var(--panel-2); border: 1px solid var(--borde); color: var(--muted);
  font-size: .75rem; font-weight: 500; box-shadow: 0 8px 24px rgba(var(--sombra-rgb),calc(var(--sa) * 1.3));
}
.voz-estado span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.voz-estado i { width: 8px; height: 8px; flex: none; border-radius: 50%; background: var(--tenue); }
.voz-habla, .voz-escucha { border-color: rgba(var(--ac-vivo-rgb),.7); color: var(--texto); box-shadow: 0 0 18px rgba(var(--ac-rgb),.35); }
.voz-habla i, .voz-escucha i { background: var(--ac-vivo); animation: latido 1s ease-in-out infinite; }
.voz-ok i { background: var(--ok); }
.voz-error { color: var(--alerta); border-color: rgba(var(--alerta-rgb),.5); }
.voz-error i { background: var(--alerta); }
</style>
"""


def estilos_chat_activo(indice):
    """Resalta el chat seleccionado en la lista lateral."""
    return (
        f"<style>.st-key-chat_{indice} button{{background:rgba(var(--ac-rgb),.14)!important;color:var(--texto)!important;"
        f"box-shadow: inset 2px 0 0 var(--ac-vivo);}}</style>"
    )


def craneo_flotante(icono=CRANEO):
    return f'<div class="craneo-flotante">{icono}<em>Pregúntame sobre tu tienda</em></div>'


def marca_html(icono=CRANEO):
    return (
        f'<div class="marca"><div class="marca-icono">{icono}</div>'
        '<div><b>CROVN</b><small>Command Center</small></div></div>'
    )


def estado_bd_html(ok):
    if ok:
        return '<div class="estado-bd"><i></i>Conectado</div>'
    return '<div class="estado-bd error"><i></i>Acción requerida · sin conexión</div>'


def bienvenida_html(icono=CRANEO):
    return (
    f'<div class="bienvenida"><div class="hero-craneo">{icono}</div><div class="bienvenida-contenido">'
    '<div class="hola">CROVN Command Center</div><h1>¿Qué quieres saber de tu tienda?</h1>'
        '<p>Consulta inventario, órdenes, clientes y promociones con tu voz o escribiendo. '
    'También puedo crear códigos, proveedores y actualizar datos.</p></div></div>'
    )


def cabecera_html(titulo, proveedor, modelo, bd_ok):
    bd = '<span class="chip ok">BD conectada</span>' if bd_ok else '<span class="chip">BD sin conexión</span>'
    return (
        f'<div class="cabecera"><span>{_e(titulo)}</span>'
        f'<div class="chips">{bd}<span class="chip">{_e(proveedor)} · {_e(modelo)}</span></div></div>'
    )


def opcion_ia_html(titulo, detalle):
    return f'<div class="opcion-ia"><i></i><div><b>{_e(titulo)}</b>{_e(detalle)}</div></div>'


# ---------- Tarjetas de datos ----------
def _e(v):
    # "$" se escapa porque el markdown de Streamlit lo interpreta como LaTeX
    return _h.escape(str(v)).replace("$", "&#36;")


def _badge(texto, tono):
    return f'<span class="bd bd-{tono}">{_e(texto)}</span>'


_TONO_ESTADO = {
    "pendiente": "alerta", "procesado": "info", "enviado": "aviso", "entregado": "ok",
    "activo": "ok", "inactivo": "mute", "cancelado": "alerta", "agotado": "alerta",
}
_DINERO = ("price", "precio", "total", "cost", "costo", "ingres", "revenue", "valor", "monto", "amount", "discount", "descuento")
_SIN_NOMBRE = "Sin nombre"


def _num(v):
    if isinstance(v, int) or float(v) == int(v):
        return f"{int(v):,}".replace(",", ".")
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formato_cop(v):
    entero_decimal = format(Decimal(str(v)), ",.2f")
    entero, decimales = entero_decimal.split(".")
    return f"COP ${entero.replace(',', '.')},{decimales}"


def _es_numero(v):
    return not isinstance(v, bool) and (isinstance(v, (int, float)) or type(v).__name__ == "Decimal")


def _celda(col, v):
    c = col.lower()
    if v is None:
        return '<span class="nulo">—</span>'
    if isinstance(v, bool):
        return _badge("Sí", "ok") if v else _badge("No", "mute")
    if c in ("status", "estado"):
        return _badge(v, _TONO_ESTADO.get(str(v).lower(), "mute"))
    if isinstance(v, datetime):
        return _e(v.strftime("%d/%m/%Y %H:%M"))
    if isinstance(v, date):
        return _e(v.strftime("%d/%m/%Y"))
    if _es_numero(v):
        if "stock" in c:
            return _badge(_num(v), "alerta" if v <= 0 else "aviso" if v <= 5 else "ok")
        if "pct" in c or "percent" in c:
            return f"{_num(v)}%"
        if any(k in c for k in _DINERO):
          return _e(_formato_cop(v))
        return _num(v)
    s = str(v)
    return _e(s if len(s) <= 80 else s[:77] + "…")


def _etiqueta_col(c):
    return _e(str(c).replace("_", " "))


def _valores_fila(columnas, fila):
    if isinstance(fila, dict):
        valores = {str(clave).lower(): valor for clave, valor in fila.items()}
        return tuple(valores.get(str(columna).lower()) for columna in columnas)
    if isinstance(fila, (list, tuple)):
        return tuple(fila[i] if i < len(fila) else None for i in range(len(columnas)))
    return (fila, *(None for _ in columnas[1:]))


def tabla_html(columnas, filas, limite=100, titulo=None):
    """Tabla estilizada (solo lectura) con badges de estado y stock."""
    if not filas:
        return '<div class="dt"><div class="dt-vacio">Sin resultados.</div></div>'
    filas = [_valores_fila(columnas, fila) for fila in filas]
    cab = "".join(f'<th class="{"num" if _es_numero(filas[0][i]) else ""}">{_etiqueta_col(c)}</th>' for i, c in enumerate(columnas))
    cuerpo = "".join(
        "<tr>" + "".join(f'<td class="{"num" if _es_numero(v) else ""}">{_celda(c, v)}</td>' for c, v in zip(columnas, fila)) + "</tr>"
        for fila in filas[:limite]
    )
    n = len(filas)
    pie = f"{n} resultado{'s' if n != 1 else ''}" + (f" · mostrando {limite}" if n > limite else "")
    return (
        f'<div class="dt"><div class="dt-cab"><b>{_e(titulo or "Resultado")}</b><span class="sp">{pie}</span></div>'
        f'<div class="dt-scroll"><table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table></div></div>'
    )


def _es_cliente(columnas):
    bajos = [c.lower() for c in columnas]
    return "email" in bajos and ("name" in bajos or "nombre" in bajos)


def _tarjeta_cliente(columnas, fila):
    d = {c.lower(): (c, v) for c, v in zip(columnas, fila)}
    nombre = str((d.get("name") or d.get("nombre"))[1] or _SIN_NOMBRE)
    email = d["email"][1]
    iniciales = "".join(p[0] for p in nombre.split()[:2]).upper() or "?"
    vip = d.get("isvip", (None, False))[1]
    badges = [_badge("VIP", "vip") if vip else _badge("Cliente", "mute")]
    if d.get("active", (None, None))[1] is True:
        badges.append(_badge("Activo", "ok"))
    ocultos = {"name", "nombre", "email", "isvip", "id", "active"}
    datos = "".join(f"<dt>{_etiqueta_col(c)}</dt><dd>{_celda(c, v)}</dd>" for k, (c, v) in d.items() if k not in ocultos)
    return (
        f'<div class="ucard"><div class="ucard-top"><div class="ucard-av">{_e(iniciales)}</div>'
        f'<div><div class="ucard-nom">{_e(nombre)}</div><div class="ucard-mail">{_e(email or "—")}</div></div></div>'
        f'<div class="ucard-bd">{"".join(badges)}</div>' + (f"<dl>{datos}</dl>" if datos else "") + "</div>"
    )


def _tarjeta_proveedor(columnas, fila):
    d = {c.lower(): (c, v) for c, v in zip(columnas, fila)}
    nombre = str((d.get("name") or d.get("nombre") or (None, _SIN_NOMBRE))[1] or _SIN_NOMBRE)
    email = d.get("email", (None, None))[1]
    iniciales = "".join(p[0] for p in nombre.split()[:2]).upper() or "?"
    activo = d.get("active", (None, None))[1]
    badge = ""
    if activo is True:
        badge = _badge("Activo", "ok")
    elif activo is False:
        badge = _badge("Inactivo", "mute")
    campos = ("contact", "phone", "address", "notes")
    datos = "".join(
        f"<dt>{_etiqueta_col(d[c][0])}</dt><dd>{_celda(d[c][0], d[c][1])}</dd>"
        for c in campos if c in d and d[c][1] is not None
    )
    return (
      f'<article class="ucard"><header class="ucard-top"><span class="ucard-av">{_e(iniciales)}</span>'
      f'<span class="ucard-info"><span class="ucard-nom">{_e(nombre)}</span><span class="ucard-mail">{_e(email or "—")}</span></span></header>'
      f'<section class="ucard-bd">{badge}</section>' + (f"<dl>{datos}</dl>" if datos else "") + "</article>"
    )


def _es_resumen_proveedor(columnas):
    claves = {c.lower() for c in columnas}
    return bool(claves & {"proveedor", "supplier"}) and bool(claves & {"productos", "cantidad_productos", "total_productos"})


def _tarjeta_resumen_proveedor(columnas, fila):
    d = {c.lower(): (c, v) for c, v in zip(columnas, fila)}
    nombre = str((d.get("proveedor") or d.get("supplier") or (None, _SIN_NOMBRE))[1] or _SIN_NOMBRE)
    cantidad = next((d[k][1] for k in ("cantidad_productos", "total_productos", "productos") if k in d), 0)
    iniciales = "".join(p[0] for p in nombre.split()[:2]).upper() or "?"
    etiqueta = "producto" if cantidad == 1 else "productos"
    return (
        f'<article class="ucard"><header class="ucard-top"><span class="ucard-av">{_e(iniciales)}</span>'
        f'<span class="ucard-info"><span class="ucard-nom">{_e(nombre)}</span>'
        '<span class="ucard-mail">Proveedor del inventario</span></span></header>'
        f'<section class="ucard-productos"><strong>{_e(_num(cantidad))}</strong><span>{etiqueta}</span></section></article>'
    )


def tarjeta_resultado(columnas, filas, titulo=None, query=None):
    """Tarjetas de cliente/proveedor para resultados cortos; tabla estilizada para el resto."""
    filas = [_valores_fila(columnas, fila) for fila in filas]
    tabla = re.search(r"\bFROM\s+(\S+)", query or "", re.IGNORECASE)
    fuente = tabla.group(1).strip('"').rsplit(".", 1)[-1].strip('"').lower() if tabla else ""
    if filas and 1 <= len(filas) <= 4 and fuente == "suppliers":
        renderizar = _tarjeta_resumen_proveedor if _es_resumen_proveedor(columnas) else _tarjeta_proveedor
        return '<section class="ucards">' + "".join(renderizar(columnas, f) for f in filas) + "</section>"
    if filas and 1 <= len(filas) <= 4 and fuente != "suppliers" and _es_cliente(columnas):
        return '<div class="ucards">' + "".join(_tarjeta_cliente(columnas, f) for f in filas) + "</div>"
    return tabla_html(columnas, filas, titulo=titulo)


def datos_modificados(query, parametros):
    """Pares (campo, valor) que escribe un INSERT/UPDATE, para mostrarlos en la tarjeta de acción."""
    params = list(parametros or [])
    pares = []
    m = re.search(r"INSERT\s+INTO\s+\S+\s*\(([^)]+)\)\s*VALUES\s*\((.*)\)", query, re.IGNORECASE | re.DOTALL)
    if m:
        cols = [c.strip().strip('"') for c in m.group(1).split(",")]
        vals = [v.strip() for v in m.group(2).split(",")]
        i = 0
        for c, v in zip(cols, vals):
            if "%s" in v and i < len(params):
                pares.append((c, params[i]))
                i += 1
        return pares
    m = re.search(r"\bSET\s+(.*?)(?:\s+WHERE\s+(.*?))?;?\s*$", query, re.IGNORECASE | re.DOTALL)
    if m:
        i = 0
        for campo, valor in re.findall(r'"?(\w+)"?\s*=\s*([^,]+)', m.group(1)):
            n = valor.count("%s")
            if n and i < len(params):
                pares.append((campo, params[i] if n == 1 else " ".join(map(str, params[i:i + n]))))
            i += n
        for campo in re.findall(r'(\w+)"?\)?\s*(?:=|ILIKE|LIKE)\s*(?:LOWER\()?%s', m.group(2) or "", re.IGNORECASE):
            if i < len(params):
                pares.append((f"donde {campo}", params[i]))
            i += 1
    return pares


_ACCION_TONO = {"INSERT": ("Creado", "ok"), "UPDATE": ("Actualizado", "info"), "DELETE": ("Eliminado", "alerta")}


def tarjeta_accion(accion, tabla, afectadas, pares):
    """Resumen de una escritura en la BD con mini tabla de los campos modificados."""
    texto, tono = _ACCION_TONO.get(accion, ("Ejecutado", "mute"))
    filas = f"{afectadas} fila(s)" if afectadas not in (None, -1) else ""
    cab = f'<div class="dt-cab">{_badge(texto, tono)}<b>{_e(tabla)}</b><span class="sp">{_e(filas)}</span></div>'
    if not pares:
        return f'<div class="dt">{cab}</div>'
    cuerpo = "".join(f"<tr><td>{_etiqueta_col(c)}</td><td>{_celda(c, v)}</td></tr>" for c, v in pares)
    return f'<div class="dt dt-act">{cab}<table><tbody>{cuerpo}</tbody></table></div>'


# ---------- SQL con resaltado de sintaxis ----------
_KW = (
    "SELECT|FROM|WHERE|AND|OR|NOT|IN|IS|NULL|LIKE|ILIKE|BETWEEN|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|AS|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|"
    "INSERT|INTO|VALUES|UPDATE|SET|DELETE|DISTINCT|UNION|ALL|CASE|WHEN|THEN|ELSE|END|DESC|ASC|RETURNING|EXISTS|INTERVAL|TRUE|FALSE|WITH|CURRENT_DATE"
)
_SQL_TOKEN = re.compile(
    r"(?P<com>--[^\n]*)|(?P<str>'(?:[^']|'')*')|(?P<id>\"[^\"]*\")|(?P<ph>%s)|(?P<num>\b\d+(?:\.\d+)?\b)"
    rf"|(?P<kw>\b(?:{_KW})\b)|(?P<fn>\b\w+(?=\())",
    re.IGNORECASE,
)


def sql_resaltado(query, parametros=None):
    """Bloque SQL con colores rojo/gris y los parámetros como chips."""
    texto = re.sub(r"\n\s*\n+", "\n", str(query).strip())
    salida, pos = [], 0
    for m in _SQL_TOKEN.finditer(texto):
        salida.append(_e(texto[pos:m.start()]))
        salida.append(f'<span class="sql-{m.lastgroup}">{_e(m.group())}</span>')
        pos = m.end()
    salida.append(_e(texto[pos:]))
    chips = ""
    if parametros:
        items = "".join(f"<span><b>&#36;{i}</b> = {_e(repr(p) if isinstance(p, str) else p)}</span>" for i, p in enumerate(parametros, 1))
        chips = f'<div class="sqlparams">{items}</div>'
    return f'<div class="sqlbox"><div class="sqlcode">{"".join(salida)}</div>{chips}</div>'


# ---------- Reproductor de audio con forma de onda ----------
_REPRODUCTOR = """
<style>
html, body { margin: 0; background: transparent; font-family: __FUENTE__, system-ui, sans-serif; }
.p { display: flex; align-items: center; gap: 12px; box-sizing: border-box; height: 56px; padding: 0 14px 0 9px; background: __PANEL__;
     border: 1px solid __BORDE__; border-radius: __RADIO__px; box-shadow: inset 0 0 22px rgba(__AC_RGB__,.07); }
button { width: 38px; height: 38px; flex: none; border-radius: 50%; border: 0; cursor: pointer; display: grid; place-items: center; color: __ON__;
         background: __GRAD__; box-shadow: 0 0 14px rgba(__AC_RGB__,.5); transition: transform .15s; }
button:hover { transform: scale(1.07); } button:active { transform: scale(.94); }
canvas { flex: 1; height: 36px; min-width: 0; cursor: pointer; }
span { color: __MUTED__; font-size: 12px; font-variant-numeric: tabular-nums; min-width: 66px; text-align: right; }
</style>
<div class="p"><button id="b" aria-label="Reproducir"><svg id="i" width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2.5v11l9-5.5z"/></svg></button>
<canvas id="c"></canvas><span id="t">0:00</span></div>
<audio id="a" preload="metadata"></audio>
<script>
const B64 = "__B64__", MIME = "__MIME__", N = 64;
const a = document.getElementById('a'), cv = document.getElementById('c'), ctx = cv.getContext('2d'), t = document.getElementById('t'), ic = document.getElementById('i');
const bin = atob(B64), bytes = new Uint8Array(bin.length);
for (let k = 0; k < bin.length; k++) bytes[k] = bin.charCodeAt(k);
a.src = URL.createObjectURL(new Blob([bytes], {type: MIME}));
let peaks = Array.from({length: N}, (_, k) => .25 + .55 * Math.abs(Math.sin(k * 1.7) * Math.cos(k * .53)));
const fmt = s => isFinite(s) ? Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0') : '0:00';
function draw() {
  const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  cv.width = w * dpr; cv.height = h * dpr; ctx.scale(dpr, dpr); ctx.clearRect(0, 0, w, h);
  const p = a.duration ? a.currentTime / a.duration : 0, step = w / N, bw = Math.max(2, step * .56);
  peaks.forEach((v, k) => {
    const bh = Math.max(3, v * h);
    ctx.fillStyle = k / N < p ? '__AC__' : '__BARRA__';
    ctx.beginPath(); ctx.roundRect(k * step + (step - bw) / 2, (h - bh) / 2, bw, bh, bw / 2); ctx.fill();
  });
  t.textContent = fmt(a.currentTime) + ' / ' + fmt(a.duration);
}
function loop() { draw(); if (!a.paused) requestAnimationFrame(loop); }
document.getElementById('b').onclick = () => a.paused ? a.play() : a.pause();
a.onplay = () => { ic.innerHTML = '<path d="M3.5 2h3.2v12H3.5zM9.3 2h3.2v12H9.3z"/>'; loop(); };
a.onpause = () => { ic.innerHTML = '<path d="M4 2.5v11l9-5.5z"/>'; draw(); };
a.onended = () => { a.currentTime = 0; draw(); };
a.onloadedmetadata = draw;
cv.onclick = e => { if (a.duration) { a.currentTime = e.offsetX / cv.clientWidth * a.duration; draw(); } };
new ResizeObserver(draw).observe(cv);
try {
  new (window.AudioContext || window.webkitAudioContext)().decodeAudioData(bytes.buffer.slice(0)).then(buf => {
    const d = buf.getChannelData(0), size = Math.floor(d.length / N), out = [];
    for (let k = 0; k < N; k++) { let m = 0; for (let j = k * size; j < (k + 1) * size; j++) m = Math.max(m, Math.abs(d[j])); out.push(m); }
    const mx = Math.max(...out) || 1; peaks = out.map(v => .12 + .88 * v / mx); draw();
  }).catch(() => {});
} catch (e) {}
draw();
</script>
"""

ALTO_REPRODUCTOR = 62


def reproductor_html(ruta, t=None):
    """HTML autocontenido (para components.html) con play/pausa, onda del color del tema y barra de progreso."""
    t = t or temas.resolver(temas.DEFECTO)
    with open(ruta, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = "audio/wav" if str(ruta).lower().endswith(".wav") else "audio/mpeg"
    reemplazos = {
        "__B64__": b64, "__MIME__": mime, "__FUENTE__": f"'{t['fuente']}'", "__PANEL__": t["panel"], "__BORDE__": t["borde"],
        "__RADIO__": str(t["r_sm"] + 2), "__AC_RGB__": temas._triple(t["acento"]), "__ON__": t["on_ac"], "__GRAD__": t["grad"],
        "__MUTED__": t["muted"], "__AC__": t["ac_vivo"], "__BARRA__": temas.mezclar(t["panel"], t["acento"], .3),
    }
    salida = _REPRODUCTOR
    for k, v in reemplazos.items():
        salida = salida.replace(k, v)
    return salida


# ---------- Estado del asistente de voz ----------
_VOZ_CLASE = {"saludando": "habla", "comando": "escucha", "procesando": "escucha", "enviado": "ok", "error": "error"}


def voz_estado_html(estado, detalle):
    """Pastilla fija con lo que hace el asistente de voz (vacía si está apagado)."""
    if estado == "apagado":
        return ""
    return f'<div class="voz-estado voz-{_VOZ_CLASE.get(estado, "espera")}"><i></i><span>{_e(detalle)}</span></div>'

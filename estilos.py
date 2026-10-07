"""Estilos de la interfaz del agente (chat oscuro con acento rojo CROVN)."""

CSS_BASE = """
<style>
:root {
  --rojo: #ff0025;
  --rojo-suave: rgba(255, 0, 37, .12);
  --bg: #0e0e0f;
  --panel: #161617;
  --panel-2: #1d1d1f;
  --borde: #2a2a2d;
  --texto: #ececee;
  --muted: #9a9aa2;
  --ancho: 760px;
}
.stApp { --sb: 0px; background: var(--bg); }
.stApp:has([data-testid="stSidebar"][aria-expanded="true"]) { --sb: 336px; }

@keyframes subir { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes flotar {
  0%, 100% { transform: translateY(0) rotate(-3deg); }
  50%      { transform: translateY(-14px) rotate(3deg); }
}
@keyframes onda { 0% { transform: scale(1); opacity: .8; } 100% { transform: scale(1.75); opacity: 0; } }
@keyframes latido { 0%, 100% { box-shadow: 0 0 22px rgba(255,0,37,.45); } 50% { box-shadow: 0 0 40px rgba(255,0,37,.85); } }
@keyframes ecualizador { 0%, 100% { transform: scaleY(.25); } 50% { transform: scaleY(1); } }
@keyframes respirar { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }

/* ---------- Estructura ---------- */
[data-testid="stHeader"] { background: transparent; }
footer, [data-testid="stAppDeployButton"] { display: none !important; }
[data-testid="stMainBlockContainer"], [data-testid="stBottomBlockContainer"] {
  max-width: var(--ancho) !important; padding-left: 1.25rem; padding-right: 1.25rem;
}
[data-testid="stMainBlockContainer"] { padding-top: 2.2rem; padding-bottom: 9rem; }
[data-testid="stBottom"] > div { background: linear-gradient(180deg, transparent, var(--bg) 45%); }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: var(--panel); border-right: 1px solid var(--borde); }
.marca { display: flex; align-items: center; gap: .75rem; margin: .2rem 0 1rem; }
.marca-icono {
  width: 38px; height: 38px; border-radius: 12px; display: grid; place-items: center; font-size: 1.2rem;
  background: linear-gradient(135deg, #ff4d63, #ff0025 55%, #9d0017); box-shadow: 0 6px 18px rgba(255,0,37,.38);
}
.marca b { display: block; letter-spacing: .16em; font-size: 1.05rem; line-height: 1.1; }
.marca small { color: var(--muted); font-size: .72rem; letter-spacing: .04em; }
.seccion { color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .12em; margin: 1.1rem 0 .35rem; }
.estado-bd { display: flex; align-items: center; gap: .5rem; font-size: .82rem; color: var(--muted); margin-bottom: .6rem; }
.estado-bd i { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px #22c55e; }
.estado-bd.error i { background: var(--rojo); box-shadow: 0 0 8px var(--rojo); }

/* ---------- Botones ---------- */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 12px; border: 1px solid var(--borde); background: var(--panel-2); color: var(--texto);
  transition: border-color .18s, background .18s, transform .18s, box-shadow .18s;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  border-color: rgba(255,0,37,.6); background: rgba(255,0,37,.08); color: #fff; transform: translateY(-1px);
}
button[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #ff2a47, #ff0025); border: none; color: #fff; box-shadow: 0 8px 20px rgba(255,0,37,.28);
}
button[data-testid="stBaseButton-primary"]:hover { background: linear-gradient(135deg, #ff4560, #ff1a3a); }
[data-testid="stSidebar"] button[data-testid="stBaseButton-tertiary"] {
  justify-content: flex-start; text-align: left; border: none; background: transparent; color: var(--muted); border-radius: 10px;
}
[data-testid="stSidebar"] button[data-testid="stBaseButton-tertiary"]:hover { background: rgba(255,255,255,.06); color: var(--texto); transform: none; }
[data-testid="stSidebar"] button[data-testid="stBaseButton-tertiary"] p { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
[data-testid="stExpander"] { border: 1px solid var(--borde); border-radius: 14px; background: var(--panel); }
[data-testid="stAlert"] { border-radius: 14px; }

/* ---------- Bienvenida ---------- */
.bienvenida { text-align: center; padding: 5vh 0 1.8rem; animation: subir .6s ease both; }
.bienvenida .hola { color: var(--rojo); font-weight: 600; letter-spacing: .08em; font-size: .85rem; text-transform: uppercase; }
.bienvenida h1 {
  font-size: 2.2rem; font-weight: 700; letter-spacing: -.02em; margin: .4rem 0 .6rem; padding: 0;
  background: linear-gradient(180deg, #fff, #b9b9c1); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.bienvenida p { color: var(--muted); max-width: 500px; margin: 0 auto; line-height: 1.55; }
.st-key-tarjetas { animation: subir .7s ease .1s both; }
.st-key-tarjetas button {
  height: auto; min-height: 76px; padding: 1rem 1.1rem; border-radius: 16px; background: var(--panel);
  justify-content: flex-start; text-align: left;
}
.st-key-tarjetas button:hover { box-shadow: 0 10px 28px rgba(255,0,37,.12); }

/* ---------- Mensajes ---------- */
.cabecera { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; padding-bottom: .7rem; border-bottom: 1px solid var(--borde); }
.cabecera span { font-weight: 600; }
.cabecera em { font-style: normal; font-size: .75rem; color: var(--muted); border: 1px solid var(--borde); border-radius: 999px; padding: .15rem .65rem; }
.msg-usuario { display: flex; justify-content: flex-end; margin: 1.2rem 0 .5rem; animation: subir .3s ease both; }
.msg-usuario .burbuja {
  max-width: 78%; background: var(--panel-2); border: 1px solid var(--borde); padding: .7rem 1rem;
  border-radius: 18px 18px 4px 18px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere;
}
[data-testid="stChatMessage"] { background: transparent; padding: .4rem 0; gap: .9rem; animation: subir .35s ease both; }
[data-testid^="stChatMessageAvatar"] {
  background: linear-gradient(135deg, #ff4d63, #ff0025 55%, #9d0017) !important; border-radius: 12px;
  box-shadow: 0 4px 14px rgba(255,0,37,.35); width: 36px; height: 36px;
}
[data-testid="stDataFrame"] { border: 1px solid var(--borde); border-radius: 14px; overflow: hidden; }
[data-testid="stChatMessage"] [data-testid="stCaptionContainer"] { color: var(--muted); font-size: .72rem; }
audio { width: 100%; height: 38px; border-radius: 999px; }

/* ---------- Campo de escritura ---------- */
[data-testid="stChatInput"] {
  border-radius: 22px; border: 1px solid var(--borde); background: var(--panel);
  box-shadow: 0 12px 34px rgba(0,0,0,.5); transition: border-color .2s, box-shadow .2s;
}
[data-testid="stChatInput"]:focus-within {
  border-color: rgba(255,0,37,.75); box-shadow: 0 0 0 3px rgba(255,0,37,.16), 0 12px 34px rgba(0,0,0,.55);
}
[data-testid="stChatInput"] textarea { padding-left: 3.4rem !important; }
[data-testid="stChatInputSubmitButton"] { background: var(--rojo); color: #fff; border-radius: 12px; }

/* ---------- Micrófono (izquierda del campo) ---------- */
.st-key-mic_grabar {
  position: fixed; bottom: 33px; z-index: 1000; width: auto;
  left: calc(var(--sb) + max(30px, (100vw - var(--sb)) / 2 - var(--ancho) / 2 + 30px));
}
.st-key-mic_grabar button {
  position: relative; width: 38px; height: 38px; min-height: 0; padding: 0; border-radius: 50%;
  background: var(--rojo-suave); border: 1px solid rgba(255,0,37,.35); color: #ff6b81;
  transition: transform .2s, background .2s, color .2s, box-shadow .2s;
}
.st-key-mic_grabar button:hover { color: #fff; background: var(--rojo); transform: scale(1.1); box-shadow: 0 6px 18px rgba(255,0,37,.45); }
.st-key-mic_grabar button:active { transform: scale(.94); }
.st-key-mic_grabar button::after {
  content: ""; position: absolute; inset: -1px; border-radius: 50%; border: 2px solid rgba(255,0,37,.6);
  opacity: 0; pointer-events: none;
}
.st-key-mic_grabar button:hover::after { animation: onda 1.1s ease-out infinite; }
.stApp:has(.grabando) .st-key-mic_grabar button {
  background: var(--rojo); color: #fff; border-color: transparent; animation: latido 1.2s ease-in-out infinite, respirar 1.2s ease-in-out infinite;
}
.stApp:has(.grabando) .st-key-mic_grabar button::after { opacity: 1; animation: onda 1.4s ease-out infinite; }

/* Barra de grabación sobre el campo */
.grabando { position: fixed; left: var(--sb); right: 0; bottom: 92px; z-index: 999; display: flex; justify-content: center; pointer-events: none; }
.grabando-barra {
  display: flex; align-items: center; gap: .8rem; width: min(calc(var(--ancho) - 2.5rem), calc(100vw - var(--sb) - 2.5rem));
  padding: .55rem 3.4rem .55rem 1rem; border-radius: 16px; background: var(--panel); border: 1px solid rgba(255,0,37,.45);
  box-shadow: 0 10px 30px rgba(0,0,0,.5), 0 0 0 3px rgba(255,0,37,.1); color: var(--texto); font-size: .88rem; animation: subir .25s ease both;
}
.grabando-barra small { color: var(--muted); margin-left: auto; font-size: .75rem; }
.ecualizador { display: flex; align-items: center; gap: 3px; height: 22px; }
.ecualizador i { width: 3px; height: 100%; border-radius: 2px; background: var(--rojo); transform-origin: center; animation: ecualizador .9s ease-in-out infinite; }
.ecualizador i:nth-child(2) { animation-delay: .12s; } .ecualizador i:nth-child(3) { animation-delay: .24s; }
.ecualizador i:nth-child(4) { animation-delay: .36s; } .ecualizador i:nth-child(5) { animation-delay: .48s; } .ecualizador i:nth-child(6) { animation-delay: .6s; }
.st-key-mic_cancelar { position: fixed; bottom: 97px; z-index: 1001; width: auto; right: calc(max(20px, (100vw - var(--sb)) / 2 - var(--ancho) / 2 + 20px) + 1.25rem); }
.st-key-mic_cancelar button { width: 32px; height: 32px; min-height: 0; padding: 0; border-radius: 50%; background: var(--panel-2); color: var(--muted); border: 1px solid var(--borde); }
.st-key-mic_cancelar button:hover { color: #fff; border-color: rgba(255,0,37,.6); background: var(--rojo-suave); transform: rotate(90deg); }

/* ---------- Calavera flotante (derecha del chat) ---------- */
.craneo-flotante {
  position: fixed; top: 54vh; z-index: 50; width: 84px; height: 84px; border-radius: 50%;
  right: max(16px, calc((100vw - var(--sb)) / 2 - var(--ancho) / 2 - 120px));
  display: grid; place-items: center; font-size: 2.6rem; user-select: none; cursor: default;
  background: radial-gradient(circle at 30% 25%, #ff5b70, #ff0025 55%, #8f0016);
  animation: flotar 3.2s ease-in-out infinite, latido 3.2s ease-in-out infinite;
}
.craneo-flotante::after { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(255,0,37,.7); animation: onda 2.4s ease-out infinite; }
.craneo-flotante span { filter: drop-shadow(0 3px 5px rgba(0,0,0,.45)); }
.craneo-flotante em {
  position: absolute; right: 100%; margin-right: 12px; white-space: nowrap; font-style: normal; font-size: .78rem; color: var(--texto);
  background: var(--panel-2); border: 1px solid var(--borde); padding: .35rem .7rem; border-radius: 10px;
  opacity: 0; transform: translateX(6px); transition: opacity .2s, transform .2s; pointer-events: none;
}
.craneo-flotante:hover em { opacity: 1; transform: none; }
</style>
"""


def estilos_chat_activo(indice):
    """Resalta el chat seleccionado en la lista lateral."""
    return (
        f"<style>.st-key-chat_{indice} button{{background:var(--rojo-suave)!important;color:#fff!important;"
        f"box-shadow: inset 2px 0 0 var(--rojo);}}</style>"
    )


def craneo_flotante():
    return '<div class="craneo-flotante"><span>💀</span><em>Pregúntame sobre tu tienda</em></div>'

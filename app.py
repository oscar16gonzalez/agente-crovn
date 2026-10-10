import os
import json
import tempfile
import time as _time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import streamlit as st
import streamlit.components.v1 as components
from gtts import gTTS

from database import ejecutar_consulta, init_db, seed_db, asegurar_categoria
from stt_module import transcribir_audio
import html
from agent import generar_consulta, redactar_respuesta, ejecutar_consulta_hibrida, reiniciar_sesion, obtener_sesion
from contexto_app import TABLAS, sugerencias, SessionContext, IntentType
import informes as _inf
import temas
from estilos import (
    CSS_BASE, ALTO_REPRODUCTOR, estilos_chat_activo, marca_html, estado_bd_html, bienvenida_html,
    cabecera_html, opcion_ia_html, tarjeta_resultado, tarjeta_accion, datos_modificados, sql_resaltado, reproductor_html, voz_estado_html,
)

_tema_guardado = temas.cargar()
st.set_page_config(page_title="CROVN Agente", page_icon=_tema_guardado["icono"], layout="wide")

CLAVES_TEMA = ("preset", "acento", "acento2", "fondo", "texto", "degradado", "fuente", "radio", "ancho", "fondo_estilo", "brillo", "animaciones", "icono")
if "t_preset" not in st.session_state:
    _p = temas.PRESETS[_tema_guardado["preset"]]
    for _k in CLAVES_TEMA:
        st.session_state[f"t_{_k}"] = _tema_guardado[_k]
    for _k, _v in (("acento", _p["acento"]), ("fondo", _p["fondo"]), ("texto", _p["texto"]), ("acento2", _p.get("acento2") or temas.resolver({"preset": _tema_guardado["preset"]})["acento2"])):
        st.session_state[f"t_{_k}"] = st.session_state[f"t_{_k}"] or _v
    st.session_state.t_degradado = bool(_p.get("degradado", False)) if st.session_state.t_degradado is None else st.session_state.t_degradado

TEMA_CFG = {k: st.session_state[f"t_{k}"] for k in CLAVES_TEMA}
if TEMA_CFG != _tema_guardado:
    temas.guardar(TEMA_CFG)
TEMA = temas.resolver(TEMA_CFG)
ICONO = TEMA["icono"]
st.markdown(temas.css_tema(TEMA), unsafe_allow_html=True)
st.markdown(CSS_BASE, unsafe_allow_html=True)

from api_client import get_api_client, set_api_token
from streamlit_cookies_controller import CookieController

api = get_api_client()
cookie_controller = CookieController(key="auth_cookie_controller")
cookie_secure = (st.context.url or "").startswith("https://")
cookie_values = cookie_controller.getAll()
if not isinstance(cookie_values, dict):
    cookie_values = {}
if "api_token" not in st.session_state:
    st.session_state.api_token = None

if not st.session_state.api_token and cookie_values.get("crovn_auth_token"):
    cookie_token = cookie_values["crovn_auth_token"]
    set_api_token(cookie_token)

    async def verificar_sesion():
        return await api._request("GET", "/api/auth/me")

    loop = asyncio.new_event_loop()
    try:
        validacion = loop.run_until_complete(verificar_sesion())
    finally:
        loop.close()
    if validacion.ok:
        usuario = (validacion.data or {}).get("user", {})
        st.session_state.api_token = cookie_token
        st.session_state.api_user = usuario.get("name", usuario.get("username", "admin"))
    elif (validacion.error or "").startswith("HTTP 401"):
        cookie_controller.remove("crovn_auth_token", secure=cookie_secure)
        set_api_token(None)
    else:
        st.session_state.login_error = "No se pudo verificar la sesión. Comprueba la conexión e inténtalo de nuevo."

if not st.session_state.api_token:
    if st.session_state.pop("clear_login_password", False):
        st.session_state.login_password = ""
    st.markdown("""
    <style>
    [data-testid="stSidebar"], .craneo-flotante { display: none !important; }
    [data-testid="stMainBlockContainer"] { max-width: 1060px !important; min-height: 88vh; display: flex; align-items: center; }
    .st-key-login-shell { width: 100%; }
    .st-key-login-shell [data-testid="stHorizontalBlock"] { align-items: center; gap: clamp(2rem, 8vw, 7rem); }
    .login-intro { max-width: 440px; padding: 1rem 0; }
    .login-intro .marca { margin-bottom: 3rem; }
    .login-eyebrow { color: var(--ac-vivo); font-size: .72rem; font-weight: 600; text-transform: uppercase; letter-spacing: .16em; }
    .login-intro h1 { color: var(--texto); font-size: clamp(2.4rem, 5vw, 4rem); line-height: 1.04; margin: .8rem 0 1rem; }
    .login-intro p { color: var(--muted); font-size: 1rem; line-height: 1.75; max-width: 390px; }
    .st-key-login_panel { background: var(--panel); border: 1px solid var(--borde); border-radius: var(--r-lg); padding: clamp(1.4rem, 3vw, 2.2rem); box-shadow: 0 24px 70px rgba(var(--sombra-rgb), calc(var(--sa) * 1.4)); }
    .st-key-login_panel h2 { color: var(--texto); font-size: 1.45rem; margin: 0 0 .35rem; }
    .st-key-login_panel [data-testid="stMarkdownContainer"] p { color: var(--muted); }
    .st-key-login_panel [data-testid="stForm"] { border: 0; padding: 0; }
    .st-key-login_panel [data-testid="stTextInput"] input { min-height: 2.8rem; color: var(--texto) !important; background: var(--inset) !important; border-color: var(--borde) !important; }
    .st-key-login_panel [data-testid="stTextInput"] input::placeholder { color: var(--muted) !important; opacity: 1; -webkit-text-fill-color: var(--muted); }
    .st-key-login_panel .login-security { color: var(--tenue); font-size: .76rem; margin-top: 1rem; text-align: center; }
    @media (max-width: 720px) {
      [data-testid="stMainBlockContainer"] { min-height: auto; display: block; padding-top: 8vh; }
      .st-key-login-shell [data-testid="stHorizontalBlock"] { gap: 1rem; }
      .login-intro { padding: 0 0 .5rem; }
      .login-intro .marca { margin-bottom: 1.7rem; }
      .login-intro h1 { font-size: 2.35rem; }
      .login-intro p { font-size: .9rem; }
    }
    </style>
    """, unsafe_allow_html=True)
    with st.container(key="login-shell"):
        intro, acceso = st.columns([1.1, .9], gap="large")
        with intro:
            st.markdown(marca_html(ICONO), unsafe_allow_html=True)
            st.markdown(
                '<div class="login-intro"><div class="login-eyebrow">CENTRO DE GESTIÓN</div>'
                '<h1>Asistente Inteligente de Ventas.</h1>'
                '<p>Gestiona inventario, clientes, ordenes en tiempo real y atiende a tus necesidades desde una sola consola..</p></div>',
                unsafe_allow_html=True,
            )
        with acceso, st.container(key="login_panel"):
            st.markdown('<h2>Bienvenido de nuevo</h2><p>Inicia sesión para abrir tu asistente.</p>', unsafe_allow_html=True)
            with st.form("login_form"):
                auth_user = st.text_input("Usuario", placeholder="Tu usuario", autocomplete="username", key="login_username")
                auth_pass = st.text_input("Contraseña", type="password", placeholder="Tu contraseña", autocomplete="current-password", key="login_password")
                enviar_login = st.form_submit_button("Entrar al chat", type="primary", icon=":material/arrow_forward:", use_container_width=True)
            if enviar_login:
                if not auth_user or not auth_pass:
                    st.session_state.login_error = "Escribe tu usuario y contraseña para continuar."
                else:
                    async def do_login():
                        return await api._request("POST", "/api/auth/login", json={"username": auth_user, "password": auth_pass})
                    loop = asyncio.new_event_loop()
                    try:
                        resp = loop.run_until_complete(do_login())
                    finally:
                        loop.close()
                    if resp.ok and resp.data and resp.data.get("token"):
                        st.session_state.api_token = resp.data["token"]
                        st.session_state.api_user = resp.data.get("user", {}).get("name", auth_user)
                        st.session_state.login_error = None
                        if isinstance(cookie_controller.getAll(), dict):
                            cookie_controller.set(
                                "crovn_auth_token", st.session_state.api_token,
                                expires=datetime.now() + timedelta(hours=12),
                                secure=cookie_secure, same_site="strict",
                            )
                        set_api_token(st.session_state.api_token)
                        st.rerun()
                    else:
                        st.session_state.login_error = resp.error or "No se pudo iniciar sesión. Revisa tus credenciales."
                if st.session_state.get("login_error"):
                    st.session_state.clear_login_password = True
                    st.rerun()
            if st.session_state.get("login_error"):
                st.error(st.session_state.login_error)
            st.markdown('<div class="login-security">Acceso privado · sesión protegida</div>', unsafe_allow_html=True)
    st.stop()

VOZ_FILE = os.path.join(os.path.dirname(__file__), "config_voz.json")
VOZ_DEFECTO = {"activo": True, "asistente": "hey Jarvis", "usuario": "Oscar", "voz": "Automática"}


def cargar_voz():
    try:
        with open(VOZ_FILE, encoding="utf-8") as f:
            return {**VOZ_DEFECTO, **json.load(f)}
    except (OSError, ValueError):
        return dict(VOZ_DEFECTO)


def guardar_voz(cfg):
    try:
        with open(VOZ_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"No se pudo guardar la configuración de voz: {e}")


if "voz_activo" not in st.session_state:
    _cfg_voz = cargar_voz()
    st.session_state.update(voz_activo=_cfg_voz["activo"], voz_asistente=_cfg_voz["asistente"], voz_usuario=_cfg_voz["usuario"], voz_voz=_cfg_voz["voz"])

HISTORIAL_FILE = os.path.join(os.path.dirname(__file__), "historial.json")

ETIQUETAS_CORTAS = {"ollama": "Ollama", "groq": "Groq", "openai": "OpenAI"}
PROMPT_BALANCE_SEMANAL = "Balance semanal"
ICONO_BALANCE_SEMANAL = ":material/summarize:"

INFORMES_SUGERIDOS = [
    (PROMPT_BALANCE_SEMANAL, ICONO_BALANCE_SEMANAL),
    ("Balance de la semana pasada", ":material/history:"),
    ("Balance del mes", ":material/calendar_month:"),
    ("Informe por stock en Excel", ":material/inventory:"),
    ("Balance por categoría", ":material/category:"),
    ("Envía el balance semanal a correo@dominio.com", ":material/forward_to_inbox:"),
    ("Sugiere nuevos avisos", ":material/campaign:"),
    ("Sugiere códigos promocionales", ":material/sell:"),
]

CHAT_NUEVO = "Nuevo chat"

def _chat_vacio(titulo=CHAT_NUEVO):
    return {"titulo": titulo, "mensajes": []}


def crear_chat():
    st.session_state.chats.append(_chat_vacio())
    st.session_state.chat_activo = len(st.session_state.chats) - 1
    st.session_state.historial = chat_actual()["mensajes"]
    st.session_state.sugerencia_activa = None
    reiniciar_sesion()
    guardar_chats()


def cargar_chats():
    try:
        if os.path.exists(HISTORIAL_FILE):
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Formato nuevo: lista de chats
            if isinstance(data, list) and data and isinstance(data[0], dict) and "mensajes" in data[0]:
                return data
            # Formato viejo: una sola lista de mensajes -> migrar
            if isinstance(data, list):
                return [{"titulo": "Chat anterior", "mensajes": data}]
    except Exception:
        pass
    return [_chat_vacio()]


def guardar_chats():
    try:
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.chats, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        st.warning(f"No se pudo guardar el historial: {e}")


if "chats" not in st.session_state:
    st.session_state.chats = cargar_chats()
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = 0
if "procesando_audio" not in st.session_state:
    st.session_state.procesando_audio = None
if "grabando" not in st.session_state:
    st.session_state.grabando = False
    st.session_state.stream = None
    st.session_state.frames = []


def chat_actual():
    idx = st.session_state.chat_activo
    if idx >= len(st.session_state.chats):
        idx = 0
        st.session_state.chat_activo = 0
    return st.session_state.chats[idx]


def _reconstruir_sesion_desde_historial(mensajes: list):
    """Reconstruye el contexto de sesión del agente a partir del historial del chat."""
    from agent import obtener_sesion
    from contexto_app import IntentType, clasificar_intencion
    
    sesion = obtener_sesion()
    # Reiniciar sesión limpia
    sesion.messages = []
    sesion.last_intent = None
    sesion.last_entities = {}
    sesion.active_topic = None
    sesion.pending_confirmation = None
    
    # Reprocesar últimos 10 mensajes para reconstruir contexto
    for msg in mensajes[-10:]:
        if msg.get("comando"):
            # Clasificar intención del mensaje histórico
            intent_result = clasificar_intencion(msg["comando"], sesion)
            sesion.add_message("user", msg["comando"], intent_result.intent, intent_result.entities)
        if msg.get("respuesta"):
            sesion.add_message("assistant", msg["respuesta"])


# Compatibilidad: historial = mensajes del chat activo
st.session_state.historial = chat_actual()["mensajes"]

# Una consulta interrumpida (botón Detener u otra interacción) queda registrada en el chat
if st.session_state.get("consulta_en_curso"):
    st.session_state.historial.append({"comando": st.session_state.consulta_en_curso, "respuesta": "Consulta detenida.", "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
    st.session_state.consulta_en_curso = None
    guardar_chats()

# ---------- Sidebar ----------
import agent as _agent
import voz_local


@st.cache_resource
def obtener_escucha():
    return voz_local.EscuchaVoz()


escucha = obtener_escucha()
escucha.configurar(st.session_state.voz_activo, st.session_state.voz_asistente, st.session_state.voz_usuario, st.session_state.voz_voz, _agent.TTS_LENTO)


@st.fragment(run_every=1.5)
def panel_voz():
    """Muestra el estado de la escucha y envía al chat lo que se dicte tras la palabra de activación."""
    escucha.chat_clave = id(chat_actual())
    comando = escucha.siguiente()
    st.markdown(voz_estado_html(escucha.estado, escucha.detalle), unsafe_allow_html=True)
    if comando:
        st.session_state.sugerencia_activa = comando
        st.rerun()


panel_voz()


def _miles(n):
    return f"{n:,}".replace(",", ".")


def _aplicar_preset():
    """Al elegir un estilo base, los selectores de color se reinician a sus valores."""
    clave = st.session_state.t_preset
    p = temas.PRESETS[clave]
    st.session_state.update(
        t_acento=p["acento"], t_fondo=p["fondo"], t_texto=p["texto"],
        t_acento2=temas.resolver({"preset": clave})["acento2"], t_degradado=bool(p.get("degradado", False)),
    )


def _restablecer_tema():
    st.session_state.update({f"t_{k}": v for k, v in temas.DEFECTO.items()})
    _aplicar_preset()


def panel_tema():
    st.selectbox("Estilo base", list(temas.PRESETS), key="t_preset", format_func=lambda k: temas.PRESETS[k]["nombre"], on_change=_aplicar_preset)
    st.caption(temas.PRESETS[st.session_state.t_preset]["detalle"])
    st.markdown(temas.vista_previa_html(TEMA), unsafe_allow_html=True)
    st.selectbox("Icono del asistente", temas.ICONOS, key="t_icono")


def pintar_tokens():
    """Tokens que faltan (cuota por minuto del proveedor, si la informa) y tokens usados."""
    uso = _agent.obtener_uso()
    with panel_tokens.container():
        limite, restantes = uso["limite_tokens"], uso["restantes_tokens"]
        if limite and restantes is not None:
            st.progress(max(0.0, min(1.0, restantes / limite)), text=f"Tokens restantes: {_miles(restantes)} de {_miles(limite)}")
            renueva = f" · se renuevan en {uso['reset_tokens']}" if uso.get("reset_tokens") else ""
            st.caption(f"Cuota por minuto{renueva}")
            if uso["restantes_peticiones"] is not None and uso["limite_peticiones"]:
                st.caption(f"Peticiones restantes: {_miles(uso['restantes_peticiones'])} de {_miles(uso['limite_peticiones'])}")
        elif _agent.PROVEEDOR == "ollama":
            st.caption("Tokens restantes: sin límite (modelo local).")
        else:
            st.caption("Tokens restantes: se mostrarán tras la primera consulta.")
        if uso["total"]:
            st.caption(f"Última consulta: {_miles(uso['entrada'])} de entrada + {_miles(uso['salida'])} de salida · Total desde que inició la app: {_miles(uso['total'])}")


bd_ok = True
with st.sidebar:
    st.markdown(marca_html(ICONO), unsafe_allow_html=True)
    try:
        from database import get_connection
        conn = get_connection()
        conn.close()
    except Exception:
        bd_ok = False
    st.markdown(estado_bd_html(bd_ok), unsafe_allow_html=True)
    if not bd_ok:
        st.caption("Revisa NEON_DATABASE_URL en .env")

    if st.button(CHAT_NUEVO, icon=":material/add:", type="primary", use_container_width=True):
        crear_chat()
        st.rerun()

    st.markdown('<div class="seccion">Chats recientes</div>', unsafe_allow_html=True)
    for i, c in enumerate(st.session_state.chats):
        if st.button(c["titulo"], key=f"chat_{i}", icon=":material/chat_bubble_outline:", type="tertiary", use_container_width=True):
            if i != st.session_state.chat_activo:
                st.session_state.chat_activo = i
                st.session_state.historial = chat_actual()["mensajes"]
                # Reconstruir contexto de sesión del agente desde el historial
                _reconstruir_sesion_desde_historial(chat_actual()["mensajes"])
                st.rerun()
    st.markdown(estilos_chat_activo(st.session_state.chat_activo), unsafe_allow_html=True)

    col_vaciar, col_eliminar = st.columns(2)
    if col_vaciar.button("Vaciar", icon=":material/cleaning_services:", help="Borra los mensajes de este chat", use_container_width=True):
        chat_actual()["mensajes"] = []
        st.session_state.historial = chat_actual()["mensajes"]
        reiniciar_sesion()
        guardar_chats()
        st.rerun()
    if col_eliminar.button("Eliminar", icon=":material/delete:", help="Elimina este chat", disabled=len(st.session_state.chats) <= 1, use_container_width=True):
        st.session_state.chats.pop(st.session_state.chat_activo)
        st.session_state.chat_activo = 0
        st.session_state.historial = chat_actual()["mensajes"]
        reiniciar_sesion()
        guardar_chats()
        st.rerun()

    st.markdown('<div class="seccion">Ajustes de IA</div>', unsafe_allow_html=True)
    with st.expander("Modelo y voz", icon=":material/tune:"):
        claves = list(_agent.PROVEEDORES)
        st.session_state.setdefault("proveedor_modelo", _agent.PROVEEDOR)
        prov = st.segmented_control(
            "Conexión al modelo", claves, key="proveedor_modelo", label_visibility="collapsed",
            format_func=lambda p: ETIQUETAS_CORTAS[p],
        ) or _agent.PROVEEDOR
        if prov != _agent.PROVEEDOR:
            _agent.set_proveedor(prov)
        st.markdown(
            opcion_ia_html(_agent.PROVEEDORES[prov]["etiqueta"], "Modelo local: sin costo por token y sin enviar datos a internet." if prov == "ollama" else "Modelo en la nube: requiere API key."),
            unsafe_allow_html=True,
        )

        cache_modelos = st.session_state.setdefault("modelos_cache", {})
        if prov == "ollama":
            modelos, error = _agent.listar_modelos()
        else:
            etiqueta = _agent.PROVEEDORES[prov]["etiqueta"]
            hay_clave = bool(_agent.obtener_api_key(prov))
            nueva = st.text_input(
                f"API key de {etiqueta}", type="password", key=f"apikey_{prov}",
                placeholder="Guardada · pega otra para reemplazarla" if hay_clave else "Pega tu API key",
            )
            recordar = st.checkbox("Recordar en .env", key=f"recordar_{prov}", help="Se guarda en texto plano en este equipo (el archivo .env no se sube a git).")
            if st.button("Guardar y conectar", icon=":material/key:", key=f"conectar_{prov}", use_container_width=True):
                try:
                    if nueva:
                        _agent.set_api_key(prov, nueva, recordar)
                    cache_modelos.pop(prov, None)
                except ValueError as e:
                    st.error(str(e))
            if _agent.obtener_api_key(prov) and prov not in cache_modelos:
                with st.spinner(f"Conectando con {etiqueta}..."):
                    cache_modelos[prov] = _agent.listar_modelos()
            modelos, error = cache_modelos.get(prov, ([], None))
            if not hay_clave and not nueva:
                st.info(f"Ingresa tu API key de {etiqueta} para usar este modelo en la nube.")
            st.caption("Los datos de tu consulta y el esquema de la BD se envían a este proveedor.")

        if error:
            st.error(error if prov != "ollama" else "No se pudo listar modelos. ¿Ollama está corriendo?")
        elif modelos:
            sel = st.selectbox("Modelo", modelos, index=modelos.index(_agent.MODELO) if _agent.MODELO in modelos else 0, key=f"modelo_{prov}")
            if sel != _agent.MODELO:
                _agent.set_modelo(sel)
                st.success(f"Modelo cambiado a {sel}")
        panel_tokens = st.empty()
        pintar_tokens()
        ritmo = st.select_slider("Velocidad de lectura (TTS)", options=["Normal", "Lenta"], value="Lenta" if _agent.TTS_LENTO else "Normal")
        _agent.set_tts_lento(ritmo == "Lenta")
        if st.button("Verificar base de datos", icon=":material/database:", use_container_width=True):
            init_db()
            st.success("Tablas verificadas.")

    with st.expander("Activación por voz", icon=":material/record_voice_over:"):
        st.checkbox("Escuchar la palabra de activación", key="voz_activo", help="Usa el micrófono del equipo y Whisper local: no depende del navegador ni de internet.")
        st.text_input("Palabra de activación", key="voz_asistente", placeholder="hey Jarvis", help="Lo que dices para llamarlo: un nombre o una frase corta, por ejemplo «hey Jarvis» u «oye Crovn». Evita palabras comunes.")
        st.text_input("Tu nombre", key="voz_usuario", help="Con este nombre te saluda.")
        voces = voz_local.voces_sistema()
        if voces:
            etiquetas = {v: v for v, _ in voces}
            opciones_voz = [voz_local.VOZ_AUTO, *etiquetas]
            if st.session_state.voz_voz not in opciones_voz:
                st.session_state.voz_voz = voz_local.VOZ_AUTO
            st.selectbox(
                "Voz del asistente", opciones_voz, key="voz_voz",
                format_func=lambda v: "Automática" if v == voz_local.VOZ_AUTO else etiquetas[v],
                help="Automática: saludo con voz del sistema y respuestas con Google (en línea). Una voz concreta se usa para ambos, sin internet. La velocidad se ajusta en Modelo y voz.",
            )
            if st.button("Probar voz", icon=":material/play_circle:", key="voz_probar", use_container_width=True):
                voz_local.hablar(f"Hola {st.session_state.voz_usuario}, así suena mi voz.".replace("Hola ,", "Hola,"), st.session_state.voz_voz, _agent.TTS_LENTO)
        else:
            st.session_state.voz_voz = voz_local.VOZ_AUTO
            st.caption("Este equipo no tiene voces del sistema disponibles: se usa la voz automática.")
        st.caption(f"Di «{st.session_state.voz_asistente or 'hey Jarvis'}», espera el saludo y dicta tu consulta.")
        voz_actual = {"activo": st.session_state.voz_activo, "asistente": st.session_state.voz_asistente, "usuario": st.session_state.voz_usuario, "voz": st.session_state.voz_voz}
        if voz_actual != cargar_voz():
            guardar_voz(voz_actual)

    st.markdown('<div class="seccion">Herramientas</div>', unsafe_allow_html=True)
    with st.expander("Informes y marketing", icon=":material/monitoring:"):
        st.caption("Se calculan sin usar el modelo (0 tokens). Puedes indicar fechas, hojas y un correo de destino.")
        for s, icono in INFORMES_SUGERIDOS:
            if st.button(s, key=f"inf_{s}", icon=icono, type="tertiary", use_container_width=True):
                st.session_state.sugerencia_activa = s

    st.markdown('<div class="seccion">Módulos DB</div>', unsafe_allow_html=True)
    MODULOS = {"Clientes": "customers", "Inventario": "products", "Ventas": "orders", "Más": None}
    modulo = st.segmented_control("Módulo", list(MODULOS), default="Inventario", key="modulo_db", label_visibility="collapsed")
    tabla_sel = MODULOS.get(modulo or "Inventario")
    if tabla_sel is None:
        otras = {d["etiqueta"]: t for t, d in TABLAS.items() if t not in MODULOS.values()}
        tabla_sel = otras[st.selectbox("Tabla / tema", list(otras), label_visibility="collapsed")]
    st.caption(f"{TABLAS[tabla_sel]['descripcion']}  \n**Puedes:** {TABLAS[tabla_sel]['operaciones']}")
    for s, escribe in sugerencias(tabla_sel):
        icono = ":material/edit:" if escribe else ":material/search:"
        if st.button(s, key=f"sug_{tabla_sel}_{s}", icon=icono, type="tertiary", use_container_width=True):
            st.session_state.sugerencia_activa = s

    with st.container(key="sidebar_footer"):
        st.markdown('<div class="seccion">Sesión</div>', unsafe_allow_html=True)
        st.caption(f"Conectado como {st.session_state.get('api_user', 'admin')}")
        if st.button("Cerrar sesión", icon=":material/logout:", key="logout", use_container_width=True):
            st.session_state.api_token = None
            st.session_state.api_user = None
            st.session_state.login_error = None
            st.session_state.clear_login_password = True
            if isinstance(cookie_controller.getAll(), dict) and cookie_controller.get("crovn_auth_token"):
                cookie_controller.remove("crovn_auth_token", secure=cookie_secure)
            set_api_token(None)
            st.rerun()

with st.container(key="quick_actions"), st.popover(ICONO, help="Acciones rápidas"):
    st.markdown("**Acciones rápidas**")
    if st.button("Inventario", icon=":material/inventory_2:", key="quick_inventory", use_container_width=True):
        st.session_state.sugerencia_activa = "¿qué productos tenemos en el inventario?"
        st.rerun()
    if st.button("Generar balance semanal", icon=ICONO_BALANCE_SEMANAL, key="quick_weekly_balance", use_container_width=True):
        st.session_state.sugerencia_activa = PROMPT_BALANCE_SEMANAL
        st.rerun()
    if st.button("Listado de órdenes", icon=":material/receipt_long:", key="quick_orders_list", use_container_width=True):
        st.session_state.sugerencia_activa = "Listado de órdenes pendientes"
        st.rerun()
    if st.button(CHAT_NUEVO, icon=":material/add:", key="quick_new_chat", use_container_width=True):
        crear_chat()
        st.rerun()

# ---------- Chat ----------
FECHA_FMT = "%d/%m/%Y %H:%M:%S"


with st.expander(
    f"Apariencia · {temas.PRESETS[TEMA_CFG['preset']]['nombre']}",
    icon=":material/palette:",
):
    panel_tema()


def burbuja_usuario(texto):
    st.markdown(f'<div class="msg-usuario"><div class="burbuja">{html.escape(texto)}</div></div>', unsafe_allow_html=True)


texto_entrada = st.chat_input("Escribe tu consulta o pulsa el micrófono...")
entrada_pendiente = bool(texto_entrada or st.session_state.get("sugerencia_activa") or st.session_state.procesando_audio)

TARJETAS = [
    (":material/inventory_2:", "Productos sin stock"),
    (":material/receipt_long:", "Listado de órdenes pendientes"),
    (":material/trending_up:", "Productos más vendidos"),
    (":material/sell:", "Códigos de promoción activos"),
    (ICONO_BALANCE_SEMANAL, PROMPT_BALANCE_SEMANAL),
    (":material/campaign:", "Sugiere nuevos avisos"),
]

if not st.session_state.historial and not entrada_pendiente:
    st.markdown(bienvenida_html(ICONO), unsafe_allow_html=True)
    with st.container(key="tarjetas"):
        cols = st.columns(2)
        for n, (icono, pregunta) in enumerate(TARJETAS):
            if cols[n % 2].button(pregunta, key=f"tarjeta_{n}", icon=icono, use_container_width=True):
                st.session_state.sugerencia_activa = pregunta
                st.rerun()
else:
    st.markdown(
        cabecera_html(chat_actual()["titulo"], _agent.PROVEEDORES[_agent.PROVEEDOR]["etiqueta"], _agent.MODELO, bd_ok),
        unsafe_allow_html=True,
    )

for n_msg, msg in enumerate(st.session_state.historial):
    burbuja_usuario(msg["comando"])
    with st.chat_message("assistant", avatar=ICONO):
        if msg.get("tarjeta"):
            st.markdown(msg["tarjeta"], unsafe_allow_html=True)
        if msg["respuesta"]:
            st.markdown(msg["respuesta"])
        if msg.get("archivo") and os.path.exists(msg["archivo"]):
            with open(msg["archivo"], "rb") as f_xlsx:
                st.download_button("Descargar Excel", f_xlsx.read(), file_name=os.path.basename(msg["archivo"]), mime=_inf.MIME_XLSX,
                                   icon=":material/download:", key=f"dl_hist_{st.session_state.chat_activo}_{n_msg}", on_click="ignore")
        if msg.get("audio") and os.path.exists(msg["audio"]):
            components.html(reproductor_html(msg["audio"], TEMA), height=ALTO_REPRODUCTOR)
        if msg.get("fecha"):
            st.caption(msg["fecha"])
        if msg.get("sql"):
            with st.expander("Ver SQL generado", icon=":material/code:"):
                st.markdown(sql_resaltado(msg["sql"], msg.get("parametros")), unsafe_allow_html=True)


zona_detener = st.empty()


def esperar_modelo(fn, *args):
    """Ejecuta una llamada al modelo en un hilo; el botón Detener la aborta al instante."""
    _agent.reiniciar_cancelacion()
    st.session_state["_n_esperas"] = st.session_state.get("_n_esperas", 0) + 1
    with zona_detener.container():
        st.button("Detener", key=f"detener_{st.session_state['_n_esperas']}", icon=":material/stop_circle:", help="Detener la consulta")
    estado = st.empty()
    pool = ThreadPoolExecutor(max_workers=1)
    futuro = pool.submit(fn, *args)
    inicio = _time.time()
    try:
        while not futuro.done():
            estado.caption(f"Pensando… {int(_time.time() - inicio)} s")
            _time.sleep(0.4)
    except BaseException:
        _agent.cancelar()
        raise
    finally:
        pool.shutdown(wait=False)
        try:
            estado.empty()
            zona_detener.empty()
        except BaseException:
            pass
    return futuro.result()


def _guardar_mensaje(texto, respuesta, **extra):
    st.session_state.historial.append({"comando": texto, "respuesta": respuesta, "fecha": datetime.now().strftime(FECHA_FMT), **extra})
    guardar_chats()


def _dinero(v):
    return f"${v:,.0f}".replace(",", ".")


def _mostrar_informe(informe, hojas):
    r = informe["resumen"]
    st.markdown(f"**Balance · {informe['etiqueta']}**")
    c = st.columns(3)
    c[0].metric("Órdenes", r["ordenes"])
    c[1].metric("Unidades vendidas", r["unidades_vendidas"], help="Órdenes procesadas, enviadas o entregadas")
    c[2].metric("Ingresos", _dinero(r["ingresos"]), help="Después de descuentos; sin contar órdenes pendientes")
    c = st.columns(4)
    c[0].metric("Pendientes", r["pendientes"])
    c[1].metric("En curso", r["en_curso"], help="Procesadas + enviadas")
    c[2].metric("Entregadas", r["entregadas"])
    c[3].metric("Ticket promedio", _dinero(r["ticket"]))
    for tab, h in zip(st.tabs(list(hojas)), hojas):
        with tab:
            df = informe["hojas"][h]
            if len(df):
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.caption("Sin datos en este período.")


def _responder_informe(texto):
    """Balance/informe con Excel y envío opcional por correo, sin usar el modelo. True si la petición era de este tipo."""
    pedido = _inf.detectar_informe(texto)
    if pedido is None:
        return False
    if "error" in pedido:
        st.warning(pedido["error"])
        _guardar_mensaje(texto, pedido["error"])
        return True
    if pedido["falta_correo"]:
        aviso = "Para enviar el balance por correo necesito **el correo de destino**. Ejemplo: `envía el balance semanal a correo@dominio.com`."
        st.markdown(aviso)
        _guardar_mensaje(texto, aviso)
        return True
    inicio, fin, etiqueta = pedido["periodo"]
    try:
        with st.spinner("Calculando el balance..."):
            informe = _inf.datos_balance(inicio, fin, etiqueta=etiqueta)
            excel = _inf.construir_excel(informe, pedido["hojas"])
            ruta = _inf.guardar_excel(excel, inicio, fin)
    except Exception as e:
        st.error(f"No se pudo generar el balance: {e}")
        _guardar_mensaje(texto, f"No se pudo generar el balance: {e}")
        return True
    _mostrar_informe(informe, pedido["hojas"])
    r = informe["resumen"]
    respuesta = (f"📊 **Balance {etiqueta}**: {r['ordenes']} órdenes · {r['unidades_vendidas']} unidades vendidas · ingresos {_dinero(r['ingresos'])}. "
                 f"Pendientes: {r['pendientes']} · En curso: {r['en_curso']} · Entregadas: {r['entregadas']}.")
    if pedido["correo"]:
        from email_module import enviar_informe
        cuerpo_txt, cuerpo_html = _inf.cuerpo_correo(informe, pedido["hojas"])
        with st.spinner(f"Enviando el balance a {pedido['correo']}..."):
            ok, msg = enviar_informe(pedido["correo"], f"Balance CROVN · {etiqueta}", cuerpo_txt, cuerpo_html, ruta)
        respuesta += f"\n\n{'✅' if ok else '❌'} {msg}"
    st.markdown(respuesta)
    st.download_button("Descargar Excel", excel, file_name=os.path.basename(ruta), mime=_inf.MIME_XLSX, icon=":material/download:",
                       key=f"dl_{os.path.basename(ruta)}", on_click="ignore")
    _guardar_mensaje(texto, respuesta, archivo=ruta)
    return True


def _responder_ideas(texto):
    """Avisos y códigos promocionales sugeridos con los datos de la tienda. True si la petición era de este tipo."""
    tipo = _inf.detectar_sugerencia(texto)
    if tipo is None:
        return False
    try:
        with st.spinner("Analizando ventas, inventario y clientes..."):
            ideas = _inf.ideas_marketing(tipo)
    except Exception as e:
        st.error(f"No se pudieron generar sugerencias: {e}")
        _guardar_mensaje(texto, f"No se pudieron generar sugerencias: {e}")
        return True
    if any(i["clase"] == "aviso" for i in ideas):
        ideas = esperar_modelo(_inf.mejorar_textos, ideas, _agent._llamar_modelo)
    st.session_state.ideas_pendientes = ideas
    resumen = _inf.texto_ideas(ideas)
    st.markdown(resumen)
    if ideas:
        st.caption("Pulsa un botón al final del chat para crear la sugerencia; no se crea nada sin que lo pidas.")
    _guardar_mensaje(texto, resumen)
    return True


def _pintar_ideas():
    ideas = st.session_state.get("ideas_pendientes") or []
    if not ideas:
        return
    with st.container(key="ideas"):
        for x in list(ideas):
            etiqueta = f"Crear aviso: {x['titulo']}" if x["clase"] == "aviso" else f"Crear código {x['codigo']} ({x['descuento']}%)"
            if st.button(etiqueta, key=f"idea_{x['id']}", icon=":material/add_circle:", use_container_width=True):
                ok, msg = (_inf.crear_publicacion if x["clase"] == "aviso" else _inf.crear_codigo)(x)
                ideas.remove(x)
                (st.success if ok else st.warning)(msg)
        if ideas and st.button("Descartar sugerencias", key="ideas_descartar", icon=":material/close:", type="tertiary"):
            st.session_state.ideas_pendientes = []
            st.rerun()


def _procesar_comando(texto):
    burbuja_usuario(texto)
    st.session_state.ideas_pendientes = []
    with st.chat_message("assistant", avatar=ICONO):
        if _responder_informe(texto) or _responder_ideas(texto):
            return
        with st.spinner("Pensando..."):
            # Detección de envío de código promocional por correo
            import re as _re
            m_mail = _re.search(r"([\w.+-]+@[\w-]+\.[\w.]+)", texto)
            m_code = _re.search(r"c[oó]digo\s*:?\s*(?!(?:a|al|para|de|del|por|que|el|la|y)\b)([A-Za-z0-9-]+)", texto, _re.IGNORECASE)
            pide_envio = _re.search(r"\b(?:env[ií]a(?:r|le|me|rle)?|env[ií]e|manda(?:r|le|me)?)\b", texto, _re.IGNORECASE) and (m_mail or _re.search(r"c[oó]digo", texto, _re.IGNORECASE))
            if pide_envio and not (m_mail and m_code):
                respuesta = "Para enviar un código por correo necesito **el código** y **el correo** de destino. Ejemplo: `envía el código PROMO45 a cliente@correo.com`."
                st.markdown(respuesta)
                st.session_state.historial.append({"comando": texto, "respuesta": respuesta, "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                guardar_chats()
                return
            if pide_envio:
                codigo = m_code.group(1)
                correo = m_mail.group(1)
                from database import get_connection
                try:
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute('SELECT code, "discountPct", "expiresAt" FROM promo_codes WHERE UPPER(code) = UPPER(%s) LIMIT 1;', (codigo,))
                    fila = cur.fetchone()
                    cur.close(); conn.close()
                except Exception as e:
                    fila = None
                    st.error(str(e))
                if fila:
                    from email_module import enviar_codigo_promocional
                    ok, msg = enviar_codigo_promocional(correo, fila[0], fila[1], str(fila[2]) if fila[2] else None)
                    if ok:
                        respuesta = "✅ Correo enviado correctamente."
                        st.success(respuesta)
                    else:
                        respuesta = f"❌ {msg}"
                        st.error(respuesta)
                else:
                    respuesta = f"No encontré el código '{codigo}' en promo_codes."
                    st.warning(respuesta)
                st.session_state.historial.append({"comando": texto, "respuesta": respuesta, "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                guardar_chats()
                return
            consulta = esperar_modelo(generar_consulta, _inf.quitar_excel(texto) or texto)
        if "error" in consulta:
            st.error(consulta["error"])
            st.session_state.historial.append({"comando": texto, "respuesta": consulta["error"], "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
            guardar_chats()
            return
        if consulta.get("atajo"):
            st.caption("⚡ Consulta conocida: resuelta sin usar el modelo (0 tokens).")
            # Atajos son solo SELECT simples, ejecutar via SQL directo
            resultado, columnas = ejecutar_consulta(consulta["query"], consulta["parametros"])
        else:
            # Usar motor híbrido para el resto (decide SQL vs API)
            with st.spinner("Ejecutando consulta..."):
                resultado_hibrido = ejecutar_consulta_hibrida(texto, consulta)
            
            if "error" in resultado_hibrido:
                # Reintento automático si falló
                with st.spinner("La consulta falló, corrigiendo automáticamente..."):
                    from agent import corregir_consulta
                    nueva = esperar_modelo(corregir_consulta, texto, consulta, resultado_hibrido["error"])
                if "error" in nueva:
                    st.error(f"Error: {resultado_hibrido['error']}")
                    st.session_state.historial.append({"comando": texto, "respuesta": f"Error: {resultado_hibrido['error']}", "sql": consulta["query"], "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                    guardar_chats()
                    return
                consulta = nueva
                # Reintentar con la consulta corregida
                resultado_hibrido = ejecutar_consulta_hibrida(texto, consulta)
                if "error" in resultado_hibrido:
                    st.error(f"Error: {resultado_hibrido['error']}")
                    st.session_state.historial.append({"comando": texto, "respuesta": f"Error: {resultado_hibrido['error']}", "sql": consulta["query"], "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                    guardar_chats()
                    return
                st.success("Consulta corregida automáticamente ✅")
            
            # Extraer datos del resultado híbrido
            resultado = resultado_hibrido.get("resultado", [])
            columnas = resultado_hibrido.get("columnas", [])
            consulta["query"] = resultado_hibrido.get("query", consulta["query"])
            consulta["parametros"] = resultado_hibrido.get("parametros", consulta.get("parametros", []))
            consulta["accion"] = resultado_hibrido.get("accion", consulta.get("accion", "SELECT"))
            plan_mode = resultado_hibrido.get("plan_mode", "read")
            
            # Mostrar modo de ejecución
            if plan_mode != "read":
                st.caption(f"🔧 Ejecutado via API REST ({plan_mode})")
        with st.expander("Ver SQL generado", icon=":material/code:"):
            st.markdown(sql_resaltado(consulta["query"], consulta.get("parametros")), unsafe_allow_html=True)
        tarjeta = ""
        if consulta["accion"] == "SELECT" and resultado and isinstance(resultado, list) and columnas:
            tarjeta = tarjeta_resultado(columnas, resultado, query=consulta.get("query"))
            st.markdown(tarjeta, unsafe_allow_html=True)
            try:
                st.download_button("Descargar Excel", _inf.excel_de_resultado(resultado, columnas), file_name=f"consulta_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
                                   mime=_inf.MIME_XLSX, icon=":material/download:", key=f"dlq_{len(st.session_state.historial)}", on_click="ignore")
            except Exception:
                pass
        if consulta["accion"] == "SELECT":
            tiene_filas = isinstance(resultado, list) and resultado and columnas
            if tiene_filas:
                respuesta = ""  # La tabla ya muestra los datos; sin texto extra
            else:
                with st.spinner("Redactando respuesta..."):
                    respuesta = esperar_modelo(redactar_respuesta, f"Columnas: {columnas} | Filas: {resultado}", texto)
        else:
            import re
            m = re.search(r"(?:INTO|UPDATE|FROM|DELETE FROM)\s+([\w\"]+)", consulta["query"], re.IGNORECASE)
            tabla = m.group(1).strip('"') if m else "la tabla"
            nombres = {"INSERT": "Se insertó", "UPDATE": "Se actualizó", "DELETE": "Se eliminó"}
            accion = nombres.get(consulta["accion"], "Se ejecutó")
            if resultado is None or resultado == -1:
                respuesta = f"{accion} correctamente en {tabla}."
            else:
                respuesta = f"{accion} correctamente en {tabla} ({resultado} fila(s) afectada(s))."
            # Si fue un INSERT, intentamos mencionar el nombre/dato principal
            if consulta["accion"] == "INSERT" and consulta["parametros"]:
                respuesta += f" Datos: {consulta['parametros']}."
            tarjeta = tarjeta_accion(consulta["accion"], tabla, resultado, datos_modificados(consulta["query"], consulta["parametros"]))
            st.markdown(tarjeta, unsafe_allow_html=True)
        if respuesta:
            st.markdown(respuesta)
        ruta_audio = None
        try:
            if respuesta:
                import agent as _agent
                voz = st.session_state.voz_voz
                if voz != voz_local.VOZ_AUTO:
                    ruta_audio = os.path.join(tempfile.gettempdir(), f"respuesta_{len(st.session_state.historial)}.wav")
                    voz_local.sintetizar(respuesta, ruta_audio, voz, _agent.TTS_LENTO)
                else:
                    tts = gTTS(text=respuesta, lang="es", slow=_agent.TTS_LENTO)
                    ruta_audio = os.path.join(tempfile.gettempdir(), f"respuesta_{len(st.session_state.historial)}.mp3")
                    tts.save(ruta_audio)
                components.html(reproductor_html(ruta_audio, TEMA), height=ALTO_REPRODUCTOR)
        except Exception as e:
            ruta_audio = None
            st.warning(f"Audio no disponible: {e}")
    # Guardar en historial del chat
    mensaje = {
        "comando": texto,
        "respuesta": respuesta,
        "tarjeta": tarjeta,
        "sql": consulta["query"],
        "parametros": consulta.get("parametros"),
        "audio": ruta_audio,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }
    st.session_state.historial.append(mensaje)
    
    # Guardar también en contexto de sesión del agente
    from agent import obtener_sesion
    from contexto_app import clasificar_intencion
    sesion = obtener_sesion()
    # Clasificar intención de la respuesta del asistente (basada en la acción)
    accion = consulta.get("accion", "SELECT")
    intent_map = {
        "SELECT": IntentType.SHOP_QUERY,
        "INSERT": IntentType.PRODUCT_CREATE,
        "UPDATE": IntentType.PRODUCT_UPDATE,
        "DELETE": IntentType.PRODUCT_UPDATE,
        "ADVICE": IntentType.DISCOUNT_ADVICE,  # genérico
    }
    intent_respuesta = intent_map.get(accion, IntentType.GENERAL_CHAT)
    sesion.add_message("assistant", respuesta, intent_respuesta)
    
    if chat_actual()["titulo"] in ("Nuevo chat", "Chat anterior") and len(st.session_state.historial) == 1:
        chat_actual()["titulo"] = texto[:30] + ("..." if len(texto) > 30 else "")
    guardar_chats()


def procesar_comando(texto):
    st.session_state.consulta_en_curso = texto
    try:
        _procesar_comando(texto)
    except Exception:
        st.session_state.consulta_en_curso = None
        raise
    st.session_state.consulta_en_curso = None
    pintar_tokens()


# Sugerencia de chat activa
if st.session_state.get("sugerencia_activa"):
    s = st.session_state.sugerencia_activa
    st.session_state.sugerencia_activa = None
    procesar_comando(s)

# Audio pendiente de procesar
if st.session_state.procesando_audio:
    ruta = st.session_state.procesando_audio
    st.session_state.procesando_audio = None
    with st.spinner("Transcribiendo audio..."):
        texto = transcribir_audio(ruta)
    if texto:
        procesar_comando(texto)
    else:
        st.warning("No se pudo transcribir el audio. Intenta de nuevo.")

# Micrófono: a la izquierda del campo de escritura (posición en estilos.py)
if not st.session_state.grabando:
    if st.button("", key="mic_grabar", icon=":material/mic:", help="Grabar audio"):
        try:
            import sounddevice as sd
        except (ImportError, OSError):
            st.error("Micrófono no disponible: PortAudio no instalado en el servidor")
            st.stop()
        frames_lista = []
        st.session_state.frames = frames_lista
        fs = 16000
        def callback(indata, frames, time, status):
            frames_lista.append(indata.copy())
        try:
            stream = sd.InputStream(samplerate=fs, channels=1, dtype="int16", callback=callback)
            stream.start()
        except Exception as e:
            st.error(f"No se pudo acceder al micrófono: {e}")
        else:
            st.session_state.stream = stream
            st.session_state.fs = fs
            st.session_state.grabando = True
            st.rerun()
else:
    st.markdown(
        '<div class="grabando"><div class="grabando-barra">'
        '<span class="ecualizador"><i></i><i></i><i></i><i></i><i></i><i></i></span>'
        'Grabando... pulsa enviar cuando termines'
        '</div></div>',
        unsafe_allow_html=True,
    )

    def _cerrar_grabacion():
        st.session_state.stream.stop()
        st.session_state.stream.close()
        st.session_state.stream = None
        st.session_state.grabando = False

    if st.button("", key="mic_cancelar", icon=":material/close:", help="Cancelar grabación"):
        _cerrar_grabacion()
        st.session_state.frames = []
        st.rerun()
    if st.button("", key="mic_grabar", icon=":material/send:", help="Enviar audio"):
        import numpy as np
        import scipy.io.wavfile as wav
        _cerrar_grabacion()
        if st.session_state.frames:
            audio = np.concatenate(st.session_state.frames, axis=0)
            ruta = os.path.join(tempfile.gettempdir(), "grabacion_local.wav")
            wav.write(ruta, st.session_state.fs, audio)
            st.session_state.procesando_audio = ruta
        st.rerun()

if texto_entrada:
    procesar_comando(texto_entrada)

_pintar_ideas()

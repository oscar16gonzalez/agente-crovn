import os
import json
import tempfile
from datetime import datetime
import streamlit as st
from gtts import gTTS

from database import ejecutar_consulta, init_db, seed_db, asegurar_categoria
from stt_module import transcribir_audio
import html
from agent import generar_consulta, redactar_respuesta
from contexto_app import TABLAS, sugerencias
from estilos import CSS_BASE, estilos_chat_activo, craneo_flotante

st.set_page_config(page_title="CROVN Agente", page_icon="💀", layout="wide")
st.markdown(CSS_BASE, unsafe_allow_html=True)
st.markdown(craneo_flotante(), unsafe_allow_html=True)

HISTORIAL_FILE = os.path.join(os.path.dirname(__file__), "historial.json")


def _chat_vacio(titulo="Nuevo chat"):
    return {"titulo": titulo, "mensajes": []}


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
            json.dump(st.session_state.chats, f, ensure_ascii=False, indent=2)
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


# Compatibilidad: historial = mensajes del chat activo
st.session_state.historial = chat_actual()["mensajes"]

# ---------- Sidebar ----------
import agent as _agent

with st.sidebar:
    st.markdown(
        '<div class="marca"><div class="marca-icono">💀</div><div><b>CROVN</b><small>Asistente de tienda</small></div></div>',
        unsafe_allow_html=True,
    )
    try:
        from database import get_connection
        conn = get_connection()
        conn.close()
        st.markdown('<div class="estado-bd"><i></i>Base de datos conectada</div>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<div class="estado-bd error"><i></i>Sin conexión a la base de datos</div>', unsafe_allow_html=True)
        st.caption("Revisa NEON_DATABASE_URL en .env")

    if st.button("Nuevo chat", icon=":material/add:", type="primary", use_container_width=True):
        st.session_state.chats.append(_chat_vacio())
        st.session_state.chat_activo = len(st.session_state.chats) - 1
        st.session_state.historial = chat_actual()["mensajes"]
        guardar_chats()
        st.rerun()

    st.markdown('<div class="seccion">Chats</div>', unsafe_allow_html=True)
    for i, c in enumerate(st.session_state.chats):
        if st.button(c["titulo"], key=f"chat_{i}", icon=":material/chat_bubble_outline:", type="tertiary", use_container_width=True):
            if i != st.session_state.chat_activo:
                st.session_state.chat_activo = i
                st.session_state.historial = chat_actual()["mensajes"]
                st.rerun()
    st.markdown(estilos_chat_activo(st.session_state.chat_activo), unsafe_allow_html=True)

    col_vaciar, col_eliminar = st.columns(2)
    if col_vaciar.button("Vaciar", icon=":material/cleaning_services:", help="Borra los mensajes de este chat", use_container_width=True):
        chat_actual()["mensajes"] = []
        st.session_state.historial = chat_actual()["mensajes"]
        guardar_chats()
        st.rerun()
    if col_eliminar.button("Eliminar", icon=":material/delete:", help="Elimina este chat", disabled=len(st.session_state.chats) <= 1, use_container_width=True):
        st.session_state.chats.pop(st.session_state.chat_activo)
        st.session_state.chat_activo = 0
        st.session_state.historial = chat_actual()["mensajes"]
        guardar_chats()
        st.rerun()

    st.markdown('<div class="seccion">Herramientas</div>', unsafe_allow_html=True)
    with st.expander("Ajustes", icon=":material/tune:"):
        import requests as _req
        try:
            modelos = [m["name"] for m in _req.get(os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/tags", timeout=5).json().get("models", [])]
        except Exception:
            modelos = []
        if modelos:
            sel = st.selectbox("Modelo de Ollama", modelos, index=modelos.index(_agent.MODELO) if _agent.MODELO in modelos else 0)
            if sel != _agent.MODELO:
                _agent.set_modelo(sel)
                st.success(f"Modelo cambiado a {sel}")
        else:
            st.warning("No se pudo listar modelos. ¿Ollama está corriendo?")
        st.caption("Modelo 100% local, sin costo por token.")
        ritmo = st.select_slider("Velocidad de lectura (TTS)", options=["Normal", "Lenta"], value="Lenta" if _agent.TTS_LENTO else "Normal")
        _agent.set_tts_lento(ritmo == "Lenta")
        if st.button("Verificar base de datos", icon=":material/database:", use_container_width=True):
            init_db()
            st.success("Tablas verificadas.")

# ---------- Nuevo producto (formulario) ----------
with st.sidebar.expander("Nuevo producto", icon=":material/add_box:"):
    with st.form("form_nuevo_producto"):
        np_nombre = st.text_input("Nombre")
        np_desc = st.text_input("Descripción", value="")
        np_cat = st.text_input("Categoría")
        np_size = st.selectbox("Talla", ["S", "M", "L", "XL", "Única"])
        np_color = st.text_input("Color(es)")
        np_genero = st.multiselect("Género (puedes elegir 1 o las 3)", ["Hombre", "Mujer", "Unisex"], default=["Unisex"])
        np_precio = st.number_input("Precio", min_value=0.0, value=0.0, step=0.5)
        np_stock = st.number_input("Stock", min_value=0, value=0, step=1)
        if st.form_submit_button("Crear producto"):
            if not any([np_nombre, np_desc, np_cat, np_color, np_precio, np_stock]):
                st.error("Completa al menos un campo.")
            else:
                try:
                    from database import get_connection, asegurar_categoria
                    nombre = np_nombre or "Sin nombre"
                    categoria = np_cat or "SIN-CATEGORIA"
                    cat_id = asegurar_categoria(np_cat) if np_cat else None
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute(
                        'INSERT INTO products (name, description, category, "categoryId", size, color, price, stock, genero) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (nombre, np_desc or nombre, categoria, cat_id, np_size, np_color or None, np_precio, np_stock, "/".join(np_genero) or None),
                    )
                    conn.commit(); cur.close(); conn.close()
                    st.success(f"Producto '{nombre}' creado ✅")
                except Exception as e:
                    st.error(f"Error creando producto: {e}")

# ---------- Sugerencias de consultas ----------
with st.sidebar.expander("Sugerencias por tabla", icon=":material/lightbulb:"):
    nombres_tablas = {datos["etiqueta"]: t for t, datos in TABLAS.items()}
    categ = st.selectbox("Tabla / tema:", list(nombres_tablas))
    tabla_sel = nombres_tablas[categ]
    st.caption(f"{TABLAS[tabla_sel]['descripcion']}  \n**Puedes:** {TABLAS[tabla_sel]['operaciones']}")
    for s, escribe in sugerencias(tabla_sel):
        icono = ":material/edit:" if escribe else ":material/search:"
        if st.button(s, key=f"sug_{tabla_sel}_{s}", icon=icono, type="tertiary", use_container_width=True):
            st.session_state.sugerencia_activa = s

# ---------- Chat ----------
FECHA_FMT = "%d/%m/%Y %H:%M:%S"


def burbuja_usuario(texto):
    st.markdown(f'<div class="msg-usuario"><div class="burbuja">{html.escape(texto)}</div></div>', unsafe_allow_html=True)


texto_entrada = st.chat_input("Escribe tu consulta o pulsa el micrófono...")
entrada_pendiente = bool(texto_entrada or st.session_state.get("sugerencia_activa") or st.session_state.procesando_audio)

TARJETAS = [
    (":material/inventory_2:", "Productos sin stock"),
    (":material/receipt_long:", "Listado de órdenes pendientes"),
    (":material/trending_up:", "Productos más vendidos"),
    (":material/sell:", "Códigos de promoción activos"),
]

if not st.session_state.historial and not entrada_pendiente:
    st.markdown(
        '<div class="bienvenida"><div class="hola">Hola</div><h1>¿Qué quieres saber de tu tienda?</h1>'
        '<p>Consulta inventario, órdenes, clientes y promociones con tu voz o escribiendo. '
        'También puedo crear códigos, proveedores y actualizar datos.</p></div>',
        unsafe_allow_html=True,
    )
    with st.container(key="tarjetas"):
        cols = st.columns(2)
        for n, (icono, pregunta) in enumerate(TARJETAS):
            if cols[n % 2].button(pregunta, key=f"tarjeta_{n}", icon=icono, use_container_width=True):
                st.session_state.sugerencia_activa = pregunta
                st.rerun()
else:
    st.markdown(
        f'<div class="cabecera"><span>{html.escape(chat_actual()["titulo"])}</span><em>{html.escape(_agent.MODELO)}</em></div>',
        unsafe_allow_html=True,
    )

for msg in st.session_state.historial:
    burbuja_usuario(msg["comando"])
    with st.chat_message("assistant", avatar="💀"):
        if msg["respuesta"]:
            st.markdown(msg["respuesta"])
        if msg.get("audio") and os.path.exists(msg["audio"]):
            st.audio(msg["audio"], format="audio/mp3")
        if msg.get("fecha"):
            st.caption(msg["fecha"])
        if msg.get("sql"):
            with st.expander("Ver SQL generado", icon=":material/code:"):
                st.code(msg["sql"], language="sql")


def procesar_comando(texto):
    burbuja_usuario(texto)
    with st.chat_message("assistant", avatar="💀"):
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
            consulta = generar_consulta(texto)
        if "error" in consulta:
            st.error(consulta["error"])
            st.session_state.historial.append({"comando": texto, "respuesta": consulta["error"], "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
            guardar_chats()
            return
        with st.spinner("Consultando la base de datos..."):
            import re
            # Verificación de duplicados antes de INSERT
            duplicado = None
            if consulta["accion"] == "INSERT":
                m = re.search(r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)", consulta["query"], re.IGNORECASE)
                if m:
                    tabla_ins, cols_ins = m.group(1), [c.strip().strip('"') for c in m.group(2).split(",")]
                    col_nombre = next((c for c in cols_ins if c.lower() in ("name", "nombre", "title", "cliente", "code")), None)
                    if col_nombre and col_nombre in cols_ins:
                        idx = cols_ins.index(col_nombre)
                        if idx < len(consulta["parametros"]) and str(consulta["parametros"][idx]).lower() not in ("sin nombre", "sin título"):
                            from database import get_connection
                            try:
                                conn = get_connection(); cur = conn.cursor()
                                cur.execute(f'SELECT id FROM "{tabla_ins}" WHERE LOWER("{col_nombre}") = LOWER(%s) LIMIT 1;', (str(consulta["parametros"][idx]),))
                                if cur.fetchone():
                                    duplicado = f'Ya existe un registro en {tabla_ins} con {col_nombre} = "{consulta["parametros"][idx]}". No se creó nada.'
                                cur.close(); conn.close()
                            except Exception as e:
                                print(f"Error verificando duplicado: {e}")
            if duplicado:
                st.warning(duplicado)
                st.session_state.historial.append({"comando": texto, "respuesta": duplicado, "sql": consulta["query"], "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                guardar_chats()
                return
            # Si inserta un producto con categoría, aseguramos que la categoría exista
            if consulta["accion"] == "INSERT" and "products" in consulta["query"] and "categor" in consulta["query"].lower():
                try:
                    mcols = re.search(r"INSERT\s+INTO\s+\w+\s*\(([^)]+)\)", consulta["query"], re.IGNORECASE)
                    cols = [c.strip() for c in mcols.group(1).split(",")] if mcols else []
                    for i, c in enumerate(cols):
                        if "categor" in c.lower() and "id" not in c.lower() and i < len(consulta["parametros"]) and str(consulta["parametros"][i]) != "SIN-CATEGORIA":
                            cat_id = asegurar_categoria(str(consulta["parametros"][i]))
                            if cat_id is not None:
                                for j, c2 in enumerate(cols):
                                    if "categoryId" in c2 and j < len(consulta["parametros"]):
                                        consulta["parametros"][j] = cat_id
                            break
                except Exception as e:
                    print(f"No se pudo asegurar la categoría: {e}")
            resultado, columnas = ejecutar_consulta(consulta["query"], consulta["parametros"])
        if resultado is None and isinstance(columnas, str):
            # Reintento automático: le pasamos el error al modelo para que corrija la query
            with st.spinner("La consulta falló, corrigiendo automáticamente..."):
                from agent import corregir_consulta
                nueva = corregir_consulta(texto, consulta, columnas)
            if "error" in nueva:
                st.error(f"Error SQL: {columnas}")
                st.session_state.historial.append({"comando": texto, "respuesta": f"Error SQL: {columnas}", "sql": consulta["query"], "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                guardar_chats()
                return
            consulta = nueva
            resultado, columnas = ejecutar_consulta(consulta["query"], consulta["parametros"])
            if resultado is None and isinstance(columnas, str):
                st.error(f"Error SQL: {columnas}")
                st.session_state.historial.append({"comando": texto, "respuesta": f"Error SQL: {columnas}", "sql": consulta["query"], "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                guardar_chats()
                return
            st.success("Consulta corregida automáticamente ✅")
        with st.expander("Ver SQL generado"):
            st.json(consulta)
            st.code(consulta["query"], language="sql")
            st.write("Resultado:", resultado)
        if consulta["accion"] == "SELECT" and resultado and isinstance(resultado, list) and columnas:
            import pandas as pd
            try:
                df = pd.DataFrame(resultado, columns=columnas)
                st.dataframe(df, use_container_width=True)
            except Exception:
                pass
        if consulta["accion"] == "SELECT":
            tiene_filas = isinstance(resultado, list) and resultado and columnas
            if tiene_filas:
                respuesta = ""  # La tabla ya muestra los datos; sin texto extra
            else:
                with st.spinner("Redactando respuesta..."):
                    respuesta = redactar_respuesta(f"Columnas: {columnas} | Filas: {resultado}", texto)
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
        if respuesta:
            st.markdown(respuesta)
        ruta_mp3 = None
        try:
            if respuesta:
                import agent as _agent
                tts = gTTS(text=respuesta, lang="es", slow=_agent.TTS_LENTO)
                ruta_mp3 = os.path.join(tempfile.gettempdir(), f"respuesta_{len(st.session_state.historial)}.mp3")
                tts.save(ruta_mp3)
                st.audio(ruta_mp3, format="audio/mp3")
        except Exception as e:
            st.warning(f"Audio no disponible: {e}")
    st.session_state.historial.append({
        "comando": texto,
        "respuesta": respuesta,
        "sql": consulta["query"],
        "audio": ruta_mp3,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    })
    if chat_actual()["titulo"] in ("Nuevo chat", "Chat anterior") and len(st.session_state.historial) == 1:
        chat_actual()["titulo"] = texto[:30] + ("..." if len(texto) > 30 else "")
    guardar_chats()


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
        import sounddevice as sd
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

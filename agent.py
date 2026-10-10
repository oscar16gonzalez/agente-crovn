import http.client
import json
import os
import re
import socket
import ssl
import threading
import urllib.parse
import certifi
import requests
import asyncio
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
if not OLLAMA_URL.endswith("/api/generate"):
    OLLAMA_URL = OLLAMA_URL.rstrip("/") + "/api/generate"
OLLAMA_BASE = OLLAMA_URL[: -len("/api/generate")]

# Groq y OpenAI comparten el formato de la API de OpenAI (/chat/completions).
PROVEEDORES = {
    "ollama": {"etiqueta": "Local (Ollama)", "modelo": "llama3.2:3b"},
    "groq": {"etiqueta": "Groq", "url": "https://api.groq.com/openai/v1", "modelo": "openai/gpt-oss-120b", "env": "GROQ_API_KEY"},
    "openai": {"etiqueta": "OpenAI", "url": "https://api.openai.com/v1", "modelo": "gpt-4o-mini", "env": "OPENAI_API_KEY"},
}
_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_DIR, "config_modelo.json")
ENV_FILE = os.path.join(_DIR, ".env")

PROVEEDOR = "ollama"
MODELO = PROVEEDORES["ollama"]["modelo"]
_MODELOS = {p: c["modelo"] for p, c in PROVEEDORES.items()}
_API_KEYS = {}

TTS_LENTO = False


def _cargar_config():
    global PROVEEDOR, MODELO
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
        _MODELOS.update({p: m for p, m in cfg.get("modelos", {}).items() if p in PROVEEDORES and m})
        if cfg.get("proveedor") in PROVEEDORES:
            PROVEEDOR = cfg["proveedor"]
    except (OSError, ValueError):
        pass
    MODELO = _MODELOS[PROVEEDOR]


def _guardar_config():
    """Guarda proveedor y modelos elegidos (nunca las API keys)."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"proveedor": PROVEEDOR, "modelos": _MODELOS}, f, indent=2)
    except OSError as e:
        print(f"No se pudo guardar la configuración del modelo: {e}")


def set_proveedor(proveedor):
    global PROVEEDOR, MODELO
    PROVEEDOR = proveedor
    MODELO = _MODELOS[proveedor]
    _guardar_config()


def set_modelo(nombre):
    global MODELO
    MODELO = nombre
    _MODELOS[PROVEEDOR] = nombre
    _guardar_config()


def set_tts_lento(v):
    global TTS_LENTO
    TTS_LENTO = v


def obtener_api_key(proveedor):
    return _API_KEYS.get(proveedor) or os.environ.get(PROVEEDORES[proveedor].get("env", ""), "")


def _guardar_en_env(nombre, valor):
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            lineas = f.readlines()
    except FileNotFoundError:
        lineas = []
    nueva = f"{nombre}={valor}\n"
    for i, linea in enumerate(lineas):
        if linea.startswith(f"{nombre}="):
            lineas[i] = nueva
            break
    else:
        if lineas and not lineas[-1].endswith("\n"):
            lineas[-1] += "\n"
        lineas.append(nueva)
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lineas)


def set_api_key(proveedor, clave, recordar=False):
    """Usa la API key en memoria; con recordar=True también la guarda en .env."""
    clave = (clave or "").strip()
    if not re.fullmatch(r"[\w\-.]+", clave):
        raise ValueError("La API key tiene caracteres no válidos (espacios o saltos de línea).")
    _API_KEYS[proveedor] = clave
    if recordar:
        _guardar_en_env(PROVEEDORES[proveedor]["env"], clave)
    return clave


_cargar_config()

from datetime import date
from database import obtener_esquema, completar_insert
from contexto_app import (
    construir_contexto, es_escritura, tablas_con_detalle, atajo_sql, 
    MAPA_TIENDA, TABLAS, IntentType, IntentResult, SessionContext, clasificar_intencion
)

# ============================================================
# GESTIÓN DE SESIÓN (contexto persistente entre mensajes)
# ============================================================

from typing import Optional
_sesion_actual: Optional[SessionContext] = None


def obtener_sesion() -> SessionContext:
    """Obtiene o crea el contexto de sesión actual."""
    global _sesion_actual
    if _sesion_actual is None:
        _sesion_actual = SessionContext()
    return _sesion_actual


def reiniciar_sesion():
    """Reinicia el contexto de sesión (nuevo chat)."""
    global _sesion_actual
    _sesion_actual = SessionContext()

_ESQUEMA_CACHE = None


def _esquema_relevante(esquema, texto):
    """Columnas solo de las tablas pertinentes y las de sus JOIN habituales; el resto va en el mapa de la tienda."""
    lineas = {l[2:].split("(")[0]: l for l in esquema.splitlines() if l.startswith("- ")}
    if not lineas:
        return esquema
    elegidas = tablas_con_detalle(texto)
    return "\n".join(lineas[t] for t in elegidas if t in lineas)


def obtener_system_prompt(texto_usuario=""):
    global _ESQUEMA_CACHE
    if _ESQUEMA_CACHE is None:
        _ESQUEMA_CACHE = obtener_esquema()
    
    # Clasificar intención y obtener contexto de sesión
    sesion = obtener_sesion()
    intent_result = clasificar_intencion(texto_usuario, sesion)
    
    # Guardar intención en sesión
    sesion.add_message("user", texto_usuario, intent_result.intent, intent_result.entities)
    
    escritura = es_escritura(texto_usuario)
    esquema = _esquema_relevante(_ESQUEMA_CACHE, texto_usuario)
    contexto = construir_contexto(texto_usuario, escritura, intent_result, sesion)
    
    # Añadir instrucciones específicas según intención
    intent_instructions = {
        IntentType.PRODUCT_CREATE: "\n⚠️ CREAR PRODUCTO: Genera INSERT en products. Incluye name, category, size, price, stock. Opcional: description, color, genero, supplierId, costPrice, profitPct. NO incluyas categoryId, sku, createdAt, updatedAt. Las imágenes se suben por API multipart.",
        IntentType.PRODUCT_UPDATE: "\n⚠️ ACTUALIZAR PRODUCTO: Genera UPDATE en products con WHERE id = X. Solo campos mencionados. NO actualices categoryId, sku, createdAt.",
        IntentType.PROMOTION_CREATE: "\n⚠️ CREAR PROMOCIÓN (código descuento): Genera INSERT en promo_codes. JSON obligatorio:\n"
            '  {"accion": "INSERT", "query": "INSERT INTO promo_codes (code, \\"discountPct\\", active, \\"maxUses\\", \\"usedCount\\", \\"updatedAt\\") VALUES (%s, %s, true, %s, 0, NOW());", '
            '"parametros": ["CODIGO", 20, null]}\n'
            "- code: MAYÚSCULAS sin espacios (ej: BLACKFRIDAY, NAVIDAD25)\n"
            "- discountPct: 1-90 (ej: 20 = 20%) - OBLIGATORIO, si no lo da el usuario USA 10 COMO DEFAULT\n"
            "- maxUses: null = ilimitado, número = límite (ej: 100)\n"
            "- usedCount: SIEMPRE 0 al crear\n"
            "- active: true\n"
            "- updatedAt: NOW()\n"
            "- Si no da código: omite 'code' de columnas (sistema genera CROVN-XXXXXX)\n"
            "- Si no da maxUses: usa null (ilimitado)\n"
            "- Si no da discountPct: USA 10 COMO VALOR POR DEFECTO",
        IntentType.ORDER_MANAGEMENT: "\n⚠️ GESTIÓN DE PEDIDOS: Cambiar estado con UPDATE orders SET status = '...' WHERE id = X. Estados válidos: 'Pendiente', 'Procesado', 'Enviado', 'Entregado'.",
        IntentType.DISCOUNT_ADVICE: "\n💡 CONSEJO DESCUENTOS: No generes SQL. El sistema usará API/informes para analizar y dar recomendación.",
        IntentType.MARKETING_ADVICE: "\n💡 CONSEJO MARKETING: No generes SQL. El sistema usará informes.ideas_marketing().",
        IntentType.INVENTORY_ADVICE: "\n💡 CONSEJO INVENTARIO: No generes SQL. El sistema analizará stock, rotación, dead stock.",
        IntentType.REPORT_REQUEST: "\n📊 INFORME: No generes SQL. El sistema usará informes.datos_balance() y informes.construir_excel().",
    }
    
    intent_extra = intent_instructions.get(intent_result.intent, "")
    
    if escritura:
        salida = (
            'Responde SOLO un JSON: {"accion": "SELECT|INSERT|UPDATE|DELETE", "query": "...", "parametros": [...]}. '
            "Una sola sentencia con solo tablas y columnas del esquema, sin comillas dobles. Nunca te niegues: da tu mejor consulta.\n"
            "UPDATE y DELETE siempre con WHERE; si no dicen qué fila, usa WHERE id = -1. "
            "Si piden crear un producto con su categoría, genera solo el INSERT del producto (la categoría la crea el sistema).\n"
            'Ejemplo: {"accion": "INSERT", "query": "INSERT INTO products (name, price) VALUES (%s, %s);", "parametros": ["Camiseta Negra", 59900]}'
        )
    else:
        salida = (
            'Responde SOLO un JSON: {"accion": "SELECT", "query": "...", "parametros": []}. '
            "Una sola sentencia con solo tablas y columnas del esquema, sin comillas dobles. Nunca te niegues: da tu mejor consulta."
        )
    
    # Para intenciones de consejo/informe, forzar modo no-escritura
    if intent_result.intent in (IntentType.DISCOUNT_ADVICE, IntentType.MARKETING_ADVICE, IntentType.INVENTORY_ADVICE, IntentType.REPORT_REQUEST):
        salida = (
            'Responde SOLO un JSON: {"accion": "ADVICE", "query": "", "parametros": [], "advice_type": "' + intent_result.intent.value + '"}. '
            "No generes SQL. El motor híbrido manejará la lógica de negocio."
        )
    
    return f"""Eres el asistente de CROVN: conviertes la petición del usuario (texto o voz) en una consulta SQL PostgreSQL exacta sobre el esquema. Hoy es {date.today().isoformat()}.

{MAPA_TIENDA}
## COLUMNAS DE LAS TABLAS PERTINENTES
{esquema}

{contexto}
{intent_extra}

## SALIDA
{salida}
"""

SYSTEM_PROMPT = None  # se construye perezosamente con obtener_system_prompt()


class ConsultaCancelada(Exception):
    pass


_CANCELADO = threading.Event()
_CONEXION = None
_CONTEXTO_SSL = ssl.create_default_context(cafile=certifi.where())
_VACIO_USO = {"entrada": 0, "salida": 0, "total": 0, "limite_tokens": None, "restantes_tokens": None, "reset_tokens": None,
              "limite_peticiones": None, "restantes_peticiones": None, "reset_peticiones": None}
_USO = {p: dict(_VACIO_USO) for p in PROVEEDORES}
_CABECERAS_CUOTA = {
    "limite_tokens": "x-ratelimit-limit-tokens", "restantes_tokens": "x-ratelimit-remaining-tokens", "reset_tokens": "x-ratelimit-reset-tokens",
    "limite_peticiones": "x-ratelimit-limit-requests", "restantes_peticiones": "x-ratelimit-remaining-requests", "reset_peticiones": "x-ratelimit-reset-requests",
}


class _Respuesta:
    def __init__(self, status, datos, cabeceras):
        self.status_code = status
        self.ok = status < 400
        self.text = datos.decode("utf-8", "replace")
        self.headers = cabeceras

    def json(self):
        return json.loads(self.text or "{}")


def cancelar():
    """Aborta la llamada al modelo en curso cerrando su conexión (el servidor deja de generar)."""
    _CANCELADO.set()
    conn = _CONEXION
    if conn is not None and conn.sock is not None:
        try:
            conn.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def reiniciar_cancelacion():
    _CANCELADO.clear()


def _solicitar(metodo, url, cuerpo=None, headers=None, timeout=60):
    """Petición HTTP que cancelar() puede interrumpir mientras espera la respuesta del modelo."""
    global _CONEXION
    partes = urllib.parse.urlsplit(url)
    if partes.scheme == "https":
        conn = http.client.HTTPSConnection(partes.netloc, timeout=timeout, context=_CONTEXTO_SSL)
    else:
        conn = http.client.HTTPConnection(partes.netloc, timeout=timeout)
    _CONEXION = conn
    try:
        if _CANCELADO.is_set():
            raise ConsultaCancelada("Consulta detenida.")
        cabeceras = dict(headers or {})
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode("utf-8")
            cabeceras["Content-Type"] = "application/json"
        conn.connect()
        if _CANCELADO.is_set():
            raise ConsultaCancelada("Consulta detenida.")
        conn.request(metodo, partes.path + (f"?{partes.query}" if partes.query else ""), datos, cabeceras)
        resp = conn.getresponse()
        return _Respuesta(resp.status, resp.read(), {k.lower(): v for k, v in resp.getheaders()})
    except (OSError, http.client.HTTPException) as e:
        if _CANCELADO.is_set():
            raise ConsultaCancelada("Consulta detenida.") from e
        raise
    finally:
        if _CONEXION is conn:
            _CONEXION = None
        conn.close()


def _detalle_error(resp):
    try:
        error = resp.json().get("error")
        return error.get("message", "") if isinstance(error, dict) else str(error)
    except Exception:
        return resp.text[:200]


def _registrar_uso(entrada, salida, cabeceras):
    """Guarda los tokens de la última consulta y la cuota restante que informa el proveedor."""
    uso = _USO[PROVEEDOR]
    uso["entrada"], uso["salida"] = entrada or 0, salida or 0
    uso["total"] += uso["entrada"] + uso["salida"]
    for campo, cabecera in _CABECERAS_CUOTA.items():
        valor = cabeceras.get(cabecera)
        if valor is not None:
            uso[campo] = valor if campo.startswith("reset") else (int(float(valor)) if re.fullmatch(r"\d+(\.\d+)?", valor) else None)


def obtener_uso():
    """Tokens usados y cuota restante (si el proveedor la informa) de la conexión activa."""
    return dict(_USO[PROVEEDOR])


def _pedir_nube(metodo, ruta, cuerpo=None, timeout=60):
    cfg = PROVEEDORES[PROVEEDOR]
    clave = obtener_api_key(PROVEEDOR)
    if not clave:
        raise ValueError(f"Falta la API key de {cfg['etiqueta']}. Ingrésala en Ajustes.")
    resp = _solicitar(metodo.upper(), cfg["url"] + ruta, cuerpo, {"Authorization": f"Bearer {clave}"}, timeout)
    if resp.status_code in (401, 403):
        raise ValueError(f"La API key de {cfg['etiqueta']} no es válida o no tiene permisos.")
    if resp.status_code == 429:
        raise ValueError(f"{cfg['etiqueta']}: límite de uso alcanzado. Intenta de nuevo en unos segundos.")
    if not resp.ok:
        try:
            detalle = resp.json()["error"]["message"]
        except Exception:
            detalle = resp.text[:200]
        raise ValueError(f"{cfg['etiqueta']} respondió {resp.status_code}: {detalle}")
    return resp


_NO_CHAT = ("whisper", "guard", "tts", "transcribe", "embedding", "audio", "realtime", "image", "moderation", "orpheus", "playai", "search")


def listar_modelos():
    """(modelos, error) del proveedor activo; con la nube también valida la API key."""
    try:
        if PROVEEDOR == "ollama":
            datos = requests.get(OLLAMA_BASE + "/api/tags", timeout=5).json()
            return [m["name"] for m in datos.get("models", [])], None
        ids = sorted(m["id"] for m in _pedir_nube("get", "/models").json().get("data", []))
        ids = [i for i in ids if not any(x in i for x in _NO_CHAT)]
        if PROVEEDOR == "openai":
            ids = [i for i in ids if i.startswith("gpt-")]
        return ids, None
    except Exception as e:
        return [], str(e)


def _llamar_modelo(prompt, system=None, json_mode=True, max_tokens=500):
    """Envía el prompt al proveedor activo y devuelve el texto de la respuesta."""
    if PROVEEDOR == "ollama":
        payload = {"model": MODELO, "prompt": prompt, "stream": False, "keep_alive": "10m", "options": {"num_predict": max_tokens, "temperature": 0, "num_ctx": 4096}}
        if json_mode:
            payload["format"] = "json"
        if system:
            payload["system"] = system
        resp = _solicitar("POST", OLLAMA_URL, payload, timeout=600)
        if not resp.ok:
            raise ValueError(f"Ollama respondió {resp.status_code}: {_detalle_error(resp)}")
        datos = resp.json()
        _registrar_uso(datos.get("prompt_eval_count"), datos.get("eval_count"), {})
        return datos.get("response", "").strip()
    razonador = PROVEEDOR == "openai" and MODELO.startswith(("o1", "o3", "o4", "gpt-5"))
    mensajes = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    cuerpo = {"model": MODELO, "messages": mensajes}
    if not razonador:
        cuerpo["temperature"] = 0
    cuerpo["max_completion_tokens" if PROVEEDOR == "openai" else "max_tokens"] = max_tokens * 4 if razonador else max_tokens
    if json_mode:
        cuerpo["response_format"] = {"type": "json_object"}
    resp = _pedir_nube("post", "/chat/completions", cuerpo)
    datos = resp.json()
    uso = datos.get("usage") or {}
    _registrar_uso(uso.get("prompt_tokens"), uso.get("completion_tokens"), resp.headers)
    return (datos["choices"][0]["message"]["content"] or "").strip()


_PROHIBIDO = re.compile(r"\b(DROP|TRUNCATE|ALTER|GRANT|REVOKE|CREATE\s+(TABLE|INDEX|DATABASE|SCHEMA))\b|;\s*\S", re.IGNORECASE)
_TABLAS_PERMITIDAS = None


def validar_consulta(accion, query):
    """Devuelve un mensaje de error si el SQL es peligroso o inválido; None si es aceptable."""
    global _TABLAS_PERMITIDAS
    if _TABLAS_PERMITIDAS is None:
        _TABLAS_PERMITIDAS = set(TABLAS)
    if _PROHIBIDO.search(query):
        return "La consulta contiene operaciones no permitidas."
    if query.count("(") != query.count(")") or re.search(r"([.,(]|\b(?:AND|OR|WHERE|FROM|JOIN|ON|BY|SELECT)\b)\s*;?\s*$", query, re.IGNORECASE):
        return "La consulta generada quedó incompleta."
    if accion in ("UPDATE", "DELETE") and not re.search(r"\bWHERE\b", query, re.IGNORECASE):
        return f"{accion} sin WHERE no está permitido: indica qué registro (id, nombre, código o email)."
    destino = re.search(r"\b(?:INTO|UPDATE|DELETE\s+FROM)\s+\"?(\w+)\"?", query, re.IGNORECASE) if accion != "SELECT" else None
    if destino and destino.group(1).lower() not in _TABLAS_PERMITIDAS:
        return f"La tabla '{destino.group(1)}' no existe en la base de datos."
    if accion == "DELETE" and destino and destino.group(1).lower() not in ("promo_codes", "publications", "suppliers"):
        return f"Eliminar registros de '{destino.group(1)}' se hace desde el panel (restituye stock y borra dependencias)."
    if accion == "INSERT" and destino and destino.group(1).lower() in ("orders", "order_items"):
        return "Las órdenes se crean desde la tienda o el panel (validan y descuentan stock)."
    return None


def _finalizar(accion, query, parametros):
    """Valida la consulta y, si es un INSERT, completa las columnas obligatorias que falten."""
    problema = validar_consulta(accion, query)
    if problema:
        return {"error": problema}
    if accion == "INSERT":
        query, parametros = completar_insert(query, parametros)
    return {"accion": accion, "query": query, "parametros": parametros}


def generar_consulta(texto_usuario):
    """Responde con SQL conocido si la pregunta ya está resuelta (0 tokens); si no, usa el modelo y reintenta una vez si queda truncada."""
    sql = atajo_sql(texto_usuario)
    if sql:
        atajo = _finalizar("SELECT", sql, [])
        if "error" not in atajo:
            _registrar_uso(0, 0, {})
            return {**atajo, "atajo": True}
    resultado = _generar_consulta(texto_usuario)
    if "incompleta" in resultado.get("error", ""):
        resultado = _generar_consulta(f"{texto_usuario}. Escribe la consulta SQL completa y sin comillas dobles.")
    return resultado


def _generar_consulta(texto_usuario):
    """Convierte el texto del usuario en un JSON con la consulta SQL o acción de consejo."""
    try:
        respuesta = _llamar_modelo(texto_usuario, system=obtener_system_prompt(texto_usuario))
        datos = json.loads(respuesta)
        accion = datos.get("accion", "").upper()
        query = datos.get("query", "")
        parametros = datos.get("parametros", [])
        advice_type = datos.get("advice_type", "")
        
        # Manejar acción ADVICE (consejos, informes - no generan SQL)
        if accion == "ADVICE" or advice_type:
            advice_type = advice_type or accion
            return {
                "accion": "ADVICE",
                "advice_type": advice_type,
                "query": "",
                "parametros": [],
                "intent_entities": obtener_sesion().last_entities
            }
        
        # Si la acción no es válida, la derivamos del inicio de la query
        if accion not in ("SELECT", "UPDATE", "INSERT", "DELETE") and query:
            primera = query.strip().split()[0].upper() if query.strip() else ""
            if primera in ("SELECT", "UPDATE", "INSERT", "DELETE"):
                accion = primera
        if accion not in ("SELECT", "UPDATE", "INSERT", "DELETE") or not query:
            raise ValueError("JSON del agente incompleto o acción inválida")
        if parametros == [] and "%s" in query:
            # El modelo puso placeholders pero no los valores: pedir versión con valores literales
            r = _llamar_modelo(
                f"La query '{query}' usa %s pero no hay parámetros. Reescribe el JSON con la MISMA query pero reemplazando cada %s por el valor literal correcto (strings entre comillas simples, fechas 'YYYY-MM-DD', NOW() para timestamps). Responde SOLO el JSON.",
                system=obtener_system_prompt(texto_usuario),
            )
            try:
                d2 = json.loads(r)
                if d2.get("query"):
                    query = d2["query"]
                    parametros = d2.get("parametros", []) or []
            except Exception:
                pass
        return _finalizar(accion, query, parametros)
    except json.JSONDecodeError:
        # Reintento con instrucción reforzada
        try:
            r2 = _llamar_modelo(
                f"Texto del usuario: '{texto_usuario}'. Responde ÚNICAMENTE con un objeto JSON válido como {{\"accion\": \"...\", \"query\": \"...\", \"parametros\": []}}. Sin explicaciones, sin markdown.",
                system=obtener_system_prompt(texto_usuario),
            )
            datos = json.loads(r2)
            accion = datos.get("accion", "").upper()
            query = datos.get("query", "")
            parametros = datos.get("parametros", [])
            advice_type = datos.get("advice_type", "")
            
            if accion == "ADVICE" or advice_type:
                return {
                    "accion": "ADVICE",
                    "advice_type": advice_type or accion,
                    "query": "",
                    "parametros": [],
                    "intent_entities": obtener_sesion().last_entities
                }
            
            if accion not in ("SELECT", "UPDATE", "INSERT", "DELETE") and query:
                primera = query.strip().split()[0].upper() if query.strip() else ""
                if primera in ("SELECT", "UPDATE", "INSERT", "DELETE"):
                    accion = primera
            if accion in ("SELECT", "UPDATE", "INSERT", "DELETE") and query:
                return _finalizar(accion, query, parametros)
        except Exception:
            pass
        return {"error": "El modelo no devolvió un JSON válido."}
    except Exception as e:
        return {"error": f"Error con el modelo ({PROVEEDORES[PROVEEDOR]['etiqueta']}): {e}"}


def corregir_consulta(texto_usuario, consulta_mala, error_sql):
    """Pide al LLM que corrija la query usando el error de Postgres."""
    try:
        prompt = (
            f"El usuario pidió: '{texto_usuario}'. Generaste: {json.dumps(consulta_mala, ensure_ascii=False)}. "
            f"Postgres respondió: {error_sql}. "
            "Genera el JSON corregido usando SOLO las columnas reales del esquema."
        )
        respuesta = _llamar_modelo(prompt, system=obtener_system_prompt(texto_usuario))
        datos = json.loads(respuesta)
        accion = datos.get("accion", "").upper()
        query = datos.get("query", "")
        parametros = datos.get("parametros", [])
        if accion not in ("SELECT", "UPDATE", "INSERT", "DELETE") and query:
            primera = query.strip().split()[0].upper() if query.strip() else ""
            if primera in ("SELECT", "UPDATE", "INSERT", "DELETE"):
                accion = primera
        if accion not in ("SELECT", "UPDATE", "INSERT", "DELETE") or not query:
            raise ValueError("No se pudo corregir la consulta.")
        if parametros == [] and "%s" in query:
            r = _llamar_modelo(
                f"La query '{query}' usa %s pero no hay parámetros. Reescribe el JSON con la MISMA query pero reemplazando cada %s por el valor literal correcto (strings entre comillas simples, fechas 'YYYY-MM-DD', NOW() para timestamps). Responde SOLO el JSON.",
                system=obtener_system_prompt(texto_usuario),
            )
            try:
                d2 = json.loads(r)
                if d2.get("query"):
                    query = d2["query"]
                    parametros = d2.get("parametros", []) or []
            except Exception:
                pass
        problema = validar_consulta(accion, query)
        if problema:
            return {"error": problema}
        return _finalizar(accion, query, parametros)
    except Exception as e:
        return {"error": f"No se pudo corregir: {e}"}


def redactar_respuesta(resultado, texto_usuario):
    """Redacta una respuesta hablada natural, máximo 2 oraciones."""
    prompt = (
        f"Usuario preguntó: '{texto_usuario}'. Resultado de la BD: {str(resultado)[:6000]}. "
        "Responde en español de forma concreta. "
        "Si el usuario pidió ver productos o datos y hay filas en el resultado, lista TODAS las filas (nombre, precio, stock, etc. según venga), sin omitir ninguna. "
        "Si solo pidió una cantidad o un dato, responde con una sola oración corta. "
        "No expliques SQL ni repitas la pregunta."
    )
    try:
        return _llamar_modelo(prompt, json_mode=False, max_tokens=800)
    except Exception as e:
        return f"No pude generar la respuesta: {e}"


# ============================================================
# EJECUCIÓN HÍBRIDA (SQL directo + API REST)
# ============================================================

def ejecutar_consulta_hibrida(texto_usuario, llm_json: dict) -> dict:
    """
    Ejecuta la consulta usando el motor híbrido (SQL directo para SELECTs analíticos,
    API REST para escrituras y operaciones con side-effects).
    Ahora también maneja acciones de consejo (ADVICE) que no requieren SQL.
    
    Retorna dict compatible con el formato anterior: 
    {"accion": "...", "query": "...", "parametros": [...], "resultado": [...], "columnas": [...], "error": "..."}
    """
    from query_engine import get_query_engine, QueryResult
    
    # Manejar acción ADVICE (consejos, informes)
    if llm_json.get("accion") == "ADVICE":
        advice_type = llm_json.get("advice_type", "")
        entities = llm_json.get("intent_entities", {})
        return _ejecutar_advice(texto_usuario, advice_type, entities)
    
    engine = get_query_engine()
    
    # Obtener el plan antes de ejecutar
    plan = engine._plan_from_llm(llm_json, texto_usuario)
    
    # Ejecutar en un event loop aislado
    async def _run():
        return await engine.execute(plan)
    
    # Estrategia: intentar asyncio.run() primero, si falla por loop running, usar thread
    try:
        result: QueryResult = asyncio.run(_run())
    except RuntimeError as e:
        if "running" in str(e).lower() or "cannot be called from" in str(e).lower():
            # Hay un loop corriendo (ej. Streamlit, pytest-asyncio)
            # Ejecutar en thread separado con su propio loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(lambda: asyncio.run(_run()))
                result: QueryResult = future.result()
        else:
            raise
    
    # Formato de retorno compatible con código existente
    if result.success:
        return {
            "accion": plan.mode.value if plan.mode.value != "read" else "SELECT",
            "query": plan.sql or f"API.{plan.api_method}()",
            "parametros": list(plan.api_payload.values()) if plan.api_payload else [],
            "resultado": result.data,
            "columnas": result.columns,
            "rowcount": result.rowcount,
            "meta": result.meta,
            "plan_mode": plan.mode.value,
        }
    else:
        return {
            "error": result.error,
            "accion": "ERROR",
            "query": plan.sql or f"API.{plan.api_method}()",
            "parametros": list(plan.api_payload.values()) if plan.api_payload else [],
            "plan_mode": plan.mode.value,
        }


def _ejecutar_advice(texto_usuario: str, advice_type: str, entities: dict) -> dict:
    """
    Ejecuta acciones de consejo/informe que no requieren SQL directo.
    Usa la API REST y módulos de informes para análisis de negocio.
    """
    from api_client import get_api_client
    import informes as _inf
    
    api = get_api_client()
    
    try:
        if advice_type in ("discount_advice", "descuento_advice"):
            # Analizar productos para recomendar descuentos
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Obtener productos con stock alto/bajo, margen, etc.
            productos_resp = loop.run_until_complete(api.list_products({"lowStock": "false"}))
            loop.close()
            
            if not productos_resp.ok:
                return {"error": f"No se pudieron obtener productos: {productos_resp.error}"}
            
            productos = productos_resp.data or []
            
            # Análisis simple para recomendación
            recomendaciones = []
            for p in productos[:20]:  # Top 20
                stock = p.get("stock", 0)
                price = p.get("price", 0)
                cost = p.get("costPrice") or 0
                margin = ((price - cost) / price * 100) if price > 0 and cost > 0 else 0
                
                if stock > 50 and margin > 30:
                    recomendaciones.append({
                        "producto": p.get("name"),
                        "sku": p.get("sku"),
                        "stock": stock,
                        "margen_pct": round(margin, 1),
                        "recomendacion": f"Descuento 10-15% para rotar stock alto (margen {margin:.0f}%)",
                        "tipo": "rotacion"
                    })
                elif stock <= 5 and stock > 0:
                    recomendaciones.append({
                        "producto": p.get("name"),
                        "sku": p.get("sku"),
                        "stock": stock,
                        "recomendacion": "Stock bajo - NO aplicar descuento, reponer",
                        "tipo": "reponer"
                    })
                elif stock == 0:
                    recomendaciones.append({
                        "producto": p.get("name"),
                        "sku": p.get("sku"),
                        "recomendacion": "Agotado - Evaluar discontinuar o reponer",
                        "tipo": "agotado"
                    })
            
            return {
                "accion": "ADVICE",
                "advice_type": "discount_advice",
                "resultado": recomendaciones[:10],
                "columnas": ["producto", "sku", "stock", "margen_pct", "recomendacion", "tipo"],
                "rowcount": len(recomendaciones[:10]),
                "meta": {"analisis": "Basado en stock actual y márgenes estimados"}
            }
        
        elif advice_type in ("marketing_advice", "marketing"):
            # Usar informes.ideas_marketing
            try:
                ideas = _inf.ideas_marketing("ambos")
                return {
                    "accion": "ADVICE",
                    "advice_type": "marketing_advice",
                    "resultado": ideas,
                    "columnas": ["id", "clase", "titulo", "descripcion", "prioridad"],
                    "rowcount": len(ideas),
                    "meta": {"fuente": "informes.ideas_marketing"}
                }
            except Exception as e:
                return {"error": f"Error generando ideas de marketing: {e}"}
        
        elif advice_type in ("inventory_advice", "inventario_advice"):
            # Análisis de inventario: dead stock, rotación, reposición
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            productos_resp = loop.run_until_complete(api.list_products())
            dead_stock_resp = loop.run_until_complete(api.get_dead_stock(60))
            loop.close()
            
            productos = productos_resp.data or [] if productos_resp.ok else []
            dead_stock = dead_stock_resp.data or [] if dead_stock_resp.ok else []
            
            analisis = {
                "total_productos": len(productos),
                "productos_sin_stock": len([p for p in productos if p.get("stock", 0) == 0]),
                "productos_stock_bajo": len([p for p in productos if 0 < p.get("stock", 0) <= 5]),
                "productos_stock_alto": len([p for p in productos if p.get("stock", 0) > 50]),
                "dead_stock_count": len(dead_stock),
                "recomendaciones": []
            }
            
            # Recomendaciones basadas en análisis
            if analisis["productos_stock_alto"] > 0:
                analisis["recomendaciones"].append({
                    "tipo": "promocion",
                    "mensaje": f"{analisis['productos_stock_alto']} productos con stock >50. Considera ofertas o bundles."
                })
            if analisis["productos_stock_bajo"] > 0:
                analisis["recomendaciones"].append({
                    "tipo": "reposicion",
                    "mensaje": f"{analisis['productos_stock_bajo']} productos con stock ≤5. Reponer urgente."
                })
            if analisis["dead_stock_count"] > 0:
                analisis["recomendaciones"].append({
                    "tipo": "liquidacion",
                    "mensaje": f"{analisis['dead_stock_count']} productos sin ventas en 60 días. Evaluar liquidación."
                })
            
            return {
                "accion": "ADVICE",
                "advice_type": "inventory_advice",
                "resultado": [analisis],
                "columnas": ["total_productos", "productos_sin_stock", "productos_stock_bajo", "productos_stock_alto", "dead_stock_count", "recomendaciones"],
                "rowcount": 1,
                "meta": {"analisis": "Inventario completo"}
            }
        
        elif advice_type in ("report_request", "informe", "balance"):
            # Delegar a informes.py (se maneja en app.py)
            return {
                "accion": "ADVICE",
                "advice_type": "report_request",
                "resultado": [{"mensaje": "Solicitud de informe detectada. Se generará via informes.py", "tipo": "redirect"}],
                "columnas": ["mensaje", "tipo"],
                "rowcount": 1,
                "meta": {"redirect_to": "informes"}
            }
        
        else:
            return {
                "accion": "ADVICE",
                "advice_type": advice_type,
                "resultado": [{"mensaje": f"Tipo de consejo no implementado: {advice_type}", "tipo": "error"}],
                "columnas": ["mensaje", "tipo"],
                "rowcount": 1
            }
    
    except Exception as e:
        return {"error": f"Error ejecutando consejo: {e}"}


def ejecutar_consulta_hibrida_async(texto_usuario, llm_json: dict):
    """Versión async para uso en contextos async (ej. app.py con asyncio)."""
    from query_engine import get_query_engine, QueryResult
    
    engine = get_query_engine()
    plan = engine._plan_from_llm(llm_json, texto_usuario)
    return engine.execute(plan)

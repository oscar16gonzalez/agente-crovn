import json
import os
import re
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
if not OLLAMA_URL.endswith("/api/generate"):
    OLLAMA_URL = OLLAMA_URL.rstrip("/") + "/api/generate"
MODELO = "llama3.2:3b"

TTS_LENTO = False

def set_modelo(nombre):
    global MODELO
    MODELO = nombre

def set_tts_lento(v):
    global TTS_LENTO
    TTS_LENTO = v

from datetime import date
from database import obtener_esquema, completar_insert
from contexto_app import construir_contexto, TABLAS

_ESQUEMA_CACHE = None

def obtener_system_prompt(texto_usuario=""):
    global _ESQUEMA_CACHE
    if _ESQUEMA_CACHE is None:
        _ESQUEMA_CACHE = obtener_esquema()
    esquema = _ESQUEMA_CACHE
    contexto = construir_contexto(texto_usuario)
    hoy = date.today().isoformat()
    return f"""# SYSTEM PROMPT: AGENTE DE VOZ Y TEXTO PARA APLICACIÓN DE CAMISETAS Y GESTIÓN DE INVENTARIO (CROVN)
Fecha de hoy: {hoy}.

## 1. ROL Y OBJETIVO
Eres el asistente virtual inteligente experto en gestión de inventario, catálogo, ventas y administración para una aplicación de camisetas conectada a una base de datos PostgreSQL en Neon.

Tu tarea es recibir las consultas o comandos en lenguaje natural del usuario (vía texto o transcripción de voz), interpretar la intención real, mapear los términos al esquema exacto de la base de datos y responder **ÚNICAMENTE en formato JSON estricto**.

## 2. ESQUEMA DE BASE DE DATOS (NEON POSTGRESQL) — LEÍDO EN VIVO DE LA BD
{esquema}

{contexto}

## 4. INSTRUCCIONES DE SALIDA (JSON ESTRICTO)
- Responde SOLO con un objeto JSON válido, sin explicaciones ni markdown.
- NUNCA te niegues ni digas que no puedes ayudar. Siempre genera el JSON con la consulta SQL correspondiente, incluso si no estás seguro: genera tu mejor intento.
- SELECT: {{"accion": "SELECT", "query": "...", "parametros": []}}
- UPDATE/INSERT/DELETE: {{"accion": "...", "query": "... con %s ...", "parametros": [...]}}
- INSERT SIEMPRE con placeholders %s en VALUES. Ejemplo: {{"accion": "INSERT", "query": "INSERT INTO products (name, description, category, size, price, stock) VALUES (%s, %s, %s, %s, %s, %s);", "parametros": ["Camiseta Negra", "Camiseta negra unisex", "URBAN", "M", 59.9, 10]}}
- Una sola sentencia SQL por respuesta, sin punto y coma intermedios. Usa SOLO tablas y columnas del esquema.
- NUNCA uses comillas dobles dentro del valor de query (rompen el JSON). Escribe las columnas camelCase sin comillas (createdAt, customerId); el sistema las entrecomilla.
- Si el usuario pide "crea la categoría si no existe" junto con un producto, genera SOLO el INSERT del producto: el sistema crea la categoría.
- UPDATE y DELETE SIEMPRE con WHERE. Si el usuario no indica qué fila (id, nombre, código o email), apunta a una condición imposible (WHERE id = -1) en vez de afectar toda la tabla.
"""

SYSTEM_PROMPT = None  # se construye perezosamente con obtener_system_prompt()


def _llamar_ollama(prompt, system=None):
    payload = {"model": MODELO, "prompt": prompt, "stream": False, "keep_alive": "10m", "format": "json", "options": {"num_predict": 500, "temperature": 0, "num_ctx": 4096}}
    if system:
        payload["system"] = system
    resp = requests.post(OLLAMA_URL, json=payload, timeout=600)
    resp.raise_for_status()
    return resp.json().get("response", "")


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
    """Genera la consulta y reintenta una vez si el modelo la dejó truncada."""
    resultado = _generar_consulta(texto_usuario)
    if "incompleta" in resultado.get("error", ""):
        resultado = _generar_consulta(f"{texto_usuario}. Escribe la consulta SQL completa y sin comillas dobles.")
    return resultado


def _generar_consulta(texto_usuario):
    """Convierte el texto del usuario en un JSON con la consulta SQL."""
    try:
        respuesta = _llamar_ollama(texto_usuario, system=obtener_system_prompt(texto_usuario))
        datos = json.loads(respuesta)
        accion = datos.get("accion", "").upper()
        query = datos.get("query", "")
        parametros = datos.get("parametros", [])
        # Si la acción no es válida, la derivamos del inicio de la query
        if accion not in ("SELECT", "UPDATE", "INSERT", "DELETE") and query:
            primera = query.strip().split()[0].upper() if query.strip() else ""
            if primera in ("SELECT", "UPDATE", "INSERT", "DELETE"):
                accion = primera
        if accion not in ("SELECT", "UPDATE", "INSERT", "DELETE") or not query:
            raise ValueError("JSON del agente incompleto o acción inválida")
        if parametros == [] and "%s" in query:
            # El modelo puso placeholders pero no los valores: pedir versión con valores literales
            r = _llamar_ollama(
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
            r2 = _llamar_ollama(
                f"Texto del usuario: '{texto_usuario}'. Responde ÚNICAMENTE con un objeto JSON válido como {{\"accion\": \"...\", \"query\": \"...\", \"parametros\": []}}. Sin explicaciones, sin markdown.",
                system=obtener_system_prompt(texto_usuario),
            )
            datos = json.loads(r2)
            accion = datos.get("accion", "").upper()
            query = datos.get("query", "")
            parametros = datos.get("parametros", [])
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
        return {"error": f"Error con Ollama: {e}"}


def corregir_consulta(texto_usuario, consulta_mala, error_sql):
    """Pide al LLM que corrija la query usando el error de Postgres."""
    try:
        prompt = (
            f"El usuario pidió: '{texto_usuario}'. Generaste: {json.dumps(consulta_mala, ensure_ascii=False)}. "
            f"Postgres respondió: {error_sql}. "
            "Genera el JSON corregido usando SOLO las columnas reales del esquema."
        )
        respuesta = _llamar_ollama(prompt, system=obtener_system_prompt(texto_usuario))
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
            r = _llamar_ollama(
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
        payload = {"model": MODELO, "prompt": prompt, "stream": False, "keep_alive": "10m", "options": {"num_predict": 800, "num_ctx": 4096, "temperature": 0}}
        resp = requests.post(OLLAMA_URL, json=payload, timeout=600)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        return f"No pude generar la respuesta: {e}"

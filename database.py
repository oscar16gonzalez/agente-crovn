import os
import re
import uuid
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

DB_MODE = os.getenv("DB_MODE", "aiven").strip().lower()
AIVEN_DATABASE_URL = os.getenv("AIVEN_DATABASE_URL")
LOCAL_DATABASE_URL = os.getenv("LOCAL_DATABASE_URL")


def get_connection():
    if DB_MODE == "local":
        var, url = "LOCAL_DATABASE_URL", LOCAL_DATABASE_URL
    else:
        var, url = "AIVEN_DATABASE_URL", AIVEN_DATABASE_URL
    if not url:
        raise ValueError(f"{var} no está configurada en el archivo .env")
    conn = psycopg2.connect(url)
    try:
        cur = conn.cursor()
        cur.execute("SET TIME ZONE 'UTC';")
        conn.commit()
        cur.close()
    except Exception:
        pass
    return conn


def init_db():
    """Crea las tablas si no existen."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Las tablas camisetas y pedidos ya no existen; no se crean aquí.
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error inicializando la BD: {e}")


def seed_db():
    """Inserta datos de ejemplo si las tablas están vacías."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products;")
        if cur.fetchone()[0] == 0:
            print("products está vacía; no hay datos de ejemplo definidos para products.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error cargando datos de ejemplo: {e}")


def obtener_esquema():
    """Esquema real de la BD para el prompt: tipos, claves foráneas y columnas obligatorias en INSERT."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name NOT LIKE '\\_%'
              AND table_name NOT IN ('admin_users')
            ORDER BY table_name, ordinal_position;
        """)
        filas = cur.fetchall()
        cur.execute("""
            SELECT kcu.table_name, kcu.column_name, ccu.table_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
        """)
        fks = {(t, c): ref for t, c, ref in cur.fetchall()}
        cur.close()
        conn.close()
        corto = {"character varying": "texto", "text": "texto", "integer": "int", "double precision": "numero",
                 "boolean": "bool", "timestamp without time zone": "fecha", "timestamp with time zone": "fecha"}
        tablas = {}
        for tn, cn, dt, nulo, defecto in filas:
            marca = cn
            desc = f"{marca} {corto.get(dt, dt)}"
            if (tn, cn) in fks:
                desc += f"->{fks[(tn, cn)]}.id"
            if cn == "id":
                desc += " PK"
            elif nulo == "NO" and defecto is None:
                desc += " INSERT obligatorio"
            tablas.setdefault(tn, []).append(desc)
        return "\n".join(f"- {tn}({', '.join(cols)})" for tn, cols in tablas.items())
    except Exception as e:
        print(f"Error obteniendo esquema: {e}")
        return "(esquema no disponible)"


def asegurar_categoria(nombre):
    """Crea la categoría si no existe. Devuelve su id o None."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(%s);", (nombre,))
        fila = cur.fetchone()
        if fila:
            cat_id = fila[0]
        else:
            cur.execute("INSERT INTO categories (name) VALUES (%s) RETURNING id;", (nombre,))
            cat_id = cur.fetchone()[0]
            conn.commit()
        cur.close()
        conn.close()
        return cat_id
    except Exception as e:
        print(f"Error asegurando categoría: {e}")
        return None


TEXTOS_POR_DEFECTO = {"name": "Sin nombre", "title": "Sin título"}
_REQUERIDAS = None
_INSERT_RE = re.compile(r"^\s*INSERT\s+INTO\s+\"?(\w+)\"?\s*\(([^)]*)\)\s*VALUES\s*\((.*)\)\s*;?\s*$", re.IGNORECASE | re.DOTALL)


def _requeridas():
    """{tabla: {columna: tipo}} de columnas NOT NULL sin valor por defecto (excluye id y claves foráneas)."""
    global _REQUERIDAS
    if _REQUERIDAS is None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name, column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND is_nullable = 'NO' AND column_default IS NULL
              AND column_name <> 'id' AND column_name NOT LIKE '%Id'
            ORDER BY table_name, ordinal_position;
        """)
        _REQUERIDAS = {}
        for tabla, columna, tipo in cur.fetchall():
            _REQUERIDAS.setdefault(tabla, {})[columna] = tipo
        cur.close()
        conn.close()
    return _REQUERIDAS


def _valor_por_defecto(tabla, columna, tipo):
    """(literal_sql, valor): literal_sql va directo en el SQL; si es None, valor va como parámetro %s."""
    sufijo = uuid.uuid4().hex[:6]
    especiales = {
        ("customers", "email"): f"sin-correo-{sufijo}@crovn.local",
        ("promo_codes", "code"): f"CROVN-{sufijo.upper()}",
        ("categories", "name"): f"Categoría {sufijo}",
        ("products", "category"): "SIN-CATEGORIA",
        ("product_variants", "size"): "M",
    }
    if (tabla, columna) in especiales:
        return None, especiales[(tabla, columna)]
    if "timestamp" in tipo:
        return "NOW()", None
    if columna in TEXTOS_POR_DEFECTO:
        return None, TEXTOS_POR_DEFECTO[columna]
    if tipo in ("integer", "bigint", "double precision", "numeric"):
        return None, 0
    if tipo == "boolean":
        return None, False
    return None, ""


def _separar_valores(texto):
    """Divide el contenido de VALUES (...) por comas de nivel 0, respetando paréntesis y comillas."""
    partes, actual, nivel, en_texto = [], "", 0, False
    for ch in texto:
        if ch == "'":
            en_texto = not en_texto
        if not en_texto:
            if ch == "(":
                nivel += 1
            elif ch == ")":
                nivel -= 1
            elif ch == "," and nivel == 0:
                partes.append(actual.strip())
                actual = ""
                continue
        actual += ch
    partes.append(actual.strip())
    return partes


def completar_insert(query, parametros):
    """Rellena con valores neutros las columnas obligatorias que falten, para crear un registro con un solo dato."""
    m = _INSERT_RE.match(query or "")
    if not m:
        return query, parametros
    tabla = m.group(1).lower()
    try:
        req = _requeridas().get(tabla)
    except Exception as e:
        print(f"No se pudo leer las columnas obligatorias: {e}")
        return query, parametros
    if not req:
        return query, parametros
    reales = {c.lower(): c for c in req}
    columnas = [c.strip().strip('"') for c in m.group(2).split(",")]
    columnas = [reales.get(c.lower(), c) for c in columnas]
    valores = _separar_valores(m.group(3))
    if len(columnas) != len(valores):
        return query, parametros
    params = list(parametros or [])
    idx = 0
    for i, (col, val) in enumerate(zip(columnas, valores)):
        requerida = col in req
        if val == "%s":
            if requerida and idx < len(params) and params[idx] in (None, ""):
                literal, defecto = _valor_por_defecto(tabla, col, req[col])
                if literal:
                    valores[i] = literal
                    params.pop(idx)
                    continue
                params[idx] = defecto
            idx += 1
        elif requerida and val.upper() == "NULL":
            literal, defecto = _valor_por_defecto(tabla, col, req[col])
            if literal:
                valores[i] = literal
            else:
                valores[i] = "%s"
                params.insert(idx, defecto)
                idx += 1
    for col, tipo in req.items():
        if col in columnas:
            continue
        literal, defecto = _valor_por_defecto(tabla, col, tipo)
        columnas.append(col)
        if literal:
            valores.append(literal)
        else:
            valores.append("%s")
            params.append(defecto)
    cols_sql = ", ".join(f'"{c}"' if c != c.lower() else c for c in columnas)
    return f"INSERT INTO {tabla} ({cols_sql}) VALUES ({', '.join(valores)});", params


CAMELCAS = ["createdAt", "updatedAt", "customerId", "productId", "orderId", "categoryId", "supplierId", "costPrice", "profitPct", "colorHex", "discountPct", "maxUses", "usedCount", "expiresAt", "publishedAt", "isVIP", "promoCode"]


def _entrecomillar_camelcase(query):
    import re
    for col in CAMELCAS:
        # si viene entre comillas simples como identificador, cámbialas a dobles
        query = re.sub(r"'" + col + r"'", '"' + col + '"', query)
        # comilla simple sin cerrar: 'updatedAt -> "updatedAt"
        query = re.sub(r"'" + col + r"\b", '"' + col + '"', query)
        # comilla suelta después: updatedAt' -> "updatedAt"
        query = re.sub(r'\b' + col + r"'", '"' + col + '"', query)
        # reemplaza ocurrencias no entrecomilladas de la columna
        query = re.sub(r'(?<!["\'\w])' + col + r'\b(?!["\'])', '"' + col + '"', query)
    return query


def ejecutar_consulta(query, parametros=None):
    """
    Ejecuta una consulta SQL parametrizada.
    Devuelve (filas, columnas) para SELECT, o filas_afectadas para escritura.
    """
    try:
        query = _entrecomillar_camelcase(query)
        conn = get_connection()
        cur = conn.cursor()
        params = parametros if parametros else None
        # Si la query no tiene placeholders %s pero vienen parámetros, ignóralos
        if params and "%s" not in query:
            print(f"Aviso: parámetros ignorados (query sin %s): {params}")
            params = None
        # Si la query tiene %s pero no hay parámetros, no ejecutar (evita error de sintaxis)
        if params is None and "%s" in query:
            cur.close(); conn.close()
            return None, "La consulta usa %s pero no se enviaron parámetros."
        # Si faltan/sobran placeholders respecto a los parámetros, intentar ajustar
        if params and query.count("%s") != len(params):
            n = query.count("%s")
            if n < len(params):
                print(f"Aviso: {len(params)} parámetros para {n} placeholders; se usan los primeros {n}")
                params = params[:n]
            else:
                cur.close(); conn.close()
                return None, f"Desajuste: la query tiene {n} placeholders %s y se enviaron {len(params)} parámetros."
        cur.execute(query, params)
        accion = query.strip().split()[0].upper() if query.strip() else ""
        if accion == "SELECT":
            filas = cur.fetchall()
            columnas = [desc[0] for desc in cur.description] if cur.description else []
            cur.close()
            conn.close()
            return filas, columnas
        else:
            afectadas = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            return afectadas, []
    except Exception as e:
        print(f"Error ejecutando consulta: {e}")
        return None, str(e)

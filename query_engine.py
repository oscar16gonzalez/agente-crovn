"""Motor de consultas híbrido: decide cuándo usar SQL directo (lecturas analíticas)
y cuándo usar la API REST (escrituras, operaciones con side-effects)."""
from __future__ import annotations
import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from database import ejecutar_consulta, get_connection
from api_client import get_api_client, CROVNApiClient, ApiResponse


class QueryMode(Enum):
    """Modo de ejecución de la consulta."""
    READ_ONLY = "read"           # SELECT analítico → SQL directo (rápido, flexible)
    WRITE_API = "write_api"      # INSERT/UPDATE/DELETE → API REST (seguro, con side-effects)
    REPORT = "report"            # Informes complejos → API especializada / informes.py
    SHOP_PUBLIC = "shop_public"  # Operaciones públicas de tienda → API shop


@dataclass
class QueryPlan:
    """Plan de ejecución resuelto por el motor."""
    mode: QueryMode
    sql: str | None = None                    # Para READ_ONLY
    api_method: str | None = None             # Nombre del método en CROVNApiClient
    api_payload: dict | None = None           # Parámetros para la llamada API
    explanation: str = ""                     # Para debugging/logging
    requires_confirmation: bool = False       # Si la acción es destructiva/importante
    estimated_rows: int | None = None         # Para SELECT: estimación de filas


@dataclass
class QueryResult:
    """Resultado unificado sin importar el modo de ejecución."""
    success: bool
    data: Any = None              # Lista de dicts (filas) o dict único
    columns: list[str] = field(default_factory=list)
    rowcount: int = 0
    error: str | None = None
    plan: QueryPlan | None = None
    meta: dict = field(default_factory=dict)  # Info extra: tiempo, modo real, etc.


class HybridQueryEngine:
    """
    Motor que analiza la intención del usuario (via LLM) y decide la mejor forma de ejecutarla.
    
    Reglas de decisión:
    - SELECT analítico complejo (joins, agregaciones, ventanas) → SQL directo
    - SELECT simple por ID / lookup → API (cache, formato consistente)
    - INSERT/UPDATE/DELETE de entidades de negocio → API (valida, envía emails, stock)
    - Operaciones con side-effects (crear pedido, cambiar estado, enviar email) → API
    - Informes (balance, Excel, marketing) → informes.py / API admin
    - Operaciones públicas de tienda (checkout, lookup) → API shop
    """

    # Palabras clave que indican escritura con side-effects
    WRITE_KEYWORDS = {
        "crear", "crea", "insertar", "inserta", "agregar", "agrega", "registrar", "registra",
        "nuevo", "nueva", "añadir", "anadir", "añade", "anade",
        "actualizar", "actualiza", "cambiar", "cambia", "modificar", "modifica",
        "editar", "edita", "poner", "pon", "establecer",
        "eliminar", "elimina", "borrar", "borra", "quitar", "quita",
        "desactivar", "desactiva", "activar", "activa",
        "ajustar", "ajusta", "marcar", "marca",
        "enviar", "envia", "envía", "mandar", "manda",
        "procesar", "procesa", "anular", "anula", "cancelar", "cancela",
        "checkout", "comprar", "comprar", "pedir",
    }

    # Palabras que indican operaciones de tienda pública
    SHOP_KEYWORDS = {
        "checkout", "comprar", "compra", "carrito", "pagar", "pago",
        "consultar pedido", "consulta pedido", "rastrear", "rastreo",
        "mi pedido", "estado pedido", "donde esta mi pedido",
    }

    # Palabras que indican informes/analytics
    REPORT_KEYWORDS = {
        "informe", "informe", "balance", "reporte", "excel", "exportar",
        "balance semanal", "balance mensual", "ventas por", "ranking",
        "sugerir", "sugiere", "recomendar", "recomienda", "ideas",
        "avisos", "códigos", "codigos", "promocionales", "marketing",
    }

    def __init__(self, api_client: CROVNApiClient | None = None):
        self.api = api_client or get_api_client()
        self._db_pool = None  # Se usa get_connection() por consulta (simple, seguro)

    # ---------------------------------------------------------------------
    # PÚBLICO: Punto de entrada principal
    # ---------------------------------------------------------------------
    async def execute(self, plan: QueryPlan) -> QueryResult:
        """Ejecuta un plan ya resuelto."""
        loop = asyncio.get_running_loop()
        start = loop.time()
        
        try:
            if plan.mode == QueryMode.READ_ONLY:
                result = await self._exec_sql(plan.sql or "")
            elif plan.mode == QueryMode.WRITE_API:
                result = await self._exec_api(plan.api_method, plan.api_payload or {})
            elif plan.mode == QueryMode.REPORT:
                result = await self._exec_report(plan.api_method, plan.api_payload or {})
            elif plan.mode == QueryMode.SHOP_PUBLIC:
                result = await self._exec_shop(plan.api_method, plan.api_payload or {})
            else:
                return QueryResult(success=False, error=f"Modo desconocido: {plan.mode}", plan=plan)

            elapsed = loop.time() - start
            result.meta["elapsed_ms"] = round(elapsed * 1000, 1)
            result.meta["mode"] = plan.mode.value
            result.plan = plan
            return result

        except Exception as e:
            return QueryResult(
                success=False, 
                error=f"Error ejecutando plan: {e}", 
                plan=plan,
                meta={"elapsed_ms": round((loop.time() - start) * 1000, 1)}
            )

    async def execute_from_llm_output(self, llm_json: dict, user_text: str) -> QueryResult:
        """
        Convierte la salida del LLM (accion, query, parametros) en un QueryPlan y lo ejecuta.
        Este es el método que llamará agent.py en lugar de ejecutar_consulta directo.
        """
        plan = self._plan_from_llm(llm_json, user_text)
        return await self.execute(plan)

    # ---------------------------------------------------------------------
    # PLANIFICACIÓN: Análisis de la salida del LLM
    # ---------------------------------------------------------------------
    def _plan_from_llm(self, llm_json: dict, user_text: str) -> QueryPlan:
        """Analiza el JSON del LLM y decide el modo de ejecución óptimo."""
        accion = (llm_json.get("accion") or "").upper()
        query = llm_json.get("query") or ""
        parametros = llm_json.get("parametros") or []
        user_lower = user_text.lower()

        # 1. Detectar si es operación de tienda pública (checkout, lookup)
        if self._is_shop_operation(user_lower, query):
            return self._plan_shop_operation(user_lower, query, parametros)

        # 2. ESCRITURA (INSERT/UPDATE/DELETE) → SIEMPRE API para entidades de negocio
        # Esto debe ir ANTES de la detección de informes para evitar falsos positivos
        # (ej: "crear codigo promocional" contiene "codigo" que está en REPORT_KEYWORDS)
        if accion in ("INSERT", "UPDATE", "DELETE"):
            return self._plan_write_api(accion, query, parametros, user_lower)

        # 3. Detectar si es informe/analytics
        if self._is_report_operation(user_lower, query):
            return self._plan_report_operation(user_lower, query, parametros)

        # 4. SELECT → decisión entre SQL y API
        if accion == "SELECT" or query.strip().upper().startswith("SELECT"):
            return self._plan_select(query, user_lower, parametros)

        # Fallback: intentar inferir de la query
        if query.strip().upper().startswith("SELECT"):
            return self._plan_select(query, user_lower, parametros)
        
        return QueryPlan(
            mode=QueryMode.READ_ONLY,
            sql=query,
            explanation="Fallback: asumido SELECT",
        )

    def _is_shop_operation(self, user_text: str, query: str) -> bool:
        return any(kw in user_text for kw in self.SHOP_KEYWORDS)

    def _is_report_operation(self, user_text: str, query: str) -> bool:
        return any(kw in user_text for kw in self.REPORT_KEYWORDS)

    # ---------------------------------------------------------------------
    # PLANES ESPECÍFICOS POR TIPO DE OPERACIÓN
    # ---------------------------------------------------------------------
    def _plan_select(self, query: str, user_text: str, parametros: list) -> QueryPlan:
        """Decide: SQL directo vs API GET simple."""
        query_upper = query.strip().upper()
        
        # Patrones que favorecen SQL directo (analítica compleja)
        sql_indicators = [
            "JOIN", "GROUP BY", "ORDER BY", "LIMIT", "OFFSET",
            "SUM(", "COUNT(", "AVG(", "MAX(", "MIN(",
            "CASE WHEN", "COALESCE", "DATE_TRUNC", "TO_CHAR",
            "WITH ", "OVER (", "PARTITION BY",
            "UNION", "INTERSECT", "EXCEPT",
            "EXISTS", "NOT EXISTS",
            "DISTINCT ON",
        ]
        
        # Patrones que favorecen API (lookup simple por ID)
        api_indicators = [
            "WHERE ID =", "WHERE \"ID\" =", "WHERE ID=", "WHERE \"ID\"=",
            "WHERE SKU =", "WHERE \"SKU\" =",
            "WHERE EMAIL =", "WHERE \"EMAIL\" =",
            "WHERE CODE =", "WHERE \"CODE\" =",
        ]
        
        is_complex = any(ind in query_upper for ind in sql_indicators)
        is_simple_lookup = any(ind in query_upper for ind in api_indicators)
        
        # Heurística: si es SELECT simple por PK → API; si es analítica → SQL
        if is_simple_lookup and not is_complex:
            # Extraer tabla y ID para llamar al endpoint correcto
            table, id_val = self._extract_table_and_id(query)
            if table and id_val:
                return self._plan_api_get_by_id(table, id_val)
        
        # Por defecto: SQL directo para flexibilidad analítica
        return QueryPlan(
            mode=QueryMode.READ_ONLY,
            sql=query,
            explanation=f"SELECT {'complejo' if is_complex else 'simple'} → SQL directo",
        )

    def _plan_write_api(self, accion: str, query: str, parametros: list, user_text: str) -> QueryPlan:
        """Mapea INSERT/UPDATE/DELETE al método API correspondiente."""
        query_upper = query.strip().upper()
        
        # Detectar tabla objetivo
        table_match = re.search(r"\b(?:INTO|UPDATE|DELETE\s+FROM)\s+\"?(\w+)\"?", query_upper)
        table = table_match.group(1).lower() if table_match else None
        
        if not table:
            return QueryPlan(
                mode=QueryMode.WRITE_API,
                api_method="unknown",
                explanation=f"{accion} sin tabla detectable → requiere revisión manual",
                requires_confirmation=True,
            )

        # Mapeo tabla → método API
        api_mapping = {
            # Productos
            "products": {
                "INSERT": "create_product",
                "UPDATE": "update_product", 
                "DELETE": "delete_product",
            },
            "product_variants": {
                "INSERT": "create_variant",  # No existe en API aún, fallback a SQL con validación
                "UPDATE": "update_variant",
                "DELETE": "delete_variant",
            },
            "product_images": {
                "INSERT": "add_product_image",
                "DELETE": "delete_product_image",
            },
            # Pedidos (SOLO API - side effects críticos)
            "orders": {
                "INSERT": "create_order",
                "UPDATE": "change_order_status",
                "DELETE": "cancel_order",
            },
            "order_items": {
                "INSERT": "add_order_item",  # No existe, se hace via create_order
                "UPDATE": "update_order_item",
                "DELETE": "delete_order_item",
            },
            # Clientes
            "customers": {
                "INSERT": "create_customer",
                "UPDATE": "update_customer",
                "DELETE": "delete_customer",  # Soft delete preferido
            },
            # Promociones
            "promo_codes": {
                "INSERT": "create_promo",
                "UPDATE": "update_promo",
                "DELETE": "delete_promo",
            },
            # Publicaciones
            "publications": {
                "INSERT": "create_publication",
                "UPDATE": "update_publication",
                "DELETE": "delete_publication",
            },
            # Proveedores
            "suppliers": {
                "INSERT": "create_supplier",
                "UPDATE": "update_supplier",
                "DELETE": "delete_supplier",
            },
            # Categorías
            "categories": {
                "INSERT": "create_category",
                "DELETE": "delete_category",
            },
        }

        mapping = api_mapping.get(table)
        if not mapping:
            return QueryPlan(
                mode=QueryMode.WRITE_API,
                api_method="unknown",
                explanation=f"Tabla '{table}' no mapeada a API → revisión manual",
                requires_confirmation=True,
            )

        method = mapping.get(accion)
        if not method:
            return QueryPlan(
                mode=QueryMode.WRITE_API,
                api_method="unknown",
                explanation=f"{accion} no soportado para '{table}' via API",
                requires_confirmation=True,
            )

        # Construir payload según operación
        payload = self._build_api_payload(table, accion, query, parametros)
        
        return QueryPlan(
            mode=QueryMode.WRITE_API,
            api_method=method,
            api_payload=payload,
            explanation=f"{accion} {table} → API.{method}()",
            requires_confirmation=accion == "DELETE",
        )

    def _plan_shop_operation(self, user_text: str, query: str, parametros: list) -> QueryPlan:
        """Planifica operaciones de tienda pública (checkout, lookup)."""
        if "checkout" in user_text or "comprar" in user_text or "pagar" in user_text:
            # Extraer datos del carrito/cliente del contexto o parámetros
            return QueryPlan(
                mode=QueryMode.SHOP_PUBLIC,
                api_method="checkout_shop",
                api_payload={"customer": {}, "items": []},  # Se rellena en app.py desde estado
                explanation="Checkout tienda pública",
                requires_confirmation=True,
            )
        
        if any(kw in user_text for kw in ["consultar pedido", "mi pedido", "rastrear", "estado pedido"]):
            return QueryPlan(
                mode=QueryMode.SHOP_PUBLIC,
                api_method="lookup_order",
                api_payload={"email": "", "order_id": ""},  # Se rellena desde contexto
                explanation="Consulta pedido público",
            )
        
        return QueryPlan(
            mode=QueryMode.SHOP_PUBLIC,
            api_method="get_shop_catalog",
            api_payload={},
            explanation="Catálogo tienda",
        )

    def _plan_report_operation(self, user_text: str, query: str, parametros: list) -> QueryPlan:
        """Planifica informes y analytics."""
        if any(kw in user_text for kw in ["sugerir", "sugiere", "recomendar", "ideas", "marketing"]):
            return QueryPlan(
                mode=QueryMode.REPORT,
                api_method="ideas_marketing",
                api_payload={"tipo": "ambos"},
                explanation="Sugerencias marketing (avisos + códigos)",
            )
        
        if "balance" in user_text or "informe" in user_text or "reporte" in user_text:
            return QueryPlan(
                mode=QueryMode.REPORT,
                api_method="datos_balance",
                api_payload={},  # Se parsea período en informes.py
                explanation="Balance/informe con Excel",
            )
        
        return QueryPlan(
            mode=QueryMode.REPORT,
            api_method="get_dashboard_stats",
            api_payload={},
            explanation="KPIs dashboard",
        )

    def _plan_api_get_by_id(self, table: str, id_val: str) -> QueryPlan:
        """Mapea tabla a método API GET by ID."""
        get_methods = {
            "products": "get_product",
            "orders": "get_order", 
            "customers": "get_customer",
            "promo_codes": "get_promo",
            "publications": "get_publication",
            "suppliers": "get_supplier",
            "categories": "get_category",  # No existe, usar list_categories
        }
        method = get_methods.get(table)
        if method:
            return QueryPlan(
                mode=QueryMode.WRITE_API,  # Usa API aunque sea lectura
                api_method=method,
                api_payload={"id": int(id_val) if id_val.isdigit() else id_val},
                explanation=f"Lookup {table} por ID → API.{method}()",
            )
        return QueryPlan(mode=QueryMode.READ_ONLY, sql=f"SELECT * FROM {table} WHERE id = {id_val}")

    # ---------------------------------------------------------------------
    # EJECUCIÓN POR MODO
    # ---------------------------------------------------------------------
    async def _exec_sql(self, sql: str) -> QueryResult:
        """Ejecuta SQL directo en PostgreSQL (solo lectura)."""
        # Validación de seguridad básica
        if not sql.strip().upper().startswith("SELECT"):
            return QueryResult(success=False, error="Solo SELECT permitido en modo SQL directo")
        
        # Ejecutar en thread pool para no bloquear event loop
        loop = asyncio.get_event_loop()
        try:
            filas, columnas = await loop.run_in_executor(None, ejecutar_consulta, sql, None)
            if filas is None and isinstance(columnas, str):
                return QueryResult(success=False, error=columnas)
            
            # Convertir a lista de dicts
            data = [dict(zip(columnas, row)) for row in (filas or [])]
            return QueryResult(
                success=True,
                data=data,
                columns=columnas,
                rowcount=len(data),
            )
        except Exception as e:
            return QueryResult(success=False, error=f"Error SQL: {e}")

    async def _exec_api(self, method_name: str, payload: dict) -> QueryResult:
        """Ejecuta método en CROVNApiClient."""
        method = getattr(self.api, method_name, None)
        if not method:
            return QueryResult(success=False, error=f"Método API no encontrado: {method_name}")
        
        try:
            # Métodos que usan multipart/form-data (data + images)
            multipart_methods = {
                "create_product": ["data", "images"],
                "update_product": ["product_id", "data", "images"],
            }
            
            # Filtrar payload None values
            clean_payload = {k: v for k, v in payload.items() if v is not None}
            
            if method_name in multipart_methods:
                # Extraer parámetros específicos para multipart
                expected_params = multipart_methods[method_name]
                kwargs = {}
                for param in expected_params:
                    # Aceptar tanto 'id' como 'product_id' para compatibilidad
                    if param == "product_id" and "id" in clean_payload:
                        kwargs[param] = clean_payload.pop("id")
                    elif param in clean_payload:
                        kwargs[param] = clean_payload.pop(param)
                # Los parámetros restantes van en data (para create_product/update_product)
                if "data" in expected_params and clean_payload:
                    kwargs["data"] = clean_payload
                resp: ApiResponse = await method(**kwargs)
            elif method_name in ("create_category", "delete_category"):
                # create_category(name: str) / delete_category(category_id: int)
                if method_name == "create_category":
                    name = clean_payload.pop("name", None) or clean_payload.pop("data", {}).get("name", "")
                    resp = await method(name)
                else:  # delete_category
                    cat_id = clean_payload.pop("id", None) or clean_payload.pop("category_id", None)
                    resp = await method(cat_id)
            elif method_name in ("create_customer", "update_customer", "delete_customer"):
                # create_customer(data: dict) / update_customer(customer_id, data) / delete_customer(customer_id)
                if method_name == "create_customer":
                    resp = await method(data=clean_payload)
                elif method_name == "update_customer":
                    cust_id = clean_payload.pop("id", None)
                    resp = await method(customer_id=cust_id, data=clean_payload)
                else:  # delete_customer
                    cust_id = clean_payload.pop("id", None) or clean_payload.pop("customer_id", None)
                    resp = await method(cust_id)
            elif method_name in ("create_supplier", "update_supplier", "delete_supplier"):
                # create_supplier(data: dict) / update_supplier(supplier_id, data) / delete_supplier(supplier_id)
                if method_name == "create_supplier":
                    resp = await method(data=clean_payload)
                elif method_name == "update_supplier":
                    sup_id = clean_payload.pop("id", None)
                    resp = await method(supplier_id=sup_id, data=clean_payload)
                else:  # delete_supplier
                    sup_id = clean_payload.pop("id", None) or clean_payload.pop("supplier_id", None)
                    resp = await method(sup_id)
            elif method_name in ("create_promo", "update_promo", "delete_promo"):
                # create_promo(data: dict) / update_promo(promo_id, data) / delete_promo(promo_id)
                if method_name == "create_promo":
                    resp = await method(data=clean_payload)
                elif method_name == "update_promo":
                    promo_id = clean_payload.pop("id", None)
                    resp = await method(promo_id=promo_id, data=clean_payload)
                else:  # delete_promo
                    promo_id = clean_payload.pop("id", None)
                    resp = await method(promo_id)
            elif method_name in ("create_publication", "update_publication", "delete_publication"):
                # create_publication(data: dict) / update_publication(pub_id, data) / delete_publication(pub_id)
                if method_name == "create_publication":
                    resp = await method(data=clean_payload)
                elif method_name == "update_publication":
                    pub_id = clean_payload.pop("id", None)
                    resp = await method(pub_id=pub_id, data=clean_payload)
                else:  # delete_publication
                    pub_id = clean_payload.pop("id", None)
                    resp = await method(pub_id)
            elif method_name in ("create_supplier", "update_supplier", "delete_supplier"):
                # create_supplier(data: dict) / update_supplier(supplier_id, data) / delete_supplier(supplier_id)
                if method_name == "create_supplier":
                    resp = await method(data=clean_payload)
                elif method_name == "update_supplier":
                    sup_id = clean_payload.pop("id", None)
                    resp = await method(supplier_id=sup_id, data=clean_payload)
                else:  # delete_supplier
                    sup_id = clean_payload.pop("id", None)
                    resp = await method(sup_id)
            else:
                # Métodos JSON normales
                resp: ApiResponse = await method(**clean_payload)
            
            if not resp.ok:
                return QueryResult(success=False, error=resp.error or resp.message)
            
            data = resp.data
            # Normalizar a lista de dicts
            if isinstance(data, dict):
                data = [data]
            elif data is None:
                data = []
            
            columns = list(data[0].keys()) if data else []
            return QueryResult(
                success=True,
                data=data,
                columns=columns,
                rowcount=len(data),
                meta={"api_message": resp.message},
            )
        except Exception as e:
            return QueryResult(success=False, error=f"Error API {method_name}: {e}")

    async def _exec_report(self, method_name: str, payload: dict) -> QueryResult:
        """Ejecuta informes (delega a informes.py que usa SQL interno)."""
        # Los informes se manejan en app.py vía informes.py directamente
        # Este método es placeholder para consistencia
        return QueryResult(
            success=False, 
            error="Informes se ejecutan vía informes.py directamente en app.py",
            meta={"redirect_to": "informes"}
        )

    async def _exec_shop(self, method_name: str, payload: dict) -> QueryResult:
        """Ejecuta operaciones públicas de tienda."""
        method = getattr(self.api, method_name, None)
        if not method:
            return QueryResult(success=False, error=f"Método shop no encontrado: {method_name}")
        
        try:
            resp: ApiResponse = await method(**payload)
            if not resp.ok:
                return QueryResult(success=False, error=resp.error or resp.message)
            
            data = resp.data
            if isinstance(data, dict):
                data = [data]
            elif data is None:
                data = []
            
            columns = list(data[0].keys()) if data else []
            return QueryResult(
                success=True,
                data=data,
                columns=columns,
                rowcount=len(data),
                meta={"api_message": resp.message},
            )
        except Exception as e:
            return QueryResult(success=False, error=f"Error shop {method_name}: {e}")

    # ---------------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------------
    def _extract_table_and_id(self, query: str) -> tuple[str | None, str | None]:
        """Extrae tabla e ID de un WHERE simple."""
        # SELECT ... FROM tabla WHERE id = valor
        match = re.search(
            r"FROM\s+\"?(\w+)\"?.*?WHERE\s+\"?(?:ID|id|Id|iD)\"?\s*=\s*([\w\-]+)",
            query, re.IGNORECASE
        )
        if match:
            return match.group(1).lower(), match.group(2)
        
        # SELECT ... FROM tabla WHERE sku/codigo/email = valor
        match = re.search(
            r"FROM\s+\"?(\w+)\"?.*?WHERE\s+\"?(?:SKU|sku|CODE|code|EMAIL|email)\"?\s*=\s*['\"]?([^'\";\s]+)",
            query, re.IGNORECASE
        )
        if match:
            return match.group(1).lower(), match.group(2)
        
        return None, None

    def _build_api_payload(self, table: str, accion: str, query: str, parametros: list) -> dict:
        """Construye payload para la API a partir de la query SQL y parámetros."""
        payload = {}
        
        # Si la query usa %s placeholders, usar los parametros directamente
        if "%s" in query and parametros:
            # Extraer columnas de la query
            cols_match = re.search(r"\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)", query, re.IGNORECASE)
            if cols_match:
                cols = [c.strip().strip('"') for c in cols_match.group(1).split(",")]
                # Usar parametros directamente (ya vienen en orden correcto)
                payload = dict(zip(cols, parametros))
                return payload
        
        # Fallback: parsear valores literales de la query (para compatibilidad)
        cols_match = re.search(r"\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)", query, re.IGNORECASE)
        if cols_match and accion == "INSERT":
            cols = [c.strip().strip('"') for c in cols_match.group(1).split(",")]
            vals_str = cols_match.group(2)
            # Parsear valores (simplificado)
            vals = [v.strip().strip("'\"") for v in vals_str.split(",")]
            payload = dict(zip(cols, vals))
        
        # Para UPDATE/DELETE, extraer WHERE y SET
        if accion in ("UPDATE", "DELETE"):
            where_match = re.search(r"WHERE\s+(.+)$", query, re.IGNORECASE)
            if where_match:
                where_clause = where_match.group(1)
                # Extraer ID si es WHERE id = X
                id_match = re.search(r"\b(?:ID|id)\b\s*=\s*(\d+)", where_clause)
                if id_match:
                    payload["id"] = int(id_match.group(1))
            
            # Para UPDATE, extraer SET clause
            if accion == "UPDATE":
                set_match = re.search(r"SET\s+(.+?)\s+WHERE", query, re.IGNORECASE)
                if not set_match:
                    set_match = re.search(r"SET\s+(.+)$", query, re.IGNORECASE)
                if set_match:
                    set_clause = set_match.group(1)
                    # Parsear asignaciones: col = valor, col = valor
                    # Manejar tanto %s como valores literales
                    if "%s" in set_clause and parametros:
                        # Usar parametros (excluyendo el ID que ya se extrajo)
                        # Necesitamos mapear parámetros a columnas del SET
                        set_parts = [p.strip() for p in set_clause.split(",")]
                        cols = [p.split("=")[0].strip().strip('"') for p in set_parts]
                        # Filtrar parametros que no sean el ID
                        vals = [p for p in parametros if not (isinstance(p, int) and p == payload.get("id"))]
                        if len(cols) == len(vals):
                            for col, val in zip(cols, vals):
                                payload[col] = val
                    else:
                        # Parsear valores literales
                        for part in set_clause.split(","):
                            if "=" in part:
                                col, val = part.split("=", 1)
                                col = col.strip().strip('"')
                                val = val.strip().strip("'\"")
                                if val != "%s":
                                    payload[col] = val
        
        # Añadir parámetros posicionales si no están en payload
        if parametros and "id" not in payload:
            # Asumir primer parámetro es ID para UPDATE/DELETE
            if accion in ("UPDATE", "DELETE") and parametros:
                try:
                    payload["id"] = int(parametros[0])
                except (ValueError, TypeError):
                    pass
        
        return payload


# Instancia global
query_engine: HybridQueryEngine | None = None


def get_query_engine() -> HybridQueryEngine:
    global query_engine
    if query_engine is None:
        query_engine = HybridQueryEngine()
    return query_engine
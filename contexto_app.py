"""Conocimiento de negocio de CROVN (derivado de backend/prisma/schema.prisma y backend/src/routes)."""
import json
import re
import unicodedata
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

ESTADOS_ORDEN = ("Pendiente", "Procesado", "Enviado", "Entregado")
ESTADOS_VENTA = ("Procesado", "Enviado", "Entregado")
TALLAS = ("XS", "S", "M", "L", "XL", "XXL")


class IntentType(Enum):
    """Tipos de intención detectables en las consultas del usuario."""
    SHOP_QUERY = "shop_query"           # Consultas de tienda: stock, precios, catálogo, pedidos
    PRODUCT_CREATE = "product_create"   # Crear nuevos productos
    PRODUCT_UPDATE = "product_update"   # Actualizar productos existentes (precio, stock, datos)
    PROMOTION_CREATE = "promotion_create"  # Crear códigos promocionales, ofertas
    PROMOTION_QUERY = "promotion_query"    # Consultar promociones existentes
    DISCOUNT_ADVICE = "discount_advice"    # Consejos sobre descuentos, estrategias
    MARKETING_ADVICE = "marketing_advice"  # Sugerencias de marketing, avisos, campañas
    INVENTORY_ADVICE = "inventory_advice"  # Consejos de inventario, stock, rotación
    REPORT_REQUEST = "report_request"      # Solicitar informes, balances, Excel
    ORDER_MANAGEMENT = "order_management"  # Cambiar estado, consultar pedidos
    CUSTOMER_QUERY = "customer_query"      # Consultar clientes, VIP, historial
    GENERAL_CHAT = "general_chat"          # Conversación general, saludos, ayuda
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    """Resultado de la clasificación de intención."""
    intent: IntentType
    confidence: float
    entities: dict = field(default_factory=dict)  # Entidades extraídas (ids, nombres, porcentajes, etc.)
    suggested_action: str = ""  # Acción sugerida para el agente
    requires_confirmation: bool = False
    context_hint: str = ""  # Pista de contexto para el prompt del LLM


@dataclass
class SessionContext:
    """Contexto de la sesión actual del chat."""
    messages: list = field(default_factory=list)  # Historial de mensajes
    last_intent: Optional[IntentType] = None
    last_entities: dict = field(default_factory=dict)
    active_topic: Optional[str] = None  # Tema activo: "productos", "promociones", "inventario", etc.
    pending_confirmation: Optional[dict] = None  # Acción pendiente de confirmación
    user_preferences: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str, intent: Optional[IntentType] = None, entities: dict = None):
        """Añade un mensaje al historial."""
        self.messages.append({
            "role": role,
            "content": content,
            "intent": intent.value if intent else None,
            "entities": entities or {},
            "timestamp": datetime.now().isoformat()
        })
        self.updated_at = datetime.now()
        if intent:
            self.last_intent = intent
        if entities:
            self.last_entities = entities
    
    def get_recent_context(self, max_messages: int = 5) -> list:
        """Obtiene los últimos N mensajes para contexto."""
        return self.messages[-max_messages:] if self.messages else []
    
    def clear_topic(self):
        """Limpia el tema activo."""
        self.active_topic = None

MAPA_TIENDA = """## LA TIENDA
CROVN: tienda online de camisetas y ropa urbana en Colombia (precios en COP) con panel de administración. Base PostgreSQL con estas tablas:
- products: catálogo e inventario de camisetas (categoryId->categories, supplierId->suppliers)
- product_variants: stock por talla y color de cada producto (productId->products)
- categories: categorías de productos
- suppliers: proveedores del inventario
- customers: clientes (email único, isVIP)
- orders: pedidos de clientes (customerId->customers; status Pendiente|Procesado|Enviado|Entregado; total, discount, promoCode)
- order_items: líneas de cada orden (orderId->orders, productId->products, quantity, price)
- promo_codes: códigos de descuento (code, discountPct, active, maxUses, usedCount, expiresAt)
- publications: ofertas, colecciones y noticias del carrusel de la tienda (productId->products, discountPct)
"""

# --- CLASIFICACIÓN DE INTENCIONES ---
INTENT_KEYWORDS = {
    IntentType.GENERAL_CHAT: [
        "hola", "buenos", "buenas", "gracias", "adios", "adiós", "chao", "bye",
        "ayuda", "help", "qué puedes", "que puedes", "quien eres", "quién eres",
        "como estas", "cómo estás", "que tal", "qué tal", "saludos"
    ],
    IntentType.PRODUCT_CREATE: [
        "crear producto", "crea producto", "nuevo producto", "nueva camiseta",
        "agregar producto", "agrega producto", "registrar producto", "registra producto",
        "insertar producto", "inserta producto", "añadir producto", "anadir producto",
        "creame un producto", "agregame un producto", "dame de alta producto",
        "crear camiseta", "crea camiseta", "nueva remera", "agregar remera",
        "crear item", "crea item", "nuevo item"
    ],
    IntentType.PRODUCT_UPDATE: [
        "actualizar producto", "actualiza producto", "cambiar precio", "cambia precio",
        "modificar producto", "modifica producto", "editar producto", "edita producto",
        "actualizar stock", "actualiza stock", "cambiar stock", "cambia stock",
        "poner precio", "poner stock", "establecer precio", "ajustar precio", "ajusta precio",
        "subir precio", "bajar precio", "sube precio", "baja precio",
        "actualizar precio", "actualiza precio", "modificar precio", "modifica precio",
        "editar precio", "edita precio"
    ],
    IntentType.PROMOTION_CREATE: [
        "crear codigo", "crear código", "crear promo", "crear promoción", "crear cupon", "crear cupón",
        "crear descuento", "generar codigo", "generar código", "generar promo", "generar cupón",
        "nuevo codigo", "nuevo código", "nueva promocion", "nueva promoción", "nuevo descuento",
        "crear oferta", "crear codigo promocional",
        "crea codigo", "crea código", "crea promo", "crea promoción", "crea cupón", "crea descuento",
        "genera codigo", "genera código", "nueva promo"
    ],
    IntentType.PROMOTION_QUERY: [
        "codigos", "códigos", "promociones", "promos", "descuentos", "cupones",
        "activos", "vigentes", "expirados", "usados", "listar", "ver", "mostrar",
        "que ofertas", "qué ofertas", "cuales son", "cuáles son", "ofertas activas",
        "promociones activas", "codigos activos", "códigos activos",
        "ver codigos", "ver códigos", "ver promociones", "ver ofertas"
    ],
    IntentType.DISCOUNT_ADVICE: [
        "recomienda descuento", "recomendar descuento", "sugiere descuento", "sugerir descuento",
        "consejo descuento", "consejos descuento", "estrategia descuento",
        "que descuento", "qué descuento", "cuanto descuento", "cuánto descuento",
        "aplicar descuento", "descuento para", "mejor descuento", "porcentaje descuento",
        "descuento en", "descuento a", "recomienda porcentaje", "sugiere porcentaje"
    ],
    IntentType.MARKETING_ADVICE: [
        "marketing", "campaña", "campana", "publicidad", "anuncio", "avisos",
        "coleccion", "colección", "lanzamiento", "promocionar", "vender más", "vender mas",
        "aumentar ventas", "atraer clientes", "fidelizar", "ideas marketing",
        "sugiere marketing", "recomienda marketing", "estrategia marketing",
        "ideas para vender", "como vender mas", "cómo vender más"
    ],
    IntentType.INVENTORY_ADVICE: [
        "inventario", "rotación", "rotacion", "agotado", "bajo stock",
        "reponer", "reposición", "reposicion", "exceso", "dead stock", "inventario muerto",
        "qué comprar", "que comprar", "qué producir", "que producir",
        "analiza inventario", "analizar inventario", "stock muerto",
        "analiza stock", "analizar stock", "recomienda stock"
    ],
    IntentType.REPORT_REQUEST: [
        "informe", "balance", "reporte", "excel", "exportar", "resumen",
        "ventas por", "ranking", "estadisticas", "estadísticas", "kpi", "metricas",
        "genera balance", "genera informe", "genera reporte", "balance semanal",
        "balance mensual", "informe ventas"
    ],
    IntentType.ORDER_MANAGEMENT: [
        "cambiar estado", "cambia estado", "marcar estado", "marca estado",
        "enviar pedido", "envia pedido", "procesar pedido", "procesa pedido",
        "entregar pedido", "entrega pedido", "anular pedido", "anula pedido",
        "cancelar pedido", "cancela pedido", "rastrear pedido", "rastreo pedido",
        "donde esta pedido", "dónde está pedido", "estado del pedido", "estado pedido",
        "marcar como enviado", "marcar como entregado", "marcar como procesado",
        "poner estado"
    ],
    IntentType.CUSTOMER_QUERY: [
        "cliente", "clientes", "vip", "correo", "email", "telefono", "teléfono",
        "comprador", "compradores", "historial", "pedidos de", "buscar cliente"
    ],
    IntentType.SHOP_QUERY: [
        "cuanto cuesta", "cuánto cuesta", "precio de", "precio del",
        "stock de", "stock del", "disponible", "hay stock", "tengo stock",
        "catalogo", "catálogo", "productos", "camisetas", "tallas", "colores",
        "buscar", "encontrar", "ver", "mostrar", "lista", "listado",
        "que hay", "qué hay", "que tienen", "qué tienen",
        "cuanto stock", "cuánto stock", "stock de", "cuanto hay", "cuánto hay",
        "precio producto", "precio camiseta", "stock camiseta"
    ],
}

# Pesos para cada tipo de intención (para desempatar)
INTENT_PRIORITY = {
    IntentType.PRODUCT_CREATE: 100,
    IntentType.PROMOTION_CREATE: 95,
    IntentType.ORDER_MANAGEMENT: 90,
    IntentType.PRODUCT_UPDATE: 85,
    IntentType.REPORT_REQUEST: 80,
    IntentType.DISCOUNT_ADVICE: 75,
    IntentType.MARKETING_ADVICE: 75,
    IntentType.INVENTORY_ADVICE: 75,
    IntentType.PROMOTION_QUERY: 70,
    IntentType.CUSTOMER_QUERY: 65,
    IntentType.SHOP_QUERY: 60,
    IntentType.GENERAL_CHAT: 50,
    IntentType.UNKNOWN: 0,
}

REGLAS_COMUN = """## REGLAS
- Columnas camelCase (createdAt, customerId, discountPct, isVIP...) sin comillas dobles: el sistema las entrecomilla. Nunca uses comillas dobles en la consulta.
- Texto: LOWER(col) LIKE '%valor%'. Fechas 'YYYY-MM-DD' tal cual las dice el usuario, sin restar días. Hoy: CURRENT_DATE.
- Ventas e ingresos = órdenes con status IN ('Procesado','Enviado','Entregado'); 'Pendiente' aún no es venta.
"""

REGLAS_ESCRITURA = """- Timestamps actuales: NOW(). En UPDATE/INSERT usa %s con los valores en parametros (sin % literal en esas consultas).
- INSERT: solo las columnas que el usuario mencionó (con una basta). No inventes datos ni pidas más: el sistema completa las obligatorias. No incluyas updatedAt ni createdAt.
- No se crean ni borran órdenes, ítems, clientes, productos ni categorías con DELETE (se hace en el panel).
- Si piden algo no permitido, genera la consulta más cercana (el sistema la valida).
"""

# Tablas que, además de la pertinente, hacen falta para los JOIN habituales.
RELACIONES_UTILES = {
    "orders": ("customers",),
    "order_items": ("orders", "products"),
    "product_variants": ("products",),
    "publications": ("products",),
}

# Cada ejemplo: (pregunta, sql, parametros)
TABLAS = {
    "products": {
        "etiqueta": "Productos",
        "descripcion": "Catálogo e inventario de camisetas. Cada producto tiene talla/color principal; sus variantes talla x color están en product_variants.",
        "operaciones": "Consultar, crear, cambiar precio/stock/datos.",
        "palabras": ["producto", "camiseta", "inventario", "stock", "talla", "precio", "genero", "mujer", "hombre", "unisex",
                     "dama", "caballero", "sku", "agotad", "caro", "barato", "costo", "ganancia", "catalogo", "existencia",
                     "unidades", "disponible", "color"],
        "reglas": [
            "NUNCA uses SELECT * ni selecciones image (Base64 enorme). Usa: id, sku, name, category, genero, size, color, price, stock.",
            "stock = unidades que muestra el panel. Sin stock: stock = 0. Stock bajo: stock <= 5.",
            "genero: dama/mujer/femenino -> LOWER(genero) LIKE '%mujer%'; caballero/hombre/masculino -> LIKE '%hombre%'; unisex/mixto -> LIKE '%unisex%'. Puede haber varios separados por / (ej. 'Mujer/Hombre') o NULL.",
            "category es texto libre (retro, qatar...). Filtra con LOWER(category) LIKE '%valor%'.",
            "size válidas: XS, S, M, L, XL, XXL. price > 0 y stock >= 0 (COP). Ganancia = price - \"costPrice\".",
            "INSERT de producto: solo las columnas mencionadas (name, description, category, size, color, price, stock, genero...). No incluyas categoryId ni sku; el sistema completa lo demás.",
        ],
        "ejemplos": [
            ("¿qué productos tenemos en el inventario?", """SELECT id, sku, name, category, genero, size, color, price, stock FROM products ORDER BY id;""", []),
            ("productos de mujer", """SELECT id, name, category, genero, size, price, stock FROM products WHERE LOWER(genero) LIKE '%mujer%' ORDER BY name;""", []),
            ("camisetas de la categoría qatar", """SELECT id, name, category, size, color, price, stock FROM products WHERE LOWER(category) LIKE '%qatar%';""", []),
            ("productos sin stock", """SELECT id, name, category, size, price FROM products WHERE stock = 0;""", []),
            ("productos con stock bajo", """SELECT id, name, size, stock FROM products WHERE stock <= 5 ORDER BY stock;""", []),
            ("producto más caro", """SELECT id, name, category, price FROM products ORDER BY price DESC LIMIT 1;""", []),
            ("productos de talla M", """SELECT id, name, category, size, color, price, stock FROM products WHERE size = 'M';""", []),
            ("buscar la camiseta retro", """SELECT id, name, category, size, color, price, stock FROM products WHERE LOWER(name) LIKE '%retro%' OR LOWER(category) LIKE '%retro%';""", []),
            ("valor total del inventario", """SELECT COALESCE(SUM(price * stock), 0) AS valor_inventario, COALESCE(SUM(stock), 0) AS unidades FROM products;""", []),
            ("ganancia por producto", """SELECT id, name, "costPrice", price, ROUND((price - COALESCE("costPrice", 0))::numeric, 0) AS ganancia FROM products ORDER BY ganancia DESC;""", []),
            ("cambia el precio del producto 12 a 59900", """UPDATE products SET price = %s, "updatedAt" = NOW() WHERE id = %s;""", [59900, 12]),
            ("actualiza el stock del producto 12 a 20", """UPDATE products SET stock = %s, "updatedAt" = NOW() WHERE id = %s;""", [20, 12]),
            ("crea el producto Camiseta Negra talla M de 59900 con 10 unidades en la categoría URBAN para hombre",
             """INSERT INTO products (name, description, category, "categoryId", size, price, stock, genero) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);""",
             ["Camiseta Negra", "Camiseta Negra", "URBAN", None, "M", 59900, 10, "Hombre"]),
            ("crea un producto llamado Gorra", """INSERT INTO products (name) VALUES (%s);""", ["Gorra"]),
        ],
    },
    "product_variants": {
        "etiqueta": "Variantes (talla / color)",
        "descripcion": "Combinaciones talla x color de un producto, cada una con stock y SKU propios (clave única productId+size+color).",
        "operaciones": "Consultar y ajustar stock.",
        "palabras": ["variante", "talla", "color", "sku", "por talla", "por color"],
        "reglas": [
            "Une con products por v.\"productId\" = p.id. Para 'stock por talla/color' usa v.stock, no products.stock.",
            "Variante agotada: v.stock = 0.",
        ],
        "ejemplos": [
            ("variantes del producto 11", """SELECT v.id, v.size, v.color, v.stock, v.sku FROM product_variants v WHERE v."productId" = 11 ORDER BY v.size;""", []),
            ("stock por talla y color de la camiseta retro", """SELECT p.name, v.size, v.color, v.stock FROM product_variants v JOIN products p ON p.id = v."productId" WHERE LOWER(p.name) LIKE '%retro%' ORDER BY v.size;""", []),
            ("variantes agotadas", """SELECT p.name, v.size, v.color, v.stock FROM product_variants v JOIN products p ON p.id = v."productId" WHERE v.stock = 0;""", []),
            ("comparar stock del producto con el de sus variantes", """SELECT p.id, p.name, p.stock AS stock_producto, COALESCE(SUM(v.stock), 0) AS stock_variantes FROM products p LEFT JOIN product_variants v ON v."productId" = p.id GROUP BY p.id, p.name, p.stock ORDER BY p.id;""", []),
            ("actualiza el stock de la variante 3 a 8", """UPDATE product_variants SET stock = %s, "updatedAt" = NOW() WHERE id = %s;""", [8, 3]),
        ],
    },
    "categories": {
        "etiqueta": "Categorías",
        "descripcion": "Categorías de productos (nombre único). products.\"categoryId\" apunta a categories.id.",
        "operaciones": "Consultar y crear.",
        "palabras": ["categoria"],
        "reglas": ["name es único. Para contar productos por categoría une products.\"categoryId\" = categories.id."],
        "ejemplos": [
            ("lista las categorías con su número de productos", """SELECT c.id, c.name, COUNT(p.id) AS productos FROM categories c LEFT JOIN products p ON p."categoryId" = c.id GROUP BY c.id, c.name ORDER BY c.name;""", []),
            ("categorías sin productos", """SELECT c.id, c.name FROM categories c LEFT JOIN products p ON p."categoryId" = c.id GROUP BY c.id, c.name HAVING COUNT(p.id) = 0;""", []),
            ("crea la categoría VERANO", """INSERT INTO categories (name) VALUES (%s);""", ["VERANO"]),
        ],
    },
    "orders": {
        "etiqueta": "Órdenes",
        "descripcion": "Pedidos de clientes. total ya incluye el descuento; discount es el monto descontado y promoCode el código usado.",
        "operaciones": "Consultar, reportes de ventas y cambiar estado. No crea ni elimina órdenes.",
        "palabras": ["orden", "pedido", "venta", "vendid", "ingreso", "factur", "estado", "pendiente", "procesad", "enviad",
                     "entregad", "anulad", "cancelad", "hoy", "mes", "semana", "recaud"],
        "reglas": [
            "status solo admite exactamente: 'Pendiente', 'Procesado', 'Enviado', 'Entregado' (no existe 'Cancelado': anular = borrar la orden desde el panel).",
            "Sinónimos: pendientes/sin despachar -> 'Pendiente'; procesados/confirmados -> 'Procesado'; enviados/en camino -> 'Enviado'; entregados/recibidos -> 'Entregado'.",
            "Siempre une con customers (c.id = o.\"customerId\") para mostrar el nombre del cliente.",
            "Ingresos = SUM(total) con status IN ('Procesado','Enviado','Entregado').",
            "Cambiar estado: UPDATE orders SET status = '<estado>' WHERE id = N (el correo al cliente solo se envía desde el panel).",
        ],
        "ejemplos": [
            ("listado de órdenes pendientes", """SELECT o.id, c.name AS cliente, o.total, o.status, o."createdAt" FROM orders o JOIN customers c ON c.id = o."customerId" WHERE o.status = 'Pendiente' ORDER BY o."createdAt" DESC;""", []),
            ("órdenes enviadas", """SELECT o.id, c.name AS cliente, o.total, o.status, o."createdAt" FROM orders o JOIN customers c ON c.id = o."customerId" WHERE o.status = 'Enviado' ORDER BY o."createdAt" DESC;""", []),
            ("resumen de órdenes por estado", """SELECT status, COUNT(*) AS ordenes, SUM(total) AS total FROM orders GROUP BY status ORDER BY status;""", []),
            ("cuántas órdenes hay", """SELECT COUNT(*) AS total FROM orders;""", []),
            ("órdenes de hoy", """SELECT o.id, c.name AS cliente, o.total, o.status FROM orders o JOIN customers c ON c.id = o."customerId" WHERE DATE(o."createdAt") = CURRENT_DATE;""", []),
            ("ingresos totales", """SELECT COALESCE(SUM(total), 0) AS ingresos, COUNT(*) AS ventas FROM orders WHERE status IN ('Procesado', 'Enviado', 'Entregado');""", []),
            ("ventas por mes", """SELECT TO_CHAR("createdAt", 'YYYY-MM') AS mes, COUNT(*) AS ordenes, SUM(total) AS total FROM orders WHERE status IN ('Procesado', 'Enviado', 'Entregado') GROUP BY 1 ORDER BY 1;""", []),
            ("órdenes que usaron código promocional", """SELECT o.id, c.name AS cliente, o."promoCode", o.discount, o.total FROM orders o JOIN customers c ON c.id = o."customerId" WHERE o."promoCode" IS NOT NULL;""", []),
            ("detalle de la orden 1", """SELECT o.id, c.name AS cliente, p.name AS producto, oi.quantity, oi.price, oi.quantity * oi.price AS subtotal, o.total FROM orders o JOIN customers c ON c.id = o."customerId" JOIN order_items oi ON oi."orderId" = o.id JOIN products p ON p.id = oi."productId" WHERE o.id = 1;""", []),
            ("marca la orden 5 como enviada", """UPDATE orders SET status = %s WHERE id = %s;""", ["Enviado", 5]),
        ],
    },
    "order_items": {
        "etiqueta": "Ítems de órdenes (más vendidos)",
        "descripcion": "Líneas de cada orden: producto, cantidad y precio unitario al momento de la compra (snapshot).",
        "operaciones": "Solo consultar (ranking de ventas, detalle de órdenes).",
        "palabras": ["item", "vendid", "mas vendido", "top", "articulo", "compro", "comprado", "ranking"],
        "reglas": [
            "Subtotal = quantity * price. Une order_items.\"orderId\" = orders.id y order_items.\"productId\" = products.id.",
        ],
        "ejemplos": [
            ("productos más vendidos", """SELECT p.id, p.name, SUM(oi.quantity) AS unidades, SUM(oi.quantity * oi.price) AS ingresos FROM order_items oi JOIN products p ON p.id = oi."productId" GROUP BY p.id, p.name ORDER BY unidades DESC LIMIT 5;""", []),
            ("ítems de la orden 1", """SELECT oi.id, p.name AS producto, oi.quantity, oi.price, oi.quantity * oi.price AS subtotal FROM order_items oi JOIN products p ON p.id = oi."productId" WHERE oi."orderId" = 1;""", []),
            ("unidades vendidas por categoría", """SELECT p.category, SUM(oi.quantity) AS unidades FROM order_items oi JOIN products p ON p.id = oi."productId" GROUP BY p.category ORDER BY unidades DESC;""", []),
        ],
    },
    "customers": {
        "etiqueta": "Clientes",
        "descripcion": "Clientes de la tienda (email único). VIP = 3 o más pedidos o 300000 COP o más gastados; es solo una insignia, no da descuento.",
        "operaciones": "Consultar, validar, crear y actualizar datos. No elimina (borraría sus pedidos).",
        "palabras": ["cliente", "vip", "correo", "email", "telefono", "direccion", "comprador"],
        "reglas": [
            "email es único: para 'validar si existe' usa SELECT con LOWER(email) = LOWER('...'). Si no existe, ofrece crearlo pero no lo insertes sin que lo pida.",
            "Pedidos y gasto de un cliente: LEFT JOIN orders o ON o.\"customerId\" = c.id con COUNT(o.id) y SUM(o.total).",
            "INSERT customers: solo las columnas mencionadas (name, email, phone, address); con una basta.",
        ],
        "ejemplos": [
            ("lista de clientes", """SELECT id, name, email, phone, "isVIP", "createdAt" FROM customers ORDER BY "createdAt" DESC;""", []),
            ("clientes VIP", """SELECT id, name, email, phone FROM customers WHERE "isVIP" = true;""", []),
            ("clientes con su número de pedidos y total gastado", """SELECT c.id, c.name, c.email, COUNT(o.id) AS pedidos, COALESCE(SUM(o.total), 0) AS total_gastado, c."isVIP" FROM customers c LEFT JOIN orders o ON o."customerId" = c.id GROUP BY c.id, c.name, c.email, c."isVIP" ORDER BY total_gastado DESC;""", []),
            ("clientes que ya califican como VIP", """SELECT c.id, c.name, COUNT(o.id) AS pedidos, COALESCE(SUM(o.total), 0) AS gastado FROM customers c LEFT JOIN orders o ON o."customerId" = c.id GROUP BY c.id, c.name HAVING COUNT(o.id) >= 3 OR COALESCE(SUM(o.total), 0) >= 300000;""", []),
            ("valida si el cliente ana@correo.com existe", """SELECT id, name, email, phone FROM customers WHERE LOWER(email) = LOWER('ana@correo.com');""", []),
            ("órdenes del cliente Ana", """SELECT o.id, c.name AS cliente, o.total, o.status, o."createdAt" FROM orders o JOIN customers c ON c.id = o."customerId" WHERE LOWER(c.name) LIKE '%ana%' ORDER BY o."createdAt" DESC;""", []),
            ("clientes sin pedidos", """SELECT c.id, c.name, c.email FROM customers c LEFT JOIN orders o ON o."customerId" = c.id WHERE o.id IS NULL;""", []),
            ("crea el cliente Ana Pérez con correo ana@correo.com y teléfono 3001234567",
             """INSERT INTO customers (name, email, phone, address, "updatedAt") VALUES (%s, %s, %s, %s, NOW());""",
             ["Ana Pérez", "ana@correo.com", "3001234567", ""]),
            ("actualiza el teléfono del cliente ana@correo.com a 3109876543", """UPDATE customers SET phone = %s, "updatedAt" = NOW() WHERE LOWER(email) = LOWER(%s);""", ["3109876543", "ana@correo.com"]),
            ("crea un cliente llamado Luis", """INSERT INTO customers (name) VALUES (%s);""", ["Luis"]),
        ],
    },
    "promo_codes": {
        "etiqueta": "Promociones (códigos de descuento)",
        "descripcion": "Códigos de descuento (code único en MAYÚSCULAS). Se aplican en el checkout; usedCount sube con cada uso.",
        "operaciones": "Consultar, crear, activar/desactivar, eliminar y enviar por correo.",
        "palabras": ["codigo", "promo", "descuento", "cupon", "expir", "vencid", "usos"],
        "reglas": [
            "code en MAYÚSCULAS sin espacios; discountPct entre 1 y 100. Si el usuario no da el código, el sistema genera uno CROVN-XXXXXX; si no da el descuento queda en 0.",
            "\"maxUses\" NULL = ilimitado (NUNCA 0: 0 deja el código agotado). \"expiresAt\" NULL = no expira.",
            "Estado: Inactivo si active = false; Expirado si \"expiresAt\" < NOW(); Agotado si \"maxUses\" no es NULL y \"usedCount\" >= \"maxUses\"; si no, Activo.",
            "Para desactivar usa UPDATE ... SET active = false (no DELETE) salvo que pida eliminar.",
            "Enviar un código por correo ('envía el código X a correo@dominio.com') lo resuelve el sistema aparte; no generes SQL para eso.",
            "IMPORTANT: Al crear código promocional, SIEMPRE genera JSON con: accion: 'INSERT', query: 'INSERT INTO promo_codes (code, \"discountPct\", active, \"maxUses\", \"usedCount\", \"updatedAt\") VALUES (%s, %s, true, %s, 0, NOW());', parametros: [\"CODIGO\", 20, null] (usar null para maxUses ilimitado). Si no da código, omite 'code' de columnas y usa DEFAULT.",
        ],
        "ejemplos": [
            ("códigos de promoción activos", """SELECT code, "discountPct", "maxUses", "usedCount", "expiresAt" FROM promo_codes WHERE active = true AND ("expiresAt" IS NULL OR "expiresAt" >= NOW()) AND ("maxUses" IS NULL OR "usedCount" < "maxUses") ORDER BY "createdAt" DESC;""", []),
            ("todos los códigos con su estado", """SELECT code, "discountPct", "usedCount", "maxUses", "expiresAt", CASE WHEN NOT active THEN 'Inactivo' WHEN "expiresAt" IS NOT NULL AND "expiresAt" < NOW() THEN 'Expirado' WHEN "maxUses" IS NOT NULL AND "usedCount" >= "maxUses" THEN 'Agotado' ELSE 'Activo' END AS estado FROM promo_codes ORDER BY "createdAt" DESC;""", []),
            ("códigos expirados", """SELECT code, "discountPct", "expiresAt" FROM promo_codes WHERE "expiresAt" IS NOT NULL AND "expiresAt" < NOW();""", []),
            ("código promocional más usado", """SELECT code, "discountPct", "usedCount" FROM promo_codes ORDER BY "usedCount" DESC LIMIT 1;""", []),
            ("crea un código promocional DESCUENTO10 con 10% hasta el 31/12/2026",
             """INSERT INTO promo_codes (code, "discountPct", active, "maxUses", "usedCount", "expiresAt", "updatedAt") VALUES (%s, %s, true, NULL, 0, %s, NOW());""",
             ["DESCUENTO10", 10, "2026-12-31"]),
            ("crea el código VERANO20 con 20% y máximo 50 usos",
             """INSERT INTO promo_codes (code, "discountPct", active, "maxUses", "usedCount", "updatedAt") VALUES (%s, %s, true, %s, 0, NOW());""",
             ["VERANO20", 20, 50]),
            ("crea el código OTOÑO15", """INSERT INTO promo_codes (code) VALUES (%s);""", ["OTOÑO15"]),
            ("crea un código con 15% de descuento", """INSERT INTO promo_codes (discountPct) VALUES (%s);""", [15]),
            ("crea código promocional BLACKFRIDAY 30% max 100 usos",
             """INSERT INTO promo_codes (code, "discountPct", active, "maxUses", "usedCount", "updatedAt") VALUES (%s, %s, true, %s, 0, NOW());""",
             ["BLACKFRIDAY", 30, 100]),
            ("crea código NAVIDAD25 con 25% sin límite de usos",
             """INSERT INTO promo_codes (code, "discountPct", active, "maxUses", "usedCount", "updatedAt") VALUES (%s, %s, true, NULL, 0, NOW());""",
             ["NAVIDAD25", 25, None]),
            ("desactiva el código PROMO45", """UPDATE promo_codes SET active = false, "updatedAt" = NOW() WHERE UPPER(code) = UPPER(%s);""", ["PROMO45"]),
            ("elimina el código VERANO10", """DELETE FROM promo_codes WHERE UPPER(code) = UPPER(%s);""", ["VERANO10"]),
        ],
    },
    "publications": {
        "etiqueta": "Publicaciones (ofertas, colecciones, noticias)",
        "descripcion": "Contenido del carrusel de la tienda. Una oferta puede asociarse a un producto (productId) y aplica discountPct a ese producto.",
        "operaciones": "Consultar, crear, activar/desactivar.",
        "palabras": ["publicacion", "oferta", "noticia", "coleccion", "banner", "promocion"],
        "reglas": [
            "NUNCA uses SELECT * (la columna image es Base64 enorme). Usa: id, title, type, active, \"discountPct\", \"publishedAt\", \"expiresAt\", \"productId\".",
            "type solo: 'noticia', 'coleccion' o 'oferta' (por defecto 'noticia'). discountPct entre 0 y 90 y solo tiene sentido en 'oferta'.",
            "Estado: Inactiva si active = false; Programada si \"publishedAt\" > NOW(); Expirada si \"expiresAt\" < NOW(); si no, Activa.",
            "INSERT publications: solo las columnas mencionadas (title, subtitle, content, type, productId, discountPct, active...); con una basta.",
        ],
        "ejemplos": [
            ("publicaciones activas", """SELECT id, title, type, "discountPct", "publishedAt", "expiresAt", "productId" FROM publications WHERE active = true AND ("publishedAt" IS NULL OR "publishedAt" <= NOW()) AND ("expiresAt" IS NULL OR "expiresAt" >= NOW());""", []),
            ("ofertas", """SELECT id, title, "discountPct", active, "productId" FROM publications WHERE type = 'oferta' ORDER BY "createdAt" DESC;""", []),
            ("todas las publicaciones con su estado", """SELECT id, title, type, CASE WHEN NOT active THEN 'Inactiva' WHEN "publishedAt" IS NOT NULL AND "publishedAt" > NOW() THEN 'Programada' WHEN "expiresAt" IS NOT NULL AND "expiresAt" < NOW() THEN 'Expirada' ELSE 'Activa' END AS estado FROM publications ORDER BY "createdAt" DESC;""", []),
            ("ofertas con el producto asociado", """SELECT pu.id, pu.title, pu."discountPct", p.name AS producto, p.price FROM publications pu LEFT JOIN products p ON p.id = pu."productId" WHERE pu.type = 'oferta';""", []),
            ("crea una oferta del 20% para el producto 12",
             """INSERT INTO publications (title, subtitle, content, type, active, "productId", "discountPct", "updatedAt") VALUES (%s, %s, %s, 'oferta', true, %s, %s, NOW());""",
             ["Oferta especial", "Aprovecha", "Descuento por tiempo limitado", 12, 20]),
            ("desactiva la publicación 3", """UPDATE publications SET active = false, "updatedAt" = NOW() WHERE id = %s;""", [3]),
            ("crea una publicación llamada Nueva colección", """INSERT INTO publications (title) VALUES (%s);""", ["Nueva colección"]),
        ],
    },
    "suppliers": {
        "etiqueta": "Proveedores",
        "descripcion": "Proveedores del inventario. products.\"supplierId\" apunta a suppliers.id.",
        "operaciones": "Consultar, crear, activar/desactivar.",
        "palabras": ["proveedor", "supplier"],
        "reglas": [
            "INSERT suppliers: solo las columnas mencionadas (name, contact, phone, email, address, notes); con una basta.",
            "Productos de un proveedor: JOIN products p ON p.\"supplierId\" = s.id.",
        ],
        "ejemplos": [
            ("proveedores activos", """SELECT id, name, contact, phone, email FROM suppliers WHERE active = true ORDER BY name;""", []),
            ("productos por proveedor", """SELECT s.name AS proveedor, COUNT(p.id) AS productos FROM suppliers s LEFT JOIN products p ON p."supplierId" = s.id GROUP BY s.name ORDER BY productos DESC;""", []),
            ("productos sin proveedor", """SELECT id, name, category FROM products WHERE "supplierId" IS NULL;""", []),
            ("crea un proveedor llamado Textiles SA con teléfono 3001234567",
             """INSERT INTO suppliers (name, contact, phone, email, address, notes, active, "updatedAt") VALUES (%s, %s, %s, %s, %s, %s, true, NOW());""",
             ["Textiles SA", None, "3001234567", None, None, None]),
            ("desactiva el proveedor 1", """UPDATE suppliers SET active = false, "updatedAt" = NOW() WHERE id = %s;""", [1]),
            ("crea el proveedor Textiles SA", """INSERT INTO suppliers (name) VALUES (%s);""", ["Textiles SA"]),
        ],
    },
}

_VERBOS = {
    "INSERT": ("crea", "crear", "creame", "agrega", "agregar", "registra", "registrar", "inserta", "nuevo", "nueva", "anade", "anadir"),
    "UPDATE": ("actualiza", "actualizar", "cambia", "cambiar", "modifica", "modificar", "marca", "marcar", "desactiva", "desactivar",
               "activa", "activar", "ajusta", "ajustar", "edita", "editar", "pon", "poner"),
    "DELETE": ("elimina", "eliminar", "borra", "borrar", "quita", "quitar"),
}


def _norm(texto):
    sin_tildes = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


def _accion(sql):
    return sql.lstrip().split()[0].upper()


def es_escritura(texto):
    """True si la petición parece crear, modificar o borrar datos; ante la duda conviene tratarla como escritura."""
    palabras = set(re.findall(r"\w+", _norm(texto)))
    return any(v in palabras for vs in _VERBOS.values() for v in vs)


def tablas_relevantes(texto, max_tablas=3):
    """Tablas ordenadas por coincidencia de palabras clave con el texto del usuario."""
    t = _norm(texto)
    puntajes = []
    for orden, (nombre, datos) in enumerate(TABLAS.items()):
        puntaje = sum(1 for p in datos["palabras"] if p in t)
        if puntaje:
            puntajes.append((-puntaje, orden, nombre))
    if not puntajes:
        return ["products", "orders"]
    puntajes.sort()
    return [n for p, _, n in puntajes[:max_tablas] if -p * 2 >= -puntajes[0][0]]


def tablas_con_detalle(texto):
    """Tablas cuyas columnas se envían al modelo: las pertinentes y, al consultar, las de sus JOIN habituales."""
    elegidas = tablas_relevantes(texto, max_tablas=2)
    if not es_escritura(texto):
        for nombre in list(elegidas):
            elegidas += [t for t in RELACIONES_UTILES.get(nombre, ()) if t not in elegidas]
    return elegidas


def _elegir_ejemplos(texto, ejemplos, k):
    t = _norm(texto)
    palabras = {w for w in re.findall(r"\w+", t) if len(w) > 3}
    verbos = {a for a, vs in _VERBOS.items() if any(v in t.split() for v in vs)}

    def puntaje(i_ej):
        i, (pregunta, sql, _) = i_ej
        p = _norm(pregunta)
        s = sum(1 for w in palabras if w in p)
        if _accion(sql) in verbos:
            s += 2
        return (-s, i)

    return [e for _, e in sorted(enumerate(ejemplos), key=puntaje)[:k]]


def _sin_comillas(texto):
    return texto.replace('"', "")


_RE_REGLA_ESCRITURA = re.compile(r"\b(INSERT|UPDATE|DELETE)\b|Cambiar estado|sistema genera|Enviar un código|code en MAYÚSCULAS", re.IGNORECASE)


def construir_contexto(texto, escritura=None, intent_result: Optional[IntentResult] = None, session_context: Optional[SessionContext] = None):
    """
    Construye el contexto para el LLM incluyendo:
    - Reglas de negocio
    - Ejemplos relevantes
    - Información de intención clasificada
    - Contexto de sesión (historial reciente)
    """
    if escritura is None:
        escritura = es_escritura(texto)
    
    partes = [_sin_comillas(REGLAS_COMUN + (REGLAS_ESCRITURA if escritura else ""))]
    
    # Añadir información de intención si está disponible
    if intent_result:
        partes.append(f"### INTENCIÓN DETECTADA: {intent_result.intent.value.upper()}")
        partes.append(f"Confianza: {intent_result.confidence:.0%}")
        partes.append(f"Acción sugerida: {intent_result.suggested_action}")
        if intent_result.context_hint:
            partes.append(f"Contexto: {intent_result.context_hint}")
        if intent_result.entities:
            partes.append(f"Entidades extraídas: {json.dumps(intent_result.entities, ensure_ascii=False)}")
        if intent_result.requires_confirmation:
            partes.append("⚠️ REQUIERE CONFIRMACIÓN DEL USUARIO ANTES DE EJECUTAR")
        partes.append("")  # Línea en blanco
    
    # Añadir contexto de sesión (últimos 3 mensajes)
    if session_context and session_context.messages:
        recent = session_context.get_recent_context(3)
        if recent:
            partes.append("### CONTEXTO DE SESIÓN (últimos mensajes):")
            for msg in recent:
                role = "Usuario" if msg["role"] == "user" else "Asistente"
                partes.append(f"- {role}: {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")
            partes.append("")
    
    # Tablas relevantes y ejemplos
    for i, nombre in enumerate(tablas_relevantes(texto, max_tablas=2)):
        datos = TABLAS[nombre]
        cabecera = f"### {nombre}: {datos['descripcion']}"
        partes.append(cabecera + (f" Permitido: {datos['operaciones']}" if escritura else ""))
        partes.extend(f"- {_sin_comillas(r)}" for r in datos["reglas"] if escritura or not _RE_REGLA_ESCRITURA.search(r))
        ejemplos = datos["ejemplos"] if escritura else [e for e in datos["ejemplos"] if _accion(e[1]) == "SELECT"]
        for pregunta, sql, params in _elegir_ejemplos(texto, ejemplos, 3 if i == 0 else 2):
            extra = f" | parametros: {json.dumps(params, ensure_ascii=False)}" if params else ""
            partes.append(f"- {pregunta} -> {_sin_comillas(sql)}{extra}")
    
    return "\n".join(partes)


_RUIDO = {"mostrar", "muestra", "muestrame", "lista", "listado", "listar", "ver", "dame", "dime", "quiero", "necesito", "cual", "cuales",
          "que", "tenemos", "tengo", "hay", "existen", "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "en", "por",
          "favor", "todos", "todas", "me", "mi", "mis", "tienda", "inventario", "y", "a", "al", "para"}
_PLURALES = (("ones", 2), ("ores", 2), ("enes", 2), ("eres", 2))


def _raiz(palabra):
    for fin, quitar in _PLURALES:
        if palabra.endswith(fin):
            return palabra[:-quitar]
    return palabra[:-1] if len(palabra) > 3 and palabra.endswith("s") and not palabra.endswith("ss") else palabra


def _clave(texto):
    """Palabras significativas de una pregunta (sin relleno ni plurales) para reconocer preguntas ya conocidas."""
    palabras = re.findall(r"[a-z0-9]+(?:[@.][a-z0-9]+)*", _norm(texto))
    return frozenset(_raiz(p) for p in palabras if p not in _RUIDO)


def _extraer_entidades(texto: str, intent: IntentType) -> dict:
    """Extrae entidades relevantes del texto según la intención."""
    entidades = {}
    texto_lower = texto.lower()
    
    # Extraer IDs numéricos
    ids = re.findall(r'\b(\d+)\b', texto)
    if ids:
        entidades["ids"] = [int(x) for x in ids]
    
    # Extraer porcentajes
    pcts = re.findall(r'(\d+)\s*%', texto)
    if pcts:
        entidades["porcentajes"] = [int(x) for x in pcts]
    
    # Extraer emails
    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', texto)
    if emails:
        entidades["emails"] = emails
    
    # Extraer códigos (mayúsculas con guiones/números)
    codigos = re.findall(r'\b([A-Z0-9]{4,}(?:-[A-Z0-9]+)?)\b', texto.upper())
    if codigos:
        entidades["codigos"] = codigos
    
    # Extraer precios (COP)
    precios = re.findall(r'[\$]?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)', texto)
    if precios:
        entidades["precios"] = [float(p.replace(".", "").replace(",", ".")) for p in precios]
    
    # Entidades específicas por intención
    if intent in (IntentType.PRODUCT_CREATE, IntentType.PRODUCT_UPDATE):
        # Buscar categoría
        for cat in ["camiseta", "camisetas", "gorra", "gorras", "pantalon", "pantalones", "hoodie", "hoodies", "sudadera", "sudaderas"]:
            if cat in texto_lower:
                entidades["categoria_sugerida"] = cat
                break
        # Buscar tallas
        tallas_encontradas = [t for t in TALLAS if t.lower() in texto_lower]
        if tallas_encontradas:
            entidades["tallas"] = tallas_encontradas
        # Buscar colores
        colores = ["negro", "blanco", "rojo", "gris", "azul", "verde", "beige", "blanco", "negro"]
        colores_encontrados = [c for c in colores if c in texto_lower]
        if colores_encontrados:
            entidades["colores"] = colores_encontrados
    
    if intent == IntentType.DISCOUNT_ADVICE:
        if entidades.get("porcentajes"):
            entidades["descuento_sugerido"] = entidades["porcentajes"][0]
    
    if intent == IntentType.PROMOTION_CREATE:
        if entidades.get("porcentajes"):
            entidades["descuento_pct"] = entidades["porcentajes"][0]
        if entidades.get("codigos"):
            entidades["codigo_sugerido"] = entidades["codigos"][0]
    
    return entidades


def clasificar_intencion(texto: str, contexto: Optional[SessionContext] = None) -> IntentResult:
    """
    Clasifica la intención del usuario basándose en palabras clave y contexto.
    Retorna un IntentResult con la intención, confianza y entidades extraídas.
    """
    if not texto or not texto.strip():
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            suggested_action="Pide al usuario que reformule su consulta."
        )
    
    texto_norm = _norm(texto)
    palabras = set(re.findall(r"\w+", texto_norm))
    
    # Detectar verbos de acción al inicio (primeras 3-4 palabras)
    primeras_palabras = re.findall(r"\w+", texto_norm)[:4]
    verbos_inicio = {"crear", "crea", "nuevo", "nueva", "agregar", "agrega", "registrar", "registra",
                     "actualizar", "actualiza", "cambiar", "cambia", "modificar", "modifica",
                     "editar", "edita", "poner", "pon", "establecer", "ajustar", "ajusta",
                     "generar", "genera", "listar", "ver", "mostrar", "buscar", "encontrar",
                     "recomendar", "recomienda", "recomiendame", "recomiendanos",
                     "sugerir", "sugiere", "sugiereme", "sugierenos",
                     "analiza", "analizar", "analizame",
                     "cambiar", "cambia", "marcar", "marca", "enviar", "envia", "procesar",
                     "entregar", "entrega", "anular", "anula", "cancelar", "cancela"}
    
    accion_detectada = None
    for p in primeras_palabras:
        if p in verbos_inicio:
            accion_detectada = p
            break
    
    # Puntuación por intención
    scores = {}
    for intent_type, keywords in INTENT_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in texto_norm:
                # Bonus si la palabra clave aparece al inicio (primera acción)
                inicio = texto_norm.find(kw)
                if inicio < 30:  # En los primeros 30 caracteres
                    score += 8
                else:
                    score += 3
                # Bonus extra si es coincidencia exacta de palabra
                if kw in palabras:
                    score += 2
            # También buscar palabras individuales de la frase clave
            kw_palabras = kw.split()
            if len(kw_palabras) > 1:
                coincidencias = sum(1 for pw in kw_palabras if pw in palabras)
                if coincidencias >= len(kw_palabras) * 0.7:  # 70% de las palabras coinciden
                    score += coincidencias * 2
        
        # BOOST CRÍTICO: Si la acción detectada al inicio coincide con la intención
        if accion_detectada:
            verbos_por_intent = {
                IntentType.PRODUCT_CREATE: {"crear", "crea", "nuevo", "nueva", "agregar", "agrega", "registrar", "registra"},
                IntentType.PRODUCT_UPDATE: {"actualizar", "actualiza", "cambiar", "cambia", "modificar", "modifica", "editar", "edita", "poner", "ajustar", "ajusta"},
                IntentType.PROMOTION_CREATE: {"crear", "crea", "generar", "genera"},
                IntentType.PROMOTION_QUERY: {"listar", "ver", "mostrar", "buscar", "encontrar"},
                IntentType.DISCOUNT_ADVICE: {"recomendar", "recomienda", "sugerir", "sugiere"},
                IntentType.MARKETING_ADVICE: {"sugerir", "sugiere", "recomendar", "recomienda"},
                IntentType.INVENTORY_ADVICE: {"analizar", "analiza"},
                IntentType.REPORT_REQUEST: {"generar", "genera"},
                IntentType.ORDER_MANAGEMENT: {"cambiar", "cambia", "marcar", "marca", "enviar", "envia", "procesar", "entregar", "anular", "anula", "cancelar", "cancela"},
                IntentType.SHOP_QUERY: {"buscar", "encontrar", "ver", "mostrar", "listar"},
                IntentType.CUSTOMER_QUERY: {"buscar"},
            }
            if intent_type in verbos_por_intent and accion_detectada in verbos_por_intent[intent_type]:
                score += 20  # Boost muy fuerte para acción correcta al inicio
        
        scores[intent_type] = score
    
    # Boost por contexto de sesión
    if contexto and contexto.last_intent:
        # Si la intención anterior fue de creación/actualización, priorizar confirmaciones
        if contexto.last_intent in (IntentType.PRODUCT_CREATE, IntentType.PROMOTION_CREATE, IntentType.PRODUCT_UPDATE):
            # Palabras de confirmación
            confirm_words = {"si", "sí", "confirmo", "dale", "hazlo", "ok", "vale", "correcto", "exacto"}
            if any(w in palabras for w in confirm_words):
                scores[contexto.last_intent] = scores.get(contexto.last_intent, 0) + 5
                entidades = _extraer_entidades(texto, contexto.last_intent)
                return IntentResult(
                    intent=contexto.last_intent,
                    confidence=0.9,
                    entities=entidades,
                    suggested_action="Confirmar acción pendiente",
                    requires_confirmation=True,
                    context_hint=f"El usuario confirma la {contexto.last_intent.value.replace('_', ' ')} anterior."
                )
    
    # Encontrar la intención con mayor score
    if not scores or max(scores.values()) == 0:
        return IntentResult(
            intent=IntentType.GENERAL_CHAT,
            confidence=0.3,
            suggested_action="Responder de forma conversacional o pedir clarificación."
        )
    
    # Desempatar por prioridad
    max_score = max(scores.values())
    candidatos = [intent for intent, score in scores.items() if score == max_score]
    intent_ganadora = max(candidatos, key=lambda x: INTENT_PRIORITY.get(x, 0))
    
    confidence = min(0.9, 0.4 + (max_score * 0.1))
    entidades = _extraer_entidades(texto, intent_ganadora)
    
    # Generar acción sugerida y context_hint según intención
    suggested_actions = {
        IntentType.SHOP_QUERY: "Consultar catálogo/inventario via API o SQL",
        IntentType.PRODUCT_CREATE: "Crear producto via API REST (multipart/form-data para imágenes)",
        IntentType.PRODUCT_UPDATE: "Actualizar producto via API REST",
        IntentType.PROMOTION_CREATE: "Crear código promocional u oferta via API",
        IntentType.PROMOTION_QUERY: "Listar promociones activas/inactivas",
        IntentType.DISCOUNT_ADVICE: "Dar consejo estratégico basado en datos de ventas/stock",
        IntentType.MARKETING_ADVICE: "Sugerir campañas, avisos, colecciones via informes.py",
        IntentType.INVENTORY_ADVICE: "Analizar stock, rotación, dead stock via SQL/API",
        IntentType.REPORT_REQUEST: "Generar informe Excel via informes.py",
        IntentType.ORDER_MANAGEMENT: "Gestionar pedidos (estado, consulta) via API",
        IntentType.CUSTOMER_QUERY: "Consultar clientes, VIP, historial via API/SQL",
        IntentType.GENERAL_CHAT: "Responder conversacionalmente",
    }
    
    context_hints = {
        IntentType.SHOP_QUERY: "El usuario quiere ver productos, stock o precios. Usa API shop o SQL SELECT.",
        IntentType.PRODUCT_CREATE: "El usuario quiere crear un producto. Necesita: nombre, categoría, precio, stock, talla, color. Las imágenes van por multipart.",
        IntentType.PRODUCT_UPDATE: "El usuario quiere modificar un producto existente. Identifica el ID y los campos a cambiar.",
        IntentType.PROMOTION_CREATE: "El usuario quiere crear un código descuento u oferta. Código en MAYÚSCULAS, descuento 1-90%.",
        IntentType.PROMOTION_QUERY: "El usuario quiere ver códigos u ofertas existentes. Filtra por active, expiresAt, maxUses.",
        IntentType.DISCOUNT_ADVICE: "El usuario pide consejo sobre descuentos. Analiza ventas, stock, margen para recomendar.",
        IntentType.MARKETING_ADVICE: "El usuario quiere ideas de marketing. Usa informes.ideas_marketing() con datos reales.",
        IntentType.INVENTORY_ADVICE: "El usuario quiere optimizar inventario. Analiza rotación, stock bajo, dead stock.",
        IntentType.REPORT_REQUEST: "El usuario quiere un informe/balance. Usa informes.datos_balance() y informes.construir_excel().",
        IntentType.ORDER_MANAGEMENT: "El usuario quiere gestionar un pedido. Estados válidos: Pendiente, Procesado, Enviado, Entregado.",
        IntentType.CUSTOMER_QUERY: "El usuario consulta clientes. Une con orders para ver pedidos y gasto total.",
        IntentType.GENERAL_CHAT: "Conversación general. Responde amablemente y ofrece ayuda específica.",
    }
    
    return IntentResult(
        intent=intent_ganadora,
        confidence=confidence,
        entities=entidades,
        suggested_action=suggested_actions.get(intent_ganadora, "Procesar según contexto"),
        context_hint=context_hints.get(intent_ganadora, ""),
        requires_confirmation=intent_ganadora in (IntentType.PRODUCT_CREATE, IntentType.PROMOTION_CREATE, IntentType.ORDER_MANAGEMENT)
    )


_ATAJOS = None


def atajo_sql(texto):
    """SQL de un ejemplo conocido si la pregunta es equivalente (mismas palabras significativas); None si no."""
    global _ATAJOS
    if _ATAJOS is None:
        _ATAJOS = {}
        for datos in TABLAS.values():
            for pregunta, sql, params in datos["ejemplos"]:
                clave = _clave(pregunta)
                if clave and not params and _accion(sql) == "SELECT":
                    _ATAJOS.setdefault(clave, sql)
    if es_escritura(texto):
        return None
    clave = _clave(texto)
    return _ATAJOS.get(clave) if clave else None


def sugerencias(nombre_tabla):
    """[(pregunta, es_escritura)] para la UI."""
    return [(p, _accion(s) != "SELECT") for p, s, _ in TABLAS[nombre_tabla]["ejemplos"]]

"""Conocimiento de negocio de CROVN (derivado de backend/prisma/schema.prisma y backend/src/routes)."""
import json
import re
import unicodedata

ESTADOS_ORDEN = ("Pendiente", "Procesado", "Enviado", "Entregado")
ESTADOS_VENTA = ("Procesado", "Enviado", "Entregado")
TALLAS = ("XS", "S", "M", "L", "XL", "XXL")

REGLAS_GLOBALES = """## 3. REGLAS DE NEGOCIO GLOBALES (CROVN: tienda de ropa urbana en Colombia, moneda COP)
- Columnas camelCase (createdAt, updatedAt, customerId, productId, orderId, discountPct, maxUses, usedCount, expiresAt, publishedAt, isVIP, promoCode...) escríbelas SIN comillas dobles: el sistema las entrecomilla solo. NUNCA uses comillas dobles dentro de la consulta.
- Texto: compara con LOWER(col) LIKE '%valor%'. Fechas: 'YYYY-MM-DD' tal cual las dice el usuario (05/10/2026 -> '2026-10-05'), sin restar días ni zonas horarias. Timestamps actuales: NOW(). Hoy: CURRENT_DATE.
- INSERT: incluye SOLO las columnas que el usuario mencionó; con un solo dato basta. NUNCA inventes valores ni pidas más datos: el sistema completa solo las columnas obligatorias que falten (updatedAt, correo, código, etc.). No incluyas updatedAt ni createdAt.
- Parámetros: en UPDATE/INSERT usa %s y devuelve los valores en "parametros". No uses el carácter % literal en queries que llevan %s.
- Ingresos/ventas = órdenes con status IN ('Procesado','Enviado','Entregado'); una orden 'Pendiente' aún no cuenta como venta.
- El agente NO crea ni elimina órdenes, ítems, clientes, productos ni categorías con DELETE: eso se hace en el panel porque descuenta/restituye stock y valida reglas.
- Si el usuario pide algo fuera de lo permitido, genera igualmente la consulta más cercana (el sistema la valida).
"""

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
        ],
        "ejemplos": [
            ("códigos de promoción activos y utilizables", """SELECT code, "discountPct", "maxUses", "usedCount", "expiresAt" FROM promo_codes WHERE active = true AND ("expiresAt" IS NULL OR "expiresAt" >= NOW()) AND ("maxUses" IS NULL OR "usedCount" < "maxUses") ORDER BY "createdAt" DESC;""", []),
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
    "INSERT": ("crea", "crear", "agrega", "agregar", "registra", "nuevo", "nueva", "anade"),
    "UPDATE": ("actualiza", "cambia", "modifica", "marca", "desactiva", "activa", "ajusta", "edita"),
    "DELETE": ("elimina", "borra", "quita"),
}


def _norm(texto):
    sin_tildes = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


def _accion(sql):
    return sql.lstrip().split()[0].upper()


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
    return [n for _, _, n in sorted(puntajes)[:max_tablas]]


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


def construir_contexto(texto):
    """Reglas globales + reglas y ejemplos solo de las tablas relevantes (cabe en el contexto del modelo)."""
    partes = [_sin_comillas(REGLAS_GLOBALES), "## 3b. TABLAS RELEVANTES PARA ESTA PETICIÓN (sigue sus reglas y el patrón de sus ejemplos)"]
    for i, nombre in enumerate(tablas_relevantes(texto)):
        datos = TABLAS[nombre]
        partes.append(f"### {nombre}: {datos['descripcion']}\nOperaciones permitidas: {datos['operaciones']}")
        partes.extend(f"- {_sin_comillas(r)}" for r in datos["reglas"])
        partes.append("Ejemplos:")
        for pregunta, sql, params in _elegir_ejemplos(texto, datos["ejemplos"], 6 if i == 0 else 3):
            extra = f" | parametros: {json.dumps(params, ensure_ascii=False)}" if params else ""
            partes.append(f'- {pregunta} -> {_sin_comillas(sql)}{extra}')
    return "\n".join(partes)


def sugerencias(nombre_tabla):
    """[(pregunta, es_escritura)] para la UI."""
    return [(p, _accion(s) != "SELECT") for p, s, _ in TABLAS[nombre_tabla]["ejemplos"]]

"""Evalúa la precisión del agente: ejecuta los SELECT y solo valida (sin ejecutar) las escrituras."""
import sys
import time
from agent import generar_consulta, MODELO, set_modelo
from database import ejecutar_consulta
from contexto_app import TABLAS, ESTADOS_ORDEN

PREGUNTAS = [
    # (pregunta, tabla esperada en la query, texto prohibido en la query)
    ("¿qué productos tenemos?", "products", "image"),
    ("productos de mujer", "products", "image"),
    ("productos sin stock", "products", "image"),
    ("producto más caro", "products", None),
    ("stock por talla y color del producto 13", "product_variants", None),
    ("listado de órdenes pendientes", "orders", "cancelado"),
    ("órdenes enviadas", "orders", None),
    ("cuánto hemos vendido en total", "orders", "cancelado"),
    ("productos más vendidos", "order_items", None),
    ("clientes VIP", "customers", None),
    ("cuántos pedidos ha hecho cada cliente", "customers", None),
    ("códigos de promoción activos", "promo_codes", None),
    ("códigos promocionales expirados", "promo_codes", None),
    ("publicaciones activas", "publications", "image"),
    ("proveedores activos", "suppliers", None),
    ("categorías con su número de productos", "categories", None),
    ("crea un código promocional OTOÑO15 con 15% hasta el 31/12/2026", "promo_codes", None),
    ("marca la orden 5 como enviada", "orders", None),
    ("desactiva el código PROMO45", "promo_codes", None),
    ("crea el cliente Luis Gómez con correo luis@correo.com", "customers", None),
    ("elimina todos los productos", None, None),
    ("borra la tabla de clientes", None, None),
]


def evaluar():
    ok = 0
    for pregunta, tabla, prohibido in PREGUNTAS:
        t0 = time.time()
        r = generar_consulta(pregunta)
        seg = time.time() - t0
        estado, detalle = "OK", ""
        if tabla is None:
            # Debe ser rechazada
            if "error" not in r:
                estado, detalle = "FALLO", f"debía rechazarse y generó: {r['query']}"
        elif "error" in r:
            estado, detalle = "FALLO", r["error"]
        else:
            q = r["query"]
            if tabla not in q.lower():
                estado, detalle = "FALLO", f"no usa {tabla}: {q}"
            elif prohibido and prohibido in q.lower():
                estado, detalle = "FALLO", f"contiene '{prohibido}': {q}"
            elif r["accion"] == "SELECT":
                filas, cols = ejecutar_consulta(q, r["parametros"])
                if filas is None:
                    estado, detalle = "FALLO", f"error SQL: {cols} | {q}"
                else:
                    detalle = f"{len(filas)} fila(s)"
            else:
                detalle = f"(no ejecutada) {q} {r['parametros']}"
        ok += estado == "OK"
        print(f"[{estado}] {seg:4.1f}s  {pregunta}\n        {detalle}")
    print(f"\nModelo {MODELO}: {ok}/{len(PREGUNTAS)} correctas")
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1:
        set_modelo(sys.argv[1])
    evaluar()

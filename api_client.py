"""Cliente tipado para la API REST del backend CROVN.
Reemplaza el acceso directo a SQL para escrituras y operaciones con side-effects."""
from __future__ import annotations
import httpx
from typing import Any
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class ApiResponse:
    ok: bool
    data: Any = None
    message: str = ""
    error: str | None = None


# 1x1 pixel PNG transparente para usar como imagen dummy cuando no se proporciona ninguna
_DUMMY_PNG = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x05\x00\x1a\x0c\x00\x00\x00\x00IEND\xaeB`\x82'


class CROVNApiClient:
    """Cliente asíncrono para la API REST del backend."""

    def __init__(
        self,
        base_url: str = "http://localhost:4000",
        token: str | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._default_headers(),
            )
        return self._client

    def _default_headers(self) -> dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def set_token(self, token: str | None):
        self.token = token
        # Forzar recreación del cliente con nuevo header
        if self._client and not self._client.is_closed:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._client.aclose())
            except RuntimeError:
                # No running event loop, close synchronously
                import threading
                def close_client():
                    new_loop = asyncio.new_event_loop()
                    new_loop.run_until_complete(self._client.aclose())
                    new_loop.close()
                threading.Thread(target=close_client, daemon=True).start()
        self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
    ) -> ApiResponse:
        """Ejecuta petición HTTP y normaliza respuesta."""
        headers = self._default_headers()
        # Si hay files, quitar Content-Type para que httpx ponga multipart/form-data
        if files:
            headers.pop("Content-Type", None)

        try:
            resp = await self.client.request(
                method, path, params=params, json=json, data=data, files=files, headers=headers
            )
            if resp.status_code >= 400:
                try:
                    err = resp.json()
                    msg = err.get("message") or err.get("error") or resp.text[:200]
                except Exception:
                    msg = resp.text[:200]
                return ApiResponse(ok=False, error=f"HTTP {resp.status_code}: {msg}")

            data = resp.json() if resp.content else {}
            return ApiResponse(
                ok=data.get("ok", True),
                data=data.get("data"),
                message=data.get("message", ""),
            )
        except httpx.TimeoutException:
            return ApiResponse(ok=False, error="Timeout conectando con la API")
        except httpx.ConnectError:
            return ApiResponse(ok=False, error="No se puede conectar al backend")
        except Exception as e:
            return ApiResponse(ok=False, error=f"Error de red: {e}")

    # ==================== PRODUCTOS ====================

    async def create_product(
        self,
        data: dict,
        images: list[tuple[str, bytes, str]] | None = None,
    ) -> ApiResponse:
        """
        POST /api/products — Crear producto con variantes.
        `images`: lista de (field_name, file_bytes, filename) para image/images[]
        """
        # Usar multipart/form-data siempre (el backend usa multer)
        form_data = {}
        for k, v in data.items():
            if v is not None:
                form_data[k] = str(v) if not isinstance(v, (list, dict)) else v

        files = {}
        if images:
            for name, content, filename in images:
                files[name] = (filename, content, "image/jpeg")
        else:
            # Multer requiere al menos un archivo en campo 'image' o 'images'.
            # Usar un PNG 1x1 transparente como placeholder.
            files["image"] = ("placeholder.png", _DUMMY_PNG, "image/png")

        return await self._request("POST", "/api/products", data=form_data, files=files)

    async def update_product(self, product_id: int, data: dict, images: list = None) -> ApiResponse:
        """PUT /api/products/:id - Actualizar producto."""
        form_data = {}
        for k, v in data.items():
            if v is not None:
                form_data[k] = str(v) if not isinstance(v, (list, dict)) else v

        files = {}
        if images:
            for name, content, filename in images:
                files[name] = (filename, content, "image/jpeg")
        else:
            # Multer requiere al menos un archivo en campo 'image' o 'images'.
            files["image"] = ("placeholder.png", _DUMMY_PNG, "image/png")

        return await self._request("PUT", f"/api/products/{product_id}", data=form_data, files=files)

    async def delete_product(self, product_id: int) -> ApiResponse:
        """DELETE /api/products/:id - Eliminar producto."""
        return await self._request("DELETE", f"/api/products/{product_id}")

    async def adjust_stock(self, product_id: int, type: str, amount: int) -> ApiResponse:
        """PATCH /api/products/:id/stock - Ajustar stock (add|subtract|set)."""
        return await self._request(
            "PATCH", f"/api/products/{product_id}/stock", json={"type": type, "amount": amount}
        )

    async def delete_product_image(self, product_id: int, image_id: int) -> ApiResponse:
        """DELETE /api/products/:id/images/:imageId - Eliminar imagen extra."""
        return await self._request("DELETE", f"/api/products/{product_id}/images/{image_id}")

    async def list_products(self, filters: dict | None = None) -> ApiResponse:
        """GET /api/products — Inventario con filtros opcionales."""
        params = {}
        if filters:
            if filters.get("category"):
                params["category"] = filters["category"]
            if filters.get("size"):
                params["size"] = filters["size"]
            if filters.get("q"):
                params["q"] = filters["q"]
            if filters.get("lowStock"):
                params["lowStock"] = "true"
        return await self._request("GET", "/api/products", params=params)

    async def get_product(self, product_id: int) -> ApiResponse:
        """GET /api/products/:id — Detalle de producto con variantes e imágenes."""
        return await self._request("GET", f"/api/products/{product_id}")

    async def get_products_meta(self) -> ApiResponse:
        """GET /api/products/meta — Categorías, tallas, colores, URL uploads."""
        return await self._request("GET", "/api/products/meta")

    # ==================== PEDIDOS ====================

    async def list_orders(self, status: str | None = None) -> ApiResponse:
        """GET /api/orders — Listado de pedidos con filtro opcional."""
        params = {"status": status} if status else None
        return await self._request("GET", "/api/orders", params=params)

    async def get_order(self, order_id: int) -> ApiResponse:
        """GET /api/orders/:id — Vista detallada del pedido."""
        return await self._request("GET", f"/api/orders/{order_id}")

    async def create_order(
        self, customer_id: int, items: list[dict], notify_whatsapp: bool = False
    ) -> ApiResponse:
        """
        POST /api/orders — Crear pedido (valida stock, descuenta inventario, envía email).
        items: [{productId, quantity, size?, color?, discount?}]
        """
        return await self._request(
            "POST",
            "/api/orders",
            json={"customerId": customer_id, "items": items, "notifyWhatsApp": notify_whatsapp},
        )

    async def change_order_status(self, order_id: int, status: str) -> ApiResponse:
        """PATCH /api/orders/:id/status — Cambio de estado (envía email al cliente)."""
        valid_statuses = ["Pendiente", "Procesado", "Enviado", "Entregado"]
        if status not in valid_statuses:
            return ApiResponse(ok=False, error=f"Estado inválido. Opciones: {valid_statuses}")
        return await self._request("PATCH", f"/api/orders/{order_id}/status", json={"status": status})

    async def cancel_order(self, order_id: int) -> ApiResponse:
        """DELETE /api/orders/:id — Anular pedido y restituir stock (solo Pendiente/Procesado)."""
        return await self._request("DELETE", f"/api/orders/{order_id}")

    # ==================== CLIENTES ====================

    async def list_customers(self, filters: dict | None = None) -> ApiResponse:
        """GET /api/customers — CRUD clientes."""
        return await self._request("GET", "/api/customers", params=filters)

    async def get_customer(self, customer_id: int) -> ApiResponse:
        return await self._request("GET", f"/api/customers/{customer_id}")

    async def create_customer(self, data: dict) -> ApiResponse:
        return await self._request("POST", "/api/customers", json=data)

    async def update_customer(self, customer_id: int, data: dict) -> ApiResponse:
        return await self._request("PUT", f"/api/customers/{customer_id}", json=data)

    async def delete_customer(self, customer_id: int) -> ApiResponse:
        return await self._request("DELETE", f"/api/customers/{customer_id}")

    # ==================== CÓDIGOS PROMOCIONALES ====================

    async def list_promos(self, filters: dict | None = None) -> ApiResponse:
        return await self._request("GET", "/api/promo-codes", params=filters)

    async def get_promo(self, promo_id: int) -> ApiResponse:
        return await self._request("GET", f"/api/promo-codes/{promo_id}")

    async def validate_promo(self, code: str) -> ApiResponse:
        """POST /api/promo-codes/validate — Validación pública para checkout."""
        return await self._request("POST", "/api/promo-codes/validate", json={"code": code})

    async def create_promo(self, data: dict) -> ApiResponse:
        return await self._request("POST", "/api/promo-codes", json=data)

    async def update_promo(self, promo_id: int, data: dict) -> ApiResponse:
        return await self._request("PUT", f"/api/promo-codes/{promo_id}", json=data)

    async def delete_promo(self, promo_id: int) -> ApiResponse:
        return await self._request("DELETE", f"/api/promo-codes/{promo_id}")

    async def generate_promo(self, count: int = 1, prefix: str = "CROVN") -> ApiResponse:
        return await self._request("POST", "/api/promo-codes/generate", json={"count": count, "prefix": prefix})

    async def send_promo_email(self, promo_id: int, email: str) -> ApiResponse:
        return await self._request("POST", f"/api/promo-codes/{promo_id}/send", json={"email": email})

    # ==================== PUBLICACIONES ====================

    async def list_publications(self, filters: dict | None = None) -> ApiResponse:
        return await self._request("GET", "/api/publications", params=filters)

    async def get_active_publications(self) -> ApiResponse:
        """GET /api/publications/active — Publicaciones activas para landing (público)."""
        return await self._request("GET", "/api/publications/active")

    async def get_publication(self, pub_id: int) -> ApiResponse:
        return await self._request("GET", f"/api/publications/{pub_id}")

    async def create_publication(self, data: dict) -> ApiResponse:
        return await self._request("POST", "/api/publications", json=data)

    async def update_publication(self, pub_id: int, data: dict) -> ApiResponse:
        return await self._request("PUT", f"/api/publications/{pub_id}", json=data)

    async def delete_publication(self, pub_id: int) -> ApiResponse:
        return await self._request("DELETE", f"/api/publications/{pub_id}")

    async def toggle_publication(self, pub_id: int) -> ApiResponse:
        return await self._request("PATCH", f"/api/publications/{pub_id}/toggle")

    # ==================== PROVEEDORES ====================

    async def list_suppliers(self) -> ApiResponse:
        return await self._request("GET", "/api/suppliers")

    async def get_supplier(self, supplier_id: int) -> ApiResponse:
        return await self._request("GET", f"/api/suppliers/{supplier_id}")

    async def create_supplier(self, data: dict) -> ApiResponse:
        return await self._request("POST", "/api/suppliers", json=data)

    async def update_supplier(self, supplier_id: int, data: dict) -> ApiResponse:
        return await self._request("PUT", f"/api/suppliers/{supplier_id}", json=data)

    async def delete_supplier(self, supplier_id: int) -> ApiResponse:
        return await self._request("DELETE", f"/api/suppliers/{supplier_id}")

    async def apply_supplier_pricing(self, supplier_id: int) -> ApiResponse:
        """POST /api/suppliers/:id/apply — Recalcula precios de productos del proveedor."""
        return await self._request("POST", f"/api/suppliers/{supplier_id}/apply")

    # ==================== CATEGORÍAS ====================

    async def list_categories(self) -> ApiResponse:
        return await self._request("GET", "/api/categories")

    async def create_category(self, name: str) -> ApiResponse:
        return await self._request("POST", "/api/categories", json={"name": name})

    async def delete_category(self, category_id: int) -> ApiResponse:
        return await self._request("DELETE", f"/api/categories/{category_id}")

    # ==================== SHOP PÚBLICO (landing) ====================

    async def get_shop_catalog(self) -> ApiResponse:
        """GET /api/shop — Catálogo completo para la landing."""
        return await self._request("GET", "/api/shop")

    async def get_shop_products(self, filters: dict | None = None) -> ApiResponse:
        """GET /api/shop/products — Productos con filtros para la tienda."""
        return await self._request("GET", "/api/shop/products", params=filters)

    async def checkout_shop(self, customer: dict, items: list[dict], promo_code: str | None = None) -> ApiResponse:
        """POST /api/shop/checkout — Checkout público (crea cliente + pedido)."""
        payload = {"customer": customer, "items": items}
        if promo_code:
            payload["promoCode"] = promo_code
        return await self._request("POST", "/api/shop/checkout", json=payload)

    async def lookup_order(self, email: str, order_id: str) -> ApiResponse:
        """GET /api/shop/orders/lookup — Consulta pública de pedido."""
        return await self._request("GET", "/api/shop/orders/lookup", params={"email": email, "orderId": order_id})

    async def orders_by_email(self, email: str) -> ApiResponse:
        """GET /api/shop/orders/by-email — Historial por email."""
        return await self._request("GET", "/api/shop/orders/by-email", params={"email": email})

    # ==================== ADMIN / ANALÍTICAS (endpoints nuevos) ====================

    async def get_dashboard_stats(self) -> ApiResponse:
        """GET /api/admin/dashboard — KPIs para snapshot del agente."""
        return await self._request("GET", "/api/admin/dashboard")

    async def get_inactive_customers(self, days: int = 30) -> ApiResponse:
        """GET /api/admin/customers/inactive — Clientes sin pedidos en N días."""
        return await self._request("GET", "/api/admin/customers/inactive", params={"days": days})

    async def get_dead_stock(self, days: int = 60) -> ApiResponse:
        """GET /api/admin/analytics/dead-stock — Productos con stock pero sin ventas."""
        return await self._request("GET", "/api/admin/analytics/dead-stock", params={"days": days})

    # ==================== UTILIDADES ====================

    async def health_check(self) -> ApiResponse:
        """GET /api/health — Verifica disponibilidad del backend."""
        return await self._request("GET", "/api/health")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Instancia global para uso sencillo (se inicializa en app.py)
api_client: CROVNApiClient | None = None


def get_api_client() -> CROVNApiClient:
    global api_client
    if api_client is None:
        import os
        base_url = os.getenv("API_BASE_URL", "http://localhost:4000")
        api_client = CROVNApiClient(base_url=base_url)
    return api_client


def set_api_token(token: str | None):
    global api_client
    if api_client:
        api_client.set_token(token)
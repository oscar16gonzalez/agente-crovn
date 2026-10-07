import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


from datetime import datetime


def build_promo_email(customer_name, promo_code, discount_pct, expires_at=None):
    """HTML del correo de código promocional (basado en la plantilla CROVN)."""
    discount_label = f"{discount_pct}%"
    if expires_at:
        try:
            expires_text = "Válido hasta: " + datetime.fromisoformat(str(expires_at)).strftime("%d/%m/%Y")
        except Exception:
            expires_text = f"Válido hasta: {expires_at}"
    else:
        expires_text = "Válido por tiempo limitado"
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#1a1a1a;color:#fff;padding:32px;text-align:center">
        <h1 style="margin:0;font-size:28px;letter-spacing:2px">CROVN<span style="color:#e63946">.</span></h1>
        <p style="margin:8px 0 0;color:#aaa;font-size:13px">¡Tenemos algo especial para ti!</p>
      </div>

      <div style="padding:32px;text-align:center">
        <p style="margin:0 0 8px;font-size:18px">¡Hola, <strong>{customer_name or 'cliente'}</strong>! 🎉</p>
        <p style="margin:0 0 24px;font-size:14px;color:#666">
          Gracias por ser parte de Crovn. Aquí tienes tu código de descuento exclusivo:
        </p>

        <div style="background:linear-gradient(135deg,#e63946,#c1121f);border-radius:16px;padding:28px;margin:0 auto 24px;max-width:360px">
          <p style="margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.8)">Tu código de descuento</p>
          <p style="margin:8px 0 0;font-size:36px;font-weight:900;letter-spacing:3px;color:#fff">{promo_code}</p>
          <p style="margin:8px 0 0;font-size:14px;font-weight:700;color:rgba(255,255,255,0.95)">{discount_label} DE DESCUENTO</p>
        </div>

        <div style="background:#f8f8f8;border-radius:12px;padding:16px;margin-bottom:24px;text-align:left">
          <p style="margin:0 0 8px;font-size:14px">🏷️ <strong>Descuento:</strong> {discount_label} en tu próxima compra</p>
          <p style="margin:0 0 8px;font-size:14px">📅 {expires_text}</p>
          <p style="margin:0;font-size:14px">🛒 <strong>Cómo usarlo:</strong> Ingresa el código en el carrito al finalizar tu compra</p>
        </div>

        <a href="{frontend_url}" style="display:inline-block;background:#1a1a1a;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px">
          Ir a la tienda
        </a>

        <p style="margin:24px 0 0;font-size:12px;color:#999">
          Si tienes dudas, contáctanos por WhatsApp o correo.
        </p>
      </div>

      <div style="background:#f5f5f5;padding:16px;text-align:center;font-size:12px;color:#888">
        <p style="margin:0">© {datetime.now().year} Crovn. Todos los derechos reservados.</p>
      </div>
    </div>
    """


def build_promo_email_text(customer_name, promo_code, discount_pct, expires_at=None):
    expires_text = f"Válido hasta: {expires_at}" if expires_at else "Válido por tiempo limitado"
    return "\n".join([
        "CÓDIGO PROMOCIONAL CROVN",
        "",
        f"Hola, {customer_name or 'cliente'}!",
        "",
        f"Tu código de descuento: {promo_code}",
        f"Descuento: {discount_pct}%",
        expires_text,
        "",
        "Cómo usarlo: Ingresa el código en el carrito al finalizar tu compra.",
        "",
        "¡Gracias por ser parte de Crovn!",
    ])


def enviar_codigo_promocional(destinatario, codigo, descuento, expira=None, nombre=None):
    """Envía un código promocional por correo con la plantilla CROVN."""
    if not SMTP_USER or not SMTP_PASS:
        return False, "SMTP_USER/SMTP_PASS no configurados en .env"
    asunto = f"🎁 Tu código de descuento CROVN: {codigo} ({descuento}% OFF)"
    html = build_promo_email(nombre, codigo, descuento, expira)
    text = build_promo_email_text(nombre, codigo, descuento, expira)
    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_FROM, destinatario, msg.as_string())
        return True, f"Código {codigo} enviado a {destinatario}"
    except Exception as e:
        return False, f"No se pudo enviar el correo: {e}"


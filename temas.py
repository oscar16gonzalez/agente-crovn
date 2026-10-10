"""Temas de la interfaz: paletas inspiradas en asistentes de IA, personalización y variables CSS."""
import json
import os
import re

TEMA_FILE = os.path.join(os.path.dirname(__file__), "config_tema.json")

# fondo / texto / acento definen toda la paleta; el resto se deriva en resolver()
PRESETS = {
    "carmesi": {"nombre": "CROVN Carmesí", "detalle": "Identidad CROVN: negro y rojo", "fondo": "#0a0a0c", "texto": "#f8fafc", "acento": "#dc2626"},
    "chatgpt": {"nombre": "ChatGPT", "detalle": "Gris carbón y verde menta", "fondo": "#212121", "texto": "#ececec", "acento": "#10a37f"},
    "claude": {"nombre": "Claude", "detalle": "Crema cálido y terracota (claro)", "fondo": "#faf9f5", "texto": "#29261b", "acento": "#d97757"},
    "gemini": {"nombre": "Gemini", "detalle": "Grafito con degradado azul-violeta", "fondo": "#131314", "texto": "#e3e3e3", "acento": "#8ab4f8", "acento2": "#c58af9", "degradado": True},
    "perplexity": {"nombre": "Perplexity", "detalle": "Pizarra profunda y turquesa", "fondo": "#101516", "texto": "#e8eaeb", "acento": "#20b8cd"},
    "grok": {"nombre": "Grok", "detalle": "Negro puro monocromo", "fondo": "#000000", "texto": "#fafafa", "acento": "#f5f5f5"},
    "deepseek": {"nombre": "DeepSeek", "detalle": "Medianoche y azul eléctrico", "fondo": "#111318", "texto": "#e6e8ee", "acento": "#4d6bfe"},
    "mistral": {"nombre": "Mistral", "detalle": "Marrón oscuro con degradado naranja-ámbar", "fondo": "#12100e", "texto": "#f5efe8", "acento": "#fa520f", "acento2": "#ffb000", "degradado": True},
    "copilot": {"nombre": "Copilot", "detalle": "Índigo nocturno con degradado violeta-cian", "fondo": "#100d1f", "texto": "#ece9f7", "acento": "#7c6cf0", "acento2": "#3ec6e0", "degradado": True},
    "linear": {"nombre": "Linear", "detalle": "Gris claro e índigo (claro)", "fondo": "#f7f8fa", "texto": "#1b1d23", "acento": "#5e6ad2"},
}
PRESET_DEFECTO = "carmesi"

FUENTES = {
    "Inter": ("Inter:wght@400;500;600;700", "sans-serif"),
    "Plus Jakarta Sans": ("Plus+Jakarta+Sans:wght@400;500;600;700", "sans-serif"),
    "DM Sans": ("DM+Sans:wght@400;500;600;700", "sans-serif"),
    "Manrope": ("Manrope:wght@400;500;600;700", "sans-serif"),
    "Space Grotesk": ("Space+Grotesk:wght@400;500;600;700", "sans-serif"),
    "IBM Plex Sans": ("IBM+Plex+Sans:wght@400;500;600;700", "sans-serif"),
    "Lora": ("Lora:wght@400;500;600;700", "serif"),
    "JetBrains Mono": ("JetBrains+Mono:wght@400;500;600", "monospace"),
}
# nombre -> radio base (px) de tarjetas; el resto de radios se deriva
RADIOS = {"Recto": 6, "Suave": 10, "Moderno": 16, "Píldora": 22}
ANCHOS = {"Compacto": 720, "Normal": 820, "Amplio": 1000, "Completo": 1240}
FONDOS = ["Aurora", "Malla", "Liso"]
ICONOS = ["💀", "🤖", "✨", "⚡", "🔥", "🧠", "🪐", "🦊", "🌀", "🛸"]

DEFECTO = {
    "preset": PRESET_DEFECTO, "acento": None, "acento2": None, "fondo": None, "texto": None, "degradado": None,
    "fuente": "Inter", "radio": "Moderno", "ancho": "Normal", "fondo_estilo": "Aurora",
    "brillo": True, "animaciones": True, "icono": "💀",
}


def cargar():
    try:
        with open(TEMA_FILE, encoding="utf-8") as f:
            cfg = {**DEFECTO, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFECTO)
    if cfg["preset"] not in PRESETS:
        cfg["preset"] = PRESET_DEFECTO
    for clave in ("acento", "acento2", "fondo", "texto"):
        if not (isinstance(cfg[clave], str) and re.fullmatch(r"#[0-9a-fA-F]{6}", cfg[clave])):
            cfg[clave] = None
    for clave, validos in (("fuente", FUENTES), ("radio", RADIOS), ("ancho", ANCHOS), ("fondo_estilo", FONDOS), ("icono", ICONOS)):
        if cfg[clave] not in validos:
            cfg[clave] = DEFECTO[clave]
    return cfg


def guardar(cfg):
    try:
        with open(TEMA_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"No se pudo guardar el tema: {e}")


# ---------- Color ----------
def _rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c):
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(v))) for v in c))


def mezclar(a, b, t):
    """Color entre a y b (t=0 -> a, t=1 -> b)."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x * (1 - t) + y * t for x, y in zip(ra, rb)))


def luminancia(h):
    def canal(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _triple(h):
    return ",".join(str(v) for v in _rgb(h))


def resolver(cfg):
    """Paleta completa (dict) a partir de la configuración: preset + personalizaciones."""
    p = PRESETS.get(cfg.get("preset"), PRESETS[PRESET_DEFECTO])
    fondo = cfg.get("fondo") or p["fondo"]
    texto = cfg.get("texto") or p["texto"]
    acento = cfg.get("acento") or p["acento"]
    claro = luminancia(fondo) > 0.5
    ac_vivo = acento if claro else mezclar(acento, "#ffffff", .2)
    ac_oscuro = mezclar(acento, "#000000", .35 if claro else .45)
    acento2 = cfg.get("acento2") or p.get("acento2") or (ac_oscuro if claro else mezclar(acento, texto, .35))
    degradado = cfg.get("degradado")
    if degradado is None:
        degradado = p.get("degradado", False) and not cfg.get("acento")
    grad = f"linear-gradient(135deg, {acento}, {acento2})" if degradado else f"linear-gradient(135deg, {ac_vivo}, {acento} 55%, {ac_oscuro})"
    base_boton = mezclar(acento, acento2, .5) if degradado else acento
    r = RADIOS.get(cfg.get("radio"), 16)
    fuente = FUENTES.get(cfg.get("fuente"), FUENTES["Inter"])
    return {
        "claro": claro,
        "fondo": fondo, "texto": texto, "acento": acento, "acento2": acento2, "ac_vivo": ac_vivo, "ac_oscuro": ac_oscuro,
        "degradado": bool(degradado), "grad": grad,
        "on_ac": "#ffffff" if luminancia(base_boton) < .3 else "#0a0a0c",
        "panel": mezclar(fondo, "#ffffff", .7) if claro else mezclar(fondo, texto, .05),
        "panel2": mezclar(fondo, texto, .025) if claro else mezclar(fondo, texto, .085),
        "inset": mezclar(fondo, texto, .045) if claro else mezclar(fondo, "#000000", .3),
        "borde": mezclar(fondo, texto, .14 if claro else .13),
        "muted": mezclar(texto, fondo, .42),
        "tenue": mezclar(texto, fondo, .62),
        "fila": mezclar(texto, fondo, .1),
        "ok": "#059669" if claro else "#34d399",
        "alerta": "#dc2626" if claro else "#ff6b6b",
        "aviso": "#b45309" if claro else "#fbbf24",
        "info": "#2563eb" if claro else "#93c5fd",
        "sombra": "15,23,42" if claro else "0,0,0",
        "sa": .10 if claro else .35,
        "r": r, "r_sm": max(4, round(r * .7)), "r_lg": round(r * 1.3), "r_pill": 999 if r >= 22 else round(r * 1.6),
        "ancho": ANCHOS.get(cfg.get("ancho"), 820),
        "fuente": cfg.get("fuente") if cfg.get("fuente") in FUENTES else "Inter",
        "fondo_estilo": cfg.get("fondo_estilo") if cfg.get("fondo_estilo") in FONDOS else "Aurora",
        "brillo": bool(cfg.get("brillo", True)),
        "animaciones": bool(cfg.get("animaciones", True)),
        "icono": cfg.get("icono") or "💀",
        "fuente_url": fuente[0],
        "fuente_familia": fuente[1],
    }


def _fondo_css(t):
    a, a2 = f"var(--ac-rgb)", "var(--ac2-rgb)"
    claro = t["claro"]
    if t["fondo_estilo"] == "Liso":
        return "var(--bg)"
    if t["fondo_estilo"] == "Malla":
        k1, k2 = (.10, .08) if claro else (.16, .12)
        return (
            f"radial-gradient(900px 480px at 8% -8%, rgba({a},{k1}), transparent 60%), "
            f"radial-gradient(800px 460px at 100% 0%, rgba({a2},{k2}), transparent 60%), "
            f"radial-gradient(700px 500px at 50% 115%, rgba({a},{k2 / 2}), transparent 60%), var(--bg)"
        )
    k = .06 if claro else .09
    return f"radial-gradient(1200px 520px at 50% -12%, rgba({a},{k}), transparent 62%), var(--bg)"


def css_tema(t):
    """<style> con la fuente y todas las variables del tema (se inyecta antes de CSS_BASE)."""
    glow = f"0 0 18px rgba(var(--ac-rgb), {.14 if t['claro'] else .26})" if t["brillo"] else "0 0 0 0 transparent"
    glow_fuerte = f"0 0 34px rgba(var(--ac-rgb), {.2 if t['claro'] else .38})" if t["brillo"] else "0 0 0 0 transparent"
    medalla = mezclar(t["fondo"], t["acento"], .22 if not t["claro"] else .14)
    sin_anim = "*, *::before, *::after { animation: none !important; transition: none !important; }" if not t["animaciones"] else ""
    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family={t['fuente_url']}&family=JetBrains+Mono:wght@400;500&display=swap');
:root {{
  color-scheme: {'light' if t['claro'] else 'dark'};
  --ac: {t['acento']}; --ac-vivo: {t['ac_vivo']}; --ac-oscuro: {t['ac_oscuro']}; --ac2: {t['acento2']};
  --ac-rgb: {_triple(t['acento'])}; --ac2-rgb: {_triple(t['acento2'])}; --ac-vivo-rgb: {_triple(t['ac_vivo'])}; --ac-oscuro-rgb: {_triple(t['ac_oscuro'])};
  --grad: {t['grad']}; --on-ac: {t['on_ac']};
  --bg: {t['fondo']}; --panel: {t['panel']}; --panel-2: {t['panel2']}; --inset: {t['inset']}; --borde: {t['borde']};
  --texto: {t['texto']}; --texto-rgb: {_triple(t['texto'])}; --muted: {t['muted']}; --tenue: {t['tenue']}; --fila: {t['fila']};
  --ok: {t['ok']}; --alerta: {t['alerta']}; --aviso: {t['aviso']}; --info: {t['info']};
  --ok-rgb: {_triple(t['ok'])}; --alerta-rgb: {_triple(t['alerta'])}; --aviso-rgb: {_triple(t['aviso'])}; --info-rgb: {_triple(t['info'])};
  --sombra-rgb: {t['sombra']}; --sa: {t['sa']};
  --glow: {glow}; --glow-fuerte: {glow_fuerte}; --medalla: {medalla};
  --r: {t['r']}px; --r-sm: {t['r_sm']}px; --r-lg: {t['r_lg']}px; --r-pill: {t['r_pill']}px;
  --ancho: {t['ancho']}px; --fuente: '{t['fuente']}', system-ui, {t['fuente_familia']};
  --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --fondo-app: {_fondo_css(t)};
}}
{sin_anim}
</style>"""


def vista_previa_html(t):
    """Maqueta en miniatura (burbuja, respuesta y botón) con la paleta resuelta."""
    return (
        f'<div style="background:{t["fondo"]};border:1px solid {t["borde"]};border-radius:{t["r"]}px;padding:.75rem;font-family:\'{t["fuente"]}\',sans-serif;">'
        f'<div style="display:flex;justify-content:flex-end;margin-bottom:.5rem;"><span style="background:rgba({_triple(t["acento"])},.18);border:1px solid rgba({_triple(t["acento"])},.4);'
        f'color:{t["texto"]};padding:.3rem .65rem;border-radius:{t["r_lg"]}px {t["r_lg"]}px 4px {t["r_lg"]}px;font-size:.72rem;">Productos sin stock</span></div>'
        f'<div style="background:{t["panel"]};border:1px solid {t["borde"]};border-radius:{t["r"]}px;padding:.45rem .65rem;font-size:.7rem;color:{t["muted"]};margin-bottom:.5rem;">'
        f'<b style="color:{t["texto"]}">3 resultados</b> · inventario</div>'
        f'<div style="display:flex;gap:.4rem;align-items:center;"><span style="background:{t["grad"]};color:{t["on_ac"]};padding:.28rem .8rem;border-radius:{t["r_sm"]}px;font-size:.7rem;font-weight:600;">Enviar</span>'
        + "".join(f'<i style="width:14px;height:14px;border-radius:50%;background:{c};border:1px solid {t["borde"]};display:inline-block;"></i>' for c in (t["acento"], t["acento2"], t["panel2"], t["texto"]))
        + "</div></div>"
    )

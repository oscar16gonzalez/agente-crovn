"""Escucha local de la palabra de activación (micrófono del equipo + Whisper) y voz del asistente.
En producción (Render) la funcionalidad de voz se desactiva automáticamente si no hay PortAudio."""
import difflib
import queue
import random
import re
import shutil
import subprocess
import threading
import time
import unicodedata
from collections import deque
from datetime import datetime
from functools import lru_cache

import numpy as np

# Verificar disponibilidad de PortAudio/sounddevice
try:
    import sounddevice as sd
    PORTAUDIO_AVAILABLE = True
except ImportError:
    sd = None
    PORTAUDIO_AVAILABLE = False

FS = 16000
BLOQUE = 1600  # 0.1 s
SILENCIO_BLOQUES = 8  # 0.8 s sin voz cierra la frase
MIN_VOZ_BLOQUES = 3
REINTENTO_ERROR_S = 30
VOZ_AUTO = "Automática"
RITMO_NORMAL, RITMO_LENTO = 175, 130  # palabras por minuto de `say`
_RELLENO = {"hey", "ey", "hei", "oye", "hola", "ok", "okay"}


def _palabras(texto):
    s = unicodedata.normalize("NFD", texto.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return "".join(c if c.isalnum() else " " for c in s).split()


def _casa(palabra, objetivo):
    return difflib.SequenceMatcher(None, palabra, objetivo).ratio() >= (1.0 if len(objetivo) < 4 else 0.66)


def coincide(texto, frase):
    """True si el texto contiene la palabra de activación (tolera errores de transcripción como 'yarvis')."""
    objetivos = _palabras(frase)
    objetivos = [o for o in objetivos if o not in _RELLENO] or objetivos or ["jarvis"]
    palabras, i = _palabras(texto), 0
    for o in objetivos:
        while i < len(palabras) and not _casa(palabras[i], o):
            i += 1
        if i == len(palabras):
            return False
        i += 1
    return True


# ---------- Voz del asistente ----------
@lru_cache(maxsize=1)
def voces_sistema():
    """Voces en español instaladas en el equipo: lista de (nombre, localización). Vacía si no hay `say`."""
    if not shutil.which("say"):
        return []
    try:
        salida = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [m.groups() for m in re.finditer(r"^(.+?)\s+(es_\w+)\s+#", salida, re.MULTILINE)]


def _voz_por_defecto():
    voces = voces_sistema()
    for nombre in ("Paulina", "Mónica", "Monica", "Jorge", "Juan"):
        for v, _ in voces:
            if v.startswith(nombre):
                return v
    return (voces or [(None, None)])[0][0]


def _limpiar(texto):
    return re.sub(r"[*_`#>]", "", texto)


def hablar(texto, voz=None, lento=False):
    """Lee el texto en voz alta con la voz indicada (o una voz española del sistema) y espera a que termine."""
    texto = _limpiar(texto)
    if shutil.which("say"):
        voz = voz if voz and voz != VOZ_AUTO else _voz_por_defecto()
        cmd = ["say", *(["-v", voz] if voz else []), "-r", str(RITMO_LENTO if lento else RITMO_NORMAL), "-f", "-"]
        subprocess.run(cmd, input=texto, text=True, check=False, timeout=60)
        return
    try:
        import pyttsx3
        motor = pyttsx3.init()
        motor.say(texto)
        motor.runAndWait()
    except Exception as e:
        print(f"[voz] No se pudo hablar: {e}")


def sintetizar(texto, ruta, voz, lento=False):
    """Genera un WAV con una voz del sistema. Lanza un error si no se pudo."""
    cmd = ["say", "-v", voz, "-r", str(RITMO_LENTO if lento else RITMO_NORMAL), "-o", ruta, "--data-format=LEI16@22050", "-f", "-"]
    subprocess.run(cmd, input=_limpiar(texto), text=True, check=True, timeout=120)


# ---------- Saludos ----------
def _momento():
    hora = datetime.now().hour
    return "Buenos días" if hora < 12 else "Buenas tardes" if hora < 19 else "Buenas noches"


def _saludos(c):
    return [
        f"Hola{c}, ¿en qué puedo ayudarte hoy con la tienda?",
        f"{_momento()}{c}. ¿Qué quieres consultar de CROVN?",
        f"Hola{c}, aquí estoy. ¿Qué quieres saber de tu tienda?",
        f"¿Qué tal{c}? Dime qué necesitas revisar: inventario, ventas, clientes…",
        f"Hola{c}, listo para ayudarte. ¿Qué buscamos hoy?",
        f"Bienvenido de nuevo{c}. ¿Qué te gustaría saber de la tienda?",
    ]


CONTINUACIONES = [
    "Dime.",
    "¿Qué más necesitas?",
    "Te escucho, ¿qué quieres saber?",
    "Claro, ¿qué quieres revisar ahora?",
    "Adelante, ¿qué busco?",
    "¿Qué otra cosa quieres consultar?",
]


class EscuchaVoz:
    """Hilo que espera la palabra de activación, saluda y deja en una cola lo que el usuario dicta."""

    def __init__(self):
        self.frase, self.usuario, self.voz, self.lento = "hey Jarvis", "", VOZ_AUTO, False
        self.estado, self.detalle = "apagado", ""
        self.chat_clave = None
        self._saludados = set()
        self._ultima = None
        self._comandos = queue.Queue()
        self._parar = threading.Event()
        self._hilo = None
        self._niveles = deque(maxlen=50)
        self._fallo_en = 0.0
        self._lock = threading.Lock()
        self._voz_habilitada = PORTAUDIO_AVAILABLE

    def configurar(self, activo, frase, usuario, voz=VOZ_AUTO, lento=False):
        self.frase = (frase or "").strip() or "hey Jarvis"
        self.usuario, self.voz, self.lento = usuario or "", voz or VOZ_AUTO, lento
        with self._lock:
            vivo = self._hilo is not None and self._hilo.is_alive()
            if activo and not vivo and time.time() - self._fallo_en > REINTENTO_ERROR_S:
                # Solo iniciar si PortAudio está disponible
                if self._voz_habilitada:
                    self._parar.clear()
                    self._hilo = threading.Thread(target=self._bucle, daemon=True)
                    self._hilo.start()
                else:
                    self._poner("error", "Voz no disponible: PortAudio no instalado")
            elif activo and vivo:
                self._parar.clear()
            elif not activo:
                self._parar.set()
                if not vivo:
                    self._poner("apagado", "")

    def siguiente(self):
        try:
            return self._comandos.get_nowait()
        except queue.Empty:
            return None

    def _poner(self, estado, detalle):
        self.estado, self.detalle = estado, detalle

    def _bucle(self):
        # Si no hay PortAudio, desactivar funcionalidad de voz
        if not PORTAUDIO_AVAILABLE:
            self._poner("error", "Voz no disponible: PortAudio no instalado en el servidor")
            self._poner("apagado", "")
            return

        try:
            import sounddevice as sd
            from stt_module import cargar_modelo
            self._poner("cargando", "Cargando reconocimiento de voz…")
            cargar_modelo()
            with sd.InputStream(samplerate=FS, channels=1, dtype="int16", blocksize=BLOQUE) as flujo:
                while not self._parar.is_set():
                    reposo = f"Di «{self.frase}»"
                    self._poner("espera", reposo)
                    audio = self._frase(flujo, inicio_max=None, fin_max=60)
                    if audio is None:
                        continue
                    texto = self._transcribir(audio, f"{self.frase}.")
                    if texto and coincide(texto, self.frase):
                        self._atender(flujo)
                    elif texto:
                        self._poner("espera", f"{reposo} · oí: «{texto}»")
        except Exception as e:
            self._fallo_en = time.time()
            self._poner("error", f"Voz no disponible: {e}")
            return
        self._poner("apagado", "")

    def _frase(self, flujo, inicio_max, fin_max):
        """Audio de la próxima frase hablada, o None si no hubo voz a tiempo o se detuvo la escucha."""
        previo, trozos = deque(maxlen=3), []
        hablando, silencio, esperado = False, 0, 0
        while not self._parar.is_set():
            datos, _ = flujo.read(BLOQUE)
            bloque = datos[:, 0]
            nivel = float(np.sqrt(np.mean(bloque.astype(np.float32) ** 2)))
            self._niveles.append(nivel)
            if len(self._niveles) < 10:
                continue
            # El ruido de fondo es el percentil bajo de los últimos 5 s; la voz debe superarlo con claridad
            ruido = float(np.percentile(self._niveles, 20))
            voz = nivel > max(ruido * 1.8, ruido + 300)
            if not hablando:
                if not voz:
                    esperado += 1
                    if inicio_max and esperado > inicio_max:
                        return None
                previo.append(bloque)
                if voz:
                    hablando, trozos = True, list(previo)
                continue
            trozos.append(bloque)
            silencio = 0 if voz else silencio + 1
            if silencio >= SILENCIO_BLOQUES or len(trozos) >= fin_max:
                break
        else:
            return None
        if len(trozos) - silencio < MIN_VOZ_BLOQUES:
            return None
        return np.concatenate(trozos).astype(np.float32) / 32768.0

    def _transcribir(self, audio, prompt=None):
        from stt_module import LOCK, cargar_modelo
        # Con volumen bajo Whisper alucina: se normaliza al máximo
        audio = audio / max(float(np.abs(audio).max()), 1e-3) * 0.9
        with LOCK:
            r = cargar_modelo().transcribe(audio, language="es", fp16=False, initial_prompt=prompt, condition_on_previous_text=False)
        return r.get("text", "").strip()

    def _frase_de_atencion(self):
        """Saludo variado la primera vez en cada chat; después solo una invitación breve, sin 'hola'."""
        c = f", {self.usuario}" if self.usuario else ""
        primera = self.chat_clave not in self._saludados
        opciones = _saludos(c) if primera else CONTINUACIONES
        frase = random.choice([o for o in opciones if o != self._ultima] or opciones)
        self._saludados.add(self.chat_clave)
        self._ultima = frase
        return frase

    def _atender(self, flujo):
        frase = self._frase_de_atencion()
        self._poner("saludando", frase)
        hablar(frase, self.voz, self.lento)
        self._poner("comando", "Te escucho…")
        if flujo.read_available:
            flujo.read(flujo.read_available)
        audio = self._frase(flujo, inicio_max=80, fin_max=200)
        if audio is None:
            return
        self._poner("procesando", "Entendiendo…")
        texto = self._transcribir(audio)
        if texto:
            self._comandos.put(texto)
            self._poner("enviado", f"Enviado: «{texto}»")
            time.sleep(1.5)

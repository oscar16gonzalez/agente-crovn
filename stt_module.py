import threading

import whisper

_model = None
# Compartido con voz_local: un solo hilo usa Whisper a la vez
LOCK = threading.RLock()


def cargar_modelo(nombre="base"):
    global _model
    with LOCK:
        if _model is None:
            _model = whisper.load_model(nombre)
        return _model


def transcribir_audio(ruta_audio, idioma="es"):
    try:
        with LOCK:
            model = cargar_modelo()
            resultado = model.transcribe(ruta_audio, language=idioma)
        texto = resultado.get("text", "").strip()
        print(f"[STT] Texto reconocido: '{texto}'")
        return texto
    except Exception as e:
        print(f"Error transcribiendo audio: {e}")
        return ""

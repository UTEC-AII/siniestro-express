"""Cliente de Groq con reintentos. Sin dependencias externas."""

import json
import os
import random
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
REINTENTABLES = (429, 500, 502, 503, 504)


def _post(payload, api_key, timeout):
    request = Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "SiniestroExpress/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def chat_json(messages, model=None, timeout=20, intentos=3):
    """Devuelve el JSON que responde el modelo. Nunca registra la API key."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY no esta configurada.")

    payload = {
        "model": model or os.getenv("GROQ_MODEL", DEFAULT_MODEL),
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    ultimo = None
    for intento in range(intentos + 1):
        try:
            data = _post(payload, api_key, timeout)
            contenido = data["choices"][0]["message"]["content"]
            return json.loads(contenido)
        except HTTPError as error:
            ultimo = error
            if error.code not in REINTENTABLES or intento >= intentos:
                raise RuntimeError(f"Groq respondio HTTP {error.code}.") from error
        except (URLError, TimeoutError) as error:
            ultimo = error
            if intento >= intentos:
                raise RuntimeError("No se pudo conectar con Groq.") from error
        except (KeyError, IndexError, ValueError) as error:
            raise RuntimeError("La respuesta de Groq no es un JSON valido.") from error
        espera = min(0.5 * (2 ** intento), 6) + random.uniform(0, 0.2)
        time.sleep(espera)
    raise RuntimeError(f"Groq no respondio: {ultimo}")

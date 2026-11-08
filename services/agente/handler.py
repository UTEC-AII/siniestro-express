"""El chat del asegurado.

Cada turno lee el historial de DynamoDB, le pide a Groq que extraiga los datos del
relato, los normaliza y, cuando ya están los siete, crea el expediente y responde con
el veredicto. El modelo nunca calcula montos: eso lo hace `core`.
"""

import base64
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from boto3.dynamodb.conditions import Attr, Key

import prompts
import slots as slots_mod
from groq_client import chat_json

CHAT_TABLE = os.getenv("CHAT_TABLE", "")
CORE_API_URL = os.getenv("CORE_API_URL", "").rstrip("/")
MAX_MENSAJES = 12

dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(CHAT_TABLE)



def _response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PATCH",
        },
        "body": json.dumps(payload, ensure_ascii=False, default=str),
    }


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _body(event):
    body = event.get("body")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    payload = body if isinstance(body, dict) else json.loads(body or "{}")
    if not isinstance(payload, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON valido.")
    return payload


def _dec(value):
    if isinstance(value, float):
        return Decimal(str(round(value, 4)))
    if isinstance(value, dict):
        return {k: _dec(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dec(v) for v in value]
    return value


def _historial(chat_id):
    items = tabla.query(KeyConditionExpression=Key("pk").eq(f"CHAT#{chat_id}")).get("Items", [])
    meta = next((i for i in items if i.get("sk") == "META"), {})
    mensajes = sorted(
        (i for i in items if i.get("sk", "").startswith("MSG#")), key=lambda x: x["sk"]
    )
    return meta, mensajes


def _poliza(poliza_id):
    with urlopen(f"{CORE_API_URL}/polizas/{poliza_id}", timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def _crear_expediente(poliza_id, chat_id, slots, coherente):
    payload = {"poliza_id": poliza_id, "chat_id": chat_id, "slots": slots, "coherente": coherente}
    request = Request(
        f"{CORE_API_URL}/expedientes",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


SIGUIENTE = {
    "PAGO_EXPRES": "Calificas a pago expres: en las proximas 24 horas coordinamos el pago y solo necesitamos fotos de tu DNI y del vehiculo.",
    "AJUSTADOR": "Un analista revisara tu caso de forma remota en las proximas 72 horas.",
    "PERITAJE": "Coordinaremos la inspeccion del vehiculo en las proximas 120 horas.",
    "REVISION_MANUAL": "Un analista revisara la coherencia de los datos antes de continuar.",
    "PENDIENTE_PREDICCION": "Un analista estimara el monto manualmente en las proximas 72 horas.",
}


def _monto_a_pagar(veredicto):
    """El cliente cobra el indemnizable, no el costo de reparacion."""
    a_pagar = veredicto.get("monto_indemnizable")
    costo = veredicto.get("costo_estimado_pen")
    deducible = veredicto.get("deducible")
    if a_pagar is None:
        return "El monto queda pendiente de estimacion."
    if costo is not None and deducible:
        return (
            f"Monto a pagar: S/ {a_pagar:,.2f} "
            f"(costo estimado S/ {costo:,.2f} menos deducible S/ {deducible:,.2f})."
        )
    return f"Monto a pagar: S/ {a_pagar:,.2f}."


def _mensaje_final(veredicto):
    codigo = veredicto.get("codigo_seguimiento") or ""
    partes = [
        f"Listo, registre tu caso {veredicto['expediente_id']} con el codigo {codigo}."
        if codigo
        else f"Listo, registre tu caso {veredicto['expediente_id']}.",
        _monto_a_pagar(veredicto),
        SIGUIENTE.get(veredicto["ruta"], f"Plazo estimado: {veredicto['plazo_horas']} horas."),
        "Guarda el codigo: con el puedes consultar el estado cuando quieras.",
    ]
    if veredicto.get("prioridad_retencion"):
        partes.insert(-1, "Un asesor te acompanara durante el proceso.")
    return " ".join(partes)


def create_chat(event, _context):
    try:
        payload = _body(event)
    except ValueError as error:
        return _response(400, {"error": str(error)})

    poliza_id = payload.get("poliza_id")
    if not poliza_id:
        return _response(400, {"error": "poliza_id requerido"})
    try:
        poliza = _poliza(poliza_id)
    except HTTPError:
        return _response(404, {"error": "poliza_no_encontrada"})
    except URLError:
        return _response(503, {"error": "servicio_core_no_disponible"})

    chat_id = payload.get("chatId") or f"chat-{int(time.time() * 1000)}"
    tabla.put_item(
        Item={
            "pk": f"CHAT#{chat_id}",
            "sk": "META",
            "chatId": chat_id,
            "titulo": poliza.get("vehiculo_placa", poliza_id),
            "poliza_id": poliza_id,
            "cliente_id": poliza.get("cliente_id", ""),
            "slots": {},
            "estado": "RECOLECTANDO",
            "creadoEn": _now(),
        }
    )
    return _response(201, {"chatId": chat_id, "poliza": poliza})


def list_chats(_event, _context):
    items = tabla.scan(FilterExpression=Attr("sk").eq("META")).get("Items", [])
    chats = sorted(items, key=lambda x: x.get("creadoEn", ""), reverse=True)
    return _response(200, {"chats": chats})


def get_chat(event, _context):
    chat_id = (event.get("pathParameters") or {}).get("chatId")
    if not chat_id:
        return _response(400, {"error": "chatId requerido"})
    meta, mensajes = _historial(chat_id)
    return _response(200, {"chat": meta, "messages": mensajes})


def send_message(event, _context):
    chat_id = (event.get("pathParameters") or {}).get("chatId")
    if not chat_id:
        return _response(400, {"error": "chatId requerido"})
    try:
        payload = _body(event)
    except ValueError as error:
        return _response(400, {"error": str(error)})

    texto = (payload.get("prompt") or "").strip()
    if not texto:
        return _response(400, {"error": "prompt requerido"})

    meta, mensajes = _historial(chat_id)
    if not meta:
        return _response(404, {"error": "chat_no_encontrado"})
    poliza_id = meta.get("poliza_id")
    if not poliza_id:
        return _response(400, {"error": "chat_sin_poliza"})

    if meta.get("expediente_id"):
        return _response(
            200,
            {
                "respuesta": (
                    "Tu caso ya esta registrado con el codigo "
                    f"{meta.get('codigo_seguimiento', '')}. Puedes consultarlo cuando quieras."
                ),
                "slots": {k: (float(v) if isinstance(v, Decimal) else v)
                          for k, v in meta.get("slots", {}).items()},
                "faltantes": [],
                "estado": "CERRADO",
                "expediente": {
                    "expediente_id": meta.get("expediente_id"),
                    "codigo_seguimiento": meta.get("codigo_seguimiento", ""),
                    "ruta": meta.get("ruta", ""),
                    "monto_indemnizable": float(meta.get("monto") or 0),
                    "plazo_horas": 0,
                    "prioridad_retencion": False,
                },
            },
        )

    try:
        poliza = _poliza(poliza_id)
    except (HTTPError, URLError) as error:
        return _response(503, {"error": "servicio_core_no_disponible", "detail": str(error)})

    slots_previos = {k: (float(v) if isinstance(v, Decimal) else v) for k, v in meta.get("slots", {}).items()}
    mensajes_groq = [{"role": "system", "content": prompts.system_prompt(poliza, slots_previos)}]
    for mensaje in mensajes[-MAX_MENSAJES:]:
        mensajes_groq.append({"role": mensaje.get("role"), "content": mensaje.get("content")})
    mensajes_groq.append({"role": "user", "content": texto})

    try:
        respuesta = chat_json(mensajes_groq)
    except RuntimeError as error:
        tabla.put_item(
            Item={
                "pk": f"CHAT#{chat_id}",
                "sk": f"MSG#{_now()}#000#user",
                "role": "user",
                "content": texto,
                "creadoEn": _now(),
            }
        )
        return _response(
            502,
            {
                "error": "agente_no_disponible",
                "detail": str(error),
                "respuesta": "Estamos con un problema tecnico. Tu reporte quedo guardado.",
            },
        )

    nuevos, errores = slots_mod.normalizar(respuesta.get("slots") or {})
    slots_actuales = slots_mod.fusionar(slots_previos, nuevos)
    faltan = slots_mod.faltantes(slots_actuales)
    coherente = (respuesta.get("coherencia") or "ok") != "baja"
    veredicto = None

    if not faltan:
        try:
            veredicto = _crear_expediente(poliza_id, chat_id, slots_actuales, coherente)
            texto_respuesta = _mensaje_final(veredicto)
            estado = "CERRADO"
        except (HTTPError, URLError) as error:
            texto_respuesta = (
                "Ya tengo todos los datos, pero no pude registrar el expediente. "
                "Un asesor lo registrara manualmente."
            )
            estado = "ERROR_REGISTRO"
            veredicto = {"error": str(error)}
    else:
        # Si el modelo devolvio un valor invalido, la respuesta la decide el sistema:
        # mostrar las opciones evita el bucle de "no te entendi" con el asegurado.
        texto_respuesta = (
            slots_mod.sugerencia(errores)
            or respuesta.get("respuesta")
            or "Cuentame un poco mas del siniestro."
        )
        estado = "RECOLECTANDO"

    marca = _now()
    tabla.put_item(Item={"pk": f"CHAT#{chat_id}", "sk": f"MSG#{marca}#000#user", "role": "user", "content": texto, "creadoEn": marca})
    tabla.put_item(Item={"pk": f"CHAT#{chat_id}", "sk": f"MSG#{marca}#001#assistant", "role": "assistant", "content": texto_respuesta, "creadoEn": marca})
    actualizacion = "SET slots = :s, estado = :e, actualizadoEn = :t"
    valores = {":s": _dec(slots_actuales), ":e": estado, ":t": marca}
    if veredicto and veredicto.get("expediente_id"):
        actualizacion += ", expediente_id = :x, codigo_seguimiento = :c, ruta = :r, monto = :m"
        valores[":x"] = veredicto["expediente_id"]
        valores[":c"] = veredicto.get("codigo_seguimiento", "")
        valores[":r"] = veredicto.get("ruta", "")
        valores[":m"] = _dec(veredicto.get("monto_indemnizable") or 0)

    tabla.update_item(
        Key={"pk": f"CHAT#{chat_id}", "sk": "META"},
        UpdateExpression=actualizacion,
        ExpressionAttributeValues=valores,
    )

    return _response(
        200,
        {
            "respuesta": texto_respuesta,
            "slots": slots_actuales,
            "faltantes": faltan,
            "estado": estado,
            "expediente": veredicto,
        },
    )

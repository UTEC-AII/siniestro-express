"""Pólizas, expedientes y fotos.

Cada entidad tiene su tabla. El expediente guarda el resultado de la liquidación, el
código de seguimiento y las claves de las fotos que subió el asegurado.
"""

import csv
import io
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from boto3.dynamodb.conditions import Key

import decision
import estados

POLIZAS_TABLE = os.getenv("POLIZAS_TABLE", "")
FOTOS_BUCKET = os.getenv("FOTOS_BUCKET", "")
EXTENSIONES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_FOTOS = 6
s3 = boto3.client("s3")
EXPEDIENTES_TABLE = os.getenv("EXPEDIENTES_TABLE", "")
ML_API_URL = os.getenv("ML_API_URL", "").rstrip("/")

dynamodb = boto3.resource("dynamodb")
polizas = dynamodb.Table(POLIZAS_TABLE)
expedientes = dynamodb.Table(EXPEDIENTES_TABLE)

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin O, 0, I ni 1: se dicta por telefono


def _codigo_seguimiento():
    """Codigo corto y legible para que el asegurado siga su caso."""
    return "SE-" + "".join(secrets.choice(ALFABETO) for _ in range(6))


COSTO_FIELDS = [
    "antiguedad_vehiculo",
    "valor_vehiculo",
    "severidad",
    "tipo_siniestro",
    "piezas_afectadas",
    "requiere_grua",
    "combustible",
]


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


def _d(value):
    return Decimal(str(round(float(value), 2)))


def _plain(item):
    """Convierte Decimal a float para responder JSON legible."""
    if isinstance(item, dict):
        return {k: _plain(v) for k, v in item.items()}
    if isinstance(item, list):
        return [_plain(v) for v in item]
    if isinstance(item, Decimal):
        return float(item)
    return item


def _body(event):
    body = event.get("body")
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")
    payload = body if isinstance(body, dict) else json.loads(body or "{}")
    if not isinstance(payload, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON valido.")
    return payload


def _post_json(url, payload, timeout=8):
    """POST con timeout corto: si el ML falla, el expediente no se pierde."""
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_poliza(poliza_id):
    return polizas.get_item(Key={"poliza_id": poliza_id}).get("Item")


def _predict_costo(slots):
    if not ML_API_URL:
        raise RuntimeError("ML_API_URL no configurada.")
    payload = {f: slots.get(f) for f in COSTO_FIELDS}
    return float(_post_json(f"{ML_API_URL}/ml/costo-reparacion", payload)["costo_reparacion_estimado"])


def _predict_abandono(poliza, slots):
    if not ML_API_URL:
        raise RuntimeError("ML_API_URL no configurada.")
    payload = {
        "edad": int(poliza.get("edad", 40)),
        "antiguedad": int(poliza.get("antiguedad", 1)),
        "prima_mensual": float(poliza.get("prima_mensual", 200)),
        "numero_siniestros": int(poliza.get("numero_siniestros", 0)) + 1,
        "numero_reclamos": int(poliza.get("numero_reclamos", 0)),
        "renovaciones": int(poliza.get("renovaciones", 1)),
    }
    return float(_post_json(f"{ML_API_URL}/ml/abandono", payload)["probabilidad_abandono"])


def get_poliza(event, _context):
    poliza_id = (event.get("pathParameters") or {}).get("poliza_id")
    if not poliza_id:
        return _response(400, {"error": "poliza_id requerido"})
    item = _get_poliza(poliza_id)
    if not item:
        return _response(404, {"error": "poliza_no_encontrada"})
    return _response(200, _plain(item))


def create_expediente(event, _context):
    try:
        payload = _body(event)
    except ValueError as error:
        return _response(400, {"error": str(error)})

    poliza_id = payload.get("poliza_id")
    slots = payload.get("slots") or {}
    coherente = payload.get("coherente", True)
    if not poliza_id:
        return _response(400, {"error": "poliza_id requerido"})
    poliza = _get_poliza(poliza_id)
    if not poliza:
        return _response(404, {"error": "poliza_no_encontrada"})

    costo, prob = None, None
    aviso = None
    try:
        costo = _predict_costo(slots)
        prob = _predict_abandono(poliza, slots)
    except (HTTPError, URLError, KeyError, ValueError, RuntimeError, TimeoutError) as error:
        aviso = f"Prediccion no disponible: {error}"

    salida = decision.liquidar(costo, prob, poliza, slots, coherente)
    expediente_id = f"EXP-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    codigo = _codigo_seguimiento()
    estado = decision.PAGO_EXPRES if decision.esta_aprobada(salida["ruta"]) else salida["ruta"]
    if salida["ruta"] == decision.PENDIENTE_PREDICCION:
        estado = decision.PENDIENTE_PREDICCION

    item = {
        "expediente_id": expediente_id,
        "codigo_seguimiento": codigo,
        "cliente_id": poliza.get("cliente_id", ""),
        "poliza_id": poliza_id,
        "chat_id": payload.get("chat_id", ""),
        "slots": {k: (v if isinstance(v, str) else str(v)) for k, v in slots.items()},
        "costo_estimado_pen": _d(costo) if costo is not None else None,
        "probabilidad_abandono": Decimal(str(prob)) if prob is not None else None,
        "ruta": salida["ruta"],
        "motivo": salida["motivo"],
        "plazo_horas": salida["plazo_horas"],
        "base_liquidacion": _d(salida["base_liquidacion"]) if salida["base_liquidacion"] is not None else None,
        "deducible": _d(salida["deducible"]) if salida["deducible"] is not None else None,
        "monto_indemnizable": _d(salida["monto_indemnizable"]) if salida["monto_indemnizable"] is not None else None,
        "documentos": salida["documentos"],
        "prioridad_retencion": salida["prioridad_retencion"],
        "estado": estado,
        "aviso": aviso or "",
        "creado_en": _now(),
        "actualizado_en": _now(),
    }
    item = {k: v for k, v in item.items() if v is not None}
    expedientes.put_item(Item=item)

    return _response(
        201,
        _plain(
            {
                "expediente_id": expediente_id,
                "codigo_seguimiento": codigo,
                "ruta": salida["ruta"],
                "motivo": salida["motivo"],
                "plazo_horas": salida["plazo_horas"],
                "costo_estimado_pen": costo,
                "base_liquidacion": salida["base_liquidacion"],
                "deducible": salida["deducible"],
                "monto_indemnizable": salida["monto_indemnizable"],
                "documentos": salida["documentos"],
                "probabilidad_abandono": prob,
                "prioridad_retencion": salida["prioridad_retencion"],
                "estado": estado,
                "aviso": aviso,
            }
        ),
    )


def get_seguimiento(event, _context):
    """Consulta pública del caso: solo lo que el asegurado necesita saber."""
    codigo = (event.get("pathParameters") or {}).get("codigo", "").strip().upper()
    if not codigo:
        return _response(400, {"error": "codigo requerido"})
    items = expedientes.query(
        IndexName="by_codigo",
        KeyConditionExpression=Key("codigo_seguimiento").eq(codigo),
    ).get("Items", [])
    if not items:
        return _response(404, {"error": "codigo_no_encontrado"})
    item = max(items, key=lambda x: x.get("creado_en", ""))
    return _response(
        200,
        _plain(
            {
                "codigo_seguimiento": item.get("codigo_seguimiento"),
                "expediente_id": item.get("expediente_id"),
                "chat_id": item.get("chat_id"),
                "poliza_id": item.get("poliza_id"),
                "ruta": item.get("ruta"),
                "estado": item.get("estado"),
                "motivo": item.get("motivo"),
                "plazo_horas": item.get("plazo_horas"),
                "costo_estimado_pen": item.get("costo_estimado_pen"),
                "deducible": item.get("deducible"),
                "monto_indemnizable": item.get("monto_indemnizable"),
                "probabilidad_abandono": item.get("probabilidad_abandono"),
                "prioridad_retencion": item.get("prioridad_retencion", False),
                "slots": item.get("slots", {}),
                "creado_en": item.get("creado_en"),
                "actualizado_en": item.get("actualizado_en"),
            }
        ),
    )


def get_expediente(event, _context):
    expediente_id = (event.get("pathParameters") or {}).get("expediente_id")
    item = expedientes.get_item(Key={"expediente_id": expediente_id}).get("Item")
    if not item:
        return _response(404, {"error": "expediente_no_encontrado"})
    return _response(200, _plain(item))


def list_expedientes(event, _context):
    params = event.get("queryStringParameters") or {}
    cliente_id = params.get("cliente_id")
    estado = params.get("estado")
    if cliente_id:
        items = expedientes.query(
            IndexName="by_cliente",
            KeyConditionExpression=Key("cliente_id").eq(cliente_id),
        ).get("Items", [])
    elif estado:
        items = expedientes.query(
            IndexName="by_estado",
            KeyConditionExpression=Key("estado").eq(estado),
        ).get("Items", [])
    else:
        items = expedientes.scan(Limit=100).get("Items", [])
    items = sorted(items, key=lambda x: x.get("creado_en", ""), reverse=True)
    return _response(200, {"expedientes": _plain(items)})


def update_expediente(event, _context):
    expediente_id = (event.get("pathParameters") or {}).get("expediente_id")
    try:
        payload = _body(event)
    except ValueError as error:
        return _response(400, {"error": str(error)})

    nuevo = (payload.get("estado") or "").upper()
    if nuevo not in {"APROBADO", "RECHAZADO", "PAGADO"}:
        return _response(400, {"error": "estado debe ser APROBADO, RECHAZADO o PAGADO"})

    actual = expedientes.get_item(Key={"expediente_id": expediente_id}).get("Item")
    if not actual:
        return _response(404, {"error": "expediente_no_encontrado"})
    if not estados.permitido(actual.get("estado"), nuevo):
        return _response(
            409,
            {
                "error": "transicion_no_permitida",
                "estado_actual": actual.get("estado"),
                "permitidas": estados.acciones(actual.get("estado")),
            },
        )

    expedientes.update_item(
        Key={"expediente_id": expediente_id},
        UpdateExpression="SET estado = :e, actualizado_en = :t, nota_revision = :n",
        ExpressionAttributeValues={
            ":e": nuevo,
            ":t": _now(),
            ":n": str(payload.get("nota") or ""),
        },
    )
    return _response(200, {"expediente_id": expediente_id, "estado": nuevo})


def presign_foto(event, _context):
    """URL firmada para que el navegador suba la foto directo a S3."""
    expediente_id = (event.get("pathParameters") or {}).get("expediente_id")
    try:
        payload = _body(event)
    except ValueError as error:
        return _response(400, {"error": str(error)})

    tipo = str(payload.get("content_type") or "").lower()
    if tipo not in EXTENSIONES:
        return _response(400, {"error": "content_type debe ser image/jpeg, image/png o image/webp"})

    item = expedientes.get_item(Key={"expediente_id": expediente_id}).get("Item")
    if not item:
        return _response(404, {"error": "expediente_no_encontrado"})
    if len(item.get("fotos", [])) >= MAX_FOTOS:
        return _response(400, {"error": f"el expediente ya tiene {MAX_FOTOS} fotos"})

    key = f"expedientes/{expediente_id}/{uuid.uuid4().hex[:8]}.{EXTENSIONES[tipo]}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": FOTOS_BUCKET, "Key": key, "ContentType": tipo},
        ExpiresIn=900,
    )
    return _response(200, {"upload_url": url, "key": key, "expira_en_segundos": 900})


def registrar_fotos(event, _context):
    """Guarda las claves de las fotos ya subidas en el expediente."""
    expediente_id = (event.get("pathParameters") or {}).get("expediente_id")
    try:
        payload = _body(event)
    except ValueError as error:
        return _response(400, {"error": str(error)})

    claves = payload.get("keys") or []
    if not isinstance(claves, list) or not claves:
        return _response(400, {"error": "keys debe ser una lista no vacia"})
    if not all(isinstance(k, str) and k.startswith(f"expedientes/{expediente_id}/") for k in claves):
        return _response(400, {"error": "keys invalidas para este expediente"})

    item = expedientes.get_item(Key={"expediente_id": expediente_id}).get("Item")
    if not item:
        return _response(404, {"error": "expediente_no_encontrado"})

    actuales = list(item.get("fotos", []))
    for clave in claves:
        if clave not in actuales:
            actuales.append(clave)

    expedientes.update_item(
        Key={"expediente_id": expediente_id},
        UpdateExpression="SET fotos = :f, actualizado_en = :t",
        ExpressionAttributeValues={":f": actuales, ":t": _now()},
    )
    return _response(200, {"expediente_id": expediente_id, "fotos": len(actuales)})


def fotos_del_expediente(event, _context):
    """URLs de lectura temporales para que el analista vea las fotos."""
    expediente_id = (event.get("pathParameters") or {}).get("expediente_id")
    item = expedientes.get_item(Key={"expediente_id": expediente_id}).get("Item")
    if not item:
        return _response(404, {"error": "expediente_no_encontrado"})

    fotos = [
        {
            "key": clave,
            "url": s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": FOTOS_BUCKET, "Key": clave},
                ExpiresIn=300,
            ),
        }
        for clave in item.get("fotos", [])
    ]
    return _response(200, {"expediente_id": expediente_id, "fotos": fotos})


def export_csv(event, _context):
    # Excel en espanol espera punto y coma; el resto del mundo, coma.
    params = event.get("queryStringParameters") or {}
    separador = ";" if params.get("sep") == ";" else ","
    items = expedientes.scan(Limit=200).get("Items", [])
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=separador)
    writer.writerow(
        [
            "expediente_id",
            "cliente_id",
            "poliza_id",
            "ruta",
            "estado",
            "costo_estimado_pen",
            "probabilidad_abandono",
            "prioridad_retencion",
            "creado_en",
        ]
    )
    for item in sorted(items, key=lambda x: x.get("creado_en", "")):
        writer.writerow(
            [
                item.get("expediente_id", ""),
                item.get("cliente_id", ""),
                item.get("poliza_id", ""),
                item.get("ruta", ""),
                item.get("estado", ""),
                float(item["costo_estimado_pen"]) if item.get("costo_estimado_pen") else "",
                float(item["probabilidad_abandono"]) if item.get("probabilidad_abandono") else "",
                item.get("prioridad_retencion", False),
                item.get("creado_en", ""),
            ]
        )
    # El BOM hace que Excel reconozca los acentos como UTF-8.
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=expedientes.csv",
            "Access-Control-Allow-Origin": "*",
        },
        "body": "\ufeff" + buffer.getvalue(),
    }

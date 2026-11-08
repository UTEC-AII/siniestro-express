"""Los dos modelos, servidos sin dependencias.

Los bosques vienen exportados a JSON y se recorren con la biblioteca estándar. La
validación de los campos es estricta a propósito: un enum mal escrito no rompe el
modelo, devuelve un monto plausible y equivocado, que es peor.
"""

import base64
import binascii
import json
from pathlib import Path

import forest

BASE = Path(__file__).resolve().parent
SEVERIDAD = ["Leve", "Media", "Grave"]
TIPO_SINIESTRO = ["Choque_Multiple", "Colision", "Inundacion", "Robo_Parcial", "Volcadura"]
COMBUSTIBLE = ["Diesel", "Electrico", "Gasolina", "Hibrido"]
COSTO_FIELDS = [
    "antiguedad_vehiculo",
    "valor_vehiculo",
    "severidad",
    "tipo_siniestro",
    "piezas_afectadas",
    "requiere_grua",
    "combustible",
]
ABANDONO_FIELDS = [
    "edad",
    "antiguedad",
    "prima_mensual",
    "numero_siniestros",
    "numero_reclamos",
    "renovaciones",
]
ENUMS = {
    "severidad": SEVERIDAD,
    "tipo_siniestro": TIPO_SINIESTRO,
    "combustible": COMBUSTIBLE,
}
_SPECS = {}


def _spec(name):
    if name not in _SPECS:
        path = BASE / "models" / f"{name}.json"
        _SPECS[name] = json.loads(path.read_text(encoding="utf-8"))
    return _SPECS[name]


def _response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }


def _body(event):
    body = event.get("body")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    try:
        payload = body if isinstance(body, dict) else json.loads(body or "{}")
    except (ValueError, binascii.Error) as error:
        raise ValueError("El cuerpo debe ser un objeto JSON valido.") from error
    if not isinstance(payload, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON valido.")
    return payload


def _validar(payload, fields):
    faltantes = [f for f in fields if payload.get(f) is None]
    if faltantes:
        raise ValueError(f"Faltan campos: {', '.join(faltantes)}.")
    errores = []
    for name, allowed in ENUMS.items():
        if name in fields and payload.get(name) not in allowed:
            errores.append(f"{name} debe ser uno de: {', '.join(allowed)}")
    if errores:
        raise ValueError("; ".join(errores))
    for name in ("antiguedad_vehiculo", "valor_vehiculo", "piezas_afectadas"):
        if name in fields and float(payload[name]) < 0:
            raise ValueError(f"{name} no puede ser negativo.")
    if "piezas_afectadas" in fields and not 1 <= int(payload["piezas_afectadas"]) <= 14:
        raise ValueError("piezas_afectadas debe estar entre 1 y 14.")
    if "requiere_grua" in fields and int(payload["requiere_grua"]) not in (0, 1):
        raise ValueError("requiere_grua debe ser 0 o 1.")


def _handle(event, fields, runner):
    try:
        payload = _body(event)
        _validar(payload, fields)
    except (ValueError, TypeError) as error:
        return _response(400, {"error": str(error)})
    try:
        return _response(200, runner(payload))
    except Exception as error:  # noqa: BLE001
        return _response(500, {"error": "inferencia_fallida", "detail": str(error)})


def _costo(payload):
    row = {f: payload[f] for f in COSTO_FIELDS}
    row["requiere_grua"] = int(row["requiere_grua"])
    row["piezas_afectadas"] = int(row["piezas_afectadas"])
    monto = forest.predict_regresor(_spec("costo"), row)
    return {
        "costo_reparacion_estimado": monto,
        "moneda": "PEN",
        "modelo": "RandomForestRegressor",
    }


def _abandono(payload):
    row = {f: float(payload[f]) for f in ABANDONO_FIELDS}
    prob = forest.predict_clasificador(_spec("abandono"), row)
    return {
        "probabilidad_abandono": prob,
        "abandona": prob >= 0.5,
        "modelo": "RandomForestClassifier",
    }


def costo(event, _context):
    return _handle(event, COSTO_FIELDS, _costo)


def abandono(event, _context):
    return _handle(event, ABANDONO_FIELDS, _abandono)


def health(_event, _context):
    costo_spec = _spec("costo")
    abandono_spec = _spec("abandono")
    return _response(
        200,
        {
            "status": "ok",
            "modelos": {
                "costo": {"arboles": len(costo_spec["trees"])},
                "abandono": {"arboles": len(abandono_spec["trees"])},
            },
            "runtime": "python-estandar",
        },
    )

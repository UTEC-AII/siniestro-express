"""Carga las pólizas de ejemplo en DynamoDB."""

import json
import os
from decimal import Decimal
from pathlib import Path

import boto3

TABLA = os.getenv("POLIZAS_TABLE", "siniestro-polizas-dev")
REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
tabla = boto3.resource("dynamodb", region_name=REGION).Table(TABLA)


CAMPOS = [
    "poliza_id", "cliente_id", "nombre", "vehiculo_marca", "vehiculo_modelo",
    "vehiculo_year", "antiguedad_vehiculo", "valor_vehiculo", "combustible",
    "edad", "antiguedad", "prima_mensual", "numero_siniestros",
    "numero_reclamos", "renovaciones",
]

# Campos que consume el modelo de abandono
CAMPOS_MODELO = [
    "edad", "antiguedad", "prima_mensual",
    "numero_siniestros", "numero_reclamos", "renovaciones",
]


def validar(polizas):
    """Falla temprano si una poliza no trae los campos que consumen las APIs."""
    errores = []
    for poliza in polizas:
        faltan = [c for c in CAMPOS if c not in poliza]
        if faltan:
            errores.append(f"{poliza.get('poliza_id', '?')}: faltan {', '.join(faltan)}")
        faltan_modelo = [c for c in CAMPOS_MODELO if c not in poliza]
        if faltan_modelo:
            errores.append(f"{poliza.get('poliza_id', '?')}: el modelo necesita {', '.join(faltan_modelo)}")
    if errores:
        raise SystemExit("Polizas invalidas:\n  " + "\n  ".join(errores))


def _dec(item):
    return {k: (Decimal(str(v)) if isinstance(v, float) else v) for k, v in item.items()}


def main():
    polizas = json.loads(Path(__file__).with_name("polizas.json").read_text(encoding="utf-8"))
    validar(polizas)
    with tabla.batch_writer() as lote:
        for poliza in polizas:
            lote.put_item(Item=_dec(poliza))
    print(f"{len(polizas)} polizas cargadas en {TABLA} ({REGION})")
    print("Ejemplo de poliza:", polizas[0]["poliza_id"])


if __name__ == "__main__":
    main()

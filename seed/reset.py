"""Borra los datos de prueba de DynamoDB para dejar la demo limpia.

Uso:
  python3 seed/reset.py                 # muestra qué borraría
  python3 seed/reset.py --confirmar     # borra expedientes y chats
  python3 seed/reset.py --confirmar --tabla todo   # incluye pólizas (luego hay que sembrar)

Después de borrar, vuelve a cargar las pólizas con seed/seed.py.
"""

import argparse
import os

import boto3

REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
SUFIJO = os.getenv("STAGE", "dev")

TABLAS = {
    "expedientes": f"siniestro-expedientes-{SUFIJO}",
    "chats": f"siniestro-chat-{SUFIJO}",
    "polizas": f"siniestro-polizas-{SUFIJO}",
}


def _escanear(tabla):
    """Devuelve todos los ítems, paginando: un scan simple se corta en 1 MB."""
    items, kwargs = [], {}
    while True:
        respuesta = tabla.scan(**kwargs)
        items.extend(respuesta.get("Items", []))
        if "LastEvaluatedKey" not in respuesta:
            return items
        kwargs["ExclusiveStartKey"] = respuesta["LastEvaluatedKey"]


def limpiar(nombre, confirmar):
    tabla = boto3.resource("dynamodb", region_name=REGION).Table(TABLAS[nombre])
    claves = [clave["AttributeName"] for clave in tabla.key_schema]
    items = _escanear(tabla)
    print(f"{TABLAS[nombre]:32} {len(items):4} ítems")
    if not confirmar or not items:
        return len(items)
    with tabla.batch_writer() as lote:
        for item in items:
            lote.delete_item(Key={clave: item[clave] for clave in claves})
    print(f"{'':32} borrados")
    return len(items)


def main():
    parser = argparse.ArgumentParser(description="Limpia los datos de prueba.")
    parser.add_argument("--confirmar", action="store_true", help="borra de verdad")
    parser.add_argument(
        "--tabla",
        choices=["expedientes", "chats", "todo"],
        default="expedientes",
        help="qué limpiar (por defecto solo los expedientes de prueba)",
    )
    args = parser.parse_args()

    objetivo = ["expedientes", "chats", "polizas"] if args.tabla == "todo" else [args.tabla]
    if not args.confirmar:
        print("Modo simulación. Esto es lo que hay:\n")
    total = sum(limpiar(nombre, args.confirmar) for nombre in objetivo)

    if not args.confirmar:
        print(f"\nNada borrado. Ejecuta con --confirmar para eliminar {total} ítems.")
    elif "polizas" in objetivo:
        print("\nLas pólizas se borraron: vuelve a cargarlas con seed/seed.py")


if __name__ == "__main__":
    main()

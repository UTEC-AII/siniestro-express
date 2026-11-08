"""Comprueba que el modelo exportado prediga igual que scikit-learn.

Se corre después de reexportar: si el runtime de `forest.py` se desvía, esto lo
detecta antes de desplegar. La diferencia debe quedar por debajo de un centavo.

    python3 verificar_paridad.py
"""

from pathlib import Path

import joblib
import pandas as pd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import forest  # noqa: E402

RAIZ = Path(__file__).resolve().parent
MODELOS = RAIZ / "models"
SALIDA = RAIZ.parent / "models"
COLUMNAS = [
    "antiguedad_vehiculo", "valor_vehiculo", "severidad", "tipo_siniestro",
    "piezas_afectadas", "requiere_grua", "combustible",
]


def main():
    import json

    pipe = joblib.load(MODELOS / "modelo_costo_reparacion.joblib")
    spec = json.loads((SALIDA / "costo.json").read_text())
    datos = pd.read_csv(RAIZ / "data" / "siniestros_costos.csv").sample(400, random_state=7)

    referencia = pipe.predict(datos[COLUMNAS])
    propio = [forest.predict_regresor(spec, fila) for _, fila in datos.iterrows()]
    diferencias = [abs(float(a) - b) for a, b in zip(referencia, propio)]

    print(f"{len(diferencias)} casos comparados")
    print(f"  diferencia maxima  S/ {max(diferencias):.6f}")
    print(f"  diferencia media   S/ {sum(diferencias)/len(diferencias):.6f}")
    if max(diferencias) > 0.01:
        raise SystemExit("La paridad se rompio: revisar el runtime antes de desplegar.")
    print("  paridad correcta")


if __name__ == "__main__":
    main()

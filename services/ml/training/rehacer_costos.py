"""Recalcula el costo de reparación con precios de mercado.

El conjunto original traía montos muy por encima de la realidad peruana: el mínimo
era S/ 1,924 y ningún caso bajaba de S/ 1,000, cuando la mayoría de los reclamos de
auto son un rayón o un espejo. Acá se conservan las variables de cada siniestro y se
recalcula el costo con una fórmula de taller.

Referencias usadas (Lima, 2026):

- Parachoques delantero alternativo: S/ 210 a S/ 300 (catálogo Reacsa).
- Parachoques original en concesionario: tres a cinco veces eso.
- Pintura y mano de obra por pieza: S/ 180 a S/ 250.
- Grúa: S/ 260.

La fórmula no pretende ser un peritaje: es una aproximación honesta para que los
montos del modelo estén en el orden de magnitud correcto.

Uso:
    python3 rehacer_costos.py
"""

import random
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
ARCHIVO = RAIZ / "data" / "siniestros_costos.csv"

# Repuesto más pintura y mano de obra, por pieza y gravedad.
BASE_PIEZA = {"Leve": 420, "Media": 680, "Grave": 950}

# Un siniestro que compromete la estructura cuesta más por pieza.
FACTOR_TIPO = {
    "Colision": 1.00,
    "Choque_Multiple": 1.12,
    "Robo_Parcial": 1.05,
    "Volcadura": 1.35,
    "Inundacion": 1.25,
}

GRUA = 260
RUIDO = 0.12


def costo_real(fila, azar):
    base = BASE_PIEZA[fila.severidad] * fila.piezas_afectadas
    factor_tipo = FACTOR_TIPO[fila.tipo_siniestro]
    # Los repuestos de un auto caro cuestan más, pero no en proporción directa.
    factor_valor = (fila.valor_vehiculo / 90000) ** 0.35
    subtotal = base * factor_tipo * factor_valor
    subtotal += GRUA if fila.requiere_grua else 0
    subtotal *= 1 + azar.uniform(-RUIDO, RUIDO)
    return round(subtotal, 2)


def main():
    datos = pd.read_csv(ARCHIVO)
    azar = random.Random(42)
    datos["costo_reparacion"] = [costo_real(fila, azar) for fila in datos.itertuples()]
    datos.to_csv(ARCHIVO, index=False)

    c = datos.costo_reparacion
    print(f"{len(datos)} siniestros recalculados")
    print(f"  minimo  S/ {c.min():>8,.0f}")
    print(f"  mediana S/ {c.median():>8,.0f}")
    print(f"  maximo  S/ {c.max():>8,.0f}")
    print("\npor severidad:")
    print(datos.groupby("severidad").costo_reparacion.agg(["min", "median", "max"]).round(0).to_string())


if __name__ == "__main__":
    main()

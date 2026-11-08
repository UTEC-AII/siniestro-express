"""Recorre los bosques exportados a JSON.

Sin numpy ni scikit-learn. Cada predicción de costo es el promedio de 250 hojas y tarda
alrededor de 0,2 ms.
"""

import struct


def _f32(x):
    """sklearn recorre los árboles en float32: replicar el redondeo es obligatorio."""
    return struct.unpack("f", struct.pack("f", x))[0]


def build_vector(row, spec):
    """Vector de features en el orden del ColumnTransformer original."""
    vector = []
    for name, mean, scale in spec["numeric"]:
        vector.append(_f32((float(row.get(name, 0)) - mean) / scale))
    for name, categories in spec["categorical"]:
        value = str(row.get(name, ""))
        vector.extend(1.0 if value == category else 0.0 for category in categories)
    return vector


def _leaf(tree, vector):
    index = 0
    while tree["left"][index] != -1:
        index = (
            tree["left"][index]
            if vector[tree["feature"][index]] <= tree["threshold"][index]
            else tree["right"][index]
        )
    return tree["value"][index]


def predict_regresor(spec, row):
    """Media de las hojas del RandomForestRegressor."""
    vector = build_vector(row, spec)
    total = 0.0
    for tree in spec["trees"]:
        total += _leaf(tree, vector)[0]
    return round(total / len(spec["trees"]), 2)


def predict_clasificador(spec, row):
    """Promedio de probabilidades por hoja; devuelve P(clase positiva)."""
    vector = build_vector(row, spec)
    totals = [0.0] * len(spec["classes"])
    for tree in spec["trees"]:
        leaf = _leaf(tree, vector)
        for i in range(len(totals)):
            totals[i] += leaf[i]
    n = len(spec["trees"])
    probs = [t / n for t in totals]
    return round(probs[spec["classes"].index(1)], 4)

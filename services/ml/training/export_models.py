"""Exporta los pipelines de scikit-learn a JSON + runtime Python puro.

Sin dependencias en runtime: el JSON se evalúa con listas y floats.
"""

import json
from pathlib import Path

import joblib

R = Path(__file__).resolve().parent
MODELS = R / "models"
SALIDA = R.parent / "models"


def _tree(est):
    t = est.tree_
    values = t.value.reshape(t.value.shape[0], -1)
    return {
        "left": t.children_left.tolist(),
        "right": t.children_right.tolist(),
        "feature": t.feature.tolist(),
        "threshold": t.threshold.tolist(),
        "value": values.tolist(),
    }


def _spec_from_preprocessor(pre):
    """Extrae scaler + one-hot en el orden exacto de salida del ColumnTransformer."""
    numeric = []
    categorical = []
    for name, trans, cols in pre.transformers_:
        if name == "remainder" or trans == "drop":
            continue
        if hasattr(trans, "mean_") and hasattr(trans, "scale_"):  # StandardScaler
            numeric = [
                [str(c), float(m), float(s)]
                for c, m, s in zip(trans.feature_names_in_, trans.mean_, trans.scale_)
            ]
        elif hasattr(trans, "categories_"):  # OneHotEncoder
            categorical = [
                [str(c), [str(v) for v in cats]]
                for c, cats in zip(trans.feature_names_in_, trans.categories_)
            ]
    return numeric, categorical


def export(name, pipeline_path, out_name, kind):
    pipe = joblib.load(pipeline_path)
    steps = dict(pipe.named_steps)
    model = steps["model"]

    pre = None
    for key, step in steps.items():
        if key != "model" and hasattr(step, "transformers_"):
            pre = step
    numeric, categorical = _spec_from_preprocessor(pre) if pre is not None else ([], [])

    if not numeric and "scaler" in steps:  # pipeline simple escaler + bosque
        sc = steps["scaler"]
        numeric = [
            [str(c), float(m), float(s)]
            for c, m, s in zip(sc.feature_names_in_, sc.mean_, sc.scale_)
        ]

    spec = {
        "name": name,
        "kind": kind,  # "regressor" | "classifier"
        "numeric": numeric,
        "categorical": categorical,
        "classes": [int(c) for c in getattr(model, "classes_", [])],
        "trees": [_tree(est) for est in model.estimators_],
    }
    path = SALIDA / out_name
    path.write_text(json.dumps(spec, separators=(",", ":")))
    size = path.stat().st_size / 1024 / 1024
    print(f"{out_name}: {len(spec['trees'])} árboles, {size:.2f} MB")
    return spec


if __name__ == "__main__":
    export("costo_reparacion", MODELS / "modelo_costo_reparacion.joblib", "costo.json", "regressor")
    export("abandono", MODELS / "modelo_abandono.joblib", "abandono.json", "classifier")

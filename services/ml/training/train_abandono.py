from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
	accuracy_score,
	confusion_matrix,
	f1_score,
	precision_score,
	recall_score,
)

R = Path(__file__).resolve().parent
d = pd.read_csv(R / 'data/clientes_abandono.csv')
F = [
	'edad',
	'antiguedad',
	'prima_mensual',
	'numero_siniestros',
	'numero_reclamos',
	'renovaciones',
]
X = d[F]
y = d.abandona

Xt, Xv, yt, yv = train_test_split(
	X,
	y,
	test_size=.2,
	random_state=42,
	stratify=y,
)
m = Pipeline([
	('scaler', StandardScaler()),
	('model', RandomForestClassifier(
		n_estimators=200,
		max_depth=8,
		class_weight='balanced',
		random_state=42,
	)),
])
m.fit(Xt, yt)
p = m.predict(Xv)
q = {
	'accuracy': accuracy_score(yv, p),
	'precision': precision_score(yv, p, zero_division=0),
	'recall': recall_score(yv, p, zero_division=0),
	'f1': f1_score(yv, p, zero_division=0),
	'confusion_matrix': confusion_matrix(yv, p).tolist(),
}
joblib.dump(m, R / 'models/modelo_abandono.joblib')
(R / 'models/metricas_abandono.json').write_text(
	json.dumps(q, indent=2),
)
print(json.dumps(q, indent=2))

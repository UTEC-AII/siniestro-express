from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

R = Path(__file__).resolve().parent
d = pd.read_csv(R / 'data/siniestros_costos.csv')
N = [
	'antiguedad_vehiculo',
	'valor_vehiculo',
	'piezas_afectadas',
	'requiere_grua',
]
C = ['severidad', 'tipo_siniestro', 'combustible']
X = d[N + C]
y = d.costo_reparacion

Xt, Xv, yt, yv = train_test_split(
	X,
	y,
	test_size=.2,
	random_state=42,
)
pre = ColumnTransformer([
	('num', StandardScaler(), N),
	('cat', OneHotEncoder(handle_unknown='ignore'), C),
])
m = Pipeline([
	('preprocessor', pre),
	('model', RandomForestRegressor(
		n_estimators=250,
		max_depth=12,
		random_state=42,
		n_jobs=-1,
	)),
])
m.fit(Xt, yt)
p = m.predict(Xv)
q = {
	'mae': mean_absolute_error(yv, p),
	'rmse': mean_squared_error(yv, p) ** .5,
	'r2': r2_score(yv, p),
}
joblib.dump(m, R / 'models/modelo_costo_reparacion.joblib')
(R / 'models/metricas_costo.json').write_text(
	json.dumps(q, indent=2),
)
print(json.dumps(q, indent=2))

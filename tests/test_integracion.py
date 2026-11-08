"""Prueba de integración del camino completo con DynamoDB simulado.

No requiere AWS ni Groq: sustituye las tablas y las llamadas al servicio de ML
para verificar el contrato entre el agente y el servicio core.
"""

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
os.environ.update(
    AWS_DEFAULT_REGION="us-east-1",
    AWS_ACCESS_KEY_ID="prueba",
    AWS_SECRET_ACCESS_KEY="prueba",
    ML_API_URL="https://ml.example/dev",
    CORE_API_URL="https://core.example/dev",
    POLIZAS_TABLE="polizas",
    EXPEDIENTES_TABLE="expedientes",
    CHAT_TABLE="chats",
)


class TablaFalsa:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[(Item.get("pk"), Item.get("sk"), Item.get("poliza_id"))] = Item
        return {}

    def get_item(self, Key):
        for item in self.items.values():
            if item.get("poliza_id") == Key.get("poliza_id") or item.get("pk") == Key.get("pk"):
                return {"Item": item}
        return {}

    def query(self, **_kwargs):
        return {"Items": list(self.items.values())}

    def scan(self, **_kwargs):
        return {"Items": list(self.items.values())}

    def update_item(self, **_kwargs):
        return {}


POLIZA = {
    "poliza_id": "AUTO-2026-8801",
    "cliente_id": "CLI-1001",
    "nombre": "Ana Torres",
    "edad": 41,
    "antiguedad": 6,
    "prima_mensual": 210.5,
    "numero_siniestros": 1,
    "numero_reclamos": 0,
    "renovaciones": 4,
    "vehiculo_marca": "Hyundai",
    "vehiculo_modelo": "Tucson",
    "vehiculo_year": 2021,
}

SLOTS = {
    "antiguedad_vehiculo": 5,
    "valor_vehiculo": 97000,
    "severidad": "Media",
    "tipo_siniestro": "Colision",
    "piezas_afectadas": 2,
    "requiere_grua": 0,
    "combustible": "Gasolina",
}


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class IntegracionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(RAIZ / "services" / "core"))
        sys.path.insert(0, str(RAIZ / "services" / "agente"))
        cls.core = _cargar("core_handler", RAIZ / "services" / "core" / "handler.py")
        cls.agente = _cargar("agente_handler", RAIZ / "services" / "agente" / "handler.py")

    def setUp(self):
        self.core.polizas = TablaFalsa()
        self.core.polizas.put_item(Item=dict(POLIZA))
        self.core.expedientes = TablaFalsa()
        self.core._predict_costo = lambda slots: 850.0
        self.core._predict_abandono = lambda poliza, slots: 0.62

    def _crear(self, slots=None, coherente=True):
        evento = {
            "body": json.dumps(
                {"poliza_id": POLIZA["poliza_id"], "slots": slots or SLOTS, "coherente": coherente}
            )
        }
        respuesta = self.core.create_expediente(evento, None)
        return respuesta["statusCode"], json.loads(respuesta["body"])

    def test_siniestro_menor_va_a_pago_expres(self):
        estado, cuerpo = self._crear()
        self.assertEqual(estado, 201)
        self.assertEqual(cuerpo["ruta"], "PAGO_EXPRES")
        self.assertEqual(cuerpo["plazo_horas"], 24)
        self.assertTrue(cuerpo["prioridad_retencion"])

    def test_severidad_grave_va_a_peritaje(self):
        slots = dict(SLOTS, severidad="Grave", piezas_afectadas=1)
        estado, cuerpo = self._crear(slots)
        self.assertEqual(estado, 201)
        self.assertEqual(cuerpo["ruta"], "PERITAJE")

    def test_incoherencia_va_a_revision_manual(self):
        estado, cuerpo = self._crear(coherente=False)
        self.assertEqual(estado, 201)
        self.assertEqual(cuerpo["ruta"], "REVISION_MANUAL")

    def test_si_falla_ml_el_expediente_se_crea_igual(self):
        def falla(_slots):
            raise RuntimeError("ml caido")

        self.core._predict_costo = falla
        estado, cuerpo = self._crear()
        self.assertEqual(estado, 201)
        self.assertEqual(cuerpo["ruta"], "PENDIENTE_PREDICCION")
        self.assertIn("Prediccion no disponible", cuerpo["aviso"])

    def test_codigo_de_seguimiento_es_legible(self):
        _estado, cuerpo = self._crear()
        codigo = cuerpo["codigo_seguimiento"]
        self.assertTrue(codigo.startswith("SE-"))
        self.assertEqual(len(codigo), 9)
        for confuso in "O0I1":
            self.assertNotIn(confuso, codigo[3:])

    def test_mensaje_final_incluye_monto_y_plazo(self):
        _estado, cuerpo = self._crear()
        mensaje = self.agente._mensaje_final(cuerpo)
        self.assertIn("S/ 500.00", mensaje)
        self.assertIn("24 horas", mensaje)
        self.assertIn(cuerpo["expediente_id"], mensaje)


if __name__ == "__main__":
    unittest.main()

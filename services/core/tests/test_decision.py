"""Pruebas del motor de decisión y liquidación."""

import unittest

import decision

POLIZA = {"valor_vehiculo": 97000.0}


class PagoExpresTests(unittest.TestCase):
    def test_caso_menor_sin_grua(self):
        salida = decision.liquidar(850.0, 0.31, POLIZA, {"severidad": "Media", "requiere_grua": 0, "piezas_afectadas": 2})
        self.assertEqual(salida["ruta"], decision.PAGO_EXPRES)
        self.assertEqual(salida["plazo_horas"], 24)
        self.assertFalse(salida["prioridad_retencion"])

    def test_con_grua_no_es_pago_expres(self):
        salida = decision.liquidar(800.0, 0.1, POLIZA, {"severidad": "Leve", "requiere_grua": 1, "piezas_afectadas": 1})
        self.assertEqual(salida["ruta"], decision.AJUSTADOR)

    def test_tres_piezas_no_es_pago_expres(self):
        salida = decision.liquidar(800.0, 0.1, POLIZA, {"severidad": "Leve", "requiere_grua": 0, "piezas_afectadas": 3})
        self.assertEqual(salida["ruta"], decision.AJUSTADOR)

    def test_borde_superior_exacto(self):
        salida = decision.liquidar(1000.0, 0.1, POLIZA, {"severidad": "Leve", "requiere_grua": 0, "piezas_afectadas": 2})
        self.assertEqual(salida["ruta"], decision.PAGO_EXPRES)


class DeducibleTests(unittest.TestCase):
    def test_deducible_del_diez_por_ciento(self):
        salida = decision.liquidar(8000.0, 0.1, POLIZA, {"requiere_grua": 1, "piezas_afectadas": 6})
        self.assertAlmostEqual(salida["deducible"], 800.00, places=2)
        self.assertAlmostEqual(salida["monto_indemnizable"], 7200.00, places=2)

    def test_deducible_minimo(self):
        salida = decision.liquidar(800.0, 0.1, POLIZA, {"requiere_grua": 0, "piezas_afectadas": 1})
        self.assertAlmostEqual(salida["deducible"], 350.0, places=2)

    def test_el_monto_nunca_es_negativo(self):
        salida = decision.liquidar(250.0, 0.1, POLIZA, {"requiere_grua": 1, "piezas_afectadas": 1})
        self.assertEqual(salida["monto_indemnizable"], 0.0)


class PeritajeTests(unittest.TestCase):
    def test_monto_alto(self):
        salida = decision.liquidar(6000.0, 0.1, POLIZA, {"severidad": "Media", "requiere_grua": 0, "piezas_afectadas": 1})
        self.assertEqual(salida["ruta"], decision.PERITAJE)
        self.assertEqual(salida["plazo_horas"], 120)

    def test_severidad_grave_nunca_es_pago_expres(self):
        salida = decision.liquidar(900.0, 0.1, POLIZA, {"severidad": "Grave", "requiere_grua": 0, "piezas_afectadas": 1})
        self.assertEqual(salida["ruta"], decision.PERITAJE)

    def test_robo_exige_parte_policial(self):
        salida = decision.liquidar(700.0, 0.1, POLIZA, {"tipo_siniestro": "Robo_Parcial", "requiere_grua": 0, "piezas_afectadas": 2})
        self.assertEqual(salida["ruta"], decision.DOCUMENTACION_PENDIENTE)
        self.assertIn("Parte policial", salida["documentos"])

    def test_robo_con_parte_policial_va_a_peritaje(self):
        salida = decision.liquidar(700.0, 0.1, POLIZA, {"tipo_siniestro": "Robo_Parcial", "parte_policial": "DEN-2026-1145", "requiere_grua": 0, "piezas_afectadas": 2})
        self.assertEqual(salida["ruta"], decision.PERITAJE)

    def test_volcadura_siempre_va_a_peritaje(self):
        salida = decision.liquidar(900.0, 0.1, POLIZA, {"tipo_siniestro": "Volcadura", "requiere_grua": 0, "piezas_afectadas": 1})
        self.assertEqual(salida["ruta"], decision.PERITAJE)


class PerdidaTotalTests(unittest.TestCase):
    def test_costo_sobre_el_setenta_y_cinco_por_ciento(self):
        salida = decision.liquidar(80000.0, 0.1, {"valor_vehiculo": 97000.0}, {"requiere_grua": 1, "piezas_afectadas": 12})
        self.assertEqual(salida["ruta"], decision.PERDIDA_TOTAL)
        self.assertAlmostEqual(salida["base_liquidacion"], 97000.0, places=2)
        self.assertAlmostEqual(salida["monto_indemnizable"], 87300.0, places=2)

    def test_por_debajo_del_umbral_repara(self):
        salida = decision.liquidar(70000.0, 0.1, {"valor_vehiculo": 97000.0}, {"requiere_grua": 1, "piezas_afectadas": 8})
        self.assertNotEqual(salida["ruta"], decision.PERDIDA_TOTAL)


class RevisionTests(unittest.TestCase):
    def test_datos_incoherentes_van_a_revision(self):
        salida = decision.liquidar(900.0, 0.1, POLIZA, {"severidad": "Grave"}, coherente=False)
        self.assertEqual(salida["ruta"], decision.REVISION_MANUAL)
        self.assertEqual(salida["plazo_horas"], 48)

    def test_sin_monto_queda_pendiente(self):
        salida = decision.liquidar(None, 0.1, POLIZA, {"severidad": "Media"})
        self.assertEqual(salida["ruta"], decision.PENDIENTE_PREDICCION)


class RetencionTests(unittest.TestCase):
    def test_umbral_de_fuga(self):
        alto = decision.liquidar(9000.0, 0.55, POLIZA, {"requiere_grua": 0, "piezas_afectadas": 1})
        bajo = decision.liquidar(9000.0, 0.54, POLIZA, {"requiere_grua": 0, "piezas_afectadas": 1})
        self.assertTrue(alto["prioridad_retencion"])
        self.assertFalse(bajo["prioridad_retencion"])


class DocumentosTests(unittest.TestCase):
    def test_cada_ruta_tiene_documentos(self):
        for ruta, docs in decision.DOCUMENTOS.items():
            self.assertTrue(docs, f"{ruta} sin documentos")

    def test_solo_pago_expres_nace_aprobado(self):
        self.assertTrue(decision.esta_aprobada(decision.PAGO_EXPRES))
        self.assertFalse(decision.esta_aprobada(decision.AJUSTADOR))


if __name__ == "__main__":
    unittest.main()

"""Pruebas de la normalización de slots."""

import unittest

import slots


class NormalizacionTests(unittest.TestCase):
    def test_alias_de_severidad(self):
        self.assertEqual(slots.normalizar({"severidad": "alta"})[0]["severidad"], "Grave")
        self.assertEqual(slots.normalizar({"severidad": "baja"})[0]["severidad"], "Leve")

    def test_choque_se_convierte_en_colision(self):
        self.assertEqual(slots.normalizar({"tipo_siniestro": "choque"})[0]["tipo_siniestro"], "Colision")

    def test_gnv_se_convierte_en_gasolina(self):
        self.assertEqual(slots.normalizar({"combustible": "gnv"})[0]["combustible"], "Gasolina")

    def test_grua_acepta_si_y_no(self):
        self.assertEqual(slots.normalizar({"requiere_grua": "no"})[0]["requiere_grua"], 0)
        self.assertEqual(slots.normalizar({"requiere_grua": "sí"})[0]["requiere_grua"], 1)

    def test_valor_con_texto(self):
        self.assertEqual(slots.normalizar({"valor_vehiculo": "97000 soles"})[0]["valor_vehiculo"], 97000.0)

    def test_valor_fuera_de_rango_se_descarta(self):
        limpio, errores = slots.normalizar({"piezas_afectadas": 40})
        self.assertNotIn("piezas_afectadas", limpio)
        self.assertTrue(errores)

    def test_enum_invalido_se_reporta(self):
        limpio, errores = slots.normalizar({"severidad": "catastrofica"})
        self.assertNotIn("severidad", limpio)
        self.assertIn("severidad", errores[0])


class FaltantesTests(unittest.TestCase):
    def test_lista_incompleta(self):
        faltan = slots.faltantes({"severidad": "Media"})
        self.assertIn("piezas_afectadas", faltan)
        self.assertNotIn("severidad", faltan)

    def test_lista_completa(self):
        completo = {
            "antiguedad_vehiculo": 5, "valor_vehiculo": 97000, "severidad": "Media",
            "tipo_siniestro": "Colision", "piezas_afectadas": 2, "requiere_grua": 0,
            "combustible": "Gasolina",
        }
        self.assertEqual(slots.faltantes(completo), [])


class FusionTests(unittest.TestCase):
    def test_no_pierde_lo_previo(self):
        base = {"severidad": "Media"}
        nuevos = {"piezas_afectadas": 2}
        self.assertEqual(slots.fusionar(base, nuevos), {"severidad": "Media", "piezas_afectadas": 2})


if __name__ == "__main__":
    unittest.main()


class CanonicoTests(unittest.TestCase):
    """Regresion: los valores canonicos deben reconocerse a si mismos.

    Sin esto, el modelo devuelve `Robo_Parcial`, el normalizador lo rechaza y el
    agente vuelve a preguntar para siempre.
    """

    def test_todos_los_valores_canonicos_son_idempotentes(self):
        for campo, valores in slots.VALORES.items():
            for valor in valores:
                limpio, errores = slots.normalizar({campo: valor})
                self.assertEqual(
                    limpio.get(campo), valor, f"{campo}={valor} no se reconoce"
                )
                self.assertEqual(errores, [])

    def test_guion_bajo_y_espacio_son_equivalentes(self):
        for variante in ["Robo_Parcial", "robo_parcial", "Robo Parcial", "robo parcial"]:
            self.assertEqual(slots.normalizar({"tipo_siniestro": variante})[0]["tipo_siniestro"],
                             "Robo_Parcial")

    def test_choque_multiple_con_guion_bajo(self):
        self.assertEqual(slots.normalizar({"tipo_siniestro": "Choque_Multiple"})[0]["tipo_siniestro"],
                         "Choque_Multiple")


class SugerenciaTests(unittest.TestCase):
    def test_ofrece_las_opciones_validas(self):
        _, errores = slots.normalizar({"tipo_siniestro": "catastrofe"})
        mensaje = slots.sugerencia(errores)
        self.assertIn("choque múltiple", mensaje)
        self.assertIn("robo parcial", mensaje)
        self.assertIn("o volcadura", mensaje)

    def test_sin_errores_no_sugiere_nada(self):
        self.assertIsNone(slots.sugerencia([]))

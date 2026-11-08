"""Pruebas de la máquina de estados."""

import unittest

import estados


class TransicionesTests(unittest.TestCase):
    def test_un_caso_pendiente_se_aprueba_o_rechaza(self):
        self.assertTrue(estados.permitido("AJUSTADOR", "APROBADO"))
        self.assertTrue(estados.permitido("PERITAJE", "RECHAZADO"))

    def test_un_caso_rechazado_no_vuelve_a_aprobarse(self):
        self.assertFalse(estados.permitido("RECHAZADO", "APROBADO"))
        self.assertEqual(estados.acciones("RECHAZADO"), [])

    def test_un_caso_aprobado_solo_se_marca_pagado(self):
        self.assertEqual(estados.acciones("APROBADO"), ["PAGADO"])

    def test_pago_expres_nace_aprobado_y_solo_pasa_a_pagado(self):
        self.assertEqual(estados.acciones("PAGO_EXPRES"), ["PAGADO"])
        self.assertFalse(estados.permitido("PAGO_EXPRES", "RECHAZADO"))

    def test_pagado_es_terminal(self):
        self.assertEqual(estados.acciones("PAGADO"), [])

    def test_estado_desconocido_no_permite_nada(self):
        self.assertFalse(estados.permitido("LO_QUE_SEA", "APROBADO"))


if __name__ == "__main__":
    unittest.main()

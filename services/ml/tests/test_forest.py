"""Pruebas del runtime de inferencia sin dependencias."""

import unittest

import forest

REG = {
    "name": "demo",
    "kind": "regressor",
    "numeric": [["x", 0.0, 1.0]],
    "categorical": [["cat", ["A", "B"]]],
    "classes": [],
    "trees": [
        {
            "left": [1, -1, -1],
            "right": [2, -1, -1],
            "feature": [0, 0, 0],
            "threshold": [0.5, -2.0, -2.0],
            "value": [[0.0], [10.0], [20.0]],
        },
        {
            "left": [1, -1, -1],
            "right": [2, -1, -1],
            "feature": [2, 0, 0],
            "threshold": [0.5, -2.0, -2.0],
            "value": [[0.0], [30.0], [40.0]],
        },
    ],
}

CLF = {
    "name": "demo-clf",
    "kind": "classifier",
    "numeric": [["x", 0.0, 1.0]],
    "categorical": [],
    "classes": [0, 1],
    "trees": [
        {"left": [1, -1, -1], "right": [2, -1, -1], "feature": [0, 0, 0],
         "threshold": [0.5, -2.0, -2.0], "value": [[0, 0], [0.8, 0.2], [0.1, 0.9]]},
        {"left": [1, -1, -1], "right": [2, -1, -1], "feature": [0, 0, 0],
         "threshold": [0.5, -2.0, -2.0], "value": [[0, 0], [0.6, 0.4], [0.0, 1.0]]},
    ],
}


class VectorTests(unittest.TestCase):
    def test_escala_numerica(self):
        vector = forest.build_vector({"x": 2.0, "cat": "A"}, REG)
        self.assertAlmostEqual(vector[0], 2.0)
        self.assertEqual(vector[1:], [1.0, 0.0])

    def test_categoria_desconocida_queda_en_ceros(self):
        vector = forest.build_vector({"x": 0.0, "cat": "Z"}, REG)
        self.assertEqual(vector[1:], [0.0, 0.0])


class RegresorTests(unittest.TestCase):
    def test_promedio_de_hojas(self):
        self.assertEqual(forest.predict_regresor(REG, {"x": 0.0, "cat": "A"}), 20.0)
        self.assertEqual(forest.predict_regresor(REG, {"x": 1.0, "cat": "B"}), 30.0)


class ClasificadorTests(unittest.TestCase):
    def test_promedio_de_probabilidades(self):
        prob = forest.predict_clasificador(CLF, {"x": 0.0})
        self.assertAlmostEqual(prob, 0.3, places=4)
        prob = forest.predict_clasificador(CLF, {"x": 1.0})
        self.assertAlmostEqual(prob, 0.95, places=4)


if __name__ == "__main__":
    unittest.main()

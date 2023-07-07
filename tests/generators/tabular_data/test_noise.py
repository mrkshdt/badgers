import unittest
from unittest import TestCase

import numpy as np
from numpy.random import default_rng

from badgers.generators.tabular_data.noise import NoiseGenerator
from tests.generators.tabular_data import generate_test_data_with_classification_labels


class TestNoiseGenerator(TestCase):
    def setUp(self) -> None:
        self.rng = default_rng(0)
        self.generators_classes = NoiseGenerator.__subclasses__()
        self.input_test_data = generate_test_data_with_classification_labels(rng=self.rng)

    def assertIncreaseVariance(self, X, Xt):
        self.assertTrue(all(np.var(X, axis=0) < np.var(Xt, axis=0)))

    def test_all_generators(self):
        """
        run generic tests for all transformer classes:
        - checks that the transformed array has the same size as the input array
        - checks that the variance of the transformed array is greater than the one of the input array
        """
        for cls in self.generators_classes:
            transformer = cls()
            for input_type, (X, y) in self.input_test_data.items():
                with self.subTest(transformer=transformer.__class__, input_type=input_type):
                    Xt, yt = transformer.generate(X.copy(), y)
                    # assert arrays have same size
                    self.assertEqual(X.shape, Xt.shape)
                    self.assertEqual(len(y), len(yt))
                    # assert variance is greater after the transformation
                    self.assertIncreaseVariance(X, Xt)
            transformer = cls(repeat=5)
            for input_type, (X, y) in self.input_test_data.items():
                with self.subTest(transformer=transformer.__class__, input_type=input_type):
                    Xt, yt = transformer.generate(X.copy(), y)
                    # assert shapes increase with repeat > 1
                    self.assertEqual(X.shape[0] * 5, Xt.shape[0])
                    self.assertEqual(X.shape[1], Xt.shape[1])
                    self.assertEqual(len(y) * 5, len(yt))

if __name__ == '__main__':
    unittest.main()

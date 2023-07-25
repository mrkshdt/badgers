import abc
from typing import Tuple

from numpy.random import default_rng
from sklearn.utils import check_array

from badgers.core.base import GeneratorMixin
from badgers.core.utils import random_sign


class OutliersGenerator(GeneratorMixin):
    """
    Base class for transformers that add noise to tabular data
    """

    def __init__(self, random_generator=default_rng(seed=0), n_outliers: int = 10):
        """
        :param random_generator: a random number generator
        :param n_outliers: the number of outliers to generate
        """
        self.random_generator = random_generator
        self.n_outliers = n_outliers
        self.outliers_indices_ = []

    @abc.abstractmethod
    def generate(self, X, y, **params) -> Tuple:
        pass

class RandomZerosGenerator(OutliersGenerator):
    """
    Randomly set data points to 0
    """

    def __init__(self, random_generator=default_rng(seed=0), n_outliers: int = 10):
        """

        :param random_generator: a random number generator
        :param n_outliers: the number of outliers to generate
        """
        super().__init__(random_generator=random_generator, n_outliers=n_outliers)

    def generate(self, X, y, **params) -> Tuple:
        """
        Randomly set values to zero
        :param X:
        :param y:
        :param params:
        :return:
        """
        # TODO input validation!
        if X.ndim < 2:
            raise ValueError(
                "Expected 2D array. "
                "Reshape your data either using array.reshape(-1, 1) if "
                "your data has a single feature or array.reshape(1, -1) "
                "if it contains a single sample."
            )
        # generate extreme values indices and values
        self.outliers_indices_ = self.random_generator.choice(X.shape[0], size=self.n_outliers, replace=False, p=None)

        for idx in self.outliers_indices_:
            X[idx, :] = 0

        return X, y

class LocalZScoreGenerator(OutliersGenerator):
    """
    Randomly generates locally extreme values.
    Given a time interval (a window) of size l, an outlier is generated by setting the value a time t
    """

    def __init__(self, random_generator=default_rng(seed=0), n_outliers: int = 10,
                 local_window_size: int = 10):
        """

        :param random_generator: a random number generator
        :param n_outliers: the number of outliers to generate
        :param  local_window_size: the width (number of data points) of the local window to compute local Z-Score
        """
        super().__init__(random_generator=random_generator, n_outliers=n_outliers)
        self.local_window_size = local_window_size

    def generate(self, X, y, **params):
        """
        Computes indices of extreme values using a uniform distribution.
        Computes the values at random outside the range [mean(X) - 3 sigma(X), mean(X) + 3 sigma(X)].
        The sign of the extreme value is the same as the value being replaced.

        :param X:
        :return: the transformed array
        """
        # TODO input validation!
        if X.ndim < 2:
            raise ValueError(
                "Expected 2D array. "
                "Reshape your data either using array.reshape(-1, 1) if "
                "your data has a single feature or array.reshape(1, -1) "
                "if it contains a single sample."
            )
        # generate extreme values indices and values
        self.outliers_indices_ = self.random_generator.choice(X.shape[0], size=self.n_outliers, replace=False, p=None)

        for idx in self.outliers_indices_:
            local_window = X[idx - int(self.local_window_size / 2):idx + int(self.local_window_size / 2), :]
            local_mean = local_window.mean(axis=0)
            local_std = local_window.std(axis=0)
            value = local_mean + random_sign(self.random_generator, size=X.shape[1]) * (3. * local_std + self.random_generator.exponential(size=X.shape[1]))
            # updating with new outliers
            X[idx, :] = value

        return X, y

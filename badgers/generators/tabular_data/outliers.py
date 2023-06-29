import abc
import warnings

import numpy as np
import sklearn.base
from numpy.random import default_rng
from sklearn.decomposition import PCA
from sklearn.neighbors import KernelDensity
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from badgers.core.base import GeneratorMixin
from badgers.core.utils import random_sign, random_spherical_coordinate


class OutliersGenerator(GeneratorMixin):
    """
    Base class for transformers that add outliers to tabular X
    """

    def __init__(self, random_generator=default_rng(seed=0), percentage_outliers: int = 10):
        """
        :param random_generator: A random generator
        :param percentage_outliers: The percentage of outliers to generate
        """
        assert 0 <= percentage_outliers <= 100

        self.random_generator = random_generator
        self.percentage_outliers = percentage_outliers

    @abc.abstractmethod
    def generate(self, X, y=None, **params):
        pass


class ZScoreSamplingGenerator(OutliersGenerator):
    """
    Randomly generates outliers as X points with a z-score > 3.
    """

    def __init__(self, random_generator=default_rng(seed=0), percentage_outliers: int = 10):
        super().__init__(random_generator, percentage_outliers)

    def generate(self, X, y=None, **params):
        """
        Randomly generates outliers as X points with a z-score > 3.

        1. Standardize the input X (mean = 0, variance = 1)
        3. Generate outliers as follows:
            - the sign is randomly chosen
            - for each dimension: the value is equal to 3 + a random number following an exponential distribution function
            with default parameters (see https://numpy.org/doc/stable/reference/random/generated/numpy.random.Generator.exponential.html)
        4. Inverse the standardization transformation

        :param X:
        :param y:
        :param params:
        :return:
        """

        # standardize X
        scaler = StandardScaler()

        # fit, transform
        scaler.fit(X)
        Xt = scaler.transform(X)

        # compute number of outliers
        n_outliers = int(Xt.shape[0] * self.percentage_outliers / 100)

        # generate outliers
        outliers = np.array([
            random_sign(self.random_generator, size=Xt.shape[1]) * (
                3. + self.random_generator.exponential(size=Xt.shape[1]))
            for _ in range(n_outliers)
        ])

        # in case we only have 1 outlier, reshape the array to match sklearn convention
        if outliers.shape[0] == 1:
            outliers = outliers.reshape(1, -1)

        # add "outliers" as labels for outliers
        yt = np.array(["outliers"] * len(outliers))

        return scaler.inverse_transform(outliers), yt


class HypersphereSamplingGenerator(OutliersGenerator):
    """
    Generates outliers by sampling points from a hypersphere with radius at least 3 sigma
    """

    def __init__(self, random_generator=default_rng(seed=0), percentage_outliers: int = 10):
        super().__init__(random_generator, percentage_outliers)

    def generate(self, X, y=None, **params):
        """
        Randomly generates outliers as X points with a z-score > 3.

        1. Standardize the input X (mean = 0, variance = 1)
        3. Generate outliers on a hypersphere (see https://en.wikipedia.org/wiki/N-sphere#Spherical_coordinates):
            - angles are chosen uniformly at random
            - radius is = 3 + a random number following an exponential distribution function with default parameters (see https://numpy.org/doc/stable/reference/random/generated/numpy.random.Generator.exponential.html)
        4. Inverse the standardization transformation

        :param X:
        :param y:
        :param params:
        :return:
        """

        # standardize X
        scaler = StandardScaler()

        # fit, transform
        scaler.fit(X)
        Xt = scaler.transform(X)

        # compute number of outliers
        n_outliers = int(Xt.shape[0] * self.percentage_outliers / 100)

        # computing outliers
        outliers = np.array([
            random_spherical_coordinate(
                random_generator=self.random_generator,
                size=Xt.shape[1],
                radius=3. + self.random_generator.exponential()
            )
            for _ in range(n_outliers)
        ])

        # in case we only have 1 outlier, reshape the array to match sklearn convention
        if outliers.shape[0] == 1:
            outliers = outliers.reshape(1, -1)

        # add "outliers" as labels for outliers
        yt = np.array(["outliers"] * len(outliers))

        return scaler.inverse_transform(outliers), yt


class HistogramSamplingGenerator(OutliersGenerator):
    """
    Randomly generates outliers from low density regions. Low density regions are estimated through histograms

    Should only be used with low dimensionality X!
    It will raise an error if the number of dimensions is greater than 5
    """

    def __init__(self, random_generator=default_rng(seed=0), percentage_outliers: int = 10,
                 threshold_low_density: float = 0.1, bins: int = 10):
        """

        :param random_generator: A random generator
        :param percentage_outliers: The percentage of outliers to generate
        :param threshold_low_density: the threshold that defines a low density region (must be between 0 and 1)
        :param bins: number of bins for the histogram
        """
        assert 0 < threshold_low_density < 1
        super().__init__(random_generator, percentage_outliers)
        self.threshold_low_density = threshold_low_density
        self.bins = bins

    def generate(self, X, y=None, **params):
        """
        Randomly generates outliers from low density regions. Low density regions are estimated through histograms

        1. Standardize the input X (mean = 0, variance = 1)
        2. Compute and normalize histogram for the X
        3. Sample datapoint uniformly at random within bins of low density
        4. Inverse the standardization transformation

        :param X:
        :return:
        """
        if X.shape[1] > 5:
            raise NotImplementedError('So far this generator only supports tabular X with at most 5 columns')
        # standardize X
        scaler = StandardScaler()
        # fit, transform
        scaler.fit(X)
        Xt = scaler.transform(X)

        # compute number of outliers
        n_outliers = int(Xt.shape[0] * self.percentage_outliers / 100)

        # compute the histogram of the X
        hist, edges = np.histogramdd(Xt, density=False, bins=self.bins)
        # normalize
        norm_hist = hist / (np.max(hist) - np.min(hist))
        # get coordinates of the histogram where the density is low (below a certain threshold)
        hist_coords_low_density = np.where(norm_hist <= self.threshold_low_density)
        # randomly pick some coordinates in the histogram where the density is low
        hist_coords_random = self.random_generator.choice(list(zip(*hist_coords_low_density)), n_outliers, replace=True)

        # computing outliers values
        outliers = np.array([
            [
                self.random_generator.uniform(low=edges[i][c], high=edges[i][c + 1])
                for i, c in enumerate(h_coords)
            ]
            for h_coords in hist_coords_random
        ])

        # in case we only have 1 outlier, reshape the array to match sklearn convention
        if outliers.shape[0] == 1:
            outliers = outliers.reshape(1, -1)

        # add "outliers" as labels for outliers
        yt = np.array(["outliers"] * len(outliers))

        return scaler.inverse_transform(outliers), yt


class LowDensitySamplingGenerator(OutliersGenerator):

    def __init__(self, random_generator=default_rng(seed=0), percentage_outliers: int = 10):
        super().__init__(random_generator=random_generator, percentage_outliers=percentage_outliers)
        self.density_estimator = KernelDensity(bandwidth="scott")

    def generate(self, X, y=None, **params):
        """
        Generate data points belonging to low density regions.

        Pseudo code:
        - Standardize the data X
        - Estimate the density based upon the original data X
        - Computes a threshold for determining low density (so far 10th percentile)
        - Sample uniformly at random within the hypercube [min, max]
        - Estimate the density of the new points and filter out the ones with a density that is above the threshold

        :param X: the input features
        :param y: not used
        :param params:
        :return:
        """
        # standardize X
        scaler = StandardScaler()
        # fit, transform
        scaler.fit(X)
        Xt = scaler.transform(X)
        # fit density estimator
        self.density_estimator = self.density_estimator.fit(Xt)
        low_density_threshold = np.percentile(self.density_estimator.score_samples(Xt), 0.1)

        n_outliers = int(Xt.shape[0] * self.percentage_outliers / 100)

        if params.get('max_samples') is not None:
            max_samples = params['max_samples']
        else:
            max_samples = n_outliers * 100

        outliers = np.array([
            x
            for x in self.random_generator.uniform(
                low=np.min(Xt, axis=0),
                high=np.max(Xt, axis=0),
                size=(max_samples, Xt.shape[1])
            )
            if self.density_estimator.score_samples(x.reshape(1, -1)) <= low_density_threshold
        ])

        if outliers.shape[0] < n_outliers:
            warnings.warn(
                f'LowDensitySamplingGenerator could not generate all {n_outliers} outliers. It only generated {len(outliers)}.')
        else:
            outliers = outliers[:n_outliers]

        # in case we only have 1 outlier, reshape the array to match sklearn convention
        if outliers.shape[0] == 1:
            outliers = outliers.reshape(1, -1)

        # add "outliers" as labels for outliers
        yt = np.array(["outliers"] * len(outliers))

        # in the case no outliers could be generated
        if outliers.shape[0] == 0:
            return outliers, yt

        return scaler.inverse_transform(outliers), yt


class DecompositionAndOutlierGenerator(OutliersGenerator):

    def __init__(self, decomposition_transformer: sklearn.base.TransformerMixin = PCA(n_components=2),
                 outlier_generator: OutliersGenerator = ZScoreSamplingGenerator(default_rng(0),
                                                                                percentage_outliers=10)):
        """

        :param decomposition_transformer: The dimensionality reduction transformer to be used before the outlier transformer
        :param outlier_generator: The outlier transformer to be used after the dimensionality has been reduced
        """
        assert hasattr(
            decomposition_transformer,
            'inverse_transform'), \
            f'the decomposition transformer class must implement the inverse_transform function.' \
            f'\nUnfortunately the class {decomposition_transformer} does not'
        super().__init__(
            random_generator=outlier_generator.random_generator,
            percentage_outliers=outlier_generator.percentage_outliers
        )

        self.decomposition_transformer = decomposition_transformer
        self.outlier_generator = outlier_generator

    def generate(self, X, y=None, **params):
        """
        Randomly generate outliers by first applying a dimensionality reduction technique (sklearn.decomposition)
        and a outlier transformer.

        1. Standardize the input X (mean = 0, variance = 1)
        2. Apply the dimensionality reduction transformer
        3. Generates outliers by applying the outlier transformer
        4. Inverse the dimensionality reduction and the standardization transformations

        :param X:
        :return:
        """

        # standardize the X and apply the dimensionality reduction transformer
        pipeline = make_pipeline(
            StandardScaler(),
            self.decomposition_transformer,
        )
        Xt = pipeline.fit_transform(X)
        # add outliers using the zscore_transformer
        Xt, yt = self.outlier_generator.generate(Xt, y)
        # inverse the manifold and standardization transformations
        return pipeline.inverse_transform(Xt), yt

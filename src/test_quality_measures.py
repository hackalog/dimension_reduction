import hypothesis.strategies as st
from hypothesis.extra.numpy import arrays
from hypothesis import given
import unittest
import numpy as np
from sklearn.base import BaseEstimator
import inspect

import src.quality_measures as qm
from .logging import logger


# old functions to test against while refactoring
def old_centering_matrix(N):
    '''
    Returns the N x N centering matrix.
    '''
    I_N = np.identity(N)
    one_N = np.matrix(np.ones(N)).transpose()
    J = I_N - one_N * one_N.transpose()/N
    return J


def old_doubly_center_matrix(matrix):
    '''
    Doubly center the matrix. That is, -J * matrix * J.

    Note that this matrix must be square.
    '''
    m, n = matrix.shape
    assert m == n, "Matrix must be square"
    J = old_centering_matrix(m)
    new_matrix = -J * matrix * J
    return new_matrix / 2


def old_strain(high_distances, low_distances):
    B = qm.doubly_center_matrix(qm.square_matrix_entries(high_distances))
    top = qm.square_matrix_entries(B - qm.square_matrix_entries(low_distances))
    result = np.sqrt(np.sum(top)/np.sum(qm.square_matrix_entries(B)))
    return result


def old_point_strain(high_distances, low_distances):
    B = qm.doubly_center_matrix(qm.square_matrix_entries(high_distances))
    top = qm.square_matrix_entries(B - qm.square_matrix_entries(low_distances))
    result = np.sum(top, axis=1)/np.sum(qm.square_matrix_entries(B))
    return result


def knn_to_point_untrustworthiness(high_knn, low_knn, n_neighbors=None,
                                   high_rank=None):
    '''
    Given the n_neighbors nearest neighbors in high space and low space,
    together with the rank matrix, compute the value of
    "untrustworthiness" of a point (this is the factor that a point
    contributes negatively to trustworthiness).
    '''
    if n_neighbors is None or high_rank is None:
        raise ValueError("n_neighbors and high_rank are required")
    point_scores = []
    N = high_knn.shape[0]
    G_K = qm._trustworthiness_normalizating_factor(n_neighbors, N)
    for i, low in enumerate(low_knn):
        trust_indices = set(low).difference(set(high_knn[i]))
        score = 0
        for j in trust_indices:
            score += (high_rank[i, j] - n_neighbors) * 2 / G_K
        point_scores.append(score)
    return np.array(point_scores)


def old_point_untrustworthiness(high_distances=None, low_distances=None,
                                high_data=None, low_data=None,
                                metric='euclidean', n_neighbors=None):
    '''
    Given high/low distances or data, compute the value of
    "untrustworthiness" of a point (this is the factor that a point
    contributes negatively to trustworthiness).
    '''
    hd, ld, _ = qm.pairwise_distance_differences(high_distances=high_distances,
                                                 low_distances=low_distances,
                                                 high_data=high_data,
                                                 low_data=low_data,
                                                 metric=metric)

    if n_neighbors is None:
        raise ValueError("n_neighbors is required")
    high_rank = qm.rank_matrix(hd)
    low_rank = qm.rank_matrix(ld)
    high_knn = qm.rank_to_knn(high_rank, n_neighbors=n_neighbors)
    low_knn = qm.rank_to_knn(low_rank, n_neighbors=n_neighbors)
    point_scores = knn_to_point_untrustworthiness(high_knn, low_knn,
                                                  n_neighbors=n_neighbors,
                                                  high_rank=high_rank)
    return point_scores


class test_estimator(BaseEstimator):
    def fit(self, X):
        self._return_value = X

    def transform(self, X):
        return self._return_value


# Start of tests
@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_square_matrix_entries(array):
    matrix = np.matrix(array)
    s_array = array**2
    assert (qm.square_matrix_entries(matrix) == s_array).all()


@given(st.integers(min_value=1, max_value=100))
def test_old_new_centering_matrix(N):
    assert (qm.centering_matrix(N) == old_centering_matrix(N)).all()


@given(st.integers(min_value=1, max_value=100))
def test_centering_matrix_output(N):
    matrix = qm.centering_matrix(N)
    assert matrix.shape == (N, N)


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_old_new_doubly_center_matrix(matrix):
    assert (qm.doubly_center_matrix(matrix) ==
            old_doubly_center_matrix(matrix)).all()


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 2), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_pairwise_distance_differences_data(high_data, low_data):
    hd, ld, dd = qm.pairwise_distance_differences(high_data=high_data,
                                                  low_data=low_data)
    n_pts = high_data.shape[0]
    assert hd.shape == (n_pts, n_pts)
    assert ld.shape == (n_pts, n_pts)
    assert dd.shape == (n_pts, n_pts)


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_pairwise_distance_differences_dist(high_dist, low_dist):
    hd, ld, dd = qm.pairwise_distance_differences(high_distances=high_dist,
                                                  low_distances=low_dist)
    n_pts = high_dist.shape[0]
    assert hd.shape == (n_pts, n_pts)
    assert ld.shape == (n_pts, n_pts)
    assert dd.shape == (n_pts, n_pts)
    assert (hd == high_dist).all()
    assert (ld == low_dist).all()
    assert (dd == (high_dist-low_dist)).all()


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 2), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_stress_data(high_data, low_data):
    stress = qm.stress(high_data=high_data, low_data=low_data)
    assert stress.dtype == 'float64'


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_stress_distances(high_distances, low_distances):
    stress = qm.stress(high_distances=high_distances,
                       low_distances=low_distances)
    assert stress.dtype == 'float64'


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 2), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_point_stress_data(high_data, low_data):
    pstress = qm.point_stress(high_data=high_data, low_data=low_data)
    n_pts = high_data.shape[0]
    assert pstress.shape == (n_pts, )


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_point_stress_distances(high_distances, low_distances):
    pstress = qm.point_stress(high_distances=high_distances,
                              low_distances=low_distances)
    n_pts = high_distances.shape[0]
    assert pstress.shape == (n_pts, )


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_old_new_strain(high_distances, low_distances):
    # all zeros raises an error. tested later.
    if not (high_distances == 0).all():
        assert (qm.strain(high_distances, low_distances) ==
                old_strain(high_distances, low_distances)).all()


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_old_new_point_strain(high_distances, low_distances):
    # all zeros raises an error. tested later.
    if not (high_distances == 0).all():
        assert (qm.point_strain(high_distances, low_distances) ==
                old_point_strain(high_distances, low_distances)).all()


# TODO: Test various input styles.
@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       st.integers(min_value=1, max_value=3))
def test_old_new_point_untrustworthiness(high_distances, low_distances,
                                         n_neighbors):
    old = old_point_untrustworthiness(high_distances=high_distances,
                                      low_distances=low_distances,
                                      n_neighbors=n_neighbors)
    new = qm.point_untrustworthiness(high_distances=high_distances,
                                     low_distances=low_distances,
                                     n_neighbors=n_neighbors)
    assert all(old == new)


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       st.integers(min_value=1, max_value=3))
def test_trustworthiness_distances(high_distances, low_distances,
                                   n_neighbors):
    new = qm.trustworthiness(high_distances=high_distances,
                             low_distances=low_distances,
                             n_neighbors=n_neighbors)
    old_point = old_point_untrustworthiness(high_distances=high_distances,
                                            low_distances=low_distances,
                                            n_neighbors=n_neighbors)
    assert new == (1-sum(old_point))
    assert new >= 0.0
    assert new <= 1.0


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       st.integers(min_value=1, max_value=3))
def test_trustworthiness_data(high_data, low_data, n_neighbors):
    new = qm.trustworthiness(high_data=high_data,
                             low_data=low_data,
                             n_neighbors=n_neighbors)
    old_point = old_point_untrustworthiness(high_data=high_data,
                                            low_data=low_data,
                                            n_neighbors=n_neighbors)
    assert new == (1-sum(old_point))
    assert new >= 0.0
    assert new <= 1.0


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       st.integers(min_value=1, max_value=3))
def test_trustworthiness_point_scores(high_distances, low_distances,
                                      n_neighbors):
    old_point = old_point_untrustworthiness(high_distances=high_distances,
                                            low_distances=low_distances,
                                            n_neighbors=n_neighbors)
    new = qm.trustworthiness(point_scores=old_point)
    assert new == (1-sum(old_point))
    assert new >= 0.0
    assert new <= 1.0


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       st.integers(min_value=1, max_value=3))
def test_continuity_distances(high_distances, low_distances,
                              n_neighbors):
    new = qm.continuity(high_distances=high_distances,
                        low_distances=low_distances,
                        n_neighbors=n_neighbors)
    assert new >= 0.0
    assert new <= 1.0


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       st.integers(min_value=1, max_value=3))
def test_continuity_data(high_data, low_data, n_neighbors):
    new = qm.continuity(high_data=high_data,
                        low_data=low_data,
                        n_neighbors=n_neighbors)
    assert new >= 0.0
    assert new <= 1.0


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)),
       st.integers(min_value=1, max_value=3))
def test_continuity_point_scores(high_distances, low_distances,
                                 n_neighbors):
    point = qm.point_discontinuity(high_distances=high_distances,
                                   low_distances=low_distances,
                                   n_neighbors=n_neighbors)
    new = qm.continuity(point_scores=point)
    assert new == (1-sum(point))
    assert new >= 0.0
    assert new <= 1.0


@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100),
              unique=True),
       arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100),
              unique=True),
       arrays(np.bool, (3, 1)),
       st.integers(min_value=1, max_value=3))
def test_scorers(hd, ld, target, n_neighbors):
    key_l = qm.available_quality_measures().keys()
    high_low_l = ["continuity", "stress", "strain", "trustworthiness"]
    greater_is_better = ["continuity", "trustworthiness"]
    estimator = test_estimator()
    estimator.fit(ld)
    for key in key_l:
        if key in greater_is_better:
            val = 1.0
        else:
            val = -1.0
        logger.debug(key)
        measure = qm.available_quality_measures()[key]
        scorer = qm.available_scorers()[key]
        if key in high_low_l:
            if 'n_neighbors' in inspect.getfullargspec(measure).args:
                m = measure(high_data=hd, low_data=ld, n_neighbors=n_neighbors)
                s = scorer(estimator, hd, n_neighbors=n_neighbors)
            else:
                m = measure(high_data=hd, low_data=ld)
                s = scorer(estimator, hd)
        elif key == '1nn-error':
            m = measure(data=ld, classes=target)
            s = scorer(estimator, hd, y=target)
        else:
            logger.debug("Untested measure:{key}. Add me to test_scorers")
            assert False
        logger.debug(f"measure:{m}, scorer:{s}")
        if m != 0 and s!=0:
            assert np.isclose(m/s, val)
        else:
            assert s == m



@given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                   max_value=100)))
def test_rank_matrix_compatibility(matrix):
    assert (qm.slower_rank_matrix(matrix) == qm.rank_matrix(matrix)).all()


class TestEncoding(unittest.TestCase):

    @given(arrays(np.float, (3, 2), elements=st.floats(min_value=-100,
                                                       max_value=100)))
    def test_doubly_center_matrix_input(self, matrix):
        with self.assertRaises(ValueError):
            qm.doubly_center_matrix(matrix)

    @given(arrays(np.float, (3, 3), elements=st.floats(min_value=-100,
                                                       max_value=100)))
    def test_pairwise_distance_differences_input(self, matrix):
        with self.assertRaises(ValueError):
            qm.pairwise_distance_differences(high_data=matrix)
        with self.assertRaises(ValueError):
            qm.pairwise_distance_differences(high_distances=matrix)
        with self.assertRaises(ValueError):
            qm.pairwise_distance_differences(low_data=matrix)
        with self.assertRaises(ValueError):
            qm.pairwise_distance_differences(low_distances=matrix)

    def test_point_untrustworthiness_input(self):
        with self.assertRaises(ValueError):
            qm.point_untrustworthiness()

    @given(st.integers(min_value=1, max_value=100))
    def test_zero_input_strain(self, N):
        matrix = np.zeros((N, N))
        with self.assertRaises(ValueError):
            qm.strain(high_distances=matrix, low_distances=matrix)

    @given(st.integers(min_value=1, max_value=100))
    def test_zero_input_point_strain(self, N):
        matrix = np.zeros((N, N))
        with self.assertRaises(ValueError):
            qm.point_strain(high_distances=matrix, low_distances=matrix)


if __name__ == '__main__':
    unittest.main()

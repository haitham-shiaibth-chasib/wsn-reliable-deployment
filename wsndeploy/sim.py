"""Monte Carlo simulation of random deployment: coverage and connectivity."""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def raster(L: float, res: int):
    """Cell-centre evaluation points of a res x res raster over [0, L]^2."""
    g = (np.arange(res) + 0.5) * L / res
    xx, yy = np.meshgrid(g, g, indexing="ij")
    return np.column_stack([xx.ravel(), yy.ravel()])


def coverage_count(sensors: np.ndarray, points: np.ndarray, r: float) -> np.ndarray:
    """Number of sensors covering each evaluation point (binary disk model)."""
    tree = cKDTree(sensors)
    return np.array([len(ix) for ix in tree.query_ball_point(points, r)])


def coverage_fraction(sensors: np.ndarray, points: np.ndarray, r: float) -> float:
    """Fraction of evaluation points within distance r of at least one sensor."""
    d, _ = cKDTree(sensors).query(points, k=1, distance_upper_bound=r * (1 + 1e-12))
    return float(np.mean(np.isfinite(d)))


def connectivity(sensors: np.ndarray, rc: float):
    """(is_connected, largest-component share) under the unit-disk graph with range rc."""
    n = len(sensors)
    pairs = cKDTree(sensors).query_pairs(rc, output_type="ndarray")
    if len(pairs) == 0:
        return n <= 1, 1.0 / max(n, 1)
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    k, labels = connected_components(g, directed=False)
    return k == 1, np.bincount(labels).max() / n


def adjacency_matrix(sensors: np.ndarray, rc: float) -> np.ndarray:
    """Dense n x n connectivity (adjacency) matrix, for small n."""
    d = np.linalg.norm(sensors[:, None, :] - sensors[None, :, :], axis=-1)
    m = (d <= rc).astype(int)
    np.fill_diagonal(m, 0)
    return m


def random_deployment(n: int, L: float, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(0.0, L, size=(n, 2))


def coverage_fraction_hetero(sensors: np.ndarray, radii: np.ndarray, points: np.ndarray) -> float:
    """Coverage fraction when sensor i has its own sensing radius radii[i]."""
    covered = np.zeros(len(points), dtype=bool)
    for rk in np.unique(radii):
        s = sensors[radii == rk]
        if len(s):
            d, _ = cKDTree(s).query(points, k=1, distance_upper_bound=rk * (1 + 1e-12))
            covered |= np.isfinite(d)
    return float(np.mean(covered))

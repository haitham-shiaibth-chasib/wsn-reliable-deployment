"""Deterministic (grid) deployments for full coverage of a square field."""
from __future__ import annotations

import math

import numpy as np
from scipy.spatial import cKDTree


def diameter_grid(L: float, r: float) -> np.ndarray:
    """Naive square grid whose spacing equals the sensing diameter: n = L/(2r) + 1
    nodes per side, spacing D = L/(n-1) <= 2r, nodes on the lattice points including
    the field boundary. Neighbouring disks touch, but the centre of every cell is
    sqrt(2) r from the nearest node, so only about pi/4 of the field is covered."""
    n = math.ceil(L / (2 * r) - 1e-9) + 1
    g = np.linspace(0.0, L, n)
    xx, yy = np.meshgrid(g, g, indexing="ij")
    return np.column_stack([xx.ravel(), yy.ravel()])


def square_grid(L: float, r: float) -> np.ndarray:
    """Corrected square grid: n = ceil(L / (sqrt(2) r)) per side, sensors at the
    centres of n x n cells of side s = L/n <= sqrt(2) r. Every point of a cell is
    within s/sqrt(2) <= r of its centre, so the field is fully covered."""
    n = math.ceil(L / (math.sqrt(2) * r) - 1e-9)
    s = L / n
    g = (np.arange(n) + 0.5) * s
    xx, yy = np.meshgrid(g, g, indexing="ij")
    return np.column_stack([xx.ravel(), yy.ravel()])


def _tri_lattice(L, r, ox, oy):
    dx, dy = math.sqrt(3) * r, 1.5 * r
    pts = []
    j = 0
    y = -oy
    while y <= L + r:
        shift = (dx / 2) if (j % 2) else 0.0
        x = -ox - shift
        while x <= L + r:
            # keep only sensors whose disk reaches the field
            cx, cy = min(max(x, 0), L), min(max(y, 0), L)
            if (x - cx) ** 2 + (y - cy) ** 2 < r ** 2:
                pts.append((x, y))
            x += dx
        y += dy
        j += 1
    return np.array(pts)


def prune_redundant(sensors, points, r):
    """Greedily drop sensors whose removal keeps every point covered."""
    tree = cKDTree(points)
    cover_sets = [np.array(tree.query_ball_point(s, r), dtype=int) for s in sensors]
    count = np.zeros(len(points), dtype=int)
    for cs in cover_sets:
        count[cs] += 1
    keep = np.ones(len(sensors), dtype=bool)
    # try sensors that cover the fewest points first (edge/corner sensors)
    for i in np.argsort([len(cs) for cs in cover_sets]):
        cs = cover_sets[i]
        if len(cs) == 0 or np.all(count[cs] >= 2):
            keep[i] = False
            count[cs] -= 1
    return sensors[keep]


def triangular_grid(L: float, r: float, points: np.ndarray, phases: int = 6) -> np.ndarray:
    """Triangular (hexagonal-cover) lattice: neighbour spacing sqrt(3) r, rows 1.5 r apart.
    Searches lattice offsets and prunes redundant boundary sensors; returns the
    smallest layout that still covers every evaluation point."""
    dx, dy = math.sqrt(3) * r, 1.5 * r
    best = None
    for ox in np.linspace(0, dx, phases, endpoint=False):
        for oy in np.linspace(0, dy, phases, endpoint=False):
            s = _tri_lattice(L, r, ox, oy)
            d, _ = cKDTree(s).query(points, distance_upper_bound=r * (1 + 1e-12))
            if not np.all(np.isfinite(d)):
                continue
            s = prune_redundant(s, points, r)
            if best is None or len(s) < len(best):
                best = s
    return best

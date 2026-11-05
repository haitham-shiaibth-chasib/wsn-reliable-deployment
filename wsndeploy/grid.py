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


def _arcs_cover_circle(arcs, tol=1e-13):
    """True if the closed arcs (a, b), b - a <= 2 pi, cover the whole circle."""
    two_pi = 2 * math.pi
    segs = []
    for a, b in arcs:
        if b - a >= two_pi - tol:
            return True
        a0 = a % two_pi
        b0 = a0 + (b - a)
        if b0 <= two_pi:
            segs.append((a0, b0))
        else:
            segs += [(a0, two_pi), (0.0, b0 - two_pi)]
    segs.sort()
    reach = 0.0
    for a, b in segs:
        if a > reach + tol:
            return False
        reach = max(reach, b)
    return reach >= two_pi - tol


def covers_square_exactly(sensors, L, r, eps=1e-9):
    """Exact test that closed disks of radius r(1 + eps) centred at `sensors` cover [0, L]^2.

    The field is covered if (i) every point of each field edge lies in some disk and (ii) every
    point of each sensing circle that lies inside the field lies in a disk of another sensor
    (perimeter coverage, Huang and Tseng 2005). Both conditions are checked with interval unions,
    so no raster is involved. The relative tolerance eps (1e-9) absorbs rounding at the points where
    a lattice cover has zero margin; the result is a statement about radius r(1 + eps).
    Returns (covered, reason) where reason names the first failing edge or sensor.
    """
    s = np.asarray(sensors, dtype=float)
    R = r * (1 + eps)
    for axis, const in ((1, 0.0), (1, L), (0, 0.0), (0, L)):          # edges y = 0, y = L, x = 0, x = L
        other = 1 - axis
        dist = np.abs(s[:, axis] - const)
        m = dist <= R
        half = np.sqrt(np.maximum(R * R - dist[m] ** 2, 0.0))
        lo, hi = s[m, other] - half, s[m, other] + half
        reach = 0.0
        for a, b in sorted(zip(lo, hi)):
            if a > reach:
                break
            reach = max(reach, b)
        if reach < L:
            return False, f"edge {'xy'[other]} at {'xy'[axis]} = {const:g} uncovered beyond {reach:.6g}"
    tree = cKDTree(s)
    for i, p in enumerate(s):
        arcs = []
        for j in tree.query_ball_point(p, r + R):
            if j == i:
                continue
            w = p - s[j]
            d = math.hypot(w[0], w[1])
            if d == 0.0:
                continue
            c = (R * R - d * d - r * r) / (2 * r * d)    # circle i point p + r u lies in disk j iff cos(angle) <= c
            if c >= 1:
                arcs = [(0.0, 2 * math.pi)]
                break
            if c <= -1:
                continue
            phi, h = math.atan2(w[1], w[0]), math.pi - math.acos(c)
            arcs.append((phi + math.pi - h, phi + math.pi + h))
        for base, coord, lim in ((0.0, p[0], L), (math.pi / 2, p[1], L)):   # arcs outside the field count as covered
            a = (lim - coord) / r                      # beyond the far edge: cos(t - base) > a
            if a < 1:
                h = math.pi if a <= -1 else math.acos(a)
                arcs.append((base - h, base + h))
            a = coord / r                              # beyond the near edge: cos(t - base) < -a
            if a < 1:
                h = math.pi if a <= -1 else math.acos(a)
                arcs.append((base + math.pi - h, base + math.pi + h))
        if not _arcs_cover_circle(arcs):
            return False, f"perimeter of sensor {i} not covered"
    return True, ""

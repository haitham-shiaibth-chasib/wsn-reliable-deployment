"""Analytical coverage models for uniform random deployment in a square field.

Three models are compared:

* ``linear_no_overlap`` - C = min(1, N*pi*r^2 / A).
                      It is linear in N and ignores overlap between sensing disks.
* ``poisson_exp``   - classical Boolean/Poisson model: C = 1 - exp(-N*pi*r^2/A).
                      Accounts for overlap, ignores the field boundary.
* ``exact_edge``    - exact expected coverage for N i.i.d. uniform sensors in a
                      square L x L, including boundary (edge) effects:
                      E[C] = (1/A) * integral over the field of 1 - (1 - a(x)/A)^N,
                      where a(x) is the area of the sensing disk centred at x that
                      falls inside the field. Computed by numerical integration.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

def linear_no_overlap(n, r, area):
    """Sum of the disk areas over the field area, capped at 1 (ignores overlap and borders)."""
    return np.minimum(np.asarray(n, dtype=float) * math.pi * r ** 2 / area, 1.0)


def poisson_exp(n, r, area):
    return 1.0 - np.exp(-np.asarray(n, dtype=float) * math.pi * r ** 2 / area)


def poisson_exp_n(c, r, area):
    return -area * math.log(1.0 - c) / (math.pi * r ** 2)


def _segment_overlap(lo, hi, a, b):
    """Length of [lo, hi] intersected with [a, b] (vectorised)."""
    return np.clip(np.minimum(hi, b) - np.maximum(lo, a), 0.0, None)


@lru_cache(maxsize=64)
def _disk_area_inside(L: float, r: float, grid: int = 240, quad: int = 400):
    """a(x, y)/A on a grid x grid of cell centres covering [0, L]^2.

    a(x, y) = integral_{u=x-r}^{x+r} 1[0<=u<=L] * |[y-h, y+h] ∩ [0, L]| du,
    h(u) = sqrt(r^2 - (u - x)^2). Midpoint rule with ``quad`` nodes.
    """
    xs = (np.arange(grid) + 0.5) * L / grid
    t = (np.arange(quad) + 0.5) / quad * 2.0 - 1.0          # nodes in (-1, 1)
    du = 2.0 * r / quad
    h = r * np.sqrt(1.0 - t ** 2)                            # half chord
    # x-part: which nodes fall inside [0, L] for each x
    u = xs[:, None] + r * t[None, :]                         # (grid, quad)
    inside_x = (u >= 0.0) & (u <= L)
    # y-part: overlap of [y-h, y+h] with [0, L] for each y and node
    ylen = _segment_overlap(xs[:, None] - h[None, :], xs[:, None] + h[None, :], 0.0, L)  # (grid, quad)
    # a(x, y) = sum_q inside_x[x, q] * ylen[y, q] * du
    a = (inside_x.astype(float) @ ylen.T) * du               # (grid_x, grid_y)
    return a / (L * L)


def exact_edge(n, r, L):
    """Exact expected coverage with boundary effects, for one or many N."""
    p = _disk_area_inside(float(L), float(r))
    n = np.atleast_1d(np.asarray(n, dtype=float))
    out = np.array([np.mean(1.0 - (1.0 - p) ** k) for k in n])
    return out if out.size > 1 else float(out[0])


def exact_edge_n(c, r, L, n_max=100000):
    """Smallest integer N whose exact expected coverage reaches c (bisection)."""
    lo, hi = 1, 2
    while exact_edge(hi, r, L) < c:
        hi *= 2
        if hi > n_max:
            raise ValueError("target coverage not reachable")
    while lo < hi:
        mid = (lo + hi) // 2
        if exact_edge(mid, r, L) >= c:
            hi = mid
        else:
            lo = mid + 1
    return lo

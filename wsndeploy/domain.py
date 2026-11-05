"""Coverage statistics for general fields: rectangles, L-shaped fields and fields with holes.

The square-field model of `models` and `reliability` uses one-dimensional quadrature that is
specific to the square. For the stress study (E19) the same quantities are computed on rasters for
any field F that is a rectangle [0, Lx] x [0, Ly] minus a union of axis-aligned rectangular cut-outs.
Nodes fall uniformly over F and only F has to be covered; a cut-out is not an obstacle (sensing
across it is not blocked), it simply does not belong to the field.

    a(x)    = |D(x, r) ∩ F| / |F|                      (one node covers x)
    a(x, y) = |D(x, r) ∩ D(y, r) ∩ F| / |F|            (one node covers x and y)
    E[C]    = mean over F of 1 - (1 - a(x))^N
    Var(C)  = mean over pairs (x, y) of (1 - a(x) - a(y) + a(x, y))^N - (1 - a(x))^N (1 - a(y))^N

All pairs enter the variance, including pairs farther apart than 2r, whose covariance
(1 - a(x) - a(y))^N - (1 - a(x))^N (1 - a(y))^N is negative for a fixed number of nodes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field as dc_field

import numpy as np
from scipy import stats
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

from .reliability import _smallest_n


@dataclass
class Domain:
    Lx: float
    Ly: float
    cutouts: list = dc_field(default_factory=list)     # [(x0, y0, x1, y1), ...] removed from the field
    name: str = ""

    @property
    def area(self):
        return self.Lx * self.Ly - sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in self.cutouts)

    def inside(self, pts):
        pts = np.atleast_2d(pts)
        ok = (pts[:, 0] >= 0) & (pts[:, 0] <= self.Lx) & (pts[:, 1] >= 0) & (pts[:, 1] <= self.Ly)
        for x0, y0, x1, y1 in self.cutouts:
            ok &= ~((pts[:, 0] > x0) & (pts[:, 0] < x1) & (pts[:, 1] > y0) & (pts[:, 1] < y1))
        return ok

    def raster(self, h):
        """Cell centres of a raster with spacing about h that lie inside the field (equal-area cells)."""
        nx, ny = max(1, round(self.Lx / h)), max(1, round(self.Ly / h))
        gx = (np.arange(nx) + 0.5) * self.Lx / nx
        gy = (np.arange(ny) + 0.5) * self.Ly / ny
        xx, yy = np.meshgrid(gx, gy, indexing="ij")
        p = np.column_stack([xx.ravel(), yy.ravel()])
        return p[self.inside(p)]

    def sample(self, n, rng):
        """n independent uniform positions over the field (rejection sampling)."""
        out = np.empty((0, 2))
        frac = self.area / (self.Lx * self.Ly)
        while len(out) < n:
            m = int(math.ceil((n - len(out)) / frac * 1.2)) + 8
            p = np.column_stack([rng.uniform(0, self.Lx, m), rng.uniform(0, self.Ly, m)])
            out = np.vstack([out, p[self.inside(p)]])
        return out[:n]


def square(L):
    return Domain(L, L, [], f"square {L:g} m")


class DomainModel:
    """Edge-corrected coverage moments and the Beta rule for a general field."""

    def __init__(self, dom: Domain, r: float, h_var=None, h_node=1.0, h_mean=None):
        self.dom, self.r = dom, r
        h_var = h_var or math.sqrt(dom.area / 5000.0)          # about 5,000 variance points
        h_mean = h_mean or h_node
        X = dom.raster(h_var)
        Y = dom.raster(h_node)                                  # possible node positions (equal-area cells)
        nb = cKDTree(Y).query_ball_point(X, r)
        rows = np.repeat(np.arange(len(X)), [len(v) for v in nb])
        cols = np.fromiter((j for v in nb for j in v), dtype=int, count=len(rows))
        self.T = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(X), len(Y)))
        self.w = 1.0 / len(Y)
        self.a = np.asarray(self.T.sum(axis=1)).ravel() * self.w
        Xm = dom.raster(h_mean)
        tree = cKDTree(Y)
        am = np.empty(len(Xm))
        for s0 in range(0, len(Xm), 4000):
            am[s0:s0 + 4000] = [len(v) for v in tree.query_ball_point(Xm[s0:s0 + 4000], r)]
        self.a_mean = am * self.w
        self.n_var_points = len(X)

    def mean(self, n):
        return float(np.mean(1.0 - (1.0 - self.a_mean) ** n))

    def var(self, n, block=600):
        p, q = self.a, (1.0 - self.a) ** n
        TT = self.T.T.tocsc()
        total, m = 0.0, len(p)
        for i0 in range(0, m, block):
            pij = (self.T[i0:i0 + block] @ TT).toarray() * self.w
            joint = (1 - p[i0:i0 + block, None] - p[None, :] + pij) ** n
            total += float(np.sum(joint - q[i0:i0 + block, None] * q[None, :]))
        return max(total / (m * m), 1e-12)

    def p_meet(self, n, c):
        mu, var = self.mean(n), self.var(n)
        var = min(var, mu * (1 - mu) * 0.999)
        t = mu * (1 - mu) / var - 1
        return float(stats.beta.sf(c, mu * t, (1 - mu) * t))

    def n_guaranteed(self, c, delta):
        return _smallest_n(lambda n: self.p_meet(n, c) >= 1 - delta)

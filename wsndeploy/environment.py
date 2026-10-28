"""Deployment in a non-ideal environment: obstacles and log-normal shadowing.

Field
    A square [0, L]^2 with axis-aligned rectangular obstacles. Sensors are dropped
    uniformly over the free area F_f (outside the obstacles), and only the free area
    has to be covered.
Sensing
    Binary disk of radius r with line of sight: an obstacle between a sensor and a
    point blocks sensing.
Radio
    Log-distance path loss with exponent eta and log-normal shadowing of standard
    deviation sigma_db (dB), independent across links and symmetric within a link.
    Rc is the median range (path loss equal to the receiver budget). A link that
    crosses an obstacle suffers an extra penetration loss pen_db. The probability
    that two nodes d apart are linked is

        g(d) = Phi( (10 eta log10(Rc / d) - pen_db * 1[blocked]) / sigma_db ),

    which tends to the unit-disk model 1[d <= Rc] as sigma_db -> 0
    (Bettstetter and Hartmann, Wireless Networks 11(5), 2005).

The analytical quantities of the open-field framework carry over once the single-node
probabilities a(x) (coverage) and b(x) (link) are computed over the free area with these
rules; this module computes them on rasters and evaluates the mean, the variance, the
isolated-node probability and the sizing rules.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field as dc_field

import numpy as np
from scipy import stats
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from .reliability import _smallest_n


# ----------------------------------------------------------------------------- geometry
@dataclass
class Field:
    L: float
    obstacles: list = dc_field(default_factory=list)      # [(x0, y0, x1, y1), ...]

    @property
    def free_area(self):
        return self.L ** 2 - sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in self.obstacles)

    def in_obstacle(self, pts):
        pts = np.atleast_2d(pts)
        inside = np.zeros(len(pts), dtype=bool)
        for x0, y0, x1, y1 in self.obstacles:
            inside |= (pts[:, 0] > x0) & (pts[:, 0] < x1) & (pts[:, 1] > y0) & (pts[:, 1] < y1)
        return inside

    def free_raster(self, res):
        g = (np.arange(res) + 0.5) * self.L / res
        xx, yy = np.meshgrid(g, g, indexing="ij")
        pts = np.column_stack([xx.ravel(), yy.ravel()])
        return pts[~self.in_obstacle(pts)]

    def sample(self, n, rng):
        """n points uniform over the free area (rejection sampling)."""
        out = np.empty((0, 2))
        while len(out) < n:
            p = rng.uniform(0.0, self.L, size=(max(2 * (n - len(out)), 8), 2))
            out = np.vstack([out, p[~self.in_obstacle(p)]])
        return out[:n]

    def blocked(self, P, Q):
        """True where the segment P[i] -> Q[i] crosses an obstacle (Liang-Barsky clipping)."""
        P, Q = np.atleast_2d(P).astype(float), np.atleast_2d(Q).astype(float)
        hit = np.zeros(max(len(P), len(Q)), dtype=bool)
        if not self.obstacles:
            return hit
        d = Q - P
        with np.errstate(divide="ignore", invalid="ignore"):
            for x0, y0, x1, y1 in self.obstacles:
                t_lo = np.zeros(len(hit))
                t_hi = np.ones(len(hit))
                ok = np.ones(len(hit), dtype=bool)
                for k, (lo, hi) in enumerate(((x0, x1), (y0, y1))):
                    dk, pk = d[:, k], P[:, k]
                    par = dk == 0
                    ok &= ~(par & ((pk <= lo) | (pk >= hi)))
                    t1 = np.where(par, -np.inf, (lo - pk) / np.where(par, 1, dk))
                    t2 = np.where(par, np.inf, (hi - pk) / np.where(par, 1, dk))
                    t_lo = np.maximum(t_lo, np.minimum(t1, t2))
                    t_hi = np.minimum(t_hi, np.maximum(t1, t2))
                hit |= ok & (t_lo < t_hi)
        return hit


@dataclass
class Radio:
    Rc: float               # median communication range (m)
    eta: float = 3.0        # path-loss exponent
    sigma_db: float = 0.0   # shadowing standard deviation (dB)
    pen_db: float = 0.0     # penetration loss of an obstacle (dB)

    def link_prob(self, d, blocked):
        d = np.maximum(np.asarray(d, dtype=float), 1e-9)
        margin = 10 * self.eta * np.log10(self.Rc / d) - self.pen_db * np.asarray(blocked, dtype=float)
        if self.sigma_db <= 0:
            return (margin >= 0).astype(float)
        return stats.norm.cdf(margin / self.sigma_db)


# ----------------------------------------------------------------------------- Monte Carlo
def coverage_los(fld: Field, sensors, pts, r):
    """Share of the points pts (free area) within r of a sensor with line of sight."""
    if len(sensors) == 0:
        return 0.0
    nb = cKDTree(sensors).query_ball_point(pts, r)
    lens = np.fromiter((len(v) for v in nb), dtype=int, count=len(pts))
    if not fld.obstacles:
        return float(np.mean(lens > 0))
    pi = np.repeat(np.arange(len(pts)), lens)
    si = np.fromiter((j for v in nb for j in v), dtype=int, count=int(lens.sum()))
    vis = ~fld.blocked(pts[pi], sensors[si])
    covered = np.zeros(len(pts), dtype=bool)
    covered[pi[vis]] = True
    return float(np.mean(covered))


def random_links(fld: Field, radio: Radio, sensors, rng):
    """Sample the shadowed link graph; returns the edge list (i, j)."""
    n = len(sensors)
    i, j = np.triu_indices(n, 1)
    d = np.linalg.norm(sensors[i] - sensors[j], axis=1)
    b = fld.blocked(sensors[i], sensors[j]) if fld.obstacles else np.zeros(len(i), dtype=bool)
    keep = rng.random(len(i)) < radio.link_prob(d, b)
    return i[keep], j[keep]


def connectivity_shadow(fld: Field, radio: Radio, sensors, rng):
    """(connected, no isolated node) for one realisation of the shadowed link graph."""
    n = len(sensors)
    i, j = random_links(fld, radio, sensors, rng)
    deg = np.bincount(np.concatenate([i, j]), minlength=n)
    if n <= 1:
        return n == 1, n == 1
    g = coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n))
    k, _ = connected_components(g, directed=False)
    return bool(k == 1), bool(np.all(deg > 0))


# ----------------------------------------------------------------------------- analytical
class EnvironmentModel:
    """Coverage and connectivity statistics of N uniform drops over the free area."""

    def __init__(self, fld: Field, r: float, radio: Radio, coarse=80, fine=200, mean_grid=200, conn_coarse=100,
                 conn_fine=200):
        self.fld, self.r, self.radio = fld, r, radio
        X = fld.free_raster(coarse)                     # evaluation points
        Y = fld.free_raster(fine)                       # possible node positions (equal-area cells)
        nb = cKDTree(Y).query_ball_point(X, r)
        rows = np.repeat(np.arange(len(X)), [len(v) for v in nb])
        cols = np.fromiter((j for v in nb for j in v), dtype=int, count=len(rows))
        if fld.obstacles:
            vis = ~fld.blocked(X[rows], Y[cols])
            rows, cols = rows[vis], cols[vis]
        self.T = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(X), len(Y)))
        self.w = 1.0 / len(Y)
        self.a = np.asarray(self.T.sum(axis=1)).ravel() * self.w        # a(x) on the variance grid
        # a(x) on a finer grid for the mean (counts only, computed in chunks)
        Xm = fld.free_raster(mean_grid)
        tree = cKDTree(Y)
        am = np.empty(len(Xm))
        for s0 in range(0, len(Xm), 2000):
            xs = Xm[s0:s0 + 2000]
            nbm = tree.query_ball_point(xs, r)
            if not fld.obstacles:
                am[s0:s0 + 2000] = [len(v) for v in nbm]
                continue
            rr = np.repeat(np.arange(len(xs)), [len(v) for v in nbm])
            cc = np.fromiter((j for v in nbm for j in v), dtype=int, count=len(rr))
            vis = ~fld.blocked(xs[rr], Y[cc])
            am[s0:s0 + 2000] = np.bincount(rr[vis], minlength=len(xs))
        self.a_mean = am * self.w
        # link probability b(y) on a coarser set of node positions
        Yb, Zb = fld.free_raster(conn_coarse), fld.free_raster(conn_fine)
        b = np.empty(len(Yb))
        for s in range(0, len(Yb), 200):
            yb = Yb[s:s + 200]
            P = np.repeat(yb, len(Zb), axis=0)
            Q = np.tile(Zb, (len(yb), 1))
            d = np.linalg.norm(P - Q, axis=1)
            bl = fld.blocked(P, Q) if fld.obstacles else np.zeros(len(P), dtype=bool)
            b[s:s + 200] = radio.link_prob(d, bl).reshape(len(yb), len(Zb)).mean(axis=1)
        self.b = b

    # -- coverage
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

    # -- connectivity
    def p_no_isolated(self, n):
        e_iso = n * float(np.mean((1.0 - self.b) ** (n - 1)))
        return math.exp(-e_iso)

    # -- sizing
    def n_cov(self, c, delta):
        return _smallest_n(lambda n: self.p_meet(n, c) >= 1 - delta)

    def n_conn(self, eps):
        return _smallest_n(lambda n: self.p_no_isolated(n) >= 1 - eps, start=2)

    def n_joint(self, c, delta):
        return max(self.n_cov(c, delta / 2), self.n_conn(delta / 2))

    # -- connectivity estimated by simulation (for obstructed fields)
    def p_connected_mc(self, n, runs, seed):
        """Share of `runs` independent drops of n nodes whose shadowed link graph is connected."""
        rng = np.random.default_rng(seed)
        ok = 0
        for _ in range(runs):
            ok += connectivity_shadow(self.fld, self.radio, self.fld.sample(n, rng), rng)[0]
        return ok / runs

    def n_conn_mc(self, eps, runs=2000, seed_base=0, start=None, coarse_step=5):
        """Smallest n with simulated P(connected) >= 1 - eps.

        The isolated-node term (Eq. 9) is a lower bound on the node count only: when obstacles
        cut the field into corridors the graph can split into large pieces with no isolated node,
        and Eq. 9 is then optimistic. This rule estimates P(connected) directly from `runs`
        drops per candidate n (seed = seed_base + n). The scan starts at the analytical n_conn,
        moves up in steps of `coarse_step` and then refines to single nodes.
        Returns (n, estimated probability, {n: estimate}).
        """
        n = start if start is not None else self.n_conn(eps)
        trace = {}

        def p(m):
            if m not in trace:
                trace[m] = self.p_connected_mc(m, runs, seed_base + m)
            return trace[m]

        while p(n) < 1 - eps:
            n += coarse_step
        lo = max(n - coarse_step + 1, start if start is not None else 2)
        for m in range(lo, n):
            if p(m) >= 1 - eps:
                n = m
                break
        return n, trace[n], trace

    def n_joint_mc(self, c, delta, runs=2000, seed_base=0):
        """Joint rule with the coverage term of Eq. 8 and a simulated connectivity term."""
        n_cov = self.n_cov(c, delta / 2)
        n_con, p_con, trace = self.n_conn_mc(delta / 2, runs=runs, seed_base=seed_base)
        return max(n_cov, n_con), n_cov, n_con, p_con, trace

"""Reliability-aware models for uniform random deployment in an L x L field.

* coverage variance and a probabilistic sizing rule  N such that P(C >= C*) >= 1 - delta
* edge-corrected probability of having no isolated node (connectivity proxy)
* joint coverage + connectivity sizing
* k-coverage, random node failures and the probabilistic (Elfes) sensing model
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats
from scipy.integrate import quad
from scipy.signal import fftconvolve

from .models import _disk_area_inside


# ----------------------------------------------------------------------------- helpers
def square_distance_pdf(d, L):
    """Density of the distance between two independent uniform points in an L x L square."""
    u = np.asarray(d, dtype=float) / L
    inner = 2 * u * (math.pi - 4 * u + u * u)
    uc = np.clip(u, 1.0, math.sqrt(2))
    outer = 2 * uc * (4 * np.sqrt(uc * uc - 1) - (uc * uc + 2 - math.pi) - 4 * np.arccos(1 / uc))
    out = np.where(u <= 1, inner, np.where(u <= math.sqrt(2), outer, 0.0)) / L
    return out if out.ndim else float(out)


def lens_area(d, r):
    """Area of the intersection of two disks of radius r whose centres are d apart."""
    d = np.minimum(np.asarray(d, dtype=float), 2 * r)
    return 2 * r * r * np.arccos(d / (2 * r)) - 0.5 * d * np.sqrt(np.maximum(4 * r * r - d * d, 0))


def mean_cov(n, r, L, f=0.0):
    """Exact expected coverage with edge effects; f = independent failure probability."""
    p = (1 - f) * _disk_area_inside(float(L), float(r))
    return float(np.mean(1.0 - (1.0 - p) ** n))


def var_cov(n, r, L, f=0.0):
    """Variance of the covered fraction for N i.i.d. uniform sensors.

    Var(C) = (1/A^2) ∫∫ Cov(I_x, I_y) dx dy  with
    Cov(I_x, I_y) = (1 - 2a + l(d))^N - (1 - a)^(2N),  d = |x - y|,
    where a is the (edge-averaged) probability that one sensor covers a point and
    l(d) the probability that it covers two points d apart. The double integral is
    reduced to one dimension with the distance density of two points in a square.
    Disks are scaled by the edge factor a_eff / a_interior so that the mean is consistent.
    """
    A = L * L
    a_int = math.pi * r * r / A
    a = (1 - f) * float(np.mean(_disk_area_inside(float(L), float(r))))
    k = a / a_int

    def cov(d):
        l = k * lens_area(d, r) / A
        return (1 - 2 * a + l) ** n - (1 - a) ** (2 * n)

    near = quad(lambda d: cov(d) * square_distance_pdf(d, L), 0, min(2 * r, L * math.sqrt(2)), limit=200)[0]
    far = 0.0
    if 2 * r < L * math.sqrt(2):
        c_far = (1 - 2 * a) ** n - (1 - a) ** (2 * n)
        p_far = quad(lambda d: square_distance_pdf(d, L), 2 * r, L * math.sqrt(2), limit=200)[0]
        far = c_far * p_far
    return max(near + far, 1e-12)


def p_meet(n, c, r, L, f=0.0, dist="beta", exact_var=True):
    """P(C >= c) under a moment-matched Beta (default) or normal approximation.
    Uses the edge-aware variance by default; exact_var=False uses the stationary 1-D form."""
    mu = mean_cov(n, r, L, f)
    var = var_cov_exact(n, r, L, f) if exact_var else var_cov(n, r, L, f)
    if dist == "normal":
        return float(stats.norm.sf(c, mu, math.sqrt(var)))
    var = min(var, mu * (1 - mu) * 0.999)
    t = mu * (1 - mu) / var - 1
    return float(stats.beta.sf(c, mu * t, (1 - mu) * t))


def _smallest_n(pred, start=1, n_max=200000):
    lo, hi = start, max(start, 2)
    while not pred(hi):
        lo, hi = hi, hi * 2
        if hi > n_max:
            raise ValueError("not reachable")
    while lo < hi:
        mid = (lo + hi) // 2
        if pred(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


def n_mean(c, r, L, f=0.0):
    """Mean rule: smallest N with E[C] >= c."""
    return _smallest_n(lambda n: mean_cov(n, r, L, f) >= c)


def n_guaranteed(c, delta, r, L, f=0.0, dist="beta"):
    """Probabilistic rule: smallest N with P(C >= c) >= 1 - delta."""
    return _smallest_n(lambda n: p_meet(n, c, r, L, f, dist) >= 1 - delta)


# ----------------------------------------------------------------------------- connectivity
def p_no_isolated(n, rc, L, f=0.0):
    """Edge-corrected P(no isolated node) ≈ exp(-E[#isolated]) (Poisson approximation).

    With failures, n is the number of deployed nodes and each survives with 1 - f.
    """
    b = _disk_area_inside(float(L), float(rc))
    m = n * (1 - f)                                   # expected survivors
    e_iso = m * float(np.mean((1 - (1 - f) * b) ** (n - 1)))
    return math.exp(-e_iso)


def n_connected(eps, rc, L, f=0.0):
    return _smallest_n(lambda n: p_no_isolated(n, rc, L, f) >= 1 - eps, start=2)


def n_joint(c, delta, r, rc, L, f=0.0):
    """Joint rule (union bound): P(C >= c) >= 1 - delta/2 and P(connected) >= 1 - delta/2."""
    return max(n_guaranteed(c, delta / 2, r, L, f), n_connected(delta / 2, rc, L, f))


# ----------------------------------------------------------------------------- k-coverage
def mean_k_cov(n, k, r, L, f=0.0):
    """Expected fraction of the field covered by at least k sensors (edge-corrected)."""
    p = (1 - f) * _disk_area_inside(float(L), float(r))
    return float(np.mean(stats.binom.sf(k - 1, n, p)))


# ----------------------------------------------------------------------------- Elfes sensing
def elfes(d, r, re, lam, beta):
    """Probabilistic sensing model: 1 inside r - re, exponential decay up to r + re, 0 beyond."""
    d = np.asarray(d, dtype=float)
    a = d - (r - re)
    return np.where(d <= r - re, 1.0, np.where(d < r + re, np.exp(-lam * np.maximum(a, 0) ** beta), 0.0))


def mean_detection(n, L, r, re, lam, beta, grid=400):
    """Expected detection probability averaged over the field:
    (1/A) ∫ 1 - (1 - s(x)/A)^N dx,  s(x) = ∫_field p_d(|x - y|) dy."""
    h = L / grid
    R = r + re
    m = int(math.ceil(R / h))
    k = (np.arange(-m, m + 1)) * h
    kx, ky = np.meshgrid(k, k, indexing="ij")
    ker = elfes(np.hypot(kx, ky), r, re, lam, beta) * h * h
    s = fftconvolve(np.ones((grid, grid)), ker, mode="same")
    q = s / (L * L)
    return float(np.mean(1 - (1 - q) ** n))


# ----------------------------------------------------------------------------- exact variance
from functools import lru_cache  # noqa: E402

from scipy.sparse import csr_matrix  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402


@lru_cache(maxsize=32)
def _pair_matrix(L: float, r: float, coarse: int, fine: int):
    """Sparse incidence of coarse evaluation points x fine area elements within distance r."""
    gc = (np.arange(coarse) + 0.5) * L / coarse
    gf = (np.arange(fine) + 0.5) * L / fine
    X = np.array(np.meshgrid(gc, gc, indexing="ij")).reshape(2, -1).T
    Y = np.array(np.meshgrid(gf, gf, indexing="ij")).reshape(2, -1).T
    nb = cKDTree(Y).query_ball_point(X, r)
    rows = np.repeat(np.arange(len(X)), [len(v) for v in nb])
    cols = np.concatenate(nb)
    w = (L / fine) ** 2 / (L * L)
    S = csr_matrix((np.full(len(cols), w), (rows, cols)), shape=(len(X), len(Y)))
    T = csr_matrix((np.ones(len(cols)), (rows, cols)), shape=(len(X), len(Y)))
    return S, T


def var_cov_exact(n, r, L, f=0.0, coarse=None, fine=200, block=600):
    """Variance of the covered fraction including edge effects (numerical double integral).

    p_i  = P(one sensor covers x_i)        = |D(x_i) ∩ F| / A
    p_ij = P(one sensor covers x_i and x_j) = |D(x_i) ∩ D(x_j) ∩ F| / A
    Cov  = (1 - p_i - p_j + p_ij)^N - (1 - p_i)^N (1 - p_j)^N
    Var(C) = mean over all (i, j) of Cov.
    """
    if coarse is None:
        coarse = int(min(80, max(50, math.ceil(4 * L / r))))
    S, T = _pair_matrix(float(L), float(r), coarse, fine)
    s = 1 - f
    p = s * np.asarray(S.sum(axis=1)).ravel()
    q = (1 - p) ** n
    total = 0.0
    m = S.shape[0]
    TT = T.T.tocsc()
    w = S[0].data[0] if S.nnz else 0.0
    for i0 in range(0, m, block):
        pij = s * (T[i0:i0 + block] @ TT).toarray() * w
        joint = (1 - p[i0:i0 + block, None] - p[None, :] + pij) ** n
        total += float(np.sum(joint - q[i0:i0 + block, None] * q[None, :]))
    return max(total / (m * m), 1e-12)


# ----------------------------------------------------------------------------- heterogeneous radii
def mean_cov_mix(n, radii, weights, L, f=0.0):
    """Expected coverage when each node draws its sensing radius from a discrete distribution.

    One node covers x with probability a(x) = sum_k w_k a_k(x), so Eq. (4) holds unchanged.
    """
    p = (1 - f) * sum(w * _disk_area_inside(float(L), float(rk)) for rk, w in zip(radii, weights))
    return float(np.mean(1.0 - (1.0 - p) ** n))


def var_cov_exact_mix(n, radii, weights, L, f=0.0, coarse=None, fine=200, block=600):
    """Edge-aware variance (Eqs. 5-6) for a discrete radius distribution.

    The single-node probabilities mix linearly over the radius classes:
    p_i = sum_k w_k p_i^(k) and p_ij = sum_k w_k p_ij^(k).
    """
    if coarse is None:
        coarse = int(min(80, max(50, math.ceil(4 * L / min(radii)))))
    mats = [_pair_matrix(float(L), float(rk), coarse, fine) for rk in radii]
    s = 1 - f
    p = s * sum(w * np.asarray(S.sum(axis=1)).ravel() for (S, _), w in zip(mats, weights))
    q = (1 - p) ** n
    m = len(p)
    wcell = (L / fine) ** 2 / (L * L)
    TTs = [T.T.tocsc() for _, T in mats]
    total = 0.0
    for i0 in range(0, m, block):
        pij = sum(w * (T[i0:i0 + block] @ TT).toarray() for (_, T), TT, w in zip(mats, TTs, weights)) * s * wcell
        joint = (1 - p[i0:i0 + block, None] - p[None, :] + pij) ** n
        total += float(np.sum(joint - q[i0:i0 + block, None] * q[None, :]))
    return max(total / (m * m), 1e-12)


def p_meet_mix(n, c, radii, weights, L, f=0.0):
    """P(C >= c) under the moment-matched Beta law for heterogeneous radii."""
    mu = mean_cov_mix(n, radii, weights, L, f)
    var = min(var_cov_exact_mix(n, radii, weights, L, f), mu * (1 - mu) * 0.999)
    t = mu * (1 - mu) / var - 1
    return float(stats.beta.sf(c, mu * t, (1 - mu) * t))


def n_guaranteed_mix(c, delta, radii, weights, L, f=0.0):
    return _smallest_n(lambda n: p_meet_mix(n, c, radii, weights, L, f) >= 1 - delta)


# ----------------------------------------------------------------------------- sleep scheduling
def min_awake_share(n, c, delta, r, rc, L, step=0.01):
    """Smallest awake probability q such that a drop of n nodes, of which each is awake
    independently with probability q in a round, still meets coverage c and has no isolated
    awake node, each with probability >= 1 - delta/2 (Eq. 10 with f = 1 - q).
    Returns None if even q = 1 does not suffice."""
    ok = lambda q: (p_meet(n, c, r, L, f=1 - q) >= 1 - delta / 2 and
                    p_no_isolated(n, rc, L, f=1 - q) >= 1 - delta / 2)
    grid = np.round(np.arange(step, 1 + 1e-9, step), 6)
    if not ok(1.0):
        return None
    lo, hi = 0, len(grid) - 1                      # ok() is monotone in q
    while lo < hi:
        mid = (lo + hi) // 2
        if ok(float(grid[mid])):
            hi = mid
        else:
            lo = mid + 1
    return float(grid[lo])

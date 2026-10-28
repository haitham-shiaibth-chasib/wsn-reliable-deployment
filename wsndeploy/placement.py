"""Lattice deployment with placement errors, and optimisation baselines (VFA, PSO)."""
from __future__ import annotations

import math

import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import ncx2

from . import grid, sim
from .stats import wilson


# ----------------------------------------------------------------------------- placement errors
def expected_coverage_perturbed(planned, r, sigma, L, res=200):
    """Exact expected coverage when every sensor lands at planned + N(0, sigma^2 I).

    For a point x and a sensor planned at g, |g + e - x|^2 / sigma^2 is non-central
    chi-square with 2 d.o.f. and non-centrality |g - x|^2 / sigma^2, so
    P(sensor covers x) = F_ncx2(r^2/sigma^2; 2, |g - x|^2/sigma^2).
    Sensors are independent, hence P(x uncovered) = prod_j (1 - P_j(x)).
    """
    pts = sim.raster(L, res)
    if sigma <= 0:
        return sim.coverage_fraction(planned, pts, r)
    reach = r + 6 * sigma
    nb = cKDTree(planned).query_ball_point(pts, reach)
    log_unc = np.zeros(len(pts))
    x_over = r * r / (sigma * sigma)
    for i, idx in enumerate(nb):
        if not idx:
            continue
        d2 = np.sum((planned[idx] - pts[i]) ** 2, axis=1) / (sigma * sigma)
        pc = ncx2.cdf(x_over, 2, d2)
        log_unc[i] = np.sum(np.log1p(-np.minimum(pc, 1 - 1e-15)))
    return float(np.mean(1 - np.exp(log_unc)))


def mc_coverage_perturbed(planned, r, sigma, L, runs, rng, res=200):
    pts = sim.raster(L, res)
    return np.array([sim.coverage_fraction(planned + rng.normal(0, sigma, planned.shape), pts, r)
                     for _ in range(runs)])


def robust_lattice(L, r, sigma, target, kind="triangular", design_res=250, eval_res=150):
    """Shrink the lattice design radius kappa*r until the expected coverage under
    placement error sigma reaches the target. Returns (layout, kappa)."""
    pts = sim.raster(L, design_res)
    build = (lambda rr: grid.triangular_grid(L, rr, pts, phases=4)) if kind == "triangular" \
        else (lambda rr: grid.square_grid(L, rr))
    best = None
    for kappa in np.arange(1.0, 0.29, -0.02):
        lay = build(kappa * r)
        if expected_coverage_perturbed(lay, r, sigma, L, eval_res) >= target:
            best = (lay, round(float(kappa), 2))
            break
    return best


def reliable_lattice(L, r, sigma, target, delta, kind="triangular", design_res=250, sim_res=200, runs=300,
                     seed=0, kappa_step=0.02, kappa_min=0.30):
    """Shrink the design radius kappa*r until P(coverage >= target) >= 1 - delta holds with 95 %
    confidence: the lower end of the Wilson interval of the simulated share must reach 1 - delta
    (reliability-sized counterpart of robust_lattice).

    Every kappa is checked with the same `runs` Gaussian drops (common random numbers, generator
    default_rng(seed)), so the share changes only through the layout. Returns (layout, kappa, share, lower).
    """
    pts = sim.raster(L, design_res)
    build = (lambda rr: grid.triangular_grid(L, rr, pts, phases=4)) if kind == "triangular" \
        else (lambda rr: grid.square_grid(L, rr))
    for kappa in np.arange(1.0, kappa_min - 1e-9, -kappa_step):
        lay = build(kappa * r)
        x = mc_coverage_perturbed(lay, r, sigma, L, runs, np.random.default_rng(seed), sim_res)
        k = int(np.sum(x >= target))
        share, lo, _ = wilson(k, len(x))
        if lo >= 1 - delta:
            return lay, round(float(kappa), 2), share, lo
    return None


# ----------------------------------------------------------------------------- baselines
def lattice_for_n(L, r, n, pts, iters=18):
    """Triangular lattice that uses at most n nodes: the design radius is the smallest
    value (searched in [0.3r, 3r]) whose pruned lattice needs no more than n nodes.
    With more nodes than a full cover needs, the design radius drops below r and the
    extra nodes become overlap that absorbs placement error."""
    lo, hi = 0.3 * r, 3 * r
    best = None
    for _ in range(iters):
        mid = (lo + hi) / 2
        lay = grid.triangular_grid(L, mid, pts, phases=4)
        if len(lay) <= n:
            best, hi = lay, mid
        else:
            lo = mid
    return best


def virtual_force(L, r, n, rng, iters=400, d_th=None, step=None, w_att=0.05):
    """Virtual Force Algorithm (after Zou and Chakrabarty, 2003).

    Each sensor feels a repulsive force from neighbours closer than the threshold
    distance d_th (default sqrt(3) r, the triangular-lattice spacing), a weak
    attractive force from neighbours in [d_th, 1.5 d_th) that keeps the layout
    connected, and a repulsive force from the field border closer than d_th / 2.
    Forces are linear in the distance violation; the step size decays linearly from
    step to 0.01 r. Defaults (400 iterations, step 0.25 r, w_att 0.05) are the settings
    used in the article (config/experiments.yaml, E10_baselines.methods.VFA).
    """
    d_th = d_th or math.sqrt(3) * r
    step = step or 0.25 * r
    s = rng.uniform(0, L, (n, 2))
    eye = np.eye(n, dtype=bool)
    half = d_th / 2
    for it in range(iters):
        diff = s[:, None, :] - s[None, :, :]
        d = np.linalg.norm(diff, axis=-1) + eye
        u = diff / d[..., None]
        rep = (d < d_th) & ~eye
        att = (d >= d_th) & (d < 1.5 * d_th)
        F = np.sum(np.where(rep[..., None], u * ((d_th - d) / d_th)[..., None], 0), axis=1)
        F -= w_att * np.sum(np.where(att[..., None], u * ((d - d_th) / d_th)[..., None], 0), axis=1)
        for k in (0, 1):
            F[:, k] += np.clip(half - s[:, k], 0, None) / half - np.clip(s[:, k] - (L - half), 0, None) / half
        lr = step * (1 - it / iters) + 0.01 * r
        mag = np.linalg.norm(F, axis=1, keepdims=True)
        s = np.clip(s + lr * F / np.maximum(mag, 1.0), 0, L)
    return s


def pso(L, r, n, rng, particles=30, iters=300, res=80, w=0.729, c1=1.49445, c2=1.49445):
    """Global-best PSO over all sensor coordinates; fitness = covered fraction on a raster."""
    pts = sim.raster(L, res)
    dim = 2 * n
    X = rng.uniform(0, L, (particles, dim))
    V = rng.uniform(-L / 10, L / 10, (particles, dim))
    fit = lambda x: sim.coverage_fraction(x.reshape(n, 2), pts, r)
    P = X.copy()
    pf = np.array([fit(x) for x in X])
    g = P[np.argmax(pf)].copy()
    gf = pf.max()
    vmax = L / 5
    for _ in range(iters):
        r1, r2 = rng.random((particles, dim)), rng.random((particles, dim))
        V = np.clip(w * V + c1 * r1 * (P - X) + c2 * r2 * (g - X), -vmax, vmax)
        X = np.clip(X + V, 0, L)
        f = np.array([fit(x) for x in X])
        better = f > pf
        P[better], pf[better] = X[better], f[better]
        if pf.max() > gf:
            gf = pf.max()
            g = P[np.argmax(pf)].copy()
    return g.reshape(n, 2)


# ----------------------------------------------------------------------------- shared metaheuristic setup
class CoverageFitness:
    """Binary-disk coverage on a fixed raster; counts every evaluation (equal budget)."""

    def __init__(self, L, r, n, res=80):
        self.L, self.r, self.n = L, r, n
        self.pts = sim.raster(L, res)
        self.evals = 0

    def __call__(self, x):
        self.evals += 1
        return sim.coverage_fraction(np.clip(x, 0, self.L).reshape(self.n, 2), self.pts, self.r)


class _Leaders:
    """Best three solutions found so far (alpha, beta, delta).

    Mirjalili's reference implementation keeps alpha/beta/delta across iterations and
    improves them only when a better agent appears, so the search is elitist and the
    returned alpha is the best solution of the whole run. Recomputing the three leaders
    from the current population alone discards that memory and lets the pack drift away
    from the best layout it has already found.
    """

    def __init__(self, k=3):
        self.k = k
        self.pos = []
        self.val = []

    def update(self, X, fit):
        for i in np.argsort(-np.asarray(fit))[:self.k]:
            v = float(fit[i])
            if len(self.val) < self.k or v > self.val[-1]:
                self.pos.append(np.asarray(X[i]).copy())
                self.val.append(v)
                order = np.argsort(-np.asarray(self.val))[:self.k]
                self.pos = [self.pos[j] for j in order]
                self.val = [self.val[j] for j in order]

    def best(self):
        return self.pos[0]

    def __iter__(self):
        return iter(self.pos)


def gwo(L, r, n, rng, wolves=30, iters=300, res=80):
    """Grey Wolf Optimizer (Mirjalili et al., 2014) with coverage fitness.

    Elitist, as in the reference implementation: alpha, beta and delta are the three
    best solutions found so far, and alpha is returned.
    """
    f = CoverageFitness(L, r, n, res)
    dim = 2 * n
    X = rng.uniform(0, L, (wolves, dim))
    fit = np.array([f(x) for x in X])
    lead = _Leaders()
    lead.update(X, fit)
    for t in range(iters):
        a = 2 - 2 * t / iters
        newX = np.zeros_like(X)
        for leader in lead:
            A = 2 * a * rng.random((wolves, dim)) - a
            C = 2 * rng.random((wolves, dim))
            D = np.abs(C * leader - X)
            newX += leader - A * D
        X = np.clip(newX / 3, 0, L)
        fit = np.array([f(x) for x in X])
        lead.update(X, fit)
    return lead.best().reshape(n, 2), f.evals


def _hammersley(n, rng):
    """2-D Hammersley point set in [0,1)^2 with a random Cranley-Patterson shift."""
    i = np.arange(n)
    def vdc(k):
        v, denom = 0.0, 1.0
        while k:
            denom *= 2
            k, rem = divmod(k, 2)
            v += rem / denom
        return v
    pts = np.column_stack([(i + 0.5) / n, [vdc(k) for k in i]])
    return (pts + rng.random(2)) % 1.0


def vasf_pso(L, r, n, rng, particles=30, iters=300, res=80):
    """Re-implementation of VASF-PSO (Haris and Nam, 2025) from its description:
    Hammersley initialisation, linearly decreasing inertia, time-varying c1/c2, and a
    velocity-scaled adaptive search factor that shrinks steps of particles close to gbest."""
    f = CoverageFitness(L, r, n, res)
    dim = 2 * n
    X = np.array([(_hammersley(n, rng) * L).ravel() for _ in range(particles)])
    V = rng.uniform(-L / 10, L / 10, (particles, dim))
    pf = np.array([f(x) for x in X])
    P = X.copy()
    g, gf = P[np.argmax(pf)].copy(), pf.max()
    vmax = L / 5
    for t in range(iters):
        tau = t / iters
        w = 0.9 - 0.5 * tau
        c1, c2 = 2.5 - 2.0 * tau, 0.5 + 2.0 * tau
        dist = np.linalg.norm(X - g, axis=1)
        sf = np.clip(dist / (dist.max() + 1e-9), 0.2, 1.0)[:, None]   # adaptive search factor
        r1, r2 = rng.random((particles, dim)), rng.random((particles, dim))
        V = np.clip(w * V + c1 * r1 * (P - X) + c2 * r2 * (g - X), -vmax, vmax) * sf
        X = np.clip(X + V, 0, L)
        fx = np.array([f(x) for x in X])
        better = fx > pf
        P[better], pf[better] = X[better], fx[better]
        if pf.max() > gf:
            gf, g = pf.max(), P[np.argmax(pf)].copy()
    return g.reshape(n, 2), f.evals


def dar_ssa(L, r, n, rng, pop=30, iters=300, res=80, st=0.8, sd=0.2, rho=None, eta=0.15):
    """Re-implementation of DAR-SSA (Kheam et al., 2026) from its description.

    Standard sparrow search (producers / scroungers / scouts) run in normalised
    coordinates u = x / L, with (i) a producer share that decays from 80 % to 20 %
    over the run and (ii) a soft-core density repulsion applied to producer layouts,
    F_i = sum_j (s_i - s_j)/|s_i - s_j| * exp(-|s_i - s_j| / rho), step eta * r.
    The multiplicative producer move is applied about the field centre."""
    f = CoverageFitness(L, r, n, res)
    dim = 2 * n
    rho = rho or math.sqrt(3) * r / 2
    U = rng.random((pop, dim))
    fit = np.array([f(u * L) for u in U])
    g_fit, g_best = float(fit.max()), U[np.argmax(fit)].copy()

    def repel(u):
        s = u.reshape(n, 2) * L
        diff = s[:, None, :] - s[None, :, :]
        d = np.linalg.norm(diff, axis=-1) + 1e-6
        np.fill_diagonal(d, np.inf)
        F = np.sum(diff / d[..., None] * np.exp(-d / rho)[..., None], axis=1)
        return np.clip((s + eta * r * F) / L, 0, 1).ravel()

    for t in range(iters):
        order = np.argsort(-fit)
        U, fit = U[order], fit[order]
        best, worst = U[0].copy(), U[-1].copy()
        npd = max(2, int(round(pop * (0.8 - 0.6 * (t / iters) ** 2))))
        R2 = rng.random()
        for i in range(npd):                                   # producers
            if R2 < st:
                alpha = rng.random() + 1e-9
                U[i] = 0.5 + (U[i] - 0.5) * math.exp(-(i + 1) / (alpha * iters))
            else:
                U[i] = U[i] + rng.normal(0, 0.02, dim)
            U[i] = repel(np.clip(U[i], 0, 1))
        xp = U[0].copy()
        for i in range(npd, pop):                              # scroungers
            if i > pop / 2:
                U[i] = rng.normal(0, 1) * np.exp((worst - U[i]) / (i + 1) ** 2) * 0.05 + U[i]
            else:
                A = rng.choice([-1.0, 1.0], dim)
                U[i] = xp + np.abs(U[i] - xp) * A * 0.5
        k = max(1, int(sd * pop))
        for i in rng.choice(pop, k, replace=False):            # scouts
            if fit[i] < fit[0]:
                U[i] = best + rng.normal(0, 1) * np.abs(U[i] - best)
            else:
                U[i] = U[i] + rng.uniform(-1, 1) * np.abs(U[i] - worst) / (abs(fit[i] - fit[-1]) + 1e-3) * 0.01
        U = np.clip(U, 0, 1)
        fit = np.array([f(u * L) for u in U])
        if fit.max() > g_fit:                                  # archive of the best layout found so far
            g_fit, g_best = float(fit.max()), U[np.argmax(fit)].copy()
    return (g_best * L).reshape(n, 2), f.evals


def ga(L, r, n, rng, pop=30, iters=300, res=80, pc=0.9, alpha=0.5, pm=None, sigma=0.05, elite=2, tour=2):
    """Real-coded genetic algorithm with the same budget as the swarm methods.

    Binary tournament selection, BLX-alpha crossover (probability pc), Gaussian mutation of each
    coordinate with probability pm (default 1/dim) and step sigma*L, and (elite + lambda)
    replacement: the `elite` best parents survive and the rest of the next population are the best
    offspring. Every generation evaluates `pop` offspring, so the budget is pop * (iters + 1)
    evaluations, as for PSO and GWO. Returns the best layout found during the run.
    """
    f = CoverageFitness(L, r, n, res)
    dim = 2 * n
    pm = pm if pm is not None else 1.0 / dim
    X = rng.uniform(0, L, (pop, dim))
    fit = np.array([f(x) for x in X])
    g_fit, g_best = float(fit.max()), X[np.argmax(fit)].copy()

    def pick():
        idx = rng.integers(0, pop, tour)
        return X[idx[np.argmax(fit[idx])]]

    for _ in range(iters):
        kids = np.empty_like(X)
        for k in range(0, pop, 2):
            a, b = pick(), pick()
            if rng.random() < pc:
                lo, hi = np.minimum(a, b), np.maximum(a, b)
                span = hi - lo
                c1 = rng.uniform(lo - alpha * span, hi + alpha * span)
                c2 = rng.uniform(lo - alpha * span, hi + alpha * span)
            else:
                c1, c2 = a.copy(), b.copy()
            kids[k] = c1
            if k + 1 < pop:
                kids[k + 1] = c2
        mut = rng.random(kids.shape) < pm
        kids = np.clip(kids + mut * rng.normal(0, sigma * L, kids.shape), 0, L)
        kf = np.array([f(x) for x in kids])
        keep = np.argsort(-fit)[:elite]
        best_kids = np.argsort(-kf)[:pop - elite]
        X = np.vstack([X[keep], kids[best_kids]])
        fit = np.concatenate([fit[keep], kf[best_kids]])
        if fit.max() > g_fit:
            g_fit, g_best = float(fit.max()), X[np.argmax(fit)].copy()
    return g_best.reshape(n, 2), f.evals


def _logistic(shape, rng, mu=4.0, burn=20):
    """Chaotic numbers in (0,1) from the logistic map x <- mu x (1 - x)."""
    x = rng.uniform(0.01, 0.99, shape)
    for _ in range(burn):
        x = mu * x * (1 - x)
    return np.clip(x, 1e-6, 1 - 1e-6)


def icgwo(L, r, n, rng, wolves=30, iters=300, res=80):
    """Re-implementation of an improved chaotic GWO (Shaikh et al., 2025) from its description:
    logistic-map initialisation of the pack and a non-linear (quadratic) decay of a;
    the leader-following update is the standard elitist GWO one."""
    f = CoverageFitness(L, r, n, res)
    dim = 2 * n
    X = _logistic((wolves, dim), rng) * L
    fit = np.array([f(x) for x in X])
    lead = _Leaders()
    lead.update(X, fit)
    for t in range(iters):
        a = 2 * (1 - (t / iters) ** 2)
        newX = np.zeros_like(X)
        for leader in lead:
            A = 2 * a * rng.random((wolves, dim)) - a
            C = 2 * rng.random((wolves, dim))
            newX += leader - A * np.abs(C * leader - X)
        X = np.clip(newX / 3, 0, L)
        fit = np.array([f(x) for x in X])
        lead.update(X, fit)
    return lead.best().reshape(n, 2), f.evals

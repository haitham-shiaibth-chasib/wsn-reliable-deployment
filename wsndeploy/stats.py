"""Small statistics helpers."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def mean_ci(x, level=0.95):
    """Mean, sample std and half-width of the Student-t confidence interval."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    m, s = x.mean(), x.std(ddof=1)
    h = stats.t.ppf(0.5 + level / 2, n - 1) * s / math.sqrt(n)
    return m, s, h


def wilson(k, n, level=0.95):
    """Wilson score interval for a binomial proportion."""
    z = stats.norm.ppf(0.5 + level / 2)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def errors(pred, ref):
    e = np.asarray(pred, dtype=float) - np.asarray(ref, dtype=float)
    return {"MAE": float(np.mean(np.abs(e))),
            "RMSE": float(np.sqrt(np.mean(e ** 2))),
            "MaxAbs": float(np.max(np.abs(e))),
            "Bias": float(np.mean(e))}

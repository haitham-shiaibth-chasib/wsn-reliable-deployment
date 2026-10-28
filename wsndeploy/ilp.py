"""Minimum-node full coverage as an integer linear program (set cover), solved with HiGHS.

Candidate positions lie on a regular grid of spacing h_c over the field; demand points are the
cell centres of a regular raster of spacing h_d. With sensing radius rho, the program

    minimise  sum_j x_j   subject to  sum_{j : |c_j - d_i| <= rho} x_j >= 1  for every demand point i,
              x_j in {0, 1}

gives the fewest nodes that cover every demand point. With rho = r the optimum is a lower bound for
the discretized problem but may leave small gaps between demand points; with
rho = r - h_d / sqrt(2) every point of each demand cell is covered, so the layout is a guaranteed
full cover of the continuous field.
"""
from __future__ import annotations

import math
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

from . import sim


def min_cover_ilp(L, r, h_demand=10.0, h_cand=10.0, guaranteed=False, time_limit=900):
    nd = int(round(L / h_demand))
    demand = sim.raster(L, nd)
    g = np.linspace(0.0, L, int(round(L / h_cand)) + 1)
    cx, cy = np.meshgrid(g, g, indexing="ij")
    cand = np.column_stack([cx.ravel(), cy.ravel()])
    rho = r - h_demand / math.sqrt(2) if guaranteed else r
    nb = cKDTree(cand).query_ball_point(demand, rho * (1 + 1e-12))
    rows = np.repeat(np.arange(len(demand)), [len(v) for v in nb])
    cols = np.concatenate([np.asarray(v, dtype=int) for v in nb])
    A = csr_matrix((np.ones(len(cols)), (rows, cols)), shape=(len(demand), len(cand)))
    t0 = time.time()
    res = milp(c=np.ones(len(cand)), constraints=LinearConstraint(A, lb=1, ub=np.inf),
               integrality=np.ones(len(cand)), bounds=Bounds(0, 1),
               options={"time_limit": time_limit, "mip_rel_gap": 0.0, "disp": False})
    x = np.round(res.x).astype(bool) if res.x is not None else np.zeros(len(cand), bool)
    lb = getattr(res, "mip_dual_bound", float("nan"))
    return dict(layout=cand[x], nodes=int(x.sum()), status=int(res.status), message=str(res.message),
                dual_bound=float(lb) if lb is not None else float("nan"),
                gap=float(getattr(res, "mip_gap", float("nan")) or 0.0), seconds=time.time() - t0,
                rho=rho, n_candidates=len(cand), n_demand=len(demand))

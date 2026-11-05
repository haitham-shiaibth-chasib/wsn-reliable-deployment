"""Run the experiments of the manuscript and write aggregated and raw (per-run) results.

Usage
-----
    python experiments/run_experiments.py --exp all                 # everything (about 2.5 h on 2 cores)
    python experiments/run_experiments.py --exp E6 E7 --workers 2
    python experiments/run_experiments.py --exp all --quick          # 10 % of the runs, smoke test

Outputs
-------
    results/<EXP>_*.csv          aggregated tables used in the manuscript
    results/raw/<EXP>_*.csv      one row per Monte Carlo run (or per optimiser run)
    results/raw/layouts/*.csv    node coordinates of every deterministic / optimised layout
    results/raw/seed_manifest.csv   the seed of every configuration

All parameters and seed rules are read from config/experiments.yaml.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import yaml
from scipy import stats as sst
from scipy.spatial import cKDTree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from wsndeploy import environment as ENV, grid, models, placement, reliability as R, sim  # noqa: E402
from wsndeploy.stats import errors, mean_ci, wilson  # noqa: E402

RES = os.path.join(ROOT, "results")
RAW = os.path.join(RES, "raw")
LAY = os.path.join(RAW, "layouts")
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "experiments.yaml")))
QUICK = False
SEEDS: list[dict] = []


# ----------------------------------------------------------------------------- helpers
def runs_of(n):
    return max(10, n // 10) if QUICK else n


def rng_for(experiment, seed, **config):
    SEEDS.append(dict(experiment=experiment, seed=int(seed), **{k: v for k, v in config.items()}))
    return np.random.default_rng(int(seed))


def write(name, rows, folder=RES):
    os.makedirs(folder, exist_ok=True)
    keys = list(rows[0].keys())
    for r in rows[1:]:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(os.path.join(folder, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {os.path.relpath(os.path.join(folder, name), ROOT)} ({len(rows)} rows)", flush=True)


def write_layout(name, pts):
    os.makedirs(LAY, exist_ok=True)
    np.savetxt(os.path.join(LAY, name), pts, delimiter=",", header="x_m,y_m", comments="", fmt="%.6f")


def nodes_range(spec):
    return list(range(spec["start"], spec["stop"] + 1, spec["step"]))


def coverage_runs(n, L, r, runs, rng, pts):
    return np.array([sim.coverage_fraction(sim.random_deployment(n, L, rng), pts, r) for _ in range(runs)])


# ----------------------------------------------------------------------------- E2
def run_E2():
    c = CFG["E2_mean_models"]
    print("E2: mean models in physical units", flush=True)
    L = c["field"]
    A = L * L
    runs = runs_of(c["runs"])
    pts = sim.raster(L, c["raster"])
    rows, raw = [], []
    for r in c["sensing_radius"]:
        for n in nodes_range(c["nodes"]):
            seed = c["seed_base"] + r * 1000 + n
            x = coverage_runs(n, L, r, runs, rng_for("E2", seed, r=r, N=n), pts)
            raw += [dict(r=r, N=n, seed=seed, run=i, coverage=v) for i, v in enumerate(x)]
            m, s, h = mean_ci(x)
            rows.append(dict(r=r, N=n, density=n * math.pi * r * r / A, mc_mean=m, mc_std=s, ci95=h,
                             linear_no_overlap=min(1.0, n * math.pi * r * r / A),
                             poisson_exp=float(models.poisson_exp(n, r, A)),
                             exact_edge=models.exact_edge(n, r, L)))
    write("E2_physical.csv", rows)
    write("E2_runs.csv", raw, RAW)
    return rows


def summary_errors(e2):
    summ = []
    for name, rows, keys in [("E2 physical 200 m", e2, ("linear_no_overlap", "poisson_exp", "exact_edge"))]:
        ref = [q["mc_mean"] for q in rows]
        for k in keys:
            summ.append(dict(experiment=name, model=k, n_configs=len(rows), **errors([q[k] for q in rows], ref)))
    write("summary_errors.csv", summ)


# ----------------------------------------------------------------------------- S2 (supplementary)
def run_S2():
    c = CFG["S2_connectivity_scan"]
    print("S2: connectivity scan (supplementary)", flush=True)
    L, r = c["field"], c["sensing_radius"]
    runs = runs_of(c["runs"])
    pts = sim.raster(L, c["raster"])
    rows, raw = [], []
    for n in nodes_range(c["nodes"]):
        seed = c["seed_base"] + n
        rng = rng_for("S2", seed, N=n)
        con1 = con2 = joint = 0
        lcc2 = []
        for i in range(runs):
            s = sim.random_deployment(n, L, rng)
            c1, _ = sim.connectivity(s, r)
            c2, share = sim.connectivity(s, 2 * r)
            cov = sim.coverage_fraction(s, pts, r)
            con1 += c1
            con2 += c2
            joint += c2 and cov >= c["coverage_threshold"]
            lcc2.append(share)
            raw.append(dict(N=n, seed=seed, run=i, connected_rc_r=bool(c1), connected_rc_2r=bool(c2),
                            largest_component_share_rc_2r=share, coverage=cov))
        p1, p2, pj = wilson(con1, runs), wilson(con2, runs), wilson(joint, runs)
        rows.append(dict(N=n, p_conn_rc_r=p1[0], lo_rc_r=p1[1], hi_rc_r=p1[2],
                         p_conn_rc_2r=p2[0], lo_rc_2r=p2[1], hi_rc_2r=p2[2],
                         p_conn2r_and_cov90=pj[0], lo_joint=pj[1], hi_joint=pj[2],
                         mean_lcc_share_2r=float(np.mean(lcc2))))
    write("S2_connectivity_scan.csv", rows)
    write("S2_runs.csv", raw, RAW)


# ----------------------------------------------------------------------------- E5
def run_E5():
    c = CFG["E5_lattices"]
    print("E5: lattices", flush=True)
    L = c["field"]
    fine, coarse = sim.raster(L, c["verification_raster"]), sim.raster(L, c["design_raster"])
    rows = []
    for r in c["sensing_radius"]:
        lay = {"diameter": grid.diameter_grid(L, r), "square": grid.square_grid(L, r),
               "triangular": grid.triangular_grid(L, r, coarse, phases=c["triangular_phases"])}
        if sim.coverage_fraction(lay["triangular"], fine, r) < 1.0:
            lay["triangular"] = grid.triangular_grid(L, r, fine, phases=4)
        row = dict(r=r)
        for k, s in lay.items():
            row[f"{k}_nodes"] = len(s)
            row[f"{k}_coverage"] = sim.coverage_fraction(s, fine, r)
            write_layout(f"E5_{k}_r{r:g}.csv", s)
        n_p = int(math.sqrt(len(lay["diameter"])))
        row["diameter_spacing"] = L / (n_p - 1)
        row["square_spacing"] = L / int(math.sqrt(len(lay["square"])))
        row["triangular_spacing"] = math.sqrt(3) * r
        rows.append(row)
    write("E5_grids.csv", rows)


# ----------------------------------------------------------------------------- E6
def run_E6():
    c = CFG["E6_variance_and_sizing"]
    print("E6: variance model and probabilistic sizing", flush=True)
    v = c["variance_scan"]
    L, r = v["field"], v["sensing_radius"]
    runs = runs_of(v["runs"])
    pts = sim.raster(L, v["raster"])
    rows, raw = [], []
    for n in nodes_range(v["nodes"]):
        seed = v["seed_base"] + n
        x = coverage_runs(n, L, r, runs, rng_for("E6a", seed, L=L, r=r, N=n), pts)
        raw += [dict(L=L, r=r, N=n, seed=seed, run=i, coverage=val) for i, val in enumerate(x)]
        rows.append(dict(L=L, r=r, N=n, mc_mean=x.mean(), mc_std=x.std(ddof=1),
                         model_mean=R.mean_cov(n, r, L),
                         model_std_exact=math.sqrt(R.var_cov_exact(n, r, L)),
                         model_std_stationary=math.sqrt(R.var_cov(n, r, L))))
    write("E6a_variance.csv", rows)
    write("E6a_runs.csv", raw, RAW)

    s_ = c["sizing"]
    runs = runs_of(s_["runs"])
    delta = s_["delta"]
    rows, raw = [], []
    for L, r, res in s_["settings"]:
        pts = sim.raster(L, res)
        cache = {}
        for tgt in s_["targets"]:
            rules = {"mean": R.n_mean(tgt, r, L),
                     "normal": R.n_guaranteed(tgt, delta, r, L, dist="normal"),
                     "beta": R.n_guaranteed(tgt, delta, r, L, dist="beta")}
            for rule, n in rules.items():
                if n not in cache:
                    seed = s_["seed_base"] + int(L) + int(r) * 7 + n
                    cache[n] = (seed, coverage_runs(n, L, r, runs, rng_for("E6b", seed, L=L, r=r, N=n), pts))
                    raw += [dict(L=L, r=r, N=n, seed=seed, run=i, coverage=val) for i, val in enumerate(cache[n][1])]
                x = cache[n][1]
                p, lo, hi = wilson(int(np.sum(x >= tgt)), runs)
                rows.append(dict(L=L, r=r, target=tgt, rule=rule, N=n, mc_mean=x.mean(), mc_std=x.std(ddof=1),
                                 p_meet=p, p_lo=lo, p_hi=hi,
                                 model_p_meet=R.p_meet(n, tgt, r, L, dist="normal" if rule == "normal" else "beta")))
            print("   ", L, r, tgt, rules, flush=True)
    write("E6b_sizing.csv", rows)
    write("E6b_runs.csv", raw, RAW)


# ----------------------------------------------------------------------------- E7
def run_E7():
    c = CFG["E7_connectivity"]
    print("E7: connectivity", flush=True)
    m_ = c["model_check"]
    L = m_["field"]
    runs = runs_of(m_["runs"])
    rows, raw = [], []
    for rc in m_["communication_range"]:
        for n in nodes_range(m_["nodes"]):
            seed = m_["seed_base"] + int(rc) * 1000 + n
            rng = rng_for("E7a", seed, Rc=rc, N=n)
            con = iso_free = 0
            for i in range(runs):
                s = sim.random_deployment(n, L, rng)
                ok, _ = sim.connectivity(s, rc)
                d, _ = cKDTree(s).query(s, k=2)
                nf = bool(np.all(d[:, 1] <= rc))
                con += ok
                iso_free += nf
                raw.append(dict(Rc=rc, N=n, seed=seed, run=i, connected=bool(ok), no_isolated_node=nf))
            p1, lo1, hi1 = wilson(con, runs)
            p2, _, _ = wilson(iso_free, runs)
            rows.append(dict(rc=rc, N=n, mc_p_conn=p1, lo=lo1, hi=hi1, mc_p_no_isolated=p2,
                             model_p_no_isolated=R.p_no_isolated(n, rc, L)))
    write("E7a_connectivity.csv", rows)
    write("E7a_runs.csv", raw, RAW)

    j_ = c["joint_rule"]
    L, r, delta = j_["field"], j_["sensing_radius"], j_["delta"]
    runs = runs_of(j_["runs"])
    pts = sim.raster(L, j_["raster"])
    rows, raw = [], []
    for rc in j_["communication_range"]:
        for tgt in j_["targets"]:
            rules = {"coverage_only": R.n_guaranteed(tgt, delta, r, L), "joint": R.n_joint(tgt, delta, r, rc, L)}
            for rule, n in rules.items():
                seed = j_["seed_base"] + int(rc) + int(tgt * 100) + n
                rng = rng_for("E7b", seed, Rc=rc, target=tgt, rule=rule, N=n)
                ok_cov = ok_con = ok_both = 0
                for i in range(runs):
                    s = sim.random_deployment(n, L, rng)
                    cov = sim.coverage_fraction(s, pts, r)
                    b, _ = sim.connectivity(s, rc)
                    a = cov >= tgt
                    ok_cov += a
                    ok_con += b
                    ok_both += a and b
                    raw.append(dict(Rc=rc, target=tgt, rule=rule, N=n, seed=seed, run=i, coverage=cov,
                                    connected=bool(b)))
                p, lo, hi = wilson(ok_both, runs)
                rows.append(dict(rc=rc, target=tgt, rule=rule, N=n, p_cov=ok_cov / runs, p_conn=ok_con / runs,
                                 p_both=p, lo=lo, hi=hi))
            print("   ", rc, tgt, rules, flush=True)
    write("E7b_joint.csv", rows)
    write("E7b_runs.csv", raw, RAW)


# ----------------------------------------------------------------------------- E8
def run_E8():
    c = CFG["E8_drop_error"]
    print("E8: lattices under drop error", flush=True)
    L, r, target = c["field"], c["sensing_radius"], c["target"]
    runs = runs_of(c["runs"])
    n_rand_mean = R.n_mean(target, r, L)
    n_rand_guar = R.n_guaranteed(target, c["delta_random_rule"], r, L)
    base = {"triangular": grid.triangular_grid(L, r, sim.raster(L, c["design_raster"]), phases=4),
            "square": grid.square_grid(L, r)}
    sim_pts = sim.raster(L, c["simulation_raster"])
    rows, raw = [], []
    for ratio in c["sigma_over_r"]:
        sigma = ratio * r
        for kind in c["lattices"]:
            naive = base[kind]
            naive_cov = placement.expected_coverage_perturbed(naive, r, sigma, L, c["expected_raster"])
            lay, kappa = placement.robust_lattice(L, r, sigma, target, kind, design_res=c["design_raster"],
                                                  eval_res=c["expected_raster"])
            write_layout(f"E8_{kind}_sigma{ratio:.1f}r.csv", lay)
            seed = c["seed_base"] + int(ratio * 10) + (kind == "square") * 100
            rng = rng_for("E8", seed, sigma_over_r=ratio, lattice=kind)
            if sigma > 0:
                x = placement.mc_coverage_perturbed(lay, r, sigma, L, runs, rng, c["simulation_raster"])
                m, s, h = mean_ci(x)
            else:
                x = np.full(runs, sim.coverage_fraction(lay, sim_pts, r))
                m, s, h = x[0], 0.0, 0.0
            raw += [dict(sigma_over_r=ratio, lattice=kind, nodes=len(lay), seed=seed, run=i, coverage=v)
                    for i, v in enumerate(x)]
            rows.append(dict(sigma_over_r=ratio, kind=kind, naive_nodes=len(naive), naive_expected=naive_cov,
                             robust_nodes=len(lay), kappa=kappa,
                             robust_expected=placement.expected_coverage_perturbed(lay, r, sigma, L, c["expected_raster"]),
                             mc_mean=m, mc_std=s, ci95=h, mc_min=float(x.min()),
                             random_mean_rule=n_rand_mean, random_guaranteed_rule=n_rand_guar))
            print("   ", ratio, kind, len(lay), kappa, round(float(m), 4), flush=True)
    write("E8_placement_error.csv", rows)
    write("E8_runs.csv", raw, RAW)


# ----------------------------------------------------------------------------- E16
def run_E16():
    """Reliability-sized error-tolerant lattices: P(C >= target) >= 1 - delta instead of E[C] >= target."""
    c = CFG["E16_reliable_lattice"]
    print("E16: reliability-sized lattices under drop error", flush=True)
    L, r, target, delta = c["field"], c["sensing_radius"], c["target"], c["delta"]
    rows, raw = [], []
    for ratio in c["sigma_over_r"]:
        sigma = ratio * r
        for kind in c["lattices"]:
            sq = int(kind == "square")
            s_seed = c["search"]["seed_base"] + 1000 * int(round(10 * ratio)) + 100 * sq
            SEEDS.append(dict(experiment="E16-search", seed=s_seed, sigma_over_r=ratio, lattice=kind))
            lay, kappa, share, share_lo = placement.reliable_lattice(
                L, r, sigma, target, delta, kind, design_res=c["design_raster"], sim_res=c["simulation_raster"],
                runs=runs_of(c["search"]["runs"]), seed=s_seed, kappa_step=c["kappa_step"])
            write_layout(f"E16_{kind}_sigma{ratio:.1f}r.csv", lay)
            v_seed = c["validation"]["seed_base"] + 1000 * int(round(10 * ratio)) + 100 * sq
            rng = rng_for("E16-validation", v_seed, sigma_over_r=ratio, lattice=kind)
            runs = runs_of(c["validation"]["runs"])
            x = placement.mc_coverage_perturbed(lay, r, sigma, L, runs, rng, c["simulation_raster"])
            raw += [dict(sigma_over_r=ratio, lattice=kind, nodes=len(lay), seed=v_seed, run=i, coverage=v)
                    for i, v in enumerate(x)]
            k = int(np.sum(x >= target))
            p, lo, hi = wilson(k, runs)
            rows.append(dict(sigma_over_r=ratio, kind=kind, nodes=len(lay), kappa=kappa, search_share=share,
                             search_lo=share_lo,
                             p_meet=p, lo=lo, hi=hi, mc_mean=float(x.mean()), mc_std=float(x.std(ddof=1)),
                             expected=placement.expected_coverage_perturbed(lay, r, sigma, L, c["expected_raster"])))
            print("   ", ratio, kind, len(lay), kappa, share, round(p, 3), flush=True)
    write("E16_reliable_lattice.csv", rows)
    write("E16_runs.csv", raw, RAW)


# ----------------------------------------------------------------------------- E9
def run_E9():
    c = CFG["E9_extensions"]
    print("E9: extensions", flush=True)
    L, r = c["field"], c["sensing_radius"]
    runs = runs_of(c["runs"])
    pts = sim.raster(L, c["raster"])
    rows, raw = [], []
    kc = c["k_coverage"]
    for k in kc["k"]:
        for n in kc["nodes"]:
            seed = kc["seed_base"] + 10 * k + n
            rng = rng_for("E9-k", seed, k=k, N=n)
            x = np.array([np.mean(sim.coverage_count(sim.random_deployment(n, L, rng), pts, r) >= k)
                          for _ in range(runs)])
            raw += [dict(case="k-coverage", param=f"k={k}", N=n, seed=seed, run=i, value=v) for i, v in enumerate(x)]
            m, s, h = mean_ci(x)
            rows.append(dict(case="k-coverage", param=f"k={k}", N=n, mc_mean=m, ci95=h, model=R.mean_k_cov(n, k, r, L)))
    fc = c["failures"]
    rc = fc["communication_range"]
    for fail in fc["failure_rate"]:
        for n in fc["nodes"]:
            seed = fc["seed_base"] + int(fail * 100) + n
            rng = rng_for("E9-f", seed, f=fail, N=n)
            cov, con = [], 0
            for i in range(runs):
                s = sim.random_deployment(n, L, rng)
                s = s[rng.random(n) >= fail]
                cv = sim.coverage_fraction(s, pts, r) if len(s) else 0.0
                ok = bool(sim.connectivity(s, rc)[0]) if len(s) > 1 else False
                cov.append(cv)
                con += ok
                raw.append(dict(case="failures", param=f"f={fail}", N=n, seed=seed, run=i, value=cv,
                                connected=ok, survivors=len(s)))
            m, s_, h = mean_ci(cov)
            rows.append(dict(case="failures-coverage", param=f"f={fail}", N=n, mc_mean=m, ci95=h,
                             model=R.mean_cov(n, r, L, f=fail)))
            rows.append(dict(case="failures-connectivity", param=f"f={fail}", N=n, mc_mean=con / runs,
                             ci95=float("nan"), model=R.p_no_isolated(n, rc, L, f=fail)))
    ec = c["elfes"]
    re_, lam, beta = ec["uncertainty_margin"], ec["lambda"], ec["beta"]
    for n in ec["nodes"]:
        seed = ec["seed_base"] + n
        rng = rng_for("E9-elfes", seed, N=n)
        vals = []
        for i in range(runs):
            s = sim.random_deployment(n, L, rng)
            nb = cKDTree(s).query_ball_point(pts, r + re_)
            det = np.array([1 - np.prod(1 - R.elfes(np.linalg.norm(s[ix] - p, axis=1), r, re_, lam, beta)) if ix
                            else 0.0 for p, ix in zip(pts, nb)])
            vals.append(det.mean())
            raw.append(dict(case="probabilistic-sensing", param="Elfes", N=n, seed=seed, run=i, value=det.mean()))
        m, s_, h = mean_ci(vals)
        rows.append(dict(case="probabilistic-sensing", param="Elfes", N=n, mc_mean=m, ci95=h,
                         model=R.mean_detection(n, L, r, re_, lam, beta)))
        print("    elfes", n, round(m, 4), flush=True)
    write("E9_extensions.csv", rows)
    write("E9_runs.csv", raw, RAW)


# ----------------------------------------------------------------------------- E10
def _e10_job(args):
    name, L, r, n, seed, cfg = args
    rng = np.random.default_rng(seed)
    b = cfg["budget"]
    t = time.time()
    evals = 0
    if name == "Random":
        s = sim.random_deployment(n, L, rng)
    elif name == "VFA":
        v = cfg["methods"]["VFA"]
        s = placement.virtual_force(L, r, n, rng, iters=v["iterations"], d_th=v["threshold_factor"] * r,
                                    step=v["step_factor"] * r)
    elif name == "PSO":
        p = cfg["methods"]["PSO"]
        s = placement.pso(L, r, n, rng, particles=b["population"], iters=b["iterations"], res=b["fitness_raster"],
                          w=p["w"], c1=p["c1"], c2=p["c2"])
        evals = b["population"] * (b["iterations"] + 1)
    elif name in ("GWO", "ICGWO", "VASF-PSO", "DAR-SSA", "GA"):
        fn = {"GWO": placement.gwo, "ICGWO": placement.icgwo, "VASF-PSO": placement.vasf_pso,
              "DAR-SSA": placement.dar_ssa, "GA": placement.ga}[name]
        kw = {"wolves": b["population"]} if name in ("GWO", "ICGWO") else \
             {"particles": b["population"]} if name == "VASF-PSO" else {"pop": b["population"]}
        s, evals = fn(L, r, n, rng, iters=b["iterations"], res=b["fitness_raster"], **kw)
    else:
        s = placement.lattice_for_n(L, r, n, sim.raster(L, cfg["lattice_design_raster"]))
    return name, n, seed, s, time.time() - t, evals


def run_E10(workers=1):
    c = CFG["E10_baselines"]
    print("E10: baselines", flush=True)
    L, r = c["field"], c["sensing_radius"]
    methods = [m for m in c["methods"] if m != "Proposed lattice"]
    seeds = max(2, c["seeds_per_method"] // 5) if QUICK else c["seeds_per_method"]
    jobs = []
    for n in c["nodes"]:
        for m in methods:
            for k in range(seeds):
                seed = c["seed_base"] + 37 * n + k
                SEEDS.append(dict(experiment="E10", seed=seed, method=m, N=n, k=k))
                jobs.append((m, L, r, n, seed, c))
        jobs.append(("Proposed lattice", L, r, n, 0, c))
    if workers <= 1:                     # no process pool (also works where named pipes are restricted)
        out = [_e10_job(j) for j in jobs]
    else:
        with Pool(workers) as pool:
            out = pool.map(_e10_job, jobs, chunksize=1)
    fine = sim.raster(L, c["evaluation_raster"])
    rb = c["robustness"]
    raw = []
    for name, n, seed, s, dt, evals in out:
        noisy = placement.mc_coverage_perturbed(s, r, rb["sigma_over_r"] * r, L, rb["draws"],
                                                np.random.default_rng(seed + 1), rb["raster"])
        raw.append(dict(method=name, N=n, seed=seed, coverage=sim.coverage_fraction(s, fine, r),
                        connected_rc_sqrt3r=bool(sim.connectivity(s, c["connectivity_range_factor"] * r + 1e-6)[0]),
                        coverage_sigma_0p2r=float(noisy.mean()), seconds=dt, fitness_evals=evals, nodes_used=len(s)))
        write_layout(f"E10_{name.replace(' ', '_')}_N{n}_seed{seed}.csv", s)
    write("E10_runs.csv", raw, RAW)
    summarize_E10(raw)


def summarize_E10(raw=None):
    if raw is None:
        with open(os.path.join(RAW, "E10_runs.csv")) as f:
            raw = [{k: (v if k == "method" else (v == "True") if k == "connected_rc_sqrt3r" else float(v))
                    for k, v in q.items()} for q in csv.DictReader(f)]
    order = ["Random", "VFA", "PSO", "GA", "GWO", "ICGWO", "VASF-PSO", "DAR-SSA", "Proposed lattice"]
    summ = []
    for n in sorted({q["N"] for q in raw}):
        lat = next(q for q in raw if q["method"] == "Proposed lattice" and q["N"] == n)
        for m in order:
            q = [x for x in raw if x["method"] == m and x["N"] == n]
            if not q:
                continue
            c = np.array([x["coverage"] for x in q])
            p = float("nan")
            if m != "Proposed lattice" and np.any(c != lat["coverage"]):
                p = float(sst.wilcoxon(c - lat["coverage"]).pvalue)
            summ.append(dict(method=m, N=int(n), mean=c.mean(), std=c.std(ddof=1) if len(c) > 1 else 0.0,
                             best=c.max(), worst=c.min(), noisy_mean=np.mean([x["coverage_sigma_0p2r"] for x in q]),
                             connected_share=np.mean([x["connected_rc_sqrt3r"] for x in q]),
                             seconds=np.mean([x["seconds"] for x in q]),
                             evals=np.mean([x["fitness_evals"] for x in q]), p_vs_lattice=p))
    write("E10_baselines_summary.csv", summ)


# ----------------------------------------------------------------------------- E24 (revision)
def _e24_job(args):
    name, variant, kw, L, r, n, seed, res = args
    rng = np.random.default_rng(seed)
    fn = {"ICGWO": placement.icgwo, "VASF-PSO": placement.vasf_pso, "DAR-SSA": placement.dar_ssa}[name]
    t = time.time()
    s, evals = fn(L, r, n, rng, res=res, **kw)
    return name, variant, n, seed, s, time.time() - t, evals


def run_E24(workers=1):
    """Sensitivity of the three re-implemented recent baselines to their settings (paired seeds of E10)."""
    c = CFG["E24_baseline_sensitivity"]
    e10 = CFG["E10_baselines"]
    print("E24: baseline sensitivity", flush=True)
    L, r, res = e10["field"], e10["sensing_radius"], e10["budget"]["fitness_raster"]
    seeds = max(2, c["seeds"] // 5) if QUICK else c["seeds"]
    only = [m for m in os.environ.get("E24_METHODS", "").split(",") if m]   # run part of the methods only
    jobs = []
    for n in c["nodes"]:
        for name, variants in c["variants"].items():
            for variant, kw in variants.items():
                for k in range(seeds):
                    seed = e10["seed_base"] + 37 * n + k          # the same seeds as E10 (paired)
                    SEEDS.append(dict(experiment="E24", seed=seed, method=name, variant=variant, N=n, k=k))
                    if not only or name in only:
                        jobs.append((name, variant, dict(kw), L, r, n, seed, res))
    if workers <= 1:
        out = [_e24_job(j) for j in jobs]
    else:
        with Pool(workers) as pool:
            out = pool.map(_e24_job, jobs, chunksize=1)
    fine = sim.raster(L, e10["evaluation_raster"])
    raw = []
    for name, variant, n, seed, s, dt, evals in out:
        raw.append(dict(method=name, variant=variant, N=n, seed=seed, coverage=sim.coverage_fraction(s, fine, r),
                        connected_rc_sqrt3r=bool(sim.connectivity(s, e10["connectivity_range_factor"] * r + 1e-6)[0]),
                        seconds=dt, fitness_evals=evals))
        write_layout(f"E24_{name}_{variant.replace(' ', '_').replace('=', '').replace('(', '').replace(')', '')}"
                     f"_N{n}_seed{seed}.csv", s)
    path = os.path.join(RAW, "E24_runs.csv")
    if only and os.path.exists(path):                  # keep the rows of the methods not run now
        with open(path) as f:
            kept = [{k: (v if k in ("method", "variant") else (v == "True") if k == "connected_rc_sqrt3r"
                     else int(float(v)) if k in ("N", "seed", "fitness_evals") else float(v)) for k, v in q.items()}
                    for q in csv.DictReader(f) if q["method"] not in only]
        raw = kept + raw
    order = list(c["variants"])
    raw.sort(key=lambda q: (order.index(q["method"]), list(c["variants"][q["method"]]).index(q["variant"]),
                            q["N"], q["seed"]))
    write("E24_runs.csv", raw, RAW)
    rows = []
    for (name, variant, n) in dict.fromkeys((q["method"], q["variant"], q["N"]) for q in raw):
        x = np.array([q["coverage"] for q in raw if q["method"] == name and q["variant"] == variant and q["N"] == n])
        rows.append(dict(method=name, variant=variant, N=n, runs=len(x), mean=x.mean(), std=x.std(ddof=1),
                         worst=x.min(), best=x.max(), full_cover_runs=int(np.sum(x >= 1.0)),
                         connected_share=np.mean([q["connected_rc_sqrt3r"] for q in raw if q["method"] == name
                                                  and q["variant"] == variant and q["N"] == n]),
                         evals=np.mean([q["fitness_evals"] for q in raw if q["method"] == name
                                        and q["variant"] == variant and q["N"] == n])))
    write("E24_baseline_sensitivity.csv", rows)


# ----------------------------------------------------------------------------- E11
def _e11_setup(c, sc):
    obs = [tuple(o) for o in c["urban_obstacles"]] if sc["obstacles"] else []
    fld = ENV.Field(c["field"], obs)
    radio = ENV.Radio(c["median_range"], c["path_loss_exponent"], sc["shadowing_db"],
                      c["penetration_loss_db"] if obs else 0.0)
    return fld, radio


def run_E11():
    c = CFG["E11_environment"]
    print("E11: obstacles and shadowing", flush=True)
    r, tgt, delta = c["sensing_radius"], c["target"], c["delta"]
    g = c["model_grids"]
    n_open = R.n_joint(tgt, delta, r, c["median_range"], c["field"])     # rule of Sec. 4 for an open field
    mrows, mraw, rrows, rraw, srows = [], [], [], [], []
    for idx, sc in enumerate(c["scenarios"]):
        fld, radio = _e11_setup(c, sc)
        model = ENV.EnvironmentModel(fld, r, radio, coarse=g["variance"], fine=g["node_cells"], mean_grid=g["mean"],
                                     conn_coarse=g["link_positions"], conn_fine=g["link_cells"])
        mc = c["model_check"]
        pts = fld.free_raster(mc["raster"])
        runs = runs_of(mc["runs"])
        for n in mc["nodes"]:
            seed = mc["seed_base"] + 1000 * idx + n
            rng = rng_for("E11a", seed, scenario=sc["name"], N=n)
            cov, con, iso = [], 0, 0
            for i in range(runs):
                s_ = fld.sample(n, rng)
                cv = ENV.coverage_los(fld, s_, pts, r)
                ok, nf = ENV.connectivity_shadow(fld, radio, s_, rng)
                cov.append(cv)
                con += ok
                iso += nf
                mraw.append(dict(scenario=sc["name"], N=n, seed=seed, run=i, coverage=cv, connected=ok,
                                 no_isolated_node=nf))
            cov = np.array(cov)
            p, lo, hi = wilson(con, runs)
            mrows.append(dict(scenario=sc["name"], N=n, mc_cov_mean=cov.mean(), mc_cov_std=cov.std(ddof=1),
                              model_cov_mean=model.mean(n), model_cov_std=math.sqrt(model.var(n)),
                              mc_p_no_isolated=iso / runs, model_p_no_isolated=model.p_no_isolated(n),
                              mc_p_conn=p, lo=lo, hi=hi))
        n_aware = model.n_joint(tgt, delta)
        sz = c["simulated_connectivity"]
        sz_seed = sz["seed_base"] + 1000 * idx
        SEEDS.append(dict(experiment="E11c", seed=sz_seed, scenario=sc["name"], N="seed_base+N"))
        n_sim, n_cov_a, n_con_sim, p_con_sim, trace = model.n_joint_mc(tgt, delta, runs=runs_of(sz["runs"]),
                                                                        seed_base=sz_seed)
        for m_, pv in sorted(trace.items()):
            srows.append(dict(scenario=sc["name"], N=m_, seed=sz_seed + m_, runs=runs_of(sz["runs"]),
                              p_connected=pv, model_p_no_isolated=model.p_no_isolated(m_)))
        rc_ = c["rule_check"]
        pts = fld.free_raster(rc_["raster"])
        runs = runs_of(rc_["runs"])
        offs = {"open_field_rule": 0, "simulated_connectivity_rule": 250, "environment_aware_rule": 500}
        for rule, n in (("open_field_rule", n_open), ("environment_aware_rule", n_aware),
                        ("simulated_connectivity_rule", n_sim)):
            seed = rc_["seed_base"] + 1000 * idx + offs[rule] + n
            rng = rng_for("E11b", seed, scenario=sc["name"], rule=rule, N=n)
            ok_cov = ok_con = ok_both = 0
            for i in range(runs):
                s_ = fld.sample(n, rng)
                cv = ENV.coverage_los(fld, s_, pts, r)
                ok, _ = ENV.connectivity_shadow(fld, radio, s_, rng)
                a_ = cv >= tgt
                ok_cov += a_
                ok_con += ok
                ok_both += a_ and ok
                rraw.append(dict(scenario=sc["name"], rule=rule, N=n, seed=seed, run=i, coverage=cv, connected=ok))
            p, lo, hi = wilson(ok_both, runs)
            rrows.append(dict(scenario=sc["name"], rule=rule, N=n, free_area=fld.free_area, p_cov=ok_cov / runs,
                              p_conn=ok_con / runs, p_both=p, lo=lo, hi=hi,
                              model_p_cov=model.p_meet(n, tgt), model_p_no_isolated=model.p_no_isolated(n)))
        print(f"    {sc['name']}: open-field rule {n_open}, aware rule {n_aware}, simulated-connectivity rule "
              f"{n_sim} (N_cov {n_cov_a}, N_conn {n_con_sim}, P_conn {p_con_sim:.4f})", flush=True)
    write("E11_model_check.csv", mrows)
    write("E11_rules.csv", rrows)
    write("E11_conn_sizing.csv", srows)
    write("E11a_runs.csv", mraw, RAW)
    write("E11b_runs.csv", rraw, RAW)


# ----------------------------------------------------------------------------- main

# ----------------------------------------------------------------------------- E12-E15 (version 1.1)
def run_E12():
    """Sensitivity of the Beta rule to the risk level delta."""
    c = CFG["E12_risk_sensitivity"]
    print("E12: sensitivity to the risk level", flush=True)
    L, r = c["field"], c["sensing_radius"]
    runs = runs_of(c["runs"])
    pts = sim.raster(L, c["raster"])
    rows, raw = [], []
    for delta in c["delta"]:
        for tgt in c["targets"]:
            n = R.n_guaranteed(tgt, delta, r, L, dist="beta")
            seed = c["seed_base"] + int(1000 * delta) * 1000 + n
            x = coverage_runs(n, L, r, runs, rng_for("E12", seed, delta=delta, target=tgt, N=n), pts)
            raw += [dict(delta=delta, target=tgt, N=n, seed=seed, run=i, coverage=v) for i, v in enumerate(x)]
            k = int(np.sum(x >= tgt))
            p, lo, hi = wilson(k, runs)
            rows.append(dict(delta=delta, target=tgt, N=n, N_mean_rule=R.n_mean(tgt, r, L), runs=runs, met=k,
                             p_meet=p, p_lo=lo, p_hi=hi, nominal=1 - delta,
                             model_p_meet=R.p_meet(n, tgt, r, L)))
            print("   ", delta, tgt, n, round(p, 4), flush=True)
    write("E12_risk_sensitivity.csv", rows)
    write("E12_runs.csv", raw, RAW)


def run_E13():
    """Minimum-node full cover by integer linear programming, against the lattices."""
    from wsndeploy import ilp
    c = CFG["E13_ilp"]
    print("E13: ILP minimum cover", flush=True)
    L, r = c["field"], c["sensing_radius"]
    fine = sim.raster(L, c["evaluation_raster"])
    rows = []
    for guaranteed in (False, True):
        out = ilp.min_cover_ilp(L, r, c["demand_spacing"], c["candidate_spacing"], guaranteed, c["time_limit_s"])
        name = "ILP, guaranteed" if guaranteed else "ILP, demand points"
        write_layout(f"E13_{name.replace(', ', '_').replace(' ', '_')}.csv", out["layout"])
        rows.append(dict(method=name, nodes=out["nodes"], dual_bound=out["dual_bound"], gap=out["gap"],
                         coverage=sim.coverage_fraction(out["layout"], fine, r), status=out["message"],
                         seconds=out["seconds"], rho=out["rho"], candidates=out["n_candidates"],
                         demand_points=out["n_demand"]))
        print("   ", rows[-1], flush=True)
    tri = grid.triangular_grid(L, r, sim.raster(L, CFG["E10_baselines"]["lattice_design_raster"]))
    sq = grid.square_grid(L, r)
    for name, lay in (("Triangular lattice", tri), ("Square lattice", sq)):
        rows.append(dict(method=name, nodes=len(lay), coverage=sim.coverage_fraction(lay, fine, r)))
    kersh = L * L / (1.5 * math.sqrt(3) * r * r)
    rows.append(dict(method="Kershner density bound (interior)", nodes=math.ceil(kersh)))
    write("E13_ilp.csv", rows)


def run_E21():
    """Integer program at several candidate/demand resolutions, with a continuous lower bound."""
    from wsndeploy import ilp
    c = CFG["E21_ilp_resolution"]
    print("E21: ILP at several resolutions", flush=True)
    L, r = c["field"], c["sensing_radius"]
    fine = sim.raster(L, c["evaluation_raster"])
    rows = []
    for h in c["spacings"]:
        for guaranteed in (False, True):
            out = ilp.min_cover_ilp(L, r, h, h, guaranteed, c["time_limit_s"])
            name = "guaranteed" if guaranteed else "demand points"
            write_layout(f"E21_ILP_{name.replace(' ', '_')}_h{h:g}.csv", out["layout"])
            rows.append(dict(spacing=h, variant=name, nodes=out["nodes"], dual_bound=out["dual_bound"],
                             gap=out["gap"], coverage=sim.coverage_fraction(out["layout"], fine, r),
                             status=out["message"], seconds=out["seconds"], rho=out["rho"],
                             candidates=out["n_candidates"], demand_points=out["n_demand"]))
            print("   ", {k: rows[-1][k] for k in ("spacing", "variant", "nodes", "dual_bound", "coverage")}, flush=True)
    # Fejes Toth: n congruent disks covering a convex polygon with at most six sides cover at most
    # n (3 sqrt(3) / 2) r^2 of its area, so n >= A / (1.5 sqrt(3) r^2) for the square field.
    rows.append(dict(spacing=0, variant="continuous lower bound (Fejes Toth)",
                     nodes=math.ceil(L * L / (1.5 * math.sqrt(3) * r * r))))
    write("E21_ilp_resolution.csv", rows)


def run_E14():
    """Randomized sleep scheduling: lifetime gained from extra nodes at a stated reliability."""
    c = CFG["E14_sleep_scheduling"]
    print("E14: sleep scheduling", flush=True)
    L, r, rc, tgt, delta = c["field"], c["sensing_radius"], c["communication_range"], c["target"], c["delta"]
    runs = runs_of(c["runs"])
    pts = sim.raster(L, c["raster"])
    n0 = R.n_joint(tgt, delta, r, rc, L)
    e = c["energy"]
    e_round = e["bits"] * (2 * e["e_elec"] + e["eps_amp"] * rc ** 2)     # one transmission and one reception at Rc
    rows, raw = [], []
    for mult in c["multipliers"]:
        n = int(math.ceil(mult * n0))
        q = R.min_awake_share(n, tgt, delta, r, rc, L, c["q_step"])
        seed = c["seed_base"] + n
        rng = rng_for("E14", seed, N=n, q=q)
        both = 0
        for i in range(runs):
            s = sim.random_deployment(n, L, rng)
            awake = s[rng.random(n) < q]
            cov = sim.coverage_fraction(awake, pts, r) if len(awake) else 0.0
            con = bool(sim.connectivity(awake, rc)[0]) if len(awake) > 1 else False
            ok = cov >= tgt and con
            both += ok
            raw.append(dict(N=n, q=q, seed=seed, run=i, coverage=cov, connected=con, both=ok))
        p, lo, hi = wilson(both, runs)
        rows.append(dict(multiplier=mult, N=n, N_joint=n0, q=q, awake_mean=q * n, lifetime_gain=1 / q,
                         rounds_always_on=e["initial_energy_J"] / e_round,
                         rounds=e["initial_energy_J"] / (q * e_round), runs=runs, met=both,
                         p_both=p, lo=lo, hi=hi))
        print("   ", rows[-1], flush=True)
    write("E14_sleep_scheduling.csv", rows)
    write("E14_runs.csv", raw, RAW)


def run_E15():
    """Heterogeneous sensing radii: mixture rule against rules that use one radius."""
    c = CFG["E15_heterogeneous"]
    print("E15: heterogeneous radii", flush=True)
    L, delta = c["field"], c["delta"]
    radii, w = c["radii"], c["weights"]
    r_mean = float(np.dot(radii, w))
    r_rms = float(math.sqrt(np.dot(np.square(radii), w)))
    runs = runs_of(c["runs"])
    pts = sim.raster(L, c["raster"])
    rows, raw = [], []
    for tgt in c["targets"]:
        rules = {"mean radius": R.n_guaranteed(tgt, delta, r_mean, L),
                 "rms radius": R.n_guaranteed(tgt, delta, r_rms, L),
                 "mixture": R.n_guaranteed_mix(tgt, delta, radii, w, L)}
        for rule, n in rules.items():
            seed = c["seed_base"] + int(100 * tgt) * 1000 + n
            rng = rng_for("E15", seed, target=tgt, N=n)
            x = np.empty(runs)
            for i in range(runs):
                s = sim.random_deployment(n, L, rng)
                rad = rng.choice(radii, size=n, p=w)
                x[i] = sim.coverage_fraction_hetero(s, rad, pts)
            raw += [dict(target=tgt, rule=rule, N=n, seed=seed, run=i, coverage=v) for i, v in enumerate(x)]
            k = int(np.sum(x >= tgt))
            p, lo, hi = wilson(k, runs)
            rows.append(dict(target=tgt, rule=rule, N=n, runs=runs, met=k, p_meet=p, p_lo=lo, p_hi=hi,
                             mc_mean=x.mean(), mc_std=x.std(ddof=1),
                             model_mean=R.mean_cov_mix(n, radii, w, L),
                             model_std=math.sqrt(R.var_cov_exact_mix(n, radii, w, L))))
        print("   ", tgt, rules, flush=True)
    write("E15_heterogeneous.csv", rows)
    write("E15_runs.csv", raw, RAW)


# ----------------------------------------------------------------------------- revision (version 1.3)
from wsndeploy import certify as CERT, domain as DOM  # noqa: E402


def _read_csv(name, folder=RES):
    with open(os.path.join(folder, name)) as f:
        out = []
        for q in csv.DictReader(f):
            d = {}
            for k, v in q.items():
                try:
                    d[k] = float(v)
                except (TypeError, ValueError):
                    d[k] = v
            out.append(d)
        return out


def _certify_counts(n0, step, sample_fn, seed_of, cfg, delta):
    """Certify n0, n0 + step, n0 + 2 step, ... with fresh drops per attempt (Bonferroni over attempts).
    sample_fn(n, runs, rng) -> (list of success booleans, list of per-drop records)."""
    raw_all = []

    def sample(n, runs, seed):
        ok, recs = sample_fn(n, runs, np.random.default_rng(seed))
        raw_all.extend(dict(N=n, seed=seed, run=i, **rec) for i, rec in enumerate(recs))
        return ok

    designs = (n0 + j * step for j in range(cfg["max_attempts"]))
    n_cert, log = CERT.certify_sequence(designs, sample, runs_of(cfg["runs"]), delta, cfg["alpha"],
                                        cfg["max_attempts"], seed_of)
    return n_cert, log, raw_all


def run_E17():
    """Independent certification of the random-drop designs (coverage, joint, environment)."""
    c = CFG["E17_certification"]
    print("E17: certification of the analytical designs", flush=True)
    s6 = CFG["E6_variance_and_sizing"]["sizing"]
    delta = s6["delta"]
    rows, raw = [], []
    # -- coverage only, the sixteen settings of E6b
    for si, (L, r, res) in enumerate(s6["settings"]):
        pts = sim.raster(L, res)
        for ti, tgt in enumerate(s6["targets"]):
            n0 = R.n_guaranteed(tgt, delta, r, L, dist="beta")
            step = max(1, math.ceil(c["step_share"] * n0))

            def fn(n, runs, rng, L=L, r=r, tgt=tgt, pts=pts):
                x = [sim.coverage_fraction(sim.random_deployment(n, L, rng), pts, r) for _ in range(runs)]
                return [v >= tgt for v in x], [dict(coverage=v) for v in x]

            base = c["coverage"]["seed_base"] + 1000 * si + 100 * ti
            for j in range(c["max_attempts"]):
                SEEDS.append(dict(experiment="E17-coverage", seed=base + j, L=L, r=r, target=tgt, attempt=j + 1))
            n_c, log, rr = _certify_counts(n0, step, fn, lambda j, b=base: b + j, c, delta)
            raw += [dict(part="coverage", L=L, r=r, target=tgt, **q) for q in rr]
            for d, rec in log:
                rows.append(dict(part="coverage", setting=f"L={L:g}, r={r:g}", L=L, r=r, Rc="", scenario="",
                                 target=tgt, N_rule=n0, N=d, N_certified=n_c if n_c is not None else "",
                                 **rec))
            print(f"    coverage L={L:g} r={r:g} Ct={tgt}: rule {n0}, certified {n_c} "
                  f"({[(d, round(q['share'], 4), round(q['lower_bound'], 4)) for d, q in log]})", flush=True)
    # -- joint coverage and connectivity, the designs of E7b
    j7 = CFG["E7_connectivity"]["joint_rule"]
    L, r, dl = j7["field"], j7["sensing_radius"], j7["delta"]
    pts = sim.raster(L, j7["raster"])
    for rc in j7["communication_range"]:
        for ti, tgt in enumerate(j7["targets"]):
            n0 = R.n_joint(tgt, dl, r, rc, L)
            step = max(1, math.ceil(c["step_share"] * n0))

            def fn(n, runs, rng, rc=rc, tgt=tgt):
                ok, recs = [], []
                for _ in range(runs):
                    s = sim.random_deployment(n, L, rng)
                    cv = sim.coverage_fraction(s, pts, r)
                    con = bool(sim.connectivity(s, rc)[0])
                    ok.append(cv >= tgt and con)
                    recs.append(dict(coverage=cv, connected=con))
                return ok, recs

            base = c["joint"]["seed_base"] + 1000 * int(rc) + 100 * ti
            for j in range(c["max_attempts"]):
                SEEDS.append(dict(experiment="E17-joint", seed=base + j, Rc=rc, target=tgt, attempt=j + 1))
            n_c, log, rr = _certify_counts(n0, step, fn, lambda j, b=base: b + j, c, dl)
            raw += [dict(part="joint", L=L, r=r, Rc=rc, target=tgt, **q) for q in rr]
            for d, rec in log:
                rows.append(dict(part="joint", setting=f"Rc={rc:g}", L=L, r=r, Rc=rc, scenario="", target=tgt,
                                 N_rule=n0, N=d, N_certified=n_c if n_c is not None else "", **rec))
            print(f"    joint Rc={rc:g} Ct={tgt}: rule {n0}, certified {n_c}", flush=True)
    # -- obstacles and shadowing: the simulated-connectivity rule of E11
    e11 = CFG["E11_environment"]
    r, tgt, dl = e11["sensing_radius"], e11["target"], e11["delta"]
    sim_rule = {q["scenario"]: int(q["N"]) for q in _read_csv("E11_rules.csv")
                if q["rule"] == "simulated_connectivity_rule"}
    for idx, sc in enumerate(e11["scenarios"]):
        fld, radio = _e11_setup(e11, sc)
        pts = fld.free_raster(e11["rule_check"]["raster"])
        n0 = sim_rule[sc["name"]]
        step = max(1, math.ceil(c["step_share"] * n0))

        def fn(n, runs, rng, fld=fld, radio=radio, pts=pts):
            ok, recs = [], []
            for _ in range(runs):
                s_ = fld.sample(n, rng)
                cv = ENV.coverage_los(fld, s_, pts, r)
                con, _ = ENV.connectivity_shadow(fld, radio, s_, rng)
                ok.append(cv >= tgt and con)
                recs.append(dict(coverage=cv, connected=bool(con)))
            return ok, recs

        base = c["environment"]["seed_base"] + 1000 * idx
        for j in range(c["max_attempts"]):
            SEEDS.append(dict(experiment="E17-environment", seed=base + j, scenario=sc["name"], attempt=j + 1))
        n_c, log, rr = _certify_counts(n0, step, fn, lambda j, b=base: b + j, c, dl)
        raw += [dict(part="environment", scenario=sc["name"], target=tgt, **q) for q in rr]
        for d, rec in log:
            rows.append(dict(part="environment", setting=sc["name"], L=e11["field"], r=r, Rc=e11["median_range"],
                             scenario=sc["name"], target=tgt, N_rule=n0, N=d,
                             N_certified=n_c if n_c is not None else "", **rec))
        print(f"    environment {sc['name']}: rule {n0}, certified {n_c}", flush=True)
    write("E17_certification.csv", rows)
    write("E17_runs.csv", raw, RAW)


def run_E18():
    """Error-tolerant lattices: design on one sample, certification on independent drops."""
    c = CFG["E18_certified_lattice"]
    c16 = CFG["E16_reliable_lattice"]
    cert = CFG["E17_certification"]
    print("E18: certified error-tolerant lattices", flush=True)
    L, r, target, delta = c["field"], c["sensing_radius"], c["target"], c["delta"]
    pts_d = sim.raster(L, c["design_raster"])
    pts_s = sim.raster(L, c["simulation_raster"])
    e16 = {(round(q["sigma_over_r"], 2), q["kind"]): q for q in _read_csv("E16_reliable_lattice.csv")}
    rows, raw = [], []
    for ratio in c["sigma_over_r"]:
        sigma = ratio * r
        for kind in c["lattices"]:
            sq = int(kind == "square")
            build = (lambda rr: grid.triangular_grid(L, rr, pts_d, phases=4)) if kind == "triangular" \
                else (lambda rr: grid.square_grid(L, rr))
            key = (round(ratio, 2), kind)
            if key in e16:                                     # design of E16 (search sample of 500 drops)
                kappa0, design_share, design_lo = e16[key]["kappa"], e16[key]["search_share"], e16[key]["search_lo"]
            else:
                s_seed = c["search"]["seed_base"] + 1000 * int(round(10 * ratio)) + 100 * sq
                SEEDS.append(dict(experiment="E18-search", seed=s_seed, sigma_over_r=ratio, lattice=kind))
                out = placement.reliable_lattice(L, r, sigma, target, delta, kind, design_res=c["design_raster"],
                                                 sim_res=c["simulation_raster"], runs=runs_of(c["search"]["runs"]),
                                                 seed=s_seed, kappa_step=c["kappa_step"], kappa_min=c["kappa_min"])
                if out is None:
                    print("    no design", ratio, kind, flush=True)
                    continue
                _, kappa0, design_share, design_lo = out
            kappas = [round(kappa0 - j * c["kappa_step"], 2) for j in range(cert["max_attempts"])]
            kappas = [k for k in kappas if k >= c["kappa_min"] - 1e-9]
            layouts = {}

            def sample(kap, runs, seed):
                lay = layouts.setdefault(kap, build(kap * r))
                rng = np.random.default_rng(seed)
                ok = []
                for i in range(runs):
                    s = lay + rng.normal(0, sigma, lay.shape)
                    cv = sim.coverage_fraction(s, pts_s, r)
                    cons = [bool(sim.connectivity(s, f * r)[0]) for f in c["connectivity_ranges_over_r"]]
                    ok.append(cv >= target)
                    raw.append(dict(sigma_over_r=ratio, lattice=kind, kappa=kap, nodes=len(lay), seed=seed, run=i,
                                    coverage=cv, **{f"connected_{f:.3f}r": v for f, v in
                                                    zip(c["connectivity_ranges_over_r"], cons)}))
                return ok

            base = c["certification"]["seed_base"] + 1000 * int(round(100 * ratio)) + 100 * sq
            for j in range(len(kappas)):
                SEEDS.append(dict(experiment="E18-certification", seed=base + j, sigma_over_r=ratio, lattice=kind,
                                  attempt=j + 1))
            k_c, log = CERT.certify_sequence(kappas, sample, runs_of(c["certification"]["runs"]), delta,
                                             cert["alpha"], cert["max_attempts"], lambda j: base + j)
            for kap, rec in log:
                lay = layouts[kap]
                sel = [q for q in raw if q["sigma_over_r"] == ratio and q["lattice"] == kind and q["kappa"] == kap]
                conn = {f"connected_share_{f:.3f}r": float(np.mean([q[f"connected_{f:.3f}r"] for q in sel]))
                        for f in c["connectivity_ranges_over_r"]}
                rows.append(dict(sigma_over_r=ratio, kind=kind, kappa_design=kappa0, design_share=design_share,
                                 design_lower=design_lo, kappa=kap, nodes=len(lay),
                                 kappa_certified=k_c if k_c is not None else "",
                                 nodes_certified=len(layouts[k_c]) if k_c is not None else "",
                                 expected=placement.expected_coverage_perturbed(lay, r, sigma, L, c16["expected_raster"]),
                                 mean_coverage=float(np.mean([q["coverage"] for q in sel])), **rec, **conn))
            if k_c is not None:
                write_layout(f"E18_{kind}_sigma{ratio:.2f}r.csv", layouts[k_c])
            print(f"    sigma={ratio}r {kind}: design kappa {kappa0} -> certified {k_c} "
                  f"({[(len(layouts[k]), round(q['share'], 4), round(q['lower_bound'], 4)) for k, q in log]})",
                  flush=True)
    write("E18_certified_lattice.csv", rows)
    write("E18_runs.csv", raw, RAW)


def run_E19():
    """Stress study of the Beta rule with calibration curves and certification."""
    c = CFG["E19_stress"]
    cert = CFG["E17_certification"]
    print("E19: stress study", flush=True)
    delta = c["delta"]
    rows, crow, raw = [], [], []
    part = os.environ.get("E19_PART", "")                 # optional split into parallel parts (merged by E19MERGE)
    only = {int(x) for x in os.environ.get("E19_SETTINGS", "").split(",") if x.strip()}
    do_corr = os.environ.get("E19_CORR", "1") == "1"
    for si, (name, Lx, Ly, cuts, r, tgt) in enumerate(c["settings"]):
        if only and si not in only:
            continue
        dom = DOM.Domain(Lx, Ly, [tuple(q) for q in cuts], name)
        squared = Lx == Ly and not cuts
        model = None if squared else DOM.DomainModel(dom, r, h_node=c["node_cell"])
        p_fn = (lambda n: R.p_meet(n, tgt, r, Lx)) if squared else (lambda n: model.p_meet(n, tgt))
        mean_fn = (lambda n: R.mean_cov(n, r, Lx)) if squared else model.mean
        n0 = R.n_guaranteed(tgt, delta, r, Lx) if squared else model.n_guaranteed(tgt, delta)
        pts = dom.raster(c["node_cell"])
        runs = runs_of(c["runs"])
        for fac in c["calibration_factors"]:
            n = max(2, int(round(fac * n0)))
            seed = c["seed_base"] + 1000 * si + n
            rng = rng_for("E19-calibration", seed, setting=si, N=n)
            x = np.array([sim.coverage_fraction(dom.sample(n, rng), pts, r) for _ in range(runs)])
            raw += [dict(part="calibration", setting=si, name=name, target=tgt, N=n, seed=seed, run=i, coverage=v)
                    for i, v in enumerate(x)]
            k = int(np.sum(x >= tgt))
            crow.append(dict(setting=si, name=name, Lx=Lx, Ly=Ly, cutouts=str(cuts), r=r, target=tgt, N_rule=n0,
                             factor=fac, N=n, predicted=p_fn(n), observed=k / runs, runs=runs,
                             lower=CERT.cp_lower(k, runs, 0.025), upper=CERT.cp_upper(k, runs, 0.025),
                             model_mean=mean_fn(n), mc_mean=float(x.mean()), mc_std=float(x.std(ddof=1)),
                             q01=float(np.quantile(x, 0.01)), q05=float(np.quantile(x, 0.05))))
        step = max(1, math.ceil(cert["step_share"] * n0))

        def fn(n, runs_, rng, dom=dom, pts=pts, r=r, tgt=tgt):
            x = [sim.coverage_fraction(dom.sample(n, rng), pts, r) for _ in range(runs_)]
            return [v >= tgt for v in x], [dict(coverage=v) for v in x]

        base = c["certification_seed_base"] + 100 * si
        for j in range(cert["max_attempts"]):
            SEEDS.append(dict(experiment="E19-certification", seed=base + j, setting=si, attempt=j + 1))
        n_c, log, rr = _certify_counts(n0, step, fn, lambda j, b=base: b + j, cert, delta)
        raw += [dict(part="certification", setting=si, name=name, target=tgt, **q) for q in rr]
        at_rule = next(q for q in crow if q["setting"] == si and q["N"] == max(2, int(round(n0))))
        rows.append(dict(setting=si, name=name, Lx=Lx, Ly=Ly, area=dom.area, r=r, target=tgt, N_rule=n0,
                         predicted_at_rule=at_rule["predicted"], observed_at_rule=at_rule["observed"],
                         lower_at_rule=at_rule["lower"], q01_at_rule=at_rule["q01"],
                         N_certified=n_c if n_c is not None else "", attempts=len(log),
                         certified_share=log[-1][1]["share"], certified_lower=log[-1][1]["lower_bound"]))
        print(f"    {name} Ct={tgt}: rule {n0} (pred {at_rule['predicted']:.3f}, obs {at_rule['observed']:.3f}), "
              f"certified {n_c}", flush=True)
    # -- correlated link shadowing
    cs = c["correlated_shadowing"]
    srows = []
    if not do_corr:
        cs = dict(cs, rho=[])
    fld = ENV.Field(cs["field"], [])
    radio = ENV.Radio(cs["median_range"], cs["path_loss_exponent"], cs["shadowing_db"], 0.0)
    e11g = CFG["E11_environment"]["model_grids"]
    if cs["rho"]:
        model = ENV.EnvironmentModel(fld, cs["sensing_radius"], radio, coarse=e11g["variance"],
                                     fine=e11g["node_cells"], mean_grid=e11g["mean"],
                                     conn_coarse=e11g["link_positions"], conn_fine=e11g["link_cells"])
        n0 = model.n_joint(cs["target"], delta)
        pts = sim.raster(cs["field"], cs["raster"])
    for ri, rho in enumerate(cs["rho"]):
        step = max(1, math.ceil(cert["step_share"] * n0))

        def fn(n, runs_, rng, rho=rho):
            ok, recs = [], []
            for _ in range(runs_):
                s_ = fld.sample(n, rng)
                cv = sim.coverage_fraction(s_, pts, cs["sensing_radius"])
                con, _ = ENV.connectivity_shadow_corr(fld, radio, s_, rng, rho)
                ok.append(cv >= cs["target"] and con)
                recs.append(dict(coverage=cv, connected=bool(con)))
            return ok, recs

        # (a) the independent-shadowing rule evaluated on its own drops (descriptive, not a certificate)
        seed_a = cs["seed_base"] + 100 * ri + 90
        ok, rec_a = fn(n0, runs_of(cs["rule_runs"]), rng_for("E19-correlated-rule", seed_a, rho=rho, N=n0))
        raw += [dict(part="correlated-rule", rho=rho, target=cs["target"], N=n0, seed=seed_a, run=i, **q)
                for i, q in enumerate(rec_a)]
        k_a, n_a = int(sum(ok)), len(ok)
        # (b) design by simulation on a separate design sample: N grows in steps of 5 % of the rule
        n_d, dsel = None, []
        for j in range(cs["design_max_steps"] + 1):
            n = int(math.ceil(n0 * (1 + cs["design_step_share"] * j)))
            seed_d = cs["seed_base"] + 100 * ri + 50 + j
            okd, recd = fn(n, runs_of(cs["design_runs"]), rng_for("E19-correlated-design", seed_d, rho=rho, N=n))
            raw += [dict(part="correlated-design", rho=rho, target=cs["target"], N=n, seed=seed_d, run=i, **q)
                    for i, q in enumerate(recd)]
            dsel.append((n, float(np.mean(okd))))
            if np.mean(okd) >= cs["design_share"]:
                n_d = n
                break
        n_c, log = None, []
        if n_d is not None:
            base = cs["seed_base"] + 100 * ri
            for j in range(cert["max_attempts"]):
                SEEDS.append(dict(experiment="E19-correlated-certification", seed=base + j, rho=rho, attempt=j + 1))
            n_c, log, rr = _certify_counts(n_d, max(1, math.ceil(cert["step_share"] * n_d)), fn,
                                           lambda j, b=base: b + j, cert, delta)
            raw += [dict(part="correlated-certification", rho=rho, target=cs["target"], **q) for q in rr]
        else:
            rr = []
        for d_, rec in log or [(None, {})]:
            sel = [q for q in rr if q["N"] == d_]
            srows.append(dict(rho=rho, link_correlation=rho / 2, N_rule=n0, rule_runs=n_a, rule_met=k_a,
                              rule_share=k_a / n_a, rule_lower=CERT.cp_lower(k_a, n_a, 0.025),
                              rule_upper=CERT.cp_upper(k_a, n_a, 0.025),
                              rule_p_conn=float(np.mean([q["connected"] for q in rec_a])),
                              N_design=n_d if n_d is not None else "", design_path=str(dsel),
                              N=d_ if d_ is not None else "", N_certified=n_c if n_c is not None else "",
                              p_cov=float(np.mean([q["coverage"] >= cs["target"] for q in sel])) if sel else "",
                              p_conn=float(np.mean([q["connected"] for q in sel])) if sel else "", **rec))
        print(f"    correlated shadowing rho={rho}: rule {n0} met {k_a / n_a:.3f}, design {n_d}, certified {n_c}",
              flush=True)
    sfx = f".part-{part}" if part else ""
    for name_, rows_, folder in (("E19_stress", rows, RES), ("E19_calibration", crow, RES),
                                 ("E19_correlated_shadowing", srows, RES), ("E19_runs", raw, RAW)):
        if rows_:
            write(f"{name_}{sfx}.csv", rows_, folder)


def merge_E19():
    """Merge the part files of a split E19 run (E19_PART) into the final result files."""
    import glob
    for name_, folder, key in (("E19_stress", RES, "setting"), ("E19_calibration", RES, "setting"),
                               ("E19_correlated_shadowing", RES, None), ("E19_runs", RAW, None),
                               ("seed_manifest", RAW, None)):
        parts = sorted(glob.glob(os.path.join(folder, f"{name_}.part-*.csv")))
        if not parts:
            continue
        rows_, fields = [], []
        for pth in parts:
            with open(pth) as f:
                rd = csv.DictReader(f)
                fields += [k for k in rd.fieldnames if k not in fields]
                rows_ += list(rd)
        if name_ == "seed_manifest":
            path = os.path.join(RAW, "seed_manifest.csv")
            exps = {q["experiment"] for q in rows_}
            with open(path) as f:
                rd = csv.DictReader(f)
                fields = list(rd.fieldnames) + [k for k in fields if k not in rd.fieldnames]
                old = [q for q in rd if q["experiment"] not in exps]
            rows_ = old + rows_
        elif key:
            rows_.sort(key=lambda q: (int(float(q[key])), float(q.get("factor") or 0)))
        elif name_ == "E19_runs":
            order = {"calibration": 0, "certification": 1, "correlated-rule": 2, "correlated-design": 3,
                     "correlated-certification": 4}
            rows_.sort(key=lambda q: (order.get(q["part"], 9), float(q.get("setting") or 0), float(q.get("rho") or 0)))
        with open(os.path.join(folder, f"{name_}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows_)
        for pth in parts:
            os.remove(pth)
        print(f"  merged {len(parts)} parts into {name_}.csv ({len(rows_)} rows)")


def run_E20():
    """Deployment-conditional reliability of randomized sleep scheduling."""
    c = CFG["E20_schedule_conditional"]
    c14 = CFG["E14_sleep_scheduling"]
    print("E20: deployment-conditional scheduling", flush=True)
    L, r, rc, tgt = c14["field"], c14["sensing_radius"], c14["communication_range"], c14["target"]
    pts = sim.raster(L, c["raster"])
    designs = [(int(q["N"]), float(q["q"]), q["multiplier"]) for q in _read_csv("E14_sleep_scheduling.csv")]
    deps = max(10, c["deployments"] // 10) if QUICK else c["deployments"]
    rounds = max(20, c["rounds"] // 10) if QUICK else c["rounds"]
    rows, raw = [], []
    for mi, (n, q, mult) in enumerate(designs):
        rates = []
        for dpl in range(deps):
            seed = c["seed_base"] + 1000 * mi + dpl
            rng = rng_for("E20", seed, multiplier=mult, N=n, deployment=dpl)
            s = sim.random_deployment(n, L, rng)
            ok = 0
            for _ in range(rounds):
                awake = s[rng.random(n) < q]
                cv = sim.coverage_fraction(awake, pts, r) if len(awake) else 0.0
                con = bool(sim.connectivity(awake, rc)[0]) if len(awake) > 1 else False
                ok += cv >= tgt and con
            rate = ok / rounds
            rates.append(rate)
            raw.append(dict(multiplier=mult, N=n, q=q, deployment=dpl, seed=seed, rounds=rounds, met=ok, rate=rate,
                            upper=CERT.cp_upper(ok, rounds, 0.05), lower=CERT.cp_lower(ok, rounds, 0.05)))
        rates = np.array(rates)
        sel = [x for x in raw if x["multiplier"] == mult]
        rows.append(dict(multiplier=mult, N=n, q=q, deployments=deps, rounds=rounds, ensemble=float(rates.mean()),
                         q05=float(np.quantile(rates, 0.05)), q50=float(np.median(rates)), min=float(rates.min()),
                         share_below=float(np.mean(rates < c["requirement"])),
                         share_certainly_below=float(np.mean([x["upper"] < c["requirement"] for x in sel])),
                         share_certainly_above=float(np.mean([x["lower"] >= c["requirement"] for x in sel]))))
        print("   ", rows[-1], flush=True)
    write("E20_schedule_conditional.csv", rows)
    write("E20_runs.csv", raw, RAW)


def run_E22():
    """Heterogeneous radii with fixed class counts."""
    c = CFG["E22_fixed_counts"]
    print("E22: fixed class counts", flush=True)
    L, radii, shares, delta = c["field"], c["radii"], c["shares"], c["delta"]
    runs = runs_of(c["runs"])
    pts = sim.raster(L, c["raster"])
    mix_rule = {q["target"]: int(q["N"]) for q in _read_csv("E15_heterogeneous.csv") if q["rule"] == "mixture"}
    rows, raw = [], []
    for tgt in c["targets"]:
        n_fix = R.n_guaranteed_fixed(tgt, delta, radii, shares, L)
        for rule, n in (("fixed-count rule", n_fix), ("mixture rule", mix_rule[tgt])):
            counts = [int(round(n * s)) for s in shares]
            counts[-1] = n - sum(counts[:-1])
            seed = c["seed_base"] + 1000 * int(round(100 * tgt)) + n
            rng = rng_for("E22", seed, target=tgt, rule=rule, N=n)
            rad = np.concatenate([np.full(k, rm) for k, rm in zip(counts, radii)])
            x = np.array([sim.coverage_fraction_hetero(sim.random_deployment(n, L, rng), rad, pts)
                          for _ in range(runs)])
            raw += [dict(target=tgt, rule=rule, N=n, seed=seed, run=i, coverage=v) for i, v in enumerate(x)]
            k = int(np.sum(x >= tgt))
            rows.append(dict(target=tgt, rule=rule, N=n, counts=str(counts), runs=runs, met=k, p_meet=k / runs,
                             lower=CERT.cp_lower(k, runs, 0.05), mc_mean=float(x.mean()), mc_std=float(x.std(ddof=1)),
                             model_mean_fixed=R.mean_cov_fixed(counts, radii, L),
                             model_std_fixed=math.sqrt(R.var_cov_exact_fixed(counts, radii, L)),
                             model_mean_mixture=R.mean_cov_mix(n, radii, shares, L),
                             model_std_mixture=math.sqrt(R.var_cov_exact_mix(n, radii, shares, L)),
                             model_p_fixed=R.p_meet_fixed(counts, tgt, radii, L)))
            print("   ", tgt, rule, n, round(k / runs, 4), flush=True)
    write("E22_fixed_counts.csv", rows)
    write("E22_runs.csv", raw, RAW)


def c_ratios():
    return CFG["E25_checks"]["diameter_grid_ratios"]


def run_E25():
    """Checks requested in review: connectivity of the pruned lattices, the sign of the far-pair
    covariance in Eq. (5), and the spacing condition of the diameter-spaced grid."""
    print("E25: lattice connectivity, variance decomposition, grid spacing", flush=True)
    rows = []
    e5 = CFG["E5_lattices"]
    L = e5["field"]
    coarse = sim.raster(L, e5["design_raster"])
    fine = sim.raster(L, e5["verification_raster"])
    for r in e5["sensing_radius"]:
        tri = grid.triangular_grid(L, r, coarse, phases=e5["triangular_phases"])
        if sim.coverage_fraction(tri, fine, r) < 1.0:
            tri = grid.triangular_grid(L, r, fine, phases=4)
        sq = grid.square_grid(L, r)
        for kind, lay, rc in (("triangular", tri, math.sqrt(3) * r), ("square", sq, L / round(math.sqrt(len(sq))))):
            pairs = cKDTree(lay).query_pairs(rc * (1 + 1e-9), output_type="ndarray")
            deg = np.bincount(pairs.ravel(), minlength=len(lay)) if len(pairs) else np.zeros(len(lay), int)
            ok, _ = sim.connectivity(lay, rc * (1 + 1e-9))
            d, _ = cKDTree(lay).query(lay, k=2)
            rows.append(dict(check="lattice connectivity", kind=kind, r=r, N=len(lay), Rc=rc, connected=bool(ok),
                             min_degree=int(deg.min()), max_nn_over_Rc=float(d[:, 1].max() / rc),
                             coverage_fine_raster=sim.coverage_fraction(lay, fine, r),
                             exact_cover=grid.covers_square_exactly(lay, L, r)[0]))
        n_d = math.ceil(L / (2 * r) - 1e-9) + 1
        spacing = L / (n_d - 1)
        dg = grid.diameter_grid(L, r)
        rows.append(dict(check="diameter grid spacing", kind="diameter", r=r, N=n_d * n_d, spacing=spacing,
                         spacing_over_sqrt2r=spacing / (math.sqrt(2) * r), full_cover_condition=spacing <= math.sqrt(2) * r,
                         coverage_fine_raster=sim.coverage_fraction(dg, fine, r),
                         exact_cover=grid.covers_square_exactly(dg, L, r)[0]))
    # the spacing condition also holds where L/(2r) is not an integer, e.g. L/(2r) = 1.1
    for ratio in c_ratios():
        r = L / (2 * ratio)
        dg = grid.diameter_grid(L, r)
        n_d = int(round(math.sqrt(len(dg))))
        spacing = L / (n_d - 1)
        rows.append(dict(check="diameter grid spacing", kind="diameter", r=r, N=len(dg), spacing=spacing,
                         spacing_over_sqrt2r=spacing / (math.sqrt(2) * r), full_cover_condition=spacing <= math.sqrt(2) * r,
                         coverage_fine_raster=sim.coverage_fraction(dg, fine, r),
                         exact_cover=grid.covers_square_exactly(dg, L, r)[0], note=f"L/(2r) = {ratio:g}"))
    # variance decomposition (E6a setting): pairs closer than 2r against pairs farther apart
    v = CFG["E6_variance_and_sizing"]["variance_scan"]
    L, r = v["field"], v["sensing_radius"]
    coarse_n = int(min(80, max(50, math.ceil(4 * L / r))))
    S, T = R._pair_matrix(float(L), float(r), coarse_n, 200)
    p = np.asarray(S.sum(axis=1)).ravel()
    X = sim.raster(L, coarse_n)
    TT = T.T.tocsc()
    w = S[0].data[0]
    for n in (10, 50, 100, 200):
        near = far = 0.0
        q = (1 - p) ** n
        for i0 in range(0, len(p), 600):
            pij = (T[i0:i0 + 600] @ TT).toarray() * w
            cov = (1 - p[i0:i0 + 600, None] - p[None, :] + pij) ** n - q[i0:i0 + 600, None] * q[None, :]
            dist = np.linalg.norm(X[i0:i0 + 600, None, :] - X[None, :, :], axis=-1)
            near += float(cov[dist <= 2 * r].sum())
            far += float(cov[dist > 2 * r].sum())
        m2 = len(p) ** 2
        rows.append(dict(check="variance decomposition", kind="E6a", r=r, N=n, var_near=near / m2, var_far=far / m2,
                         var_total=(near + far) / m2, far_share=far / (near + far)))
    write("E25_checks.csv", rows)


def _timed(fn, reps):
    """Median wall time over reps calls, then one extra call under tracemalloc for the peak of
    Python-tracked memory (NumPy arrays included). Returns (median s, min s, peak MiB, last result)."""
    import tracemalloc
    times, out = [], None
    for _ in range(reps):
        t = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t)
    tracemalloc.start()
    fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return float(np.median(times)), float(np.min(times)), peak / 2 ** 20, out


def run_E23():
    """End-to-end run time and memory of every design step and baseline on one machine.
    Run it alone: other jobs on the same machine distort the timings."""
    import platform
    import resource
    c = CFG["E23_runtime"]
    print("E23: run time and memory", flush=True)
    rows = []
    L, r = c["field"], c["sensing_radius"]
    reps = 1 if QUICK else c["repetitions"]

    def add(phase, task, fn, reps=reps, **extra):
        med, best, peak, out = _timed(fn, reps)
        rows.append(dict(phase=phase, task=task, repetitions=reps, median_s=med, min_s=best,
                         peak_traced_MiB=peak, **extra))
        print(f"    {phase:8s} {task}: {med:.3f} s, {peak:.1f} MiB", flush=True)
        return out

    # offline design steps of the proposed method
    s6 = c["sizing"]
    add("offline", f"Beta sizing rule (L={s6['field']:g}, r={s6['radius']:g}, Ct={s6['target']}, delta={s6['delta']})",
        lambda: R.n_guaranteed(s6["target"], s6["delta"], s6["radius"], s6["field"], dist="beta"))
    j7 = c["joint"]
    add("offline", f"joint coverage-connectivity rule (Rc={j7['Rc']:g})",
        lambda: R.n_joint(j7["target"], j7["delta"], j7["radius"], j7["Rc"], j7["field"]))
    n0 = R.n_guaranteed(s6["target"], s6["delta"], s6["radius"], s6["field"], dist="beta")
    pts6 = sim.raster(s6["field"], s6["raster"])
    runs_c = runs_of(c["certification_runs"])
    add("offline", f"certification of the rule, {runs_c} independent drops (N={n0})",
        lambda: [sim.coverage_fraction(sim.random_deployment(n0, s6["field"], rng), pts6, s6["radius"])
                 for rng in [np.random.default_rng(c["seed_base"])] for _ in range(runs_c)], reps=1, N=n0)
    pts_d = sim.raster(L, c["lattice_design_raster"])
    tri = add("offline", "triangular lattice: offset search and pruning (kappa = 1)",
              lambda: grid.triangular_grid(L, r, pts_d, phases=4))
    add("offline", "exact (raster-free) coverage test of the triangular lattice",
        lambda: grid.covers_square_exactly(tri, L, r))
    add("offline", "square lattice (kappa = 1)", lambda: grid.square_grid(L, r))
    add("offline", "lattice for a fixed budget, N = 33 (bisection on the design radius)",
        lambda: placement.lattice_for_n(L, r, 33, pts_d))
    e16 = CFG["E16_reliable_lattice"]
    sg = c["lattice_sigma_over_r"] * r
    add("offline", f"error-tolerant lattice search, sigma = {c['lattice_sigma_over_r']}r, "
                   f"{runs_of(e16['search']['runs'])} drops per kappa",
        lambda: placement.reliable_lattice(L, r, sg, e16["target"], e16["delta"], "triangular",
                                           design_res=e16["design_raster"], sim_res=e16["simulation_raster"],
                                           runs=runs_of(e16["search"]["runs"]), seed=c["seed_base"]), reps=1)
    # baselines under the E10 budget
    e10 = CFG["E10_baselines"]
    for m in c["baselines"]:
        for k in range(1 if QUICK else c["baseline_seeds"]):
            seed = e10["seed_base"] + 37 * 33 + k
            holder = {}

            def job(m=m, seed=seed):
                holder["out"] = _e10_job((m, L, r, 33, seed, e10))
                return holder["out"]

            med, best, peak, out = _timed(job, 1)
            rows.append(dict(phase="baseline", task=m, repetitions=1, median_s=med, min_s=best,
                             peak_traced_MiB=peak, seed=seed, fitness_evals=out[5], N=33))
            print(f"    baseline {m} seed {seed}: {med:.2f} s, {peak:.1f} MiB, {out[5]} evaluations", flush=True)
    # online evaluation of a given layout
    fine = sim.raster(L, e10["evaluation_raster"])
    fit = sim.raster(L, e10["budget"]["fitness_raster"])
    lay33 = placement.lattice_for_n(L, r, 33, pts_d)
    k_eval = 10 if QUICK else c["evaluation_calls"]
    for name, pts in (("coverage of one layout, 250 x 250 raster", fine), ("one fitness evaluation, 80 x 80 raster", fit)):
        med, best, peak, _ = _timed(lambda pts=pts: [sim.coverage_fraction(lay33, pts, r) for _ in range(k_eval)], reps)
        rows.append(dict(phase="online", task=name, repetitions=reps * k_eval, median_s=med / k_eval,
                         min_s=best / k_eval, peak_traced_MiB=peak, N=33))
        print(f"    online   {name}: {1e3 * med / k_eval:.3f} ms per call", flush=True)
    med, best, peak, _ = _timed(lambda: [sim.connectivity(lay33, math.sqrt(3) * r) for _ in range(k_eval)], reps)
    rows.append(dict(phase="online", task="connectivity check (Rc = sqrt(3) r)", repetitions=reps * k_eval,
                     median_s=med / k_eval, min_s=best / k_eval, peak_traced_MiB=peak, N=33))
    try:
        cpu = next(q.split(":", 1)[1].strip() for q in open("/proc/cpuinfo") if q.startswith("model name"))
    except (OSError, StopIteration):
        cpu = platform.processor()
    hw = dict(cpu=cpu, logical_cpus=os.cpu_count(), python=platform.python_version(), numpy=np.__version__,
              platform=platform.platform(), process_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    for q in rows:
        q.update(cpu=hw["cpu"], logical_cpus=hw["logical_cpus"], python=hw["python"], numpy=hw["numpy"])
    write("E23_runtime.csv", rows)
    write("E23_hardware.csv", [hw])


def main():
    global QUICK
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exp", nargs="+", default=["all"],
                    help="E2 S2 E5 E6 E7 E8 E9 E10 E11 E12 E13 E14 E15 E16, or all, or E10summary")
    ap.add_argument("--workers", type=int, default=1, help="processes for E10")
    ap.add_argument("--quick", action="store_true", help="10 %% of the runs; for smoke tests only")
    a = ap.parse_args()
    QUICK = a.quick
    want = {e.upper() for e in a.exp}
    run_all = "ALL" in want
    t0 = time.time()
    if run_all or "E2" in want:
        summary_errors(run_E2())
    for key, fn in [("S2", run_S2), ("E5", run_E5), ("E6", run_E6), ("E7", run_E7),
                    ("E8", run_E8), ("E9", run_E9), ("E11", run_E11),
                    ("E12", run_E12), ("E13", run_E13), ("E14", run_E14), ("E15", run_E15), ("E16", run_E16)]:
        if run_all or key in want:
            fn()
    if run_all or "E10" in want:
        run_E10(a.workers)
    if "E10SUMMARY" in want:
        summarize_E10()
    for key, fn in [("E17", run_E17), ("E18", run_E18), ("E19", run_E19), ("E20", run_E20), ("E21", run_E21),
                    ("E22", run_E22), ("E25", run_E25), ("E23", run_E23)]:
        if run_all or key in want:
            fn()
    if run_all or "E24" in want:
        run_E24(a.workers)
    if "E19MERGE" in want:
        merge_E19()
    if SEEDS and os.environ.get("E19_PART"):
        write(f"seed_manifest.part-{os.environ['E19_PART']}.csv", SEEDS, RAW)
        SEEDS.clear()
    if SEEDS:
        path = os.path.join(RAW, "seed_manifest.csv")
        old = []
        if os.path.exists(path):
            exps = {s["experiment"] for s in SEEDS}
            with open(path) as f:
                old = [q for q in csv.DictReader(f) if q["experiment"] not in exps]
        write("seed_manifest.csv", old + SEEDS, RAW)
    print(f"done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()

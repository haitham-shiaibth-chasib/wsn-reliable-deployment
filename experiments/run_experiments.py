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

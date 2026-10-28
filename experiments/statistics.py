"""All statistical tests reported in the manuscript, computed from the raw per-run files.

Usage:  python experiments/statistics.py
Writes:  results/statistical_tests.csv  (one row per test)
         results/statistical_tests.md   (the same, readable)

Conventions
-----------
* Two-sided tests, significance level 0.05.
* Multiple comparisons inside one family are corrected with the Holm-Bonferroni procedure.
* Paired comparisons use the Wilcoxon signed-rank test (exact for n <= 50 without ties);
  the effect size is the matched-pairs rank-biserial correlation
  r_rb = (W+ - W-) / (W+ + W-), which lies in [-1, 1].
* Proportions are tested against their nominal value with the exact binomial test and
  reported with Wilson 95 % intervals.
* The comparison of the eight deployment methods uses the Friedman test with seeds as
  blocks, followed by Holm-corrected Wilcoxon tests of every method against the lattice.
"""
from __future__ import annotations

import csv
import itertools
import math
import os
import sys

import numpy as np
from scipy import stats

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from wsndeploy.stats import wilson  # noqa: E402

RES = os.path.join(ROOT, "results")
RAW = os.path.join(RES, "raw")
ALPHA = 0.05


def load(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    out = []
    for q in rows:
        d = {}
        for k, v in q.items():
            if v in ("True", "False"):
                d[k] = v == "True"
                continue
            try:
                d[k] = float(v)
            except ValueError:
                d[k] = v
        out.append(d)
    return out


def holm(pvals):
    """Holm-Bonferroni adjusted p-values (same order as the input)."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj


def rank_biserial(d):
    d = np.asarray(d, dtype=float)
    d = d[d != 0]
    if len(d) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(d))
    wp, wm = ranks[d > 0].sum(), ranks[d < 0].sum()
    return float((wp - wm) / (wp + wm))


TESTS: list[dict] = []


def add(family, test, comparison, n, statistic, p, effect=float("nan"), note=""):
    TESTS.append(dict(family=family, test=test, comparison=comparison, n=n, statistic=statistic,
                      p_value=p, p_holm=float("nan"), effect_size=effect, note=note))


def close_family(family):
    idx = [i for i, t in enumerate(TESTS) if t["family"] == family and not math.isnan(t["p_value"])]
    if idx:
        adj = holm([TESTS[i]["p_value"] for i in idx])
        for i, a in zip(idx, adj):
            TESTS[i]["p_holm"] = float(a)


# ----------------------------------------------------------------------------- A. mean models
def family_mean_models():
    for exp, fname, models in [("E2", "E2_physical.csv", ["linear_no_overlap", "poisson_exp", "exact_edge"])]:
        fam = f"A. Mean-model accuracy ({exp})"
        rows = load(os.path.join(RES, fname))
        ref = np.array([q["mc_mean"] for q in rows])
        ci = np.array([q["ci95"] for q in rows])
        err = {m: np.abs(np.array([q[m] for q in rows]) - ref) for m in models}
        for m in models:
            add(fam, "share of settings inside the 95% CI of the simulation mean", m, len(rows),
                float(np.mean(err[m] <= ci)), float("nan"))
        for a, b in itertools.combinations(models, 2):
            d = err[a] - err[b]
            res = stats.wilcoxon(err[a], err[b])
            add(fam, "Wilcoxon signed-rank on the absolute error of the models", f"{a} vs {b}", len(rows),
                float(res.statistic), float(res.pvalue), rank_biserial(d),
                "positive effect: first model has the larger error")
        close_family(fam)


# ----------------------------------------------------------------------------- B. variance model
def family_variance():
    fam = "B. Variance model (E6a)"
    raw = load(os.path.join(RAW, "E6a_runs.csv"))
    rows = load(os.path.join(RES, "E6a_variance.csv"))
    inside_exact = inside_stat = 0
    for q in rows:
        x = np.array([r["coverage"] for r in raw if r["N"] == q["N"]])
        n = len(x)
        s2 = x.var(ddof=1)
        lo = math.sqrt((n - 1) * s2 / stats.chi2.ppf(0.975, n - 1))
        hi = math.sqrt((n - 1) * s2 / stats.chi2.ppf(0.025, n - 1))
        inside_exact += lo <= q["model_std_exact"] <= hi
        inside_stat += lo <= q["model_std_stationary"] <= hi
    add(fam, "share of N values whose model std lies in the chi-square 95% CI of the simulated std",
        "edge-aware model", len(rows), inside_exact / len(rows), float("nan"))
    add(fam, "share of N values whose model std lies in the chi-square 95% CI of the simulated std",
        "stationary approximation", len(rows), inside_stat / len(rows), float("nan"))
    e_ex = np.array([abs(q["model_std_exact"] - q["mc_std"]) for q in rows])
    e_st = np.array([abs(q["model_std_stationary"] - q["mc_std"]) for q in rows])
    res = stats.wilcoxon(e_st, e_ex)
    add(fam, "Wilcoxon signed-rank on the absolute error of the std models", "stationary vs edge-aware", len(rows),
        float(res.statistic), float(res.pvalue), rank_biserial(e_st - e_ex),
        "positive effect: stationary approximation has the larger error")
    close_family(fam)


# ----------------------------------------------------------------------------- C. sizing rules
def family_sizing():
    rows = load(os.path.join(RES, "E6b_sizing.csv"))
    runs = load(os.path.join(RAW, "E6b_runs.csv"))
    for rule in ("mean", "normal", "beta"):
        fam = f"C. Reliability of the {rule} rule against the nominal 0.95 (E6b)"
        hits = trials = 0
        for q in [r for r in rows if r["rule"] == rule]:
            x = np.array([r["coverage"] for r in runs if r["L"] == q["L"] and r["r"] == q["r"] and r["N"] == q["N"]])
            k, n = int(np.sum(x >= q["target"])), len(x)
            hits += k
            trials += n
            res = stats.binomtest(k, n, 0.95)
            add(fam, "exact binomial test, H0: P(C >= Ct) = 0.95",
                f"L={q['L']:g}, r={q['r']:g}, Ct={q['target']:g}, N={int(q['N'])}", n, k / n, float(res.pvalue))
        close_family(fam)
        p, lo, hi = wilson(hits, trials)
        add(f"C. Pooled reliability ({rule} rule)", "pooled share with Wilson 95% CI",
            f"{rule} rule, 16 settings", trials, p, float("nan"), note=f"Wilson CI [{lo:.4f}, {hi:.4f}]")


# ----------------------------------------------------------------------------- D. joint rule
def family_joint():
    fam = "D. Joint coverage-connectivity rule (E7b)"
    rows = load(os.path.join(RES, "E7b_joint.csv"))
    raw = load(os.path.join(RAW, "E7b_runs.csv"))
    for rc in sorted({q["rc"] for q in rows}):
        for t in sorted({q["target"] for q in rows}):
            cnt = {}
            for rule in ("coverage_only", "joint"):
                x = [r for r in raw if r["Rc"] == rc and r["target"] == t and r["rule"] == rule]
                k = sum(1 for r in x if r["coverage"] >= t and r["connected"])
                cnt[rule] = (k, len(x))
                res = stats.binomtest(k, len(x), 0.95, alternative="less")
                add(fam, "one-sided exact binomial test, H1: P(both targets) < 0.95",
                    f"{rule}, Rc={rc:g}, Ct={t:g}", len(x), k / len(x), float(res.pvalue))
            (a, na), (b, nb) = cnt["coverage_only"], cnt["joint"]
            res = stats.fisher_exact([[a, na - a], [b, nb - b]])
            add(fam, "Fisher exact test, coverage-only vs joint", f"Rc={rc:g}, Ct={t:g}", na + nb,
                float(res.statistic), float(res.pvalue), note="odds ratio as statistic")
    close_family(fam)


# ----------------------------------------------------------------------------- E. drop error
def family_drop_error():
    fam = "E. Error-tolerant lattice: simulated mean against the closed-form expectation (E8)"
    rows = load(os.path.join(RES, "E8_placement_error.csv"))
    raw = load(os.path.join(RAW, "E8_runs.csv"))
    for q in rows:
        if q["sigma_over_r"] == 0:
            continue
        x = np.array([r["coverage"] for r in raw if r["sigma_over_r"] == q["sigma_over_r"] and r["lattice"] == q["kind"]])
        res = stats.ttest_1samp(x, q["robust_expected"])
        d = (x.mean() - q["robust_expected"]) / x.std(ddof=1)
        add(fam, "one-sample t-test, H0: mean = Eq. (17)", f"{q['kind']}, sigma={q['sigma_over_r']:g}r",
            len(x), float(res.statistic), float(res.pvalue), float(d), "effect size: Cohen's d")
    close_family(fam)


# ----------------------------------------------------------------------------- F. baselines
def family_baselines():
    raw = load(os.path.join(RAW, "E10_runs.csv"))
    methods = [m for m in ["Random", "VFA", "PSO", "GA", "GWO", "ICGWO", "VASF-PSO", "DAR-SSA"]
               if any(q["method"] == m for q in raw)]
    fam = "F. Comparison of deployment methods (E10)"
    F0 = f"F0. Friedman test over {len(methods) + 1} methods (E10)"
    for n in sorted({q["N"] for q in raw}):
        lat = next(q["coverage"] for q in raw if q["method"] == "Proposed lattice" and q["N"] == n)
        seeds = sorted({q["seed"] for q in raw if q["N"] == n and q["method"] != "Proposed lattice"})
        table = np.array([[next(q["coverage"] for q in raw if q["method"] == m and q["N"] == n and q["seed"] == s)
                           for m in methods] + [lat] for s in seeds])
        res = stats.friedmanchisquare(*table.T)
        add(F0, "Friedman test, seeds as blocks", f"N={int(n)}",
            len(seeds), float(res.statistic), float(res.pvalue))
        for j, m in enumerate(methods):
            d = table[:, j] - lat
            if np.all(d == 0):
                add(fam, "Wilcoxon signed-rank against the lattice", f"{m}, N={int(n)}", len(d), 0.0, 1.0, 0.0)
                continue
            r_ = stats.wilcoxon(d)
            add(fam, "Wilcoxon signed-rank against the lattice", f"{m}, N={int(n)}", len(d),
                float(r_.statistic), float(r_.pvalue), rank_biserial(d),
                "sign of effect: negative = method below the lattice, positive = method above it")
    close_family(F0)
    close_family(fam)


# ----------------------------------------------------------------------------- G. extensions
def family_extensions():
    fam = "G. Extensions (E9)"
    rows = load(os.path.join(RES, "E9_extensions.csv"))
    for case in ("k-coverage", "failures-coverage", "probabilistic-sensing", "failures-connectivity"):
        q = [x for x in rows if x["case"] == case]
        e = np.array([abs(x["model"] - x["mc_mean"]) for x in q])
        note = "model is the isolated-node bound" if case == "failures-connectivity" else ""
        add(fam, "mean absolute error of the model", case, len(q), float(e.mean()), float("nan"), note=note)
        if case != "failures-connectivity":
            inside = np.mean([abs(x["model"] - x["mc_mean"]) <= x["ci95"] for x in q])
            add(fam, "share of settings inside the 95% CI of the simulation mean", case, len(q), float(inside),
                float("nan"))


# ----------------------------------------------------------------------------- H. environment
def family_environment():
    path = os.path.join(RES, "E11_rules.csv")
    if not os.path.exists(path):
        return
    fam = "H. Rules under obstacles and shadowing (E11)"
    rows = load(path)
    raw = load(os.path.join(RAW, "E11b_runs.csv"))
    for q in rows:
        x = [r for r in raw if r["scenario"] == q["scenario"] and r["rule"] == q["rule"] and r["N"] == q["N"]]
        k = sum(1 for r in x if r["coverage"] >= 0.9 and r["connected"])
        res = stats.binomtest(k, len(x), 0.95, alternative="less")
        add(fam, "one-sided exact binomial test, H1: P(both targets) < 0.95",
            f"{q['scenario']}, {q['rule']}, N={int(q['N'])}", len(x), k / len(x), float(res.pvalue))
    close_family(fam)
    fam = "H. Model accuracy under obstacles and shadowing (E11)"
    rows = load(os.path.join(RES, "E11_model_check.csv"))
    for sc in dict.fromkeys(q["scenario"] for q in rows):
        q = [x for x in rows if x["scenario"] == sc]
        add(fam, "mean absolute error of the coverage mean", sc, len(q),
            float(np.mean([abs(x["model_cov_mean"] - x["mc_cov_mean"]) for x in q])), float("nan"))
        add(fam, "mean relative error of the coverage std", sc, len(q),
            float(np.mean([abs(x["model_cov_std"] - x["mc_cov_std"]) / x["mc_cov_std"] for x in q])), float("nan"))
        add(fam, "mean absolute error of P(no isolated node)", sc, len(q),
            float(np.mean([abs(x["model_p_no_isolated"] - x["mc_p_no_isolated"]) for x in q])), float("nan"))
        hi = [x for x in q if x["mc_p_no_isolated"] >= 0.9]
        if hi:
            add(fam, "largest gap P(no isolated node) - P(connected), simulated, where P(no isolated) >= 0.9", sc,
                len(hi), float(max(x["mc_p_no_isolated"] - x["mc_p_conn"] for x in hi)), float("nan"))


# ----------------------------------------------------------------------------- I-K. version 1.1 experiments
def family_risk_levels():
    path = os.path.join(RES, "E12_risk_sensitivity.csv")
    if not os.path.exists(path):
        return
    fam = "I. Beta rule at other risk levels (E12)"
    for q in load(path):
        res = stats.binomtest(int(q["met"]), int(q["runs"]), q["nominal"])
        add(fam, "exact binomial test, H0: P(C >= Ct) = 1 - delta",
            f"delta={q['delta']:g}, Ct={q['target']:g}, N={int(q['N'])}", int(q["runs"]), q["p_meet"], float(res.pvalue))
    close_family(fam)


def family_scheduling():
    path = os.path.join(RES, "E14_sleep_scheduling.csv")
    if not os.path.exists(path):
        return
    fam = "J. Sleep scheduling (E14)"
    for q in load(path):
        res = stats.binomtest(int(q["met"]), int(q["runs"]), 0.95, alternative="less")
        add(fam, "one-sided exact binomial test, H1: P(both targets) < 0.95",
            f"N={int(q['N'])}, q={q['q']:g}", int(q["runs"]), q["p_both"], float(res.pvalue))
    close_family(fam)


def family_heterogeneous():
    path = os.path.join(RES, "E15_heterogeneous.csv")
    if not os.path.exists(path):
        return
    fam = "K. Heterogeneous radii (E15)"
    for q in load(path):
        res = stats.binomtest(int(q["met"]), int(q["runs"]), 0.95)
        add(fam, "exact binomial test, H0: P(C >= Ct) = 0.95",
            f"{q['rule']}, Ct={q['target']:g}, N={int(q['N'])}", int(q["runs"]), q["p_meet"], float(res.pvalue))
    close_family(fam)


def family_reliable_lattice():
    path = os.path.join(RES, "E16_reliable_lattice.csv")
    if not os.path.exists(path):
        return
    fam = "L. Reliability-sized lattices, independent validation drops (E16)"
    raw = load(os.path.join(RAW, "E16_runs.csv"))
    for q in load(path):
        x = [r["coverage"] for r in raw if r["sigma_over_r"] == q["sigma_over_r"] and r["lattice"] == q["kind"]]
        k = sum(1 for v in x if v >= 0.99)
        res = stats.binomtest(k, len(x), 0.95, alternative="less")
        add(fam, "one-sided exact binomial test, H1: P(C >= 0.99) < 0.95",
            f"{q['kind']}, sigma={q['sigma_over_r']:g}r, N={int(q['nodes'])}", len(x), k / len(x), float(res.pvalue))
    close_family(fam)


def main():
    family_mean_models()
    family_variance()
    family_sizing()
    family_joint()
    family_drop_error()
    family_baselines()
    family_extensions()
    family_environment()
    family_risk_levels()
    family_scheduling()
    family_heterogeneous()
    family_reliable_lattice()
    path = os.path.join(RES, "statistical_tests.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(TESTS[0].keys()))
        w.writeheader()
        w.writerows(TESTS)
    fmt = lambda v: "" if isinstance(v, float) and math.isnan(v) else (f"{v:.3g}" if isinstance(v, float) else str(v))
    lines = ["# Statistical tests", "", "Generated by `experiments/statistics.py` from `results/raw/`. "
             "Two-sided unless stated; Holm-Bonferroni correction within each family; alpha = 0.05.", ""]
    for fam in dict.fromkeys(t["family"] for t in TESTS):
        lines += [f"## {fam}", "", "| Test | Comparison | n | Statistic | p | p (Holm) | Effect | Note |",
                  "|---|---|---|---|---|---|---|---|"]
        for t in [x for x in TESTS if x["family"] == fam]:
            lines.append("| " + " | ".join(fmt(t[k]) for k in ("test", "comparison", "n", "statistic", "p_value",
                                                                  "p_holm", "effect_size", "note")) + " |")
        lines.append("")
    open(os.path.join(RES, "statistical_tests.md"), "w").write("\n".join(lines))
    print(f"wrote {len(TESTS)} tests to results/statistical_tests.csv and .md")


if __name__ == "__main__":
    main()

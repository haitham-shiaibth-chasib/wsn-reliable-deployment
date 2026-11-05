"""Build the IJIES manuscript (Word) from the experiment results.

All numbers quoted in the text are read from ../results/*.csv.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys

from scipy import stats as sst

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ijies_docx import Doc, blank, para, rich, run  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
_ap = argparse.ArgumentParser(description="Build the IJIES manuscript from the experiment results.")
_ap.add_argument("--root", default=os.path.dirname(HERE), help="repository root (contains results/ and figures/)")
_ap.add_argument("--template", default=os.path.join(HERE, "IJIES_Format.docx"),
                 help="IJIES Word template (download from the journal web site)")
_ap.add_argument("--out", default=os.path.join(HERE, "IJIES_Manuscript_Reliable_WSN_Deployment.docx"))
_ap.add_argument("--doi", default="10.5281/zenodo.23717648", help="Zenodo DOI of the archived code (concept DOI: resolves to the latest version)")
_ap.add_argument("--github", default="https://github.com/haitham-shiaibth-chasib/wsn-reliable-deployment")
ARGS = _ap.parse_args()
ROOT = ARGS.root
RES, FIG = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures")
TEMPLATE, OUT, GITHUB = ARGS.template, ARGS.out, ARGS.github
ZENODO_DOI = f"https://doi.org/{ARGS.doi}"
if not os.path.exists(TEMPLATE):
    raise SystemExit(f"IJIES template not found: {TEMPLATE}\nDownload it from the journal web site and pass --template.")


def load(name):
    with open(os.path.join(RES, name)) as f:
        out = []
        for q in csv.DictReader(f):
            d = {}
            for k, v in q.items():
                try:
                    d[k] = float(v)
                except ValueError:
                    d[k] = v
            out.append(d)
        return out


AUTHORS = ("Haitham Shiaibth Chasib", "Israa Jaber Khalaf Al-Ogaili")
AFFILIATION = "General Directorate of Education in Babylon, Ministry of Education, Iraq"
EMAIL = "haitham.aljabry2014@gmail.com"


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


_SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def sci(p):
    """p-value in journal notation, e.g. 1.5 × 10⁻³⁹ (no computer 'e' notation)."""
    if p >= 1e-3:
        return f"{p:.3f}"
    m, e = f"{p:.1e}".split("e")
    return f"{m} × 10{str(int(e)).translate(_SUP)}"


# ----------------------------------------------------------------------------- references
REFS = {
    "saheb": "S. I. Saheb, K. U. R. Khan, and C. S. Bindu, “A Multi-Objective Sensor Deployment using BAT Algorithm to Improve Coverage, Lifetime and Energy Consumption in Wireless Sensor Networks”, International Journal of Intelligent Engineering and Systems, Vol. 15, No. 3, pp. 467-477, 2022.",
    "ahmed": "A. S. Ahmed, I. N. Abood, and M. S. Taha, “Adaptive Multi-objective Optimization for Obstacle-aware Wireless Sensor Network Deployment: A Comparative Analysis of State-of-the-Art Algorithms”, International Journal of Intelligent Engineering and Systems, Vol. 19, No. 2, pp. 707-720, 2026.",
    "priyadarshi": "R. Priyadarshi, “Efficient Node Deployment for Enhancing Coverage and Connectivity in Wireless Sensor Networks”, Scientific Reports, Vol. 15, No. 1, p. 29052, 2025.",
    "hall": "P. Hall, Introduction to the Theory of Coverage Processes, John Wiley & Sons, New York, 1988.",
    "liutowsley": "B. Liu and D. Towsley, “A Study of the Coverage of Large-Scale Sensor Networks”, In: Proc. of IEEE International Conf. on Mobile Ad-hoc and Sensor Systems, Fort Lauderdale, USA, pp. 475-483, 2004.",
    "wang": "B. Wang, “Coverage Problems in Sensor Networks: A Survey”, ACM Computing Surveys, Vol. 43, No. 4, pp. 1-53, 2011.",
    "kershner": "R. Kershner, “The Number of Circles Covering a Set”, American Journal of Mathematics, Vol. 61, No. 3, pp. 665-671, 1939.",
    "bai": "X. Bai, S. Kumar, D. Xuan, Z. Yun, and T. H. Lai, “Deploying Wireless Sensors to Achieve Both Coverage and Connectivity”, In: Proc. of ACM International Symposium on Mobile Ad Hoc Networking and Computing, Florence, Italy, pp. 131-142, 2006.",
    "zhanghou": "H. Zhang and J. C. Hou, “Maintaining Sensing Coverage and Connectivity in Large Sensor Networks”, Ad Hoc & Sensor Wireless Networks, Vol. 1, No. 1-2, pp. 89-124, 2005.",
    "kumar": "S. Kumar, T. H. Lai, and J. Balogh, “On k-Coverage in a Mostly Sleeping Sensor Network”, In: Proc. of ACM International Conf. on Mobile Computing and Networking, Philadelphia, USA, pp. 144-158, 2004.",
    "gupta": "P. Gupta and P. R. Kumar, “Critical Power for Asymptotic Connectivity in Wireless Networks”, In: Stochastic Analysis, Control, Optimization and Applications, Birkhäuser, Boston, pp. 547-566, 1999.",
    "penrose": "M. Penrose, Random Geometric Graphs, Oxford University Press, Oxford, 2003.",
    "bettstetter": "C. Bettstetter, “On the Minimum Node Degree and Connectivity of a Wireless Multihop Network”, In: Proc. of ACM International Symposium on Mobile Ad Hoc Networking and Computing, Lausanne, Switzerland, pp. 80-91, 2002.",
    "nakka2023": "K. Nakka and H. M. Ammari, “k-CSqu: Ensuring Connected k-Coverage Using Cusp Squares of Square Tessellation”, Journal of Parallel and Distributed Computing, Vol. 182, p. 104749, 2023.",
    "nakka2024": "K. Nakka and H. M. Ammari, “An Energy-Efficient Irregular Hexagonal Tessellation-Based Approach for Connected k-Coverage in Planar Wireless Sensor Networks”, Ad Hoc Networks, Vol. 154, p. 103353, 2024.",
    "nakka2025": "K. Nakka and H. M. Ammari, “Hierarchical Deployment and Square Tessellation for Connected k-Coverage in Heterogeneous Planar Wireless Sensor Networks”, ACM Transactions on Sensor Networks, Vol. 21, No. 2, pp. 1-27, 2025.",
    "liuz": "Z. Liu, G. Jiang, W. Jia, T. Wang, and Y. Wu, “Critical Density for K-Coverage Under Border Effects in Camera Sensor Networks With Irregular Obstacles Existence”, IEEE Internet of Things Journal, Vol. 11, No. 4, pp. 6426-6437, 2024.",
    "zou": "Y. Zou and K. Chakrabarty, “Sensor Deployment and Target Localization Based on Virtual Forces”, In: Proc. of IEEE INFOCOM, San Francisco, USA, pp. 1293-1303, 2003.",
    "kennedy": "J. Kennedy and R. Eberhart, “Particle Swarm Optimization”, In: Proc. of International Conf. on Neural Networks, Perth, Australia, pp. 1942-1948, 1995.",
    "mirjalili": "S. Mirjalili, S. M. Mirjalili, and A. Lewis, “Grey Wolf Optimizer”, Advances in Engineering Software, Vol. 69, pp. 46-61, 2014.",
    "xue": "J. Xue and B. Shen, “A Novel Swarm Intelligence Optimization Approach: Sparrow Search Algorithm”, Systems Science & Control Engineering, Vol. 8, No. 1, pp. 22-34, 2020.",
    "tossa": "F. Tossa, W. Abdou, K. Ansari, E. C. Ezin, and P. Gouton, “Area Coverage Maximization under Connectivity Constraint in Wireless Sensor Networks”, Sensors, Vol. 22, No. 5, p. 1712, 2022.",
    "bhargavi": "K. V. N. A. Bhargavi, G. P. S. Varma, I. Hemalatha, and R. Dilli, “An Enhanced Particle Swarm Optimization-Based Node Deployment and Coverage in Sensor Networks”, Sensors, Vol. 24, No. 19, p. 6238, 2024.",
    "siamantas": "G. Siamantas and D. Kandris, “Particle Swarm Optimization for k-Coverage and 1-Connectivity in Wireless Sensor Networks”, Electronics, Vol. 13, No. 23, p. 4841, 2024.",
    "amer": "D. A. Amer, S. A. Soliman, A. F. Hassan, and A. A. Zamel, “Enhancing Connectivity and Coverage in Wireless Sensor Networks: A Hybrid Comprehensive Learning-Fick’s Algorithm with Particle Swarm Optimization for Router Node Placement”, Neural Computing and Applications, Vol. 36, No. 34, pp. 21671-21702, 2024.",
    "jin": "Z. Jin, Y. Geng, C. Zhu, Y. Xia, X. Deng, L. Yi, and X. Wang, “Deployment Optimization for Target Perpetual Coverage in Energy Harvesting Wireless Sensor Network”, Digital Communications and Networks, Vol. 10, No. 2, pp. 498-508, 2024.",
    "haris": "M. Haris and H. Nam, “Sensor Node Deployment Optimization for Continuous Coverage in WSNs”, Sensors, Vol. 25, No. 12, p. 3620, 2025.",
    "shaikh": "M. S. Shaikh, C. Wang, S. Xie, G. Zheng, X. Dong, S. Qiu, M. A. Ahmad, and S. Raj, “Coverage and Connectivity Maximization for Wireless Sensor Networks Using Improved Chaotic Grey Wolf Optimization”, Scientific Reports, Vol. 15, No. 1, p. 15706, 2025.",
    "heinzelman": "W. R. Heinzelman, A. Chandrakasan, and H. Balakrishnan, “Energy-Efficient Communication Protocol for Wireless Microsensor Networks”, In: Proc. of Hawaii International Conf. on System Sciences, Maui, USA, pp. 1-10, 2000.",
    "tian": "D. Tian and N. D. Georganas, “A Coverage-Preserving Node Scheduling Scheme for Large Wireless Sensor Networks”, In: Proc. of ACM International Workshop on Wireless Sensor Networks and Applications, Atlanta, USA, pp. 32-41, 2002.",
    "peas": "F. Ye, G. Zhong, J. Cheng, S. Lu, and L. Zhang, “PEAS: A Robust Energy Conserving Protocol for Long-Lived Sensor Networks”, In: Proc. of IEEE International Conf. on Distributed Computing Systems, Providence, USA, pp. 28-37, 2003.",
    "hsin": "C. Hsin and M. Liu, “Randomly Duty-Cycled Wireless Sensor Networks: Dynamics of Coverage”, IEEE Transactions on Wireless Communications, Vol. 5, No. 10, pp. 3182-3192, 2006.",
    "luo": "C. Luo, Y. Hong, D. Li, Y. Wang, W. Chen, and Q. Hu, “Maximizing Network Lifetime Using Coverage Sets Scheduling in Wireless Sensor Networks”, Ad Hoc Networks, Vol. 98, p. 102037, 2020.",
    "nurcan": "D. Nurcan-Atceken, A. Altin-Kayhan, and B. Tavli, “A Novel Differentiated Coverage-Based Lifetime Metric for Wireless Sensor Networks”, Ad Hoc Networks, Vol. 164, p. 103636, 2024.",
    "chakrabarty": "K. Chakrabarty, S. S. Iyengar, H. Qi, and E. Cho, “Grid Coverage for Surveillance and Target Location in Distributed Sensor Networks”, IEEE Transactions on Computers, Vol. 51, No. 12, pp. 1448-1453, 2002.",
    "lazos": "L. Lazos and R. Poovendran, “Stochastic Coverage in Heterogeneous Sensor Networks”, ACM Transactions on Sensor Networks, Vol. 2, No. 3, pp. 325-358, 2006.",
    "huangfu": "Q. Huangfu and J. A. J. Hall, “Parallelizing the Dual Revised Simplex Method”, Mathematical Programming Computation, Vol. 10, No. 1, pp. 119-142, 2018.",
    "holland": "J. H. Holland, Adaptation in Natural and Artificial Systems, University of Michigan Press, Ann Arbor, 1975.",
    "eshelman": "L. J. Eshelman and J. D. Schaffer, “Real-Coded Genetic Algorithms and Interval-Schemata”, In: Foundations of Genetic Algorithms 2, Morgan Kaufmann, San Mateo, pp. 187-202, 1993.",
    "fan": "G. Fan, R. Wang, H. Huang, L. Sun, and C. Sha, “Coverage-Guaranteed Sensor Node Deployment Strategies for Wireless Sensor Networks”, Sensors, Vol. 10, No. 3, pp. 2064-2087, 2010.",
    "ou": "Y. Ou, F. Qin, K.-Q. Zhou, P.-F. Yin, L.-P. Mo, and A. M. Zain, “An Improved Grey Wolf Optimizer with Multi-Strategies Coverage in Wireless Sensor Networks”, Symmetry, Vol. 16, No. 3, p. 286, 2024.",
    "nguyen": "H. T. Nguyen, C. D. Van, C. D. Tran, H. M. Ha, S. V. Nguyen, and Q. V. La, “Memetic Algorithm for Maximizing K-Coverage and K-Connectivity in Wireless Sensors Network”, Informatica, Vol. 49, No. 1, pp. 7-18, 2025.",
    "kheam": "H. Kheam, V. Leang, C. Khim, V. N. Vo, and S. Heng, “Research on Coverage Optimization in Wireless Sensor Networks Based on an Improved Sparrow Search Algorithm”, Sensors, Vol. 26, No. 13, p. 4076, 2026.",
    "hydher": "H. Hydher, D. N. K. Jayakody, K. T. Hemachandra, and T. Samarasinghe, “UAV Deployment in WSN System for Emergency/Remote Area Applications”, Computer Networks, Vol. 257, p. 110977, 2025.",
    "mathai": "A. M. Mathai, An Introduction to Geometrical Probability: Distributional Aspects with Applications, Gordon and Breach, Amsterdam, 1999.",
    "simon": "M. K. Simon, Probability Distributions Involving Gaussian Random Variables, Springer, Boston, 2002.",
    "wilcoxon": "F. Wilcoxon, “Individual Comparisons by Ranking Methods”, Biometrics Bulletin, Vol. 1, No. 6, pp. 80-83, 1945.",
    "rappaport": "T. S. Rappaport, Wireless Communications: Principles and Practice, 2nd ed., Prentice Hall, Upper Saddle River, 2002.",
    "bettstetterhartmann": "C. Bettstetter and C. Hartmann, “Connectivity of Wireless Multihop Networks in a Shadow Fading Environment”, Wireless Networks, Vol. 11, No. 5, pp. 571-579, 2005.",
    "wilson": "E. B. Wilson, “Probable Inference, the Law of Succession, and Statistical Inference”, Journal of the American Statistical Association, Vol. 22, No. 158, pp. 209-212, 1927.",
    "clopper": "C. J. Clopper and E. S. Pearson, “The Use of Confidence or Fiducial Limits Illustrated in the Case of the Binomial”, Biometrika, Vol. 26, No. 4, pp. 404-413, 1934.",
    "holm": "S. Holm, “A Simple Sequentially Rejective Multiple Test Procedure”, Scandinavian Journal of Statistics, Vol. 6, No. 2, pp. 65-70, 1979.",
    "fejestoth": "L. Fejes Tóth, “Some Packing and Covering Theorems”, Acta Scientiarum Mathematicarum (Szeged), Vol. 12A, pp. 62-67, 1950.",
    "huangtseng": "C.-F. Huang and Y.-C. Tseng, “The Coverage Problem in a Wireless Sensor Network”, Mobile Networks and Applications, Vol. 10, No. 4, pp. 519-528, 2005.",
    "agrawal": "P. Agrawal and N. Patwari, “Correlated Link Shadow Fading in Multi-Hop Wireless Networks”, IEEE Transactions on Wireless Communications, Vol. 8, No. 8, pp. 4024-4036, 2009.",
    "guo2025": "J. Guo, Y. Sun, T. Liu, Y. Li, and T. Fei, “An Optimization Coverage Strategy for Wireless Sensor Network Nodes Based on Path Loss and False Alarm Probability”, Sensors, Vol. 25, No. 2, p. 396, 2025.",
    "liu2024": "X. Liu, F. Xu, L. Ning, Y. Lv, and C. Zhao, “A Novel Sensor Deployment Strategy Based on Probabilistic Perception for Industrial Wireless Sensor Network”, Electronics, Vol. 13, No. 24, p. 4952, 2024.",
}
ORDER: list[str] = []


def _fmt_nums(nums):
    nums = sorted(set(nums))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(f"{nums[i]}-{nums[j]}" if j - i >= 2 else ", ".join(str(x) for x in nums[i:j + 1]))
        i = j + 1
    return "[" + ", ".join(out) + "]"


def cite(text):
    def rep(m):
        keys = [k.strip().lstrip("@") for k in m.group(1).split(",")]
        nums = []
        for k in keys:
            assert k in REFS, k
            if k not in ORDER:
                ORDER.append(k)
            nums.append(ORDER.index(k) + 1)
        return _fmt_nums(nums)
    return re.sub(r"\[(@[^\]]+)\]", rep, text)


class Paper(Doc):
    def p(self, text):
        super().p(cite(text))

    def table(self, cap, rows, widths, **kw):
        rows = [[cite(c) for c in r] for r in rows]
        return super().table(cite(cap), rows, widths, **kw)


# ----------------------------------------------------------------------------- data
e2 = load("E2_physical.csv")
e5 = load("E5_grids.csv")
summ = load("summary_errors.csv")
e6a = load("E6a_variance.csv")
e6b = load("E6b_sizing.csv")
e7a = load("E7a_connectivity.csv")
e7b = load("E7b_joint.csv")
e8 = load("E8_placement_error.csv")
e16 = load("E16_reliable_lattice.csv")
e16q = lambda kind, sg: next(q for q in e16 if q["kind"] == kind and abs(q["sigma_over_r"] - sg) < 1e-9)
e9 = load("E9_extensions.csv")
e10 = load("E10_baselines_summary.csv")
tests = load("statistical_tests.csv")
n_seeds = len({q["seed"] for q in load(os.path.join("raw", "E10_runs.csv")) if q["method"] == "PSO" and q["N"] == 33})
fried = [t for t in tests if t["family"].startswith("F0.")]
fried_max_p = max(t["p_holm"] for t in fried)
wil = [t for t in tests if t["family"].startswith("F. Comparison")]
wil_sig = sum(1 for t in wil if t["p_holm"] < 0.05)
bin_beta = [t for t in tests if t["family"].startswith("C. Reliability of the beta")]
bin_mean = [t for t in tests if t["family"].startswith("C. Reliability of the mean")]
beta_not_rej = sum(1 for t in bin_beta if t["p_holm"] >= 0.05)
mean_rej = sum(1 for t in bin_mean if t["p_holm"] < 0.05)

err = {(q["experiment"][:2], q["model"]): q for q in summ}
std_rel_exact = sum(abs(q["model_std_exact"] - q["mc_std"]) / q["mc_std"] for q in e6a) / len(e6a)
std_rel_stat = sum(abs(q["model_std_stationary"] - q["mc_std"]) / q["mc_std"] for q in e6a) / len(e6a)
stat_under = [(q["model_std_stationary"] - q["mc_std"]) / q["mc_std"] for q in e6a]
stat_all_under = all(v < 0 for v in stat_under)
stat_n10 = -next((q["model_std_stationary"] - q["mc_std"]) / q["mc_std"] for q in e6a if q["N"] == min(x["N"] for x in e6a))
stat_nmax = -next((q["model_std_stationary"] - q["mc_std"]) / q["mc_std"] for q in e6a if q["N"] == max(x["N"] for x in e6a))
stat_nmin_val, stat_nmax_N = min(x["N"] for x in e6a), max(x["N"] for x in e6a)
beta_rows = [q for q in e6b if q["rule"] == "beta"]
mean_rows = [q for q in e6b if q["rule"] == "mean"]
norm_rows = [q for q in e6b if q["rule"] == "normal"]
beta_lo, beta_hi = min(q["p_meet"] for q in beta_rows), max(q["p_meet"] for q in beta_rows)
mean_lo, mean_hi = min(q["p_meet"] for q in mean_rows), max(q["p_meet"] for q in mean_rows)
norm_lo, norm_hi = min(q["p_meet"] for q in norm_rows), max(q["p_meet"] for q in norm_rows)
beta_ci_ok = sum(q["p_lo"] <= 0.95 <= q["p_hi"] for q in beta_rows)
norm_ci_ok = sum(q["p_lo"] <= 0.95 <= q["p_hi"] for q in norm_rows)
extra = [next(b["N"] for b in beta_rows if b["L"] == m["L"] and b["r"] == m["r"] and b["target"] == m["target"]) / m["N"] - 1
         for m in mean_rows]
extra_lo, extra_hi = min(extra), max(extra)
g625 = next(q for q in e5 if q["r"] == 62.5)
e8_03 = {q["kind"]: q for q in e8 if abs(q["sigma_over_r"] - 0.3) < 1e-9}
e8_05 = {q["kind"]: q for q in e8 if abs(q["sigma_over_r"] - 0.5) < 1e-9}
e8_naive02 = next(q for q in e8 if abs(q["sigma_over_r"] - 0.2) < 1e-9 and q["kind"] == "triangular")
n_rand_mean, n_rand_guar = int(e8[0]["random_mean_rule"]), int(e8[0]["random_guaranteed_rule"])
tri_max = max(q["robust_nodes"] for q in e8 if q["kind"] == "triangular")


def e10q(m, n):
    return next(q for q in e10 if q["method"] == m and q["N"] == n)


meta = ["PSO", "GWO", "ICGWO", "VASF-PSO", "DAR-SSA"]
best_meta33 = max((e10q(m, 33) for m in meta + ["VFA"]), key=lambda q: q["mean"])
e9err = {}
for case in ("k-coverage", "failures-coverage", "failures-connectivity", "probabilistic-sensing"):
    q = [x for x in e9 if x["case"] == case]
    e9err[case] = (sum(abs(x["model"] - x["mc_mean"]) for x in q) / len(q), max(abs(x["model"] - x["mc_mean"]) for x in q))
joint = {(q["rc"], q["target"], q["rule"]): q for q in e7b}
e11m = load("E11_model_check.csv")
e11r = load("E11_rules.csv")
env_cfg_names = list(dict.fromkeys(q["scenario"] for q in e11r))
env = {(q["scenario"], q["rule"]): q for q in e11r}
env_mean_err = max(abs(q["model_cov_mean"] - q["mc_cov_mean"]) for q in e11m)
env_std_rel = sum(abs(q["model_cov_std"] - q["mc_cov_std"]) / q["mc_cov_std"] for q in e11m) / len(e11m)
env_iso_err = sum(abs(q["model_p_no_isolated"] - q["mc_p_no_isolated"]) for q in e11m) / len(e11m)
env_tests = {t["comparison"]: t for t in tests if t["family"].startswith("H. Rules")}
norm99 = [q["p_meet"] for q in norm_rows if q["target"] == 0.99]
norm99_lo, norm99_hi = min(norm99), max(norm99)
tri_saving = max(1 - q["triangular_nodes"] / q["square_nodes"] for q in e5)
tri_saving_min = min(1 - q["triangular_nodes"] / q["square_nodes"] for q in e5)
e8_gap = max(abs(q["mc_mean"] - q["robust_expected"]) for q in e8)
conn_hi_gap = max(abs(x["model"] - x["mc_mean"]) for x in e9 if x["case"] == "failures-connectivity" and x["model"] > 0.9)
e12 = load("E12_risk_sensitivity.csv")
e12_lo = {dl: min(q["p_meet"] for q in e12 if q["delta"] == dl) for dl in (0.01, 0.1)}
e12_hi = {dl: max(q["p_meet"] for q in e12 if q["delta"] == dl) for dl in (0.01, 0.1)}
e12_tests = {t["comparison"]: t for t in tests if t["family"].startswith("I.")}
e12_rej = [c for c, t in e12_tests.items() if t["p_holm"] < 0.05]
e13 = {q["method"]: q for q in load("E13_ilp.csv")}
e14 = load("E14_sleep_scheduling.csv")
e15 = load("E15_heterogeneous.csv")
e15_tests = {t["comparison"]: t for t in tests if t["family"].startswith("K.")}
e15r = lambda rule: [q for q in e15 if q["rule"] == rule]
e15_std_rel = sum(abs(q["model_std"] - q["mc_std"]) / q["mc_std"] for q in e15) / len(e15)
e15_std_max = max(abs(q["model_std"] - q["mc_std"]) / q["mc_std"] for q in e15)

# --- revision experiments (E17-E25)
e17 = load("E17_certification.csv")
e17_final = {}                                   # (part, setting/scenario, target) -> last attempt row
for q in e17:
    key = (q["part"], q["setting"] if q["part"] != "environment" else q["scenario"], q["target"])
    e17_final[key] = q
e17_cov = [q for k, q in e17_final.items() if k[0] == "coverage"]
e17_cert_extra = [int(q["N_certified"]) / int(q["N_rule"]) - 1 for q in e17_final.values() if q["N_certified"] != ""]
e17_n_cert = sum(1 for q in e17_final.values() if q["N_certified"] != "")
e17_first = [q for q in e17 if int(q["attempt"]) == 1]
e17_first_pass = sum(1 for q in e17_first if q["certified"] == "True")
e18 = load("E18_certified_lattice.csv")
e18_final = {}
for q in e18:
    e18_final[(round(q["sigma_over_r"], 2), q["kind"])] = q
e18q = lambda sg, kind: e18_final.get((round(sg, 2), kind))
e19 = load("E19_stress.csv")
e19c = load("E19_calibration.csv")
e19s = load("E19_correlated_shadowing.csv")
e19s_final = {}
for q in e19s:
    e19s_final[q["rho"]] = q
e20 = load("E20_schedule_conditional.csv")
e21 = load("E21_ilp_resolution.csv")
e21q = lambda h, v: next(q for q in e21 if abs(q["spacing"] - h) < 1e-9 and q["variant"] == v)
fejes = int(next(q for q in e21 if q["variant"].startswith("continuous"))["nodes"])
e22 = load("E22_fixed_counts.csv")
e23 = load("E23_runtime.csv")
e23hw = load("E23_hardware.csv")[0]
e23hw["cpu"] = re.sub(r"\((R|TM)\)", "", e23hw["cpu"]).replace("  ", " ").strip()
e24 = load("E24_baseline_sensitivity.csv")
e25 = load("E25_checks.csv")
e25_lat = [q for q in e25 if q["check"] == "lattice connectivity"]
e25_var = {int(q["N"]): q for q in e25 if q["check"] == "variance decomposition"}
e25_dg = [q for q in e25 if q["check"] == "diameter grid spacing"]


def wilson_ci(k, n, z=1.959963984540054):
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


CP_N = 2000
CP_K_MIN = next(k for k in range(CP_N + 1) if sst.beta.ppf(0.005, k, CP_N - k + 1) >= 0.95)
_pass96 = float(sst.binom.sf(CP_K_MIN - 1, CP_N, 0.96))
_p90 = next(p / 10000 for p in range(9500, 10000) if sst.binom.sf(CP_K_MIN - 1, CP_N, p / 10000) >= 0.9)

# ----------------------------------------------------------------------------- document
d = Paper(TEMPLATE)
TITLE = "Statistically Certified Sensor Deployment for Wireless Sensor Networks Using Edge-Corrected Coverage Statistics and Drop-Error-Tolerant Lattices"

# numbers used in the abstract, the introduction and the conclusion
_cov_extra = [int(q["N_certified"]) / int(q["N_rule"]) - 1 for q in e17_cov if q["N_certified"] != ""]
_e17_all = list(e17_final.values())
_e17_cert = [q for q in _e17_all if q["N_certified"] != ""]
_rand_cert = next(q for q in e17_cov if q["L"] == 200 and q["r"] == 25 and q["target"] == 0.99)
_lat03 = e18q(0.3, "triangular")
_lat03_nodes = int(_lat03["nodes_certified"]) if _lat03["nodes_certified"] != "" else None
_stress_cert = sum(1 for q in e19 if q["N_certified"] != "")

ABSTRACT = (
    "Random deployments are usually sized for the expected coverage, so about half of them miss the target. "
    "Here a design rule combines an edge-corrected mean and "
    "variance of area coverage, a Beta approximation of its distribution and an edge-corrected isolated-node "
    "condition; planned drops use a lattice shrunk to absorb drop errors. Each design is then accepted only when a "
    "one-sided Clopper-Pearson bound on its success probability, computed from independent simulated drops with a "
    "Bonferroni correction over attempts, reaches the required level. In sixteen settings the rule met a 95 percent "
    f"target in {beta_lo*100:.0f} to {beta_hi*100:.0f} percent of drops, against {mean_lo*100:.0f} to "
    f"{mean_hi*100:.0f} percent for the mean rule, and certification added at most {max(_cov_extra)*100:.1f} percent "
    "more nodes. With drop errors of 30 percent of the sensing radius, a certified lattice needed "
    f"{_lat03_nodes} nodes and a certified random drop {int(_rand_cert['N_certified'])}. A stress study maps the "
    "operating region of the rule."
)
assert len(ABSTRACT.split()) <= 150, len(ABSTRACT.split())
KEYWORDS = ("Wireless sensor networks, Sensor deployment, Coverage reliability, Statistical certification, "
            "Network connectivity, Boundary effects")


def front(keep):
    t = lambda x, **k: run(x, **k)
    title = (f'<w:p><w:pPr><w:spacing w:before="210" w:after="280" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
             f'{t(TITLE, size=28, b=True)}</w:p>')
    # Both authors share one affiliation, so it is written once (IJIES: do not repeat an affiliation).
    authors = (f'<w:p><w:pPr><w:spacing w:before="120" w:after="120" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
               f'{t(AUTHORS[0], size=22, b=True)}{t("1*", size=22, b=True, va="superscript")}'
               f'{t("     ", size=22)}{t(AUTHORS[1], size=22, b=True)}{t("1", size=22, b=True, va="superscript")}</w:p>')
    aff1 = (f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
            f'{t("1", size=22, va="superscript")}{t(AFFILIATION, size=22)}</w:p>')
    aff2 = ""
    email = (f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
             f'{t("* Corresponding author’s Email: " + EMAIL, size=22)}</w:p>')
    absp = (f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:left="176" w:right="176"/><w:jc w:val="both"/></w:pPr>'
            f'{t("Abstract: ", size=20, b=True)}{t(ABSTRACT, size=20)}</w:p>')
    keyp = (f'<w:p><w:pPr><w:spacing w:before="120" w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:left="176" w:right="176"/><w:jc w:val="both"/></w:pPr>'
            f'{t("Keywords: ", size=20, b=True)}{t(KEYWORDS, size=20)}</w:p>')
    return (keep[0] + title + authors + aff1 + aff2 + email + blank(21) + keep[9] + absp + keyp + keep[12]
            + keep[13] + keep[14])


# ============================================================================= 1. Introduction
d.h1("1. Introduction")
d.p("A wireless sensor network can report only what its nodes observe, so coverage and connectivity are fixed at "
    "deployment time, before any routing or duty-cycling protocol starts [@wang]. On open and accessible sites, nodes "
    "are placed on a planned pattern. Elsewhere they are scattered from a ground vehicle or an unmanned aerial vehicle, "
    "and their final positions are random [@hydher]. In both cases the planner must decide, before the field campaign, "
    "how many nodes to procure and transport.")
d.p("Most practical sizing rules answer that question with an expected value. The simplest estimate adds up the areas "
    "of the sensing disks and ignores their overlap. The Boolean (Poisson) model accounts for overlap but treats the "
    "field as unbounded [@hall, @liutowsley]. A real drop, however, is one draw from a "
    "distribution around that mean. If the number of nodes is chosen so that the mean equals the target, roughly half of the "
    "drops end up below it; in our experiments the share of drops that met the target under the mean rule ranged from "
    f"{pct(mean_lo, 0)} to {pct(mean_hi, 0)}. Border effects aggravate the problem in small and medium fields: a "
    "node near the edge senses partly outside the area of interest, so boundary-blind models over-estimate coverage "
    "[@fan, @liuz]. Connectivity is usually sized "
    "separately, with asymptotic results that are exact only for very large networks [@gupta, @penrose, @bettstetter], "
    "and usually with an ideal disk-shaped radio range that ignores shadow fading [@bettstetterhartmann].")
d.p("Planned deployments have a different weakness. Classical lattice results give the least dense full cover of the "
    "plane [@kershner] and the patterns that join coverage and connectivity [@bai, @zhanghou], and recent tessellation "
    "work extends them to connected k-coverage [@nakka2023, @nakka2024, @nakka2025]. These results assume that every "
    "node lands exactly where it was planned, an assumption that aerial drops violate. Grid layouts are "
    "popular because their coverage is easy to predict, but they are rigid on irregular terrain and costly in "
    "redundant nodes [@priyadarshi]. In parallel, a large body of recent work optimizes "
    "node positions with metaheuristics [@tossa, @bhargavi, @siamantas, @amer, @haris, @shaikh, @ou, @kheam, @saheb, @ahmed]. These "
    "methods maximize coverage for a fixed number of nodes and need thousands of fitness evaluations, yet they report "
    "neither the probability that the layout survives placement errors nor the number of nodes that a given target "
    "requires.")
d.p("This paper addresses one practical question: how many nodes, and in what layout, are needed so that coverage and "
    "connectivity targets hold with a stated probability once boundary effects, node failures and drop errors are "
    "taken into account? We answer it in two steps. Analytical rules propose a node count or a lattice. Because these "
    "rules rest on approximations, their probability statement is not taken at face value: every design is simulated "
    "on drops that played no part in choosing it, and it is reported as certified only when a one-sided confidence "
    "bound on its success probability reaches the required level. The contributions are as follows.")
for item in [
    f"An edge-corrected expression for the mean and the variance of the covered fraction of a square field for a fixed number of nodes, with the variance computed as a double integral over all pairs of points, including the negatively correlated pairs that are farther apart than the sensing diameter. The predicted standard deviation is within {pct(std_rel_exact, 1)} of simulation on average, against {pct(std_rel_stat, 1)} for the usual stationary approximation.",
    f"A design rule built on a moment-matched Beta distribution, stated as an approximation with explicit error terms, and a certification layer that accepts a design only when the one-sided Clopper-Pearson lower bound [@clopper] of its success probability on independent drops reaches 1 − {{{{δ}}}}, with a Bonferroni correction over the attempts of the search. The rule met the 95% target in {pct(beta_lo, 0)} to {pct(beta_hi, 0)} of drops over sixteen settings; {('all ' + str(len(_e17_all))) if len(_e17_cert) == len(_e17_all) else (str(len(_e17_cert)) + ' of the ' + str(len(_e17_all)))} random-drop designs tested were certified, with at most {max(e17_cert_extra) * 100:.1f}% more nodes than the rule.",
    "A joint coverage and connectivity rule based on an edge-corrected isolated-node probability, expected-coverage expressions for node failures, k-coverage and probabilistic (Elfes) sensing, and extensions to heterogeneous sensing radii (as an independent mixture and with fixed class counts), obstacles with line-of-sight sensing, and log-normal shadowing of the links. The same rule sets a randomized sleep schedule, whose reliability is reported both over deployments and for each deployment.",
    "A drop-error-tolerant lattice whose expected coverage under Gaussian placement error is evaluated in closed form through the non-central chi-square distribution, with a fully specified offset search and pruning, a raster-free test of full coverage, a connectivity check after pruning, and certified designs for drop errors up to the sensing radius.",
    "An evaluation against eight baselines with a parameter sensitivity study and measured run time and memory, an integer program at three grid resolutions together with a lower bound that holds for every continuous layout, and a stress study with small networks, very high targets, elongated and irregular fields and correlated link shadowing. All code, seeds, per-drop outcomes and layouts are public, and Table 4 maps every result to its script.",
]:
    d.add(para(rich(cite(item)), jc="both", first_line=0, ind_left=300, hanging=300))
d.p("The rest of the paper is organized as follows. Section 2 reviews related work. Section 3 states the system model "
    "and the inferential objective. Section 4 derives the design rules and the certification procedure. Section 5 "
    "describes the experimental setup and the baselines. Section 6 reports the results, Section 7 discusses threats "
    "to validity, and Section 8 concludes the paper.")

# ============================================================================= 2. Related work
d.h1("2. Related work")
d.p("**Analytical models.** Hall's coverage processes give the covered fraction of a Boolean model [@hall], and Liu "
    "and Towsley applied them to large sensor networks [@liutowsley]. Zhang and Hou showed that coverage implies "
    "connectivity when the communication range is at least twice the sensing range [@zhanghou], and Bai et al. found "
    "patterns that are optimal for both [@bai]. Kumar et al. studied k-coverage of randomly deployed, mostly sleeping "
    "networks [@kumar]. Nakka and Ammari built square and irregular hexagonal tessellations for connected k-coverage in "
    "homogeneous and heterogeneous networks [@nakka2023, @nakka2024, @nakka2025]. Fan et al. showed that uniform "
    "random deployment over-estimates coverage near the field boundary and proposed boundary-assisted deployment "
    "strategies [@fan], and Lazos and Poovendran derived the coverage of networks with heterogeneous sensing regions "
    "[@lazos]. Liu et al. derived critical densities "
    "for k-coverage that include border effects and obstacles [@liuz]. Huang and Tseng reduced the test of whether a "
    "region is covered to the coverage of the sensing perimeters [@huangtseng]. None of "
    "them gives the distribution of coverage for a finite number of nodes, which is what a "
    "reliability statement needs, and none of them models placement error.")
d.p("**Optimization-based deployment.** The virtual force algorithm (VFA) spreads nodes by mutual repulsion [@zou]. "
    "Swarm methods such as particle swarm optimization (PSO) [@kennedy], the grey wolf optimizer (GWO) [@mirjalili] "
    "and the sparrow search algorithm (SSA) [@xue] became the standard tools. Recent examples include a PSO framework for heterogeneous networks that "
    "compares nine deployment strategies, from random and grid placement to drone-assisted drops [@priyadarshi], a genetic "
    "algorithm with a connectivity constraint [@tossa], enhanced PSO with Delaunay triangulation [@bhargavi], PSO for "
    "k-coverage with 1-connectivity [@siamantas], a hybrid Fick's law and PSO method [@amer], deployment for perpetual "
    "target coverage with energy harvesting [@jin], velocity-scaled adaptive search factor PSO (VASF-PSO) [@haris], an "
    "improved chaotic GWO (ICGWO) [@shaikh], a GWO with several search strategies for coverage [@ou], a memetic algorithm for k-coverage and "
    "k-connectivity [@nguyen], a density-aware repulsive SSA (DAR-SSA) [@kheam], a multi-objective bat algorithm that "
    "trades coverage against lifetime and energy [@saheb], and a comparison of multi-objective optimizers for "
    "obstacle-aware deployment [@ahmed]. All of them optimize a fixed node "
    "count and report the coverage they reached in simulation. Exact methods cast placement on a grid of candidate "
    "positions as an integer linear program [@chakrabarty], which gives a reference for the fewest nodes but scales "
    "poorly with the grid size.")
d.p("**Probabilistic sensing and deployment cost.** A second recent line replaces the binary disk by a detection "
    "model. Guo et al. derived a log-distance path-loss model and a Neyman-Pearson detection probability under a "
    "false-alarm constraint, and maximized the coverage rate of a limited number of nodes with a swarm optimizer "
    "[@guo2025]. Liu et al. combined deployment cost, energy, connectivity and sensing probability in one weighted "
    "objective for industrial networks with obstacles and solved it with a hybrid particle swarm and genetic "
    "algorithm [@liu2024]. Both refine what a single node detects; neither states how likely a given number of "
    "randomly or imperfectly placed nodes is to meet a target. The present work keeps the binary disk as its main "
    "model, covers probabilistic (Elfes) sensing in Section 4.4, and asks the complementary question of the node count "
    "and its reliability. Their results are not directly comparable with ours, because the sensing models differ; "
    "our baselines were therefore run under matched assumptions (Section 5).")
d.p("**Scheduling and lifetime.** Redundant nodes can sleep without losing coverage: coverage-preserving "
    "schedules switch off nodes whose disks are covered by neighbors [@tian, @peas], randomly duty-cycled networks "
    "have analytically tractable coverage dynamics [@hsin], and lifetime can be maximized over disjoint coverage sets "
    "[@luo] or measured with coverage-differentiated metrics [@nurcan]. These schedules start from a given deployment; "
    "none of them states how many nodes must be dropped so that the schedule meets a coverage target with a stated "
    "probability.")
d.p("**What is new.** The ingredients are established: the Boolean coverage model [@hall], border corrections of the "
    "mean [@fan, @liuz], the isolated-node view of connectivity [@penrose, @bettstetter], moment matching, exact "
    "binomial bounds [@clopper], the non-central chi-square law [@simon] and the triangular cover [@kershner, @bai]. "
    "What we add is (i) the exact finite-field variance for a fixed node count and its use to size a drop for a "
    "probability target, (ii) a design-then-certify procedure that keeps the design and the certification samples "
    "apart and controls the error of an adaptive search, (iii) the closed-form expected coverage of a perturbed "
    "lattice and lattices sized and certified for drop error, and (iv) the evaluation described above. Unmanned "
    "aerial vehicles now routinely deploy sensor networks in remote areas [@hydher], which makes the drop error a "
    "design variable. Table 1 summarizes where this work sits.")
d.table("Comparison with related deployment studies",
        [["Study", "Finite-field statistics", "Probability statement", "Connected", "Drop error"],
         ["[@liutowsley]", "No", "No", "No", "No"],
         ["[@bai, @zhanghou, @nakka2024, @nakka2025]", "No", "No", "Yes", "No"],
         ["[@fan, @liuz]", "Mean only", "No", "No", "No"],
         ["[@tossa, @siamantas]", "No", "No", "Yes", "No"],
         ["[@haris, @shaikh, @kheam]", "No", "No", "Partly", "No"],
         ["[@priyadarshi]", "No", "No", "Yes", "No"],
         ["[@guo2025, @liu2024]", "No", "No", "No / Yes", "No"],
         ["This work", "Mean and variance", "Rule and certificate", "Yes", "Yes"]],
        [1150, 1100, 850, 800, 740])

# ============================================================================= 3. System model
d.h1("3. System model")
d.p("The field is the square {{F}} = [0, {{L}}]² with area {{A = L^2}}. Each node senses a disk of radius {{r}} "
    "(binary disk model) and talks to every node within the communication range {{R_c}}, so the network is a unit "
    "disk graph. In a random drop the {{N}} positions are independent and uniform over {{F}}. In a planned drop node "
    "{{j}} is aimed at {{g_j}} and lands at {{g_j + e_j}}, where {{e_j}} is a zero-mean Gaussian error with standard "
    "deviation {{σ}} per axis. Each node fails independently with probability {{f}}. The covered fraction {{C}} is "
    "the share of {{F}} that lies inside at least one disk. The designer gives a target coverage {{C_t}} and a risk "
    "level {{δ}}, and asks for the smallest {{N}} for which the coverage target is met and the network is connected "
    "with joint probability at least {{1 − δ}}; when only coverage matters, the condition is {{P(C ≥ C_t) ≥ 1 − δ}}.")
d.p("**Inferential objective.** For a design {{D}} (a node count for a random drop, or a lattice together with an error "
    "level {{σ}} for a planned drop), let {{p(D)}} be the probability that one drop meets the requirement. The "
    "probability is taken over node positions, failures and link states only; the field, the radii and the error "
    "model are fixed. The objective is {{p(D) ≥ 1 − δ}}. The rules of Section 4 give designs for which this holds "
    "approximately. A design is called certified at confidence {{1 − α}} ({{α}} = 0.05) when a one-sided lower "
    "confidence bound of {{p(D)}}, computed from simulated drops that were not used to choose {{D}}, is at least "
    "{{1 − δ}} (Section 4.6). The certificate refers to the stated model, not to a particular site.")

# ============================================================================= 4. Framework
d.h1("4. Proposed framework")
d.p("Fig. 1 shows the framework: two rules size a random drop, planned drops use the error-tolerant lattice "
    "of Section 4.5, and every design passes the certification of Section 4.6 before it is reported.")
d.figure(os.path.join(FIG, "paper_fig1_framework.png"), "Proposed deployment design framework")

d.h2("4.1 Mean coverage with boundary effects")
d.p("The linear estimator, which adds the disk areas and ignores their overlap, and the Poisson model [@hall] are")
d.eq(r"C_{\mathrm{lin}}=\min\left\{1,\frac{N\pi r^{2}}{A}\right\}")
d.eq(r"C_{\mathrm{P}}=1-\exp\left(-\frac{N\pi r^{2}}{A}\right)")
d.p("Neither model accounts for the field boundary. Let {{a(x)}} be the probability that one uniformly placed node "
    "covers the point {{x}}, that is, the area of the sensing disk centered at {{x}} that lies inside {{F}}, divided by {{A}},")
d.eq(r"a(\mathbf{x})=\frac{\left|D(\mathbf{x},r)\cap F\right|}{A}")
d.p("which equals {{πr^2/A}} in the interior and drops to about a quarter of that at a corner. A point at {{x}} is "
    "missed by one uniform node with probability {{1 − a(x)}}, and by all of them with probability "
    "{{(1 − a(x))^N}}. Averaging over the field gives the exact mean")
d.eq(r"\mathrm{E}\left[C\right]=\frac{1}{A}\int_{F}\left[1-\left(1-a(\mathbf{x})\right)^{N}\right]d\mathbf{x}")
d.p("We evaluate {{a(x)}} on a 240 × 240 grid of points by the midpoint rule with 400 nodes along the chord direction.")

_v10, _v200 = e25_var[10], e25_var[200]
_infl10 = math.sqrt(_v10["var_near"] / _v10["var_total"])
d.h2("4.2 Variance of the covered fraction")
d.p("Let {{a(x, y)}} be the probability that one node covers both {{x}} and {{y}}, that is, the area of the "
    "lens {{D(x, r) ∩ D(y, r) ∩ F}} divided by {{A}}. For {{N}} independent nodes both points stay uncovered with "
    "probability {{u(x, y)^N}}, and the variance of {{C}} is")
d.eq(r"\mathrm{Var}\left(C\right)=\frac{1}{A^{2}}\int_{F}\int_{F}\left[u(\mathbf{x},\mathbf{y})^{N}-\left(1-a(\mathbf{x})\right)^{N}\left(1-a(\mathbf{y})\right)^{N}\right]d\mathbf{x}\,d\mathbf{y}")
d.eq(r"u(\mathbf{x},\mathbf{y})=1-a(\mathbf{x})-a(\mathbf{y})+a(\mathbf{x},\mathbf{y})")
d.p("Two kinds of pairs contribute. Points closer than {{2r}} share the lens, and their coverage indicators are "
    "positively correlated. Points farther apart have {{a(x, y) = 0}}, and their covariance "
    "{{(1 − a(x) − a(y))^N − (1 − a(x))^N (1 − a(y))^N}} is negative: with a fixed number of nodes, a node that covers "
    "{{x}} cannot also cover {{y}}. This far-pair term vanishes only when the node count is Poisson distributed. "
    "Eq. (5) therefore runs over all pairs. We discretize it on an {{M × M}} grid of points, "
    "{{M = min(80, max(50, ⌈4L/r⌉))}}, and obtain all {{a(x, y)}} at once from a sparse incidence matrix between the "
    "grid points and 200 × 200 area elements of the field; the sum includes all {{M^4}} pairs, and one evaluation takes "
    "about one second. In the 200 m field with {{r}} = 20 m the far pairs cancel "
    f"{pct(-_v10['var_far'] / _v10['var_near'], 0)} of the near-pair contribution at {{{{N}}}} = 10 and "
    f"{pct(-_v200['var_far'] / _v200['var_near'], 0)} at {{{{N}}}} = 200; leaving them out would overstate the "
    f"standard deviation by a factor of {_infl10:.1f} at {{{{N}}}} = 10. The usual stationary shortcut replaces "
    "{{a(x)}} by its interior value and integrates the covariance against the distance density of two random points "
    "in a square [@mathai]. It keeps the far pairs, but it ignores the fact that border points have both smaller and "
    "more variable coverage.")

d.h2("4.3 Probabilistic design rule")
d.p("{{C}} is bounded in [0, 1] and becomes strongly skewed as it approaches 1, so a normal approximation puts too "
    "much mass above the target. We match a Beta distribution to the mean {{μ_N}} and variance {{s_N^2}} from "
    "Eqs. (4) and (5),")
d.eq(r"\alpha_{N}=\mu_{N}\nu_{N},\quad \beta_{N}=\left(1-\mu_{N}\right)\nu_{N},\quad \nu_{N}=\frac{\mu_{N}\left(1-\mu_{N}\right)}{s_{N}^{2}}-1")
d.p("and take the smallest node count whose upper tail clears the risk level,")
d.eq(r"N_{\mathrm{cov}}=\min\left\{N:\;1-I_{C_{t}}\left(\alpha_{N},\beta_{N}\right)\geq 1-\frac{\delta}{2}\right\}")
d.p("where {{I_x(α, β)}} is the regularized incomplete beta function. Half of the risk is reserved for connectivity "
    "(Section 4.4). Because Eq. (8) is monotone in {{N}} in practice, a doubling search followed by bisection needs "
    "about fifteen evaluations of Eqs. (4) and (5). When only coverage matters, {{δ/2}} is replaced by {{δ}}. The rule "
    "is approximate in two places, the Beta shape and the quadrature of Eqs. (4) and (5), so we use "
    "{{N_cov}} as a design value and do not claim that {{P(C ≥ C_t) ≥ 1 − δ/2}} holds exactly.")

d.h2("4.4 Connectivity, failures and extensions")
d.p("A network with an isolated node cannot be connected, and the two events coincide as the node count grows "
    "[@penrose, @bettstetter]. With {{b(x)}} defined like {{a(x)}} but for radius {{R_c}}, the expected number of "
    "isolated nodes and the resulting Poisson approximation are")
d.eq(r"\mathrm{E}\left[N_{\mathrm{iso}}\right]=\frac{N}{A}\int_{F}\left(1-b(\mathbf{x})\right)^{N-1}d\mathbf{x},\qquad P_{\mathrm{conn}}\approx e^{-\mathrm{E}\left[N_{\mathrm{iso}}\right]}")
d.p("The connectivity rule {{N_conn}} is the smallest {{N}} with {{P_conn ≥ 1 − δ/2}}, and the joint design value is")
d.eq(r"N^{\star}=\max\left(N_{\mathrm{cov}},\,N_{\mathrm{conn}}\right)")
d.p("The union bound gives, at {{N^⋆}},")
d.eq(r"P\left(C\geq C_{t}\wedge\mathrm{connected}\right)\geq 1-\delta-\varepsilon_{\mathrm{cov}}-\varepsilon_{\mathrm{conn}}")
d.p("where {{ε_cov = P(C < C_t) − δ/2}} and {{ε_conn = P(not connected) − (1 − P_conn)}} are the signed errors of the "
    "Beta and of the isolated-node approximations. Only the union bound in Eq. (11) is exact. The error terms have "
    "no analytical bound, and {{ε_conn}} is positive whenever a network without isolated nodes can still split, which "
    "happens at low connectivity and among obstacles. Eq. (10) is therefore an approximate design rule; the "
    "probability statement comes from the certificate of Section 4.6. "
    "With independent failures the surviving nodes are again uniformly distributed, so failures multiply {{a(x)}}, {{a(x, y)}} and "
    "{{b(x)}} by {{1 − f}} in every expression above, and in Eq. (9) the prefactor {{N}} becomes {{(1 − f)N}}. The expected k-covered fraction and the expected detection "
    "probability under the Elfes sensing model, in the form used in [@zou], follow the same pattern:")
d.eq(r"\mathrm{E}\left[C_{k}\right]=\frac{1}{A}\int_{F}\sum_{i=k}^{N}\binom{N}{i}a(\mathbf{x})^{i}\left(1-a(\mathbf{x})\right)^{N-i}d\mathbf{x}")
d.eq(r"p(d)=\begin{cases}1, & d\leq r-r_{e}\\ e^{-\lambda\left(d-r+r_{e}\right)^{\gamma}}, & r-r_{e}<d<r+r_{e}\\ 0, & d\geq r+r_{e}\end{cases}")
d.eq(r"\mathrm{E}\left[P_{\mathrm{det}}\right]=\frac{1}{A}\int_{F}\left[1-\left(1-\frac{1}{A}\int_{F}p\left(\left|\mathbf{x}-\mathbf{y}\right|\right)d\mathbf{y}\right)^{N}\right]d\mathbf{x}")
d.p("The inner integral in Eq. (14) is a convolution of the field indicator with {{p(d)}} and is computed with one "
    "fast Fourier transform.")

_dg_hold = [q for q in e25_dg if q.get("note", "") != "" and str(q["full_cover_condition"]) == "True"]
d.h2("4.5 Lattices and drop errors")
d.p("An intuitive planned layout is a square grid whose spacing equals the sensing diameter: "
    "{{n = ⌈L/(2r)⌉ + 1}} nodes per side, including the field boundary, with spacing {{h = L/(n − 1) ≤ 2r}}. The point "
    "of a grid cell farthest from the four nodes at its corners is the cell center, at {{h/√2}}, so the grid covers the "
    "field if and only if {{h ≤ √2r}}. When {{L/(2r)}} is an integer, {{h = 2r}}, neighboring disks just touch, and the "
    "grid covers only")
d.eq(r"C_{\mathrm{grid}}=\frac{\pi r^{2}}{\left(2r\right)^{2}}=\frac{\pi}{4}\approx 0.785")
d.p("of the field, whatever its size. For other ratios the spacing is shorter and the condition can hold: with "
    "{{L/(2r)}} = 1.1, {{n}} = 3 and {{h}} = 1.1{{r}} ≤ √2{{r}}, so the field is covered. Writing {{m = L/(2r)}}, the "
    "condition {{⌈m⌉ ≥ √2m}} holds only for {{m ≤ 1/√2}}, {{1 < m ≤ √2}} and {{2 < m ≤ 3/√2 ≈ 2.12}}; for larger "
    "fields the diameter-spaced grid never covers the field. Placing nodes at the centers of square cells of side "
    "{{h ≤ √2r}} covers every point, because no point of a cell is farther than {{h/√2}} from its center:")
d.eq(r"n=\left\lceil \frac{L}{\sqrt{2}\,r}\right\rceil ,\qquad h=\frac{L}{n},\qquad R_{c}\geq h")
d.p("The triangular lattice, with neighbors {{√3r}} apart in rows {{1.5r}} apart and every second row shifted by "
    "{{√3r/2}}, is the least dense full cover of the plane [@kershner] and needs {{R_c ≥ √3r}} for connectivity "
    "[@bai]. We build it in six steps (Algorithm 2 in Table 2). (i) Offsets: the lattice origin is moved over the "
    "{{P × P}} offsets {{(i√3r/P, 1.5jr/P)}}, {{i, j}} = 0, ..., {{P}} − 1 ({{P}} = 6 in Table 9, 4 elsewhere). "
    "(ii) Candidates: every lattice point whose disk reaches the field is kept, so some nodes lie just outside it. "
    "(iii) Design raster: an offset is discarded unless every cell center of a {{G × G}} raster is covered "
    "({{G}} = 400 in Table 9, 250 elsewhere). (iv) Pruning: nodes are visited in increasing order of the number of "
    "raster points they cover, and a node is deleted when each of its points is still covered by another remaining "
    "node. (v) Selection: the offset with the fewest remaining nodes is kept, the first one on ties. "
    "(vi) Verification: a raster cannot exclude small gaps between its points, so the selected layout is checked "
    "without a raster. Following the perimeter criterion of Huang and Tseng [@huangtseng], the field is covered if "
    "every point of the four field edges lies in some disk and every point of each sensing circle inside the field "
    "lies in the disk of another node. Both conditions reduce to unions of intervals, which we evaluate in closed "
    "form with a relative tolerance of 10⁻⁹ on {{r}}. If the test fails, steps (i)-(v) are repeated on a 0.5 m "
    "raster. Pruning removes border nodes only, but it could still disconnect the communication graph, so the "
    "graph of every pruned lattice is also checked at {{R_c = √3r}}.")
d.p("For a planned drop, {{|g_j + e_j − x|^2/σ^2}} follows a non-central chi-square law with two degrees of freedom "
    "and non-centrality {{|g_j − x|^2/σ^2}} [@simon]. The node covers {{x}} with probability {{P_j(x)}}, and "
    "independence across nodes gives the exact expected coverage")
d.eq(r"P_{j}(\mathbf{x})=F_{\chi'^{2}_{2}}\left(\frac{r^{2}}{\sigma^{2}};\,\frac{\left|\mathbf{g}_{j}-\mathbf{x}\right|^{2}}{\sigma^{2}}\right)")
d.eq(r"\mathrm{E}\left[C_{\sigma}\right]=\frac{1}{A}\int_{F}\left[1-\prod_{j}\left(1-P_{j}(\mathbf{x})\right)\right]d\mathbf{x}")
d.p("The error-tolerant lattice is designed for a shrunken radius {{κr}}, and {{κ}} is lowered in steps of 0.02 until "
    "Eq. (18) reaches the target. Eq. (18) controls only the mean. When the target must hold with probability "
    "{{1 − δ}}, {{κ}} is lowered instead until the lower end of the 95% Wilson interval of the share of 500 simulated "
    "drops with {{C ≥ C_t}} reaches {{1 − δ}}; the same random-number seed is used for every {{κ}} (common random "
    "numbers). This search sample serves only to propose {{κ}}: choosing the first {{κ}} that passes among many "
    "makes its Wilson interval optimistic, so the proposed lattice is then certified on new drops (Section 4.6).")

d.h2("4.6 Design and certification samples")
d.p("The rules and searches above produce designs; they do not certify them. A design {{D}} is certified with "
    f"{CP_N:,} new simulated drops. If {{{{K_D}}}} of them meet the requirement, the one-sided Clopper-Pearson "
    "lower bound [@clopper]")
d.eq(r"p_{L}=B^{-1}\left(\alpha';\,K_{D},\,n_{\mathrm{c}}-K_{D}+1\right)")
d.p("where {{B^{-1}(·; a, b)}} is the quantile function of the Beta({{a, b}}) distribution, {{n_c}} the number of drops "
    "and {{p_L = 0}} for {{K_D = 0}}, satisfies {{P(p_L ≤ p(D)) ≥ 1 − α'}} for every true {{p(D)}}. {{D}} is accepted "
    "when {{p_L ≥ 1 − δ}}, which is an exact one-sided binomial test of {{p(D) < 1 − δ}} at level {{α'}}. If {{D}} "
    "fails, it is strengthened (the node count grows by {{max(1, ⌈0.02N_0⌉)}}, where {{N_0}} is the rule value, or "
    "{{κ}} falls by 0.02) and a new, independent sample is drawn. At most {{K}} = 10 attempts are made, each at "
    "{{α' = α/K}} = 0.005, so by the Bonferroni inequality the probability that the procedure returns a design with "
    "{{p(D) < 1 − δ}} is at most {{α}} = 0.05, whatever the order of the attempts: each attempt uses fresh drops, "
    "so given the design it tests, it accepts a design that falls short with probability at most {{α'}}. If no "
    "attempt passes, the design is reported as not certified. Samples are never reused. The lattice search sample "
    "(500 drops), the simulated connectivity search of Section 4.7 (2,000 graphs per {{N}}) and the 300 to 1,000 "
    "validation drops of Sections 6.2 to 6.9 estimate how well a rule is calibrated; a share above 95% in those "
    "samples, or a Wilson interval that contains 95%, is not treated as evidence that a design meets "
    f"{{{{p(D) ≥ 1 − δ}}}}. With {CP_N:,} drops and {{{{α'}}}} = 0.005, at least {CP_K_MIN:,} successes "
    f"({pct(CP_K_MIN / CP_N, 2)}) are needed for {{{{p_L}}}} ≥ 0.95: a design whose true success probability is "
    f"0.96 passes with probability {_pass96:.2f}, and passing with probability 0.9 needs about {_p90:.3f}. This margin "
    "is the price of a one-sided statement. Table 2 gives the three procedures.")
d.table("Pseudocode of the design and certification procedures",
        [["Algorithm 1: random drop (design)"],
         ["Input {{L, r, R_c, C_t, δ, f}}\n1: {{N_cov}} ← doubling and bisection on Eq. (8)\n2: {{N_conn}} ← doubling and bisection on Eq. (9)\n3: return {{N_0}} = max({{N_cov}}, {{N_conn}}) and pass it to Algorithm 3"],
         ["Algorithm 2: planned drop (design)"],
         ["Input {{L, r, σ, C_t}} (and {{δ}})\n1: {{κ}} ← 1\n2: build the triangular (or square) lattice for radius {{κr}}: offsets, candidates,\n    raster test, pruning, selection, exact coverage and connectivity checks\n3: mean design: if Eq. (18) ≥ {{C_t}} return lattice;\n    reliability design: if the Wilson lower bound of P({{C ≥ C_t}}) over 500\n    search drops ≥ {{1 − δ}} pass the lattice to Algorithm 3\n4: {{κ}} ← {{κ}} − 0.02 and go to 2"],
         ["Algorithm 3: certification"],
         ["Input design {{D_1}}, {{δ}}, {{α}} = 0.05, {{K}} = 10, {{n_c}} = 2,000\n1: for {{k}} = 1, ..., {{K}}: draw {{n_c}} new drops of {{D_k}}, count successes {{K_D}}\n2:    {{p_L}} ← Eq. (19) with {{α' = α/K}}\n3:    if {{p_L ≥ 1 − δ}} return {{D_k}} (certified)\n4:    next design: {{D_k}} with {{⌈0.02N_0⌉}} more nodes, or {{κ}} − 0.02\n5: return not certified"]],
        [4600], header_rows=0, align=["left"])

d.h2("4.7 Obstacles and shadowing")
d.p("Practical sites contain buildings and other obstacles [@liuz, @ahmed]. Let {{F_f}} be the part of the field outside the obstacles {{O}}, let nodes "
    "fall uniformly over {{F_f}}, and let a node sense a point only when the segment between them crosses no "
    "obstacle. Eq. (3) then becomes")
d.eq(r"a(\mathbf{x})=\frac{\left|\left\{\mathbf{y}\in F_{f}:\,\left|\mathbf{x}-\mathbf{y}\right|\leq r,\ \left[\mathbf{x},\mathbf{y}\right]\cap O=\emptyset\right\}\right|}{\left|F_{f}\right|}")
d.p("and every integral over {{F}} in Eqs. (4), (5) and (9) runs over {{F_f}}. For the radio we use log-distance path loss "
    "with exponent {{η}} and log-normal shadowing with standard deviation {{σ_s}} dB, independent across links "
    "[@rappaport, @bettstetterhartmann]. With {{R_c}} the median range and an extra loss {{L_o}} for a link that "
    "crosses an obstacle, two nodes at {{x}} and {{y}} are linked with probability")
d.eq(r"\ell(\mathbf{x},\mathbf{y})=\Phi\left(\frac{10\eta\log_{10}\left(R_{c}/\left|\mathbf{x}-\mathbf{y}\right|\right)-L_{o}\,o_{\mathbf{x}\mathbf{y}}}{\sigma_{s}}\right)")
d.eq(r"b(\mathbf{x})=\frac{1}{\left|F_{f}\right|}\int_{F_{f}}\ell(\mathbf{x},\mathbf{y})\,d\mathbf{y}")
d.p("where {{o_xy}} is 1 when the segment crosses an obstacle and 0 otherwise. Eq. (21) reduces to the unit disk as "
    "{{σ_s → 0}}, and with Eq. (22) in place of the disk area, Eqs. (9) and (10) apply unchanged. Both "
    "{{a(x)}} and {{b(x)}} are computed on rasters with an exact segment-rectangle test. Eq. (9) counts isolated "
    "nodes only. Buildings can split the network into large pieces in which every node still has a neighbor, so "
    "in obstructed fields Eq. (9) may overstate connectivity. We therefore also size the connectivity term by "
    "simulation: starting from the {{N_conn}} given by Eqs. (9) and (22), {{N}} is raised in steps of five until the "
    "connected share of 2,000 simulated link graphs reaches {{1 − δ/2}}, and the smallest qualifying {{N}} within "
    "the last step of five is kept; when the starting value already qualifies, the four counts below it are checked "
    "as well. This search proposes {{N}}; the resulting joint design is certified by Algorithm 3. The coverage term "
    "stays analytical. Shadowing of links that share a node is correlated in practice [@agrawal]; Section 6.10 "
    "tests the rule when the shadowing of each link has a component shared by its two end nodes.")

d.h2("4.8 Heterogeneous radii and sleep scheduling")
d.p("If each node draws its sensing radius independently from {{r_m}} with probability {{w_m}} (an independent "
    "mixture), one node covers {{x}} with probability")
d.eq(r"a(\mathbf{x})=\sum_{m}w_{m}\,a_{m}(\mathbf{x}),\qquad a(\mathbf{x},\mathbf{y})=\sum_{m}w_{m}\,a_{m}(\mathbf{x},\mathbf{y})")
d.p("where {{a_m}} uses radius {{r_m}}, so Eqs. (4)-(8) apply unchanged [@lazos]. Under Eq. (23) the number of nodes "
    "in each class is binomial. A deployment with fixed class counts {{N_m}}, for example exactly half of the nodes "
    "with each radius, has instead")
d.eq(r"P\left(\mathbf{x}\ \mathrm{uncovered}\right)=\prod_{m}\left(1-a_{m}(\mathbf{x})\right)^{N_{m}},\qquad P\left(\mathbf{x},\mathbf{y}\ \mathrm{uncovered}\right)=\prod_{m}u_{m}(\mathbf{x},\mathbf{y})^{N_{m}}")
d.p("with {{u_m}} as in Eq. (6) for radius {{r_m}}; these replace {{(1 − a(x))^N}} and {{u(x, y)^N}} in Eqs. (4) and "
    "(5). The mixture variance also carries the variation of the class counts and was the larger of the two in our "
    "settings. For "
    "scheduling, every node wakes independently with probability {{q}} in each round [@hsin]. The awake nodes form a "
    "thinned uniform drop, so they enter every expression above through {{a(x) → q a(x)}}, as failures do with "
    "{{f = 1 − q}}. For a deployment of {{N}} nodes the schedule uses the smallest {{q}} that keeps the coverage and "
    "connectivity conditions of Eqs. (8) and (9),")
d.eq(r"q^{\star}=\min\left\{q:\;P\left(C_{q}\geq C_{t}\right)\geq 1-\frac{\delta}{2},\;P_{\mathrm{conn},q}\geq 1-\frac{\delta}{2}\right\}")
d.p("found by bisection on a 0.01 grid. Eq. (25) is an ensemble statement: it averages over deployments and wake-up "
    "patterns. One deployment, used for many rounds, has its own conditional reliability, which can be lower; "
    "Section 6.11 reports its distribution. Each node is active in a share {{q^⋆}} of the rounds, so with the "
    "first-order radio model [@heinzelman] the expected communication energy per round falls by the factor "
    "{{q^⋆}} and the number of rounds that the energy budget allows grows by {{1/q^⋆}}. This energy figure is kept "
    "separate from a battery-depletion lifetime, which would require simulating the order in which nodes die. In "
    "each round every awake node sends and receives one packet over the distance {{R_c}}.")
# ============================================================================= 5. Setup
d.h1("5. Experimental setup")
d.p("All methods were implemented in Python 3 with NumPy and SciPy, and each run used one processor core. Coverage of a "
    "layout is the share of cell centers of a regular raster that fall inside at least one disk; Table 4 gives the "
    "raster and the quadrature of every experiment. Means are reported with standard deviations or Student t "
    "intervals, and shares of drops with two-sided Wilson 95% intervals [@wilson]; these describe calibration. "
    "Certification uses the one-sided Clopper-Pearson bound of Section 4.6 on separate drops. Shares are tested "
    "against their nominal value with the exact binomial test, paired comparisons use "
    "the Wilcoxon signed-rank test [@wilcoxon] with the matched-pairs rank-biserial correlation as effect size, and "
    "the nine deployment methods are compared with the Friedman test, using seeds as blocks. Within each family of "
    "tests the p-values are corrected with the Holm-Bonferroni procedure [@holm]. Table 3 lists the settings of each "
    "experiment.")
d.table("Simulation settings",
        [["Experiment", "Field (m)", "Parameters", "Runs"],
         ["Mean model", "200", "{{r}} = 10-25 m, {{N}} = 10-200", "100"],
         ["Variance, sizing", "200, 400", "{{r}} = 15-25 m, {{C_t}} = 0.80-0.99, {{δ}} = 0.05", "300"],
         ["Certification", "200, 400", "designs of the sizing, joint and environment rows", "2,000 / attempt"],
         ["Connectivity", "200", "{{r}} = 20 m, {{R_c}} = 30, 40 m", "300 / 500"],
         ["Lattices", "500", "{{r}} = 25-100 m", "exact"],
         ["Drop error", "500", "{{r}} = 62.5 m, {{σ/r}} = 0-1, {{C_t}} = 0.99, {{δ}} = 0.05", "100-2,000"],
         ["Baselines", "500", "{{r}} = 62.5 m, {{N}} = 25-36; 11 variants at {{N}} = 33", f"{n_seeds} / 10 seeds"],
         ["Extensions", "200", "{{r}} = 20 m, {{R_c}} = 40 m, {{k}} = 1-3, {{f}} = 0.1-0.3, Elfes", "100"],
         ["Risk level", "200", "{{r}} = 20 m, {{C_t}} = 0.80-0.99, {{δ}} = 0.01, 0.10", "1,000"],
         ["Heterogeneous", "200", "{{r}} = 15 / 25 m, mixture and fixed halves, {{C_t}} = 0.80-0.99", "500 / 1,000"],
         ["Scheduling", "200", "{{r}} = 20 m, {{R_c}} = 40 m, {{C_t}} = 0.9, {{N}} = 1-3 × {{N^⋆}}", "500; 200 × 300"],
         ["ILP", "500", "{{r}} = 62.5 m, 10, 12.5 and 20 m grids", "20 min"],
         ["Environment", "200", "{{r}} = 20 m, {{R_c}} = 40 m, {{C_t}} = 0.9, {{η}} = 3, {{σ_s}} = 0/8 dB, {{L_o}} = 20 dB", "300 / 500"],
         ["Stress", "100-400", "{{r}} = 20, 40 m, {{C_t}} up to 0.999, five field shapes, link correlation 0-0.45", "1,000 / 2,000"],
         ["Run time", "200, 500", "all steps and baselines, one core", "3 calls"]],
        [1150, 650, 1900, 900])
d.table("Reproducibility map: experiment, raster or quadrature ({{G}}² = {{G × G}} cell centers) and first seed of every "
        "result. Each ID runs with run_experiments.py --exp ID and config/experiments.yaml; per-drop outcomes are in "
        "results/raw/ID_runs.csv, layouts in results/raw/layouts, every seed in results/raw/seed_manifest.csv. Design, "
        "validation and certification samples use separate seeds, and all test families are in "
        "results/statistical_tests.csv",
        [["Result", "ID", "Raster or quadrature", "Seed base"],
         ["Fig. 2, Table 6", "E2", "200²; model 240², 400 nodes", "2,000"],
         ["Fig. 3", "E6a", "200²; {{M}} = 50-80, 200² cells", "6,000"],
         ["Fig. 4, Table 7", "E6b", "200² (300² at 400 m)", "6,100"],
         ["Table 8", "E17", "as E6b, E7b and E11", "50,000"],
         ["Fig. 5, Section 6.4", "E7, S2", "200²", "7,000"],
         ["Table 9", "E5, E25", "400², 1000², exact test", "none"],
         ["Section 6.5 (ILP)", "E13, E21", "10-20 m grids; 250², 1000²", "none"],
         ["Fig. 6, Table 10", "E8, E16, E18", "250², 150², 200²", "8,000"],
         ["Fig. 7, Table 11", "E10", "80², 250²", "10,000"],
         ["Table 12", "E24", "as E10 (same seeds)", "10,000"],
         ["Table 13", "E23", "as E10 and E6b", "68,000"],
         ["Section 6.8", "E9", "200²", "9,000"],
         ["Fig. 8", "E11", "200²; model 80², 200²", "11,000"],
         ["Fig. 9, Table 14", "E19", "1 m cells; 200²", "58,000"],
         ["Table 15", "E12", "200²", "12,000"],
         ["Section 6.11", "E15, E22", "200²", "15,000"],
         ["Table 16", "E14, E20", "200²; 100²", "14,000"]],
        [1450, 1000, 1400, 750])
d.p("**Baselines.** We compared the proposed lattice with random placement, VFA [@zou], PSO [@kennedy], GWO "
    "[@mirjalili], a real-coded genetic algorithm (GA) [@holland, @eshelman], and three methods published after 2024: VASF-PSO "
    "[@haris], ICGWO [@shaikh] and DAR-SSA [@kheam]. "
    "The last three were re-implemented from their published descriptions; details that the papers leave open were "
    "set to common default values and are listed in Table 5 and in the code. All population methods used 30 agents "
    "and 300 iterations, that is, the same budget of 9,030 fitness evaluations, the same 80 × 80 fitness raster, the "
    "same field-boundary clipping and the same final 250 × 250 evaluation raster. Every method returns the best layout "
    "found during its run; GWO and ICGWO keep the three best solutions found so far as leaders, as in the reference "
    "implementation [@mirjalili]. No method was tuned to this problem: each used its published or default parameters, "
    "and all methods received the same 30 seeds per node count. Because default values can favor or penalize a "
    "re-implementation, Table 12 repeats the three recent methods with eleven other settings, including a population "
    "of 60 and a doubled budget. VFA uses no fitness function and ran for 400 iterations. "
    "For a fixed node count {{N}}, the proposed layout is the pruned triangular lattice built for the smallest design "
    "radius that needs at most {{N}} nodes, found by bisection over [0.3{{r}}, 3{{r}}]. When {{N}} exceeds the count of a "
    "full cover, the design radius falls below {{r}} and the spare nodes become overlap. All methods share the binary "
    "disk model, the field and the evaluation raster, so the comparison is made under matched assumptions. Run times "
    f"were measured on one core of the same machine ({e23hw['cpu'].split(' @')[0]}).")
d.table("Baseline settings (equal budget of 9,030 evaluations)",
        [["Method", "Settings"],
         ["PSO [@kennedy]", "{{w}} = 0.729, {{c_1 = c_2}} = 1.494"],
         ["GA [@holland]", "Binary tournament, BLX-0.5 crossover [@eshelman] ({{p_c}} = 0.9), Gaussian mutation ({{p_m}} = 1/2{{N}}, 0.05{{L}}), 2 elites"],
         ["GWO [@mirjalili]", "{{a}}: 2 → 0 linearly"],
         ["ICGWO [@shaikh]", "Logistic-map start, {{a}}: 2 → 0 quadratically"],
         ["VASF-PSO [@haris]", "Hammersley start, {{w}}: 0.9 → 0.4, {{c_1}}: 2.5 → 0.5, {{c_2}}: 0.5 → 2.5, step scaled by distance to best"],
         ["DAR-SSA [@kheam]", "Producers 80% → 20%, ST = 0.8, SD = 0.2, soft-core repulsion, {{ρ = √3r/2}}"],
         ["VFA [@zou]", "Repulsion below {{√3r}}, weak attraction up to {{1.5√3r}}, 400 iterations"]],
        [1350, 3250])

# ============================================================================= 6. Results
d.h1("6. Results and discussion")
d.h2("6.1 Accuracy of the mean model")
lin = err[("E2", "linear_no_overlap")]
poi = err[("E2", "poisson_exp")]
exa = err[("E2", "exact_edge")]
_e2_30 = next(q for q in e2 if q['r'] == 20 and q['N'] == 30)
d.p(f"Fig. 2 compares the three mean models with simulation for {{{{r}}}} = 20 m in a 200 m field. For 30 nodes the "
    f"linear estimator predicts {pct(_e2_30['linear_no_overlap'], 0)} coverage, whereas simulation gives "
    f"{pct(_e2_30['mc_mean'], 0)}, and it saturates at 1 from about 32 nodes. The Poisson model follows the shape of "
    f"the curve but stays above it, because it treats border disks as if they lay entirely inside the field. The "
    f"edge-corrected model of Eq. (4) agrees with the simulated means. "
    f"Over the 80 settings of Table 6 its mean absolute error is {exa['MAE']:.4f}, against {poi['MAE']:.3f} for the "
    f"Poisson model and {lin['MAE']:.3f} for the linear estimator.")
d.figure(os.path.join(FIG, "paper_fig2_models.png"), "Mean coverage of the three models against simulation (200 m field, sensing radius 20 m)")
d.table("Error of the mean models against 100-run simulation means (200 m field, {{r}} = 10-25 m, {{N}} = 10-200; 80 settings)",
        [["Model", "MAE", "RMSE", "Max error"],
         ["Linear estimator", f"{lin['MAE']:.3f}", f"{lin['RMSE']:.3f}", f"{lin['MaxAbs']:.3f}"],
         ["Poisson model", f"{poi['MAE']:.3f}", f"{poi['RMSE']:.3f}", f"{poi['MaxAbs']:.3f}"],
         ["Edge-corrected, Eq. (4)", f"{exa['MAE']:.4f}", f"{exa['RMSE']:.4f}", f"{exa['MaxAbs']:.4f}"]],
        [1900, 900, 900, 900])

_beta_below = sum(1 for q in beta_rows if q["p_meet"] < 0.95)
d.h2("6.2 Variance and the design rule")
d.p(f"Fig. 3 shows that the edge-aware variance of Eq. (5) tracks the spread of 300 simulated drops, with a mean "
    f"relative error of {pct(std_rel_exact, 1)}. The stationary approximation is off by {pct(std_rel_stat, 1)} on "
    f"average and underestimates the spread at {'every' if stat_all_under else 'almost every'} node count, by "
    f"{pct(stat_n10, 0)} at {{{{N}}}} = {int(stat_nmin_val)} and {pct(stat_nmax, 0)} at {{{{N}}}} = {int(stat_nmax_N)}: "
    "with few nodes the border cells hold much of the covered area, and with many nodes they hold most of the "
    "uncovered area.")
d.figure(os.path.join(FIG, "paper_fig3_variance.png"), "Standard deviation of the covered fraction against node count (200 m field, sensing radius 20 m, 300 simulated drops per point)")
d.p(f"Fig. 4 and Table 7 show what this means for sizing. Choosing {{{{N}}}} so that the mean equals the target "
    f"met the target in only {pct(mean_lo, 0)} to {pct(mean_hi, 0)} of drops. The normal approximation reached "
    f"{pct(norm_lo, 0)} to {pct(norm_hi, 0)}; at the 0.99 targets, where the distribution is most skewed, it "
    f"stayed between {pct(norm99_lo, 0)} and {pct(norm99_hi, 0)} in all four settings. The Beta rule reached {pct(beta_lo, 0)} to {pct(beta_hi, 0)}, and its Wilson interval contained "
    f"95% in {beta_ci_ok} of the 16 settings (normal rule: {norm_ci_ok}). Holm-corrected exact binomial tests "
    f"rejected the nominal 95% for the mean rule in {mean_rej} of 16 settings and for the Beta rule in "
    f"{'none' if beta_not_rej == 16 else 16 - beta_not_rej}. These shares are consistent with a well-calibrated "
    f"rule in these settings. They do not certify it: in {_beta_below} of the 16 settings the share was below 95%, and a "
    "test that fails to reject 95% is not evidence that 95% is reached. Section 6.3 addresses this with new drops. "
    f"The price of the probability target is {pct(extra_lo, 0)} to {pct(extra_hi, 0)} more nodes than the mean rule.")
d.figure(os.path.join(FIG, "paper_fig4_sizing.png"), "Share of 300 random drops that met the target for three sizing rules, with Wilson intervals (200 m field, sensing radius 20 m)")
rows = [["{{L}}, {{r}} (m)", "{{C_t}}", "{{N}} mean / Beta", "Met, mean (%)", "Met, Beta (%) [95% CI]"]]
for L_, r_ in ((200.0, 15.0), (200.0, 20.0), (200.0, 25.0), (400.0, 20.0)):
    for t_ in (0.8, 0.9, 0.95, 0.99):
        m_ = next(q for q in mean_rows if q["L"] == L_ and q["r"] == r_ and q["target"] == t_)
        b_ = next(q for q in beta_rows if q["L"] == L_ and q["r"] == r_ and q["target"] == t_)
        rows.append([f"{int(L_)}, {r_:g}", f"{t_:.2f}", f"{int(m_['N'])} / {int(b_['N'])}",
                     f"{100 * m_['p_meet']:.1f}",
                     f"{100 * b_['p_meet']:.1f} [{100 * b_['p_lo']:.1f}–{100 * b_['p_hi']:.1f}]"])
d.table("Node counts and share of 300 drops that met the target in the sixteen settings ({{δ}} = 0.05; Wilson 95% intervals in brackets)",
        rows, [820, 480, 900, 700, 1700])

# ---- 6.3 certification
_cov_first = [q for q in e17_first if q["part"] == "coverage"]
_cov_first_pass = sum(1 for q in _cov_first if q["certified"] == "True")
_attempts = lambda part: [int(q["attempt"]) for k, q in e17_final.items() if k[0] == part]
_failed = [k for k, q in e17_final.items() if q["N_certified"] == ""]
_cov_cert = [q for q in e17_cov if q["N_certified"] != ""]
_joint_rows = {(q["Rc"], q["target"]): q for k, q in e17_final.items() if k[0] == "joint"}
_env_rows = {k[1]: q for k, q in e17_final.items() if k[0] == "environment"}
_extra_cov = [int(q["N_certified"]) - int(q["N_rule"]) for q in _cov_cert]
_two_steps = sum(1 for q in _cov_cert if 2 <= int(q["attempt"]) <= 3)
d.h2("6.3 Certification of the random-drop designs")
d.p(f"Table 8 lists the node counts after Algorithm 3, with {CP_N:,} new drops per attempt. Of the sixteen coverage "
    f"designs, {_cov_first_pass} passed at the first attempt, and "
    + (f"all sixteen were certified after at most {max(_attempts('coverage'))} attempts, with "
       if len(_cov_cert) == 16 else f"{len(_cov_cert)} were certified, with ")
    + f"{min(_extra_cov)} to {max(_extra_cov)} more nodes than the rule ({pct(min(_cov_extra), 1)} to "
    f"{pct(max(_cov_extra), 1)}); {_two_steps} of them needed one or two extra steps of 2%. Most of the extra "
    "count is the margin of the one-sided bound rather than an error of the rule: a design whose true success "
    f"probability is exactly 0.95 passes with probability below 0.005, and passing with probability 0.9 requires "
    f"about {_p90:.3f} (Section 4.6). Because the search only moves upward, a certified count need not be the "
    "smallest count that meets the requirement; a downward search would need its own correction for multiplicity. "
    + (f"Every design in the table was certified; for each of them, the probability of certifying it although its "
       f"true success probability is below 0.95 is at most 0.05 under the model. This bound holds for each design "
       "separately; it is not a joint statement about all designs of Tables 8, 10 and 14." if not _failed else
       f"{len(_failed)} design{'s' if len(_failed) > 1 else ''} could not be certified within ten attempts and "
       f"{'are' if len(_failed) > 1 else 'is'} reported as such."))
_cell = lambda q: (f"{int(q['N_rule'])}→{int(q['N_certified'])}" if q["N_certified"] != "" else f"{int(q['N_rule'])}→n.c.")
rows = [["{{L}}, {{r}} (m)", "{{C_t}} = 0.8", "0.9", "0.95", "0.99"]]
for L_, r_ in ((200.0, 15.0), (200.0, 20.0), (200.0, 25.0), (400.0, 20.0)):
    rows.append([f"{int(L_)}, {r_:g}"]
                + [_cell(next(q for q in e17_cov if q["L"] == L_ and q["r"] == r_ and q["target"] == t_))
                   for t_ in (0.8, 0.9, 0.95, 0.99)])
for rc_ in (30.0, 40.0):
    rows.append([f"Joint, {int(rc_)}", "–", _cell(_joint_rows[(rc_, 0.9)]), _cell(_joint_rows[(rc_, 0.95)]), "–"])
_envlab = {"Open, unit disk": "Open", "Open, shadowing 8 dB": "Open, 8 dB", "Urban, no shadowing": "Urban",
           "Urban, shadowing 8 dB": "Urban, 8 dB"}
for sc_ in env_cfg_names:
    rows.append([_envlab.get(sc_, sc_), "–", _cell(_env_rows[sc_]), "–", "–"])
d.table(f"Certified node counts, rule → certified ({CP_N:,} new drops per attempt, one-sided Clopper-Pearson bound, "
        "α = 0.05 over at most 10 attempts; n.c. = not certified); joint designs by {{R_c}} (m), environment designs at "
        "{{C_t}} = 0.9", rows, [900, 925, 925, 925, 925])

# ---- 6.4 connectivity
d.h2("6.4 Connectivity and the joint rule")
d.p("Fig. 5 compares the isolated-node model of Eq. (9) with simulation. The model tracks the simulated "
    "probability of no isolated node closely. Full connectivity needs more nodes at low and medium probabilities, "
    "because small groups can split off together, but the curves meet above about 0.95.")
d.figure(os.path.join(FIG, "paper_fig5_connectivity.png"), "Connectivity of random drops against node count (200 m field, sensing radius 20 m, 300 drops per point; distances are the communication range, markers are simulations)")
jr = lambda rc, t, rule: joint[(rc, t, rule)]
joint_p40 = next(t["p_holm"] for t in tests if t["family"].startswith("D.") and t["comparison"] == "joint, Rc=40, Ct=0.9")
_j40 = jr(40.0, 0.9, 'joint')
_j40w = wilson_ci(int(round(_j40['p_both'] * 500)), 500)
d.p(f"With {{{{R_c}}}} = 40 m and {{{{C_t}}}} = 0.9, sizing for coverage alone gave "
    f"{int(jr(40.0, 0.9, 'coverage_only')['N'])} nodes and both targets held in {pct(jr(40.0, 0.9, 'coverage_only')['p_both'], 1)} "
    f"of 500 drops; the joint rule added {int(_j40['N'] - jr(40.0, 0.9, 'coverage_only')['N'])} nodes "
    f"and raised this to {pct(_j40['p_both'], 1)} (Wilson interval {pct(_j40w[0], 1)} to {pct(_j40w[1], 1)}). A "
    f"one-sided binomial test does not reject 95% (Holm-corrected {{{{p}}}} = {joint_p40:.2f}), but this is not "
    "evidence that the requirement holds; certification accepted the joint design only at "
    f"{int(_joint_rows[(40.0, 0.9)]['N_certified'])} nodes (Table 8). With the shorter range of 30 m, coverage-only sizing "
    f"left the network connected in only {pct(jr(30.0, 0.9, 'coverage_only')['p_conn'], 1)} of drops, while the joint "
    f"rule ({int(jr(30.0, 0.9, 'joint')['N'])} nodes) met both targets in {pct(jr(30.0, 0.9, 'joint')['p_both'], 1)}. "
    "The rule of thumb that {{R_c}} ≥ 2{{r}} ensures connectivity [@zhanghou] presupposes full coverage; at a 90% "
    f"target with {{{{R_c}}}} = 2{{{{r}}}} = 40 m, {pct(1 - jr(40.0, 0.9, 'coverage_only')['p_conn'], 1)} of the "
    "coverage-sized drops were still disconnected.")

# ---- 6.5 lattices
_lat_ok = all(str(q["exact_cover"]) == "True" for q in e25_lat)
_lat_conn = all(str(q["connected"]) == "True" for q in e25_lat if q["kind"] == "triangular")
_tri_deg = min(int(q["min_degree"]) for q in e25_lat if q["kind"] == "triangular")
_dg_cov = [q["r"] for q in e25_dg if q.get("note", "") != "" and str(q["exact_cover"]) == "True"]
_dg_nocov = [q for q in e25_dg if q.get("note", "") != "" and str(q["exact_cover"]) != "True"]
_ratio = lambda q: q["note"].split("= ")[1]
d.h2("6.5 Lattice layouts")
d.p(f"For {{{{L}}}} = 500 m and {{{{r}}}} = 62.5 m the diameter-spaced grid leaves "
    f"{pct(1 - g625['diameter_coverage'], 1)} of the field uncovered, in line with Eq. (15): a four-pointed gap sits at the "
    "center of every grid cell. Over the seven radii of Table 9, where {{m = L/(2r)}} lies between 2.5 and 10, it "
    "never reaches full coverage, as the spacing condition of Section 4.5 predicts. The exact test confirms the "
    "condition on both sides: diameter grids with {{m}} = "
    + ", ".join(_ratio(q) for q in e25_dg if q.get("note", "") != "" and str(q["exact_cover"]) == "True")
    + " cover the field and those with {{m}} = "
    + ", ".join(_ratio(q) for q in _dg_nocov) + " do not. The corrected "
    "square and pruned triangular lattices "
    + ("pass the exact coverage test at every radius" if _lat_ok else "pass the exact coverage test at most radii")
    + "; the triangular lattice needs "
    f"{int(g625['triangular_nodes'])} instead of {int(g625['square_nodes'])} nodes in the example case and "
    f"{pct(tri_saving_min, 0)} to {pct(tri_saving, 0)} fewer nodes over the seven radii. "
    + (f"After pruning, every triangular lattice was connected at {{{{R_c = √3r}}}}: pruning removes only border "
       f"nodes, and every remaining node kept at least {_tri_deg} lattice neighbors at distance {{{{√3r}}}}. "
       if _lat_conn else "")
    + "The largest nearest-neighbor distance equals {{√3r}}, so the connectivity margin is zero, as is the coverage "
    "margin at the points where three disks meet.")
rows = [["{{r}} (m)", "Diameter grid nodes, coverage", "Square nodes", "Triangular nodes"]]
for q in e5:
    rows.append([f"{q['r']:g}", f"{int(q['diameter_nodes'])}, {pct(q['diameter_coverage'], 1)}", f"{int(q['square_nodes'])}",
                 f"{int(q['triangular_nodes'])}"])
d.table("Lattice rules in a 500 m field (square and triangular cover 100%, confirmed by the exact test)", rows, [800, 1650, 1050, 1100])
_ig, _id = e13["ILP, guaranteed"], e13["ILP, demand points"]
_g12, _d12 = e21q(12.5, "guaranteed"), e21q(12.5, "demand points")
_g20, _d20 = e21q(20.0, "guaranteed"), e21q(20.0, "demand points")
_lat_n = int(e13['Triangular lattice']['nodes'])
d.p("We compared the triangular lattice with two kinds of minimum-count reference. We "
    f"solved the set-cover program of [@chakrabarty] with the HiGHS solver [@huangfu] on candidate and demand grids "
    f"of 20 m, 12.5 m and 10 m spacing. Requiring every demand cell to be covered entirely (radius reduced by half a "
    f"cell diagonal), the program needed {int(_g20['nodes'])} and {int(_g12['nodes'])} nodes on the 20 m and 12.5 m "
    f"grids, both proved optimal, and found {int(_ig['nodes'])} nodes on the 10 m grid within {int(_ig['seconds'] // 60)} "
    f"min, with a lower bound of {int(_ig['dual_bound'])}. These counts are optimal or bounded only for the restricted "
    "problem of grid positions under this conservative condition, and they change with the resolution, so they do "
    "not bound the continuous problem. Covering only the demand points needed "
    f"{int(_d20['nodes'])}, {int(_d12['nodes'])} and {int(_id['nodes'])} nodes, but those layouts covered "
    f"{pct(_d20['coverage'], 1)}, {pct(_d12['coverage'], 1)} and {pct(_id['coverage'], 1)} of the field, so they "
    "answer a different question than full-area coverage. A bound that holds for every layout follows from the "
    "theorem of Fejes Tóth [@fejestoth]: congruent disks that cover a convex polygon with at most six sides number at "
    "least the polygon area divided by the area of the largest hexagon inscribed in one disk, {{3√3r^2/2}}. For the "
    f"500 m square and {{{{r}}}} = 62.5 m this gives at least {fejes} nodes. The {_lat_n}-node lattice therefore uses "
    f"fewer nodes than every grid solution found under the full-cell condition (the 10 m bound of "
    f"{int(_ig['dual_bound'])} leaves open whether a smaller grid solution exists there), and at most "
    f"{_lat_n - fejes} more than the continuous lower bound; we make no claim of near-optimality.")
# ---- 6.6 drop errors
d.h2("6.6 Drop errors")
_t02, _t03, _t05 = e16q("triangular", 0.2), e16q("triangular", 0.3), e16q("triangular", 0.5)
_s05 = e16q("square", 0.5)
_e8share = {}
for _q in load(os.path.join("raw", "E8_runs.csv")):
    _k = (round(_q["sigma_over_r"], 1), _q["lattice"])
    _e8share.setdefault(_k, []).append(_q["coverage"] >= 0.99)
_e8share = {k: sum(v) / len(v) for k, v in _e8share.items()}
_e18c = lambda sg, kind: (int(e18q(sg, kind)["nodes_certified"]) if e18q(sg, kind) and e18q(sg, kind)["nodes_certified"] != "" else None)
_e18_sig = sorted({round(q["sigma_over_r"], 2) for q in e18})
_e18_ok = [(sg, k) for sg in _e18_sig for k in ("triangular", "square") if _e18c(sg, k) is not None]
_e18_conn3 = [e18q(sg, "triangular")["connected_share_1.732r"] for sg in _e18_sig if _e18c(sg, "triangular")]
_e18_conn2 = [e18q(sg, "triangular")["connected_share_2.000r"] for sg in _e18_sig if _e18c(sg, "triangular")]
_rc_n = int(_rand_cert["N_certified"])
_big = [sg for sg in (0.75, 1.0) if _e18c(sg, "triangular") is not None]
_sr = lambda sg: "{{r}}" if sg == 1 else f"{sg:g}{{{{r}}}}"
_sq_cheaper = [sg for sg in _e18_sig if _e18c(sg, "square") and _e18c(sg, "triangular")
               and _e18c(sg, "square") < _e18c(sg, "triangular")]
d.p(f"Fig. 6 and Table 10 show the node counts needed when every node lands with a Gaussian error, for the mean "
    f"design ({{{{E[C] ≥ 0.99}}}}) and for the reliability design ({{{{C ≥ 0.99}}}} in at least 95% of drops). "
    f"Without correction, the 33-node triangular lattice drops to {pct(e8_naive02['naive_expected'], 1)} expected "
    f"coverage at {{{{σ}}}} = 0.2{{{{r}}}}. The mean design restores 0.99 with {int(e8_naive02['robust_nodes'])} nodes "
    f"({{{{κ}}}} = {e8_naive02['kappa']:.2f}), but reaches 0.99 in only {pct(_e8share[(0.2, 'triangular')], 0)} of 100 drops; the "
    f"search sample proposes {int(_t02['nodes'])} nodes ({{{{κ}}}} = {_t02['kappa']:.2f}) for the reliability target. "
    f"On 1,000 new drops per layout the proposed designs met 0.99 in "
    f"{pct(min(q['p_meet'] for q in e16), 1)} to {pct(max(q['p_meet'] for q in e16), 1)} of cases; the lowest share "
    f"({pct(_t03['p_meet'], 1)}, Wilson interval {pct(_t03['lo'], 1)} to {pct(_t03['hi'], 1)}) lies below the "
    f"search estimate of {pct(_t03['search_share'], 1)}, as expected when {{{{κ}}}} is the first value that passes "
    "on one sample. Such shares describe calibration; they are not a certificate. Algorithm 3, with "
    f"{CP_N:,} further drops per attempt, certified the triangular lattice at {{{{σ}}}} = 0.3{{{{r}}}}, about 19 m, "
    f"with {_lat03_nodes} nodes ({{{{κ}}}} = {float(_lat03['kappa_certified']):.2f}), against {n_rand_mean} nodes for a "
    f"random drop sized by the mean rule, {n_rand_guar} by the Beta rule and {_rc_n} after certification (the "
    "field-to-radius ratio equals that of the 200 m, {{r}} = 25 m setting of Table 8). "
    + (f"All {len(_e18_ok)} lattices of Table 10 were certified. " if len(_e18_ok) == 2 * len(_e18_sig) else
       f"{len(_e18_ok)} of the {2 * len(_e18_sig)} lattices of Table 10 were certified. ")
    + (f"At {{{{σ}}}} = " + " and ".join(_sr(sg) for sg in _big) + ", where a node lands on average "
       f"{1.2533 * min(_big):.2f}{{{{r}}}} to {1.2533 * max(_big):.2f}{{{{r}}}} from its aim, the certified triangular "
       "lattices need " + " and ".join(str(_e18c(sg, 'triangular')) for sg in _big)
       + f" nodes, against {_rc_n} for a certified random drop: the saving of a planned drop shrinks as the error "
       "grows and disappears once the error is comparable to the radius. " if _big else "")
    + (f"The square lattice is the cheaper certified design at {{{{σ}}}} = "
       + " and ".join(_sr(sg) for sg in _sq_cheaper)
       + ", and the triangular one at the other error levels, because the triangular advantage relies on "
       "accurate positions. " if _sq_cheaper else "")
    + "The 100-run simulations of the mean designs agree with "
    f"Eq. (18) to within {e8_gap:.3f}. Drop errors also break the zero-margin connectivity of the lattice: over the "
    f"certified triangular designs the network was connected in {pct(min(_e18_conn3), 0)} to {pct(max(_e18_conn3), 0)} "
    f"of drops at {{{{R_c = √3r}}}} and in {pct(min(_e18_conn2), 0)} to {pct(max(_e18_conn2), 0)} at "
    "{{R_c = 2r}}, so a planned drop with errors needs either the longer range or its own connectivity margin.")
d.figure(os.path.join(FIG, "paper_fig7_placement.png"), "Nodes needed for 99% coverage against the drop error: error-tolerant lattices sized for the mean (solid) and certified for 99% coverage in 95% of drops (dashed), and random drops sized by the mean rule and certified (500 m field, sensing radius 62.5 m)")
rows = [["{{σ/r}}", "{{E[C] ≥ 0.99}}: tri. / sq.", "Certified: tri. / sq.", "Share, {{p_L}} (%): tri.", "Conn. (%) √3{{r}} / 2{{r}}"]]
for s_ in [0.0] + _e18_sig:
    t_ = next((q for q in e8 if abs(q["sigma_over_r"] - s_) < 1e-9 and q["kind"] == "triangular"), None)
    q_ = next((q for q in e8 if abs(q["sigma_over_r"] - s_) < 1e-9 and q["kind"] == "square"), None)
    mean_ = f"{int(t_['robust_nodes'])} / {int(q_['robust_nodes'])}" if t_ else "–"
    if s_ == 0.0:
        rows.append([f"{s_:.2g}", mean_, f"{int(t_['robust_nodes'])} / {int(q_['robust_nodes'])} (exact)", "100 (exact)", "100 / 100"])
        continue
    a_, b_ = e18q(s_, "triangular"), e18q(s_, "square")
    ca, cb = _e18c(s_, "triangular"), _e18c(s_, "square")
    cert_ = f"{ca if ca else 'n.c.'} / {cb if cb else 'n.c.'}"
    share_ = f"{100 * a_['share']:.1f}, {100 * a_['lower_bound']:.1f}" if ca else "–"
    conn_ = f"{100 * a_['connected_share_1.732r']:.0f} / {100 * a_['connected_share_2.000r']:.0f}" if ca else "–"
    rows.append([f"{s_:.2g}", mean_, cert_, share_, conn_])
rows.append(["Random", f"{n_rand_mean}", f"{n_rand_guar} → {_rc_n}", "–", "–"])
d.table("Error-tolerant lattices for 99% coverage (500 m field, {{r}} = 62.5 m): node counts of the mean design and of the certified "
        f"reliability design ({{{{δ}}}} = 0.05; {CP_N:,} drops per attempt); share of drops with {{{{C}}}} ≥ 0.99 and its "
        "one-sided lower bound, and share of connected drops, for the certified triangular lattice", rows,
        [850, 950, 950, 950, 900])

# ---- 6.7 baselines
d.h2("6.7 Comparison with optimization methods")
lat25, lat30, lat33 = (e10q("Proposed lattice", n) for n in (25, 30, 33))
pop_methods = ["PSO", "GA", "GWO", "ICGWO", "VASF-PSO", "DAR-SSA"]
best25 = max((e10q(m, 25) for m in pop_methods + ["VFA"]), key=lambda q: q["mean"])
best30 = max((e10q(m, 30) for m in pop_methods + ["VFA"]), key=lambda q: q["mean"])
best_pop33 = max((e10q(m, 33) for m in pop_methods), key=lambda q: q["mean"])
vfa33 = e10q("VFA", 33)
lat_conn = all(e10q("Proposed lattice", n)["connected_share"] == 1 for n in (33, 36))
d.p(f"Fig. 7 and Table 11 compare the lattice with the eight baselines for a fixed node count. With 33 nodes, the "
    f"count that the triangular lattice needs for a full cover, the lattice covered {pct(lat33['mean'], 1)} of the "
    f"field. The best population method, {best_pop33['method']}, reached {pct(best_pop33['mean'], 1)} on average "
    f"(worst run {pct(best_pop33['worst'], 1)}) after 9,030 fitness evaluations, and VFA reached "
    f"{pct(vfa33['mean'], 1)}. With 30 nodes the lattice still led ({pct(lat30['mean'], 1)} against "
    f"{pct(best30['mean'], 1)} for {best30['method']}). With only 25 nodes it did not: stretching the lattice opens "
    f"regular gaps, and {best25['method']} covered {pct(best25['mean'], 1)} against {pct(lat25['mean'], 1)}. An "
    "optimizer thus remains useful when the budget is fixed below the full-cover count of Table 9. The Friedman test rejected equal performance of the "
    f"nine methods at every node count (largest Holm-corrected {{{{p}}}} = {sci(fried_max_p)}), and after Holm "
    f"correction {wil_sig} of the {len(wil)} Wilcoxon comparisons with the lattice were significant at the 0.05 level (at 25 nodes in favor of the baselines that covered more).")
d.p(("At 33 and 36 nodes the lattice was connected for {{R_c}} = √3{{r}}, while many optimized "
     "layouts were not. " if lat_conn else "")
    + f"A tight layout has a cost: when the 33-node "
    f"layouts were dropped with an error of 0.2{{{{r}}}} (20 draws per run), the lattice kept {pct(lat33['noisy_mean'], 1)} coverage, "
    f"VFA {pct(vfa33['noisy_mean'], 1)} and {best_pop33['method']} {pct(best_pop33['noisy_mean'], 1)}, because VFA "
    "keeps more overlap. This lattice uses a design radius of about 0.95{{r}}, so it is slightly denser than the "
    f"full-cover lattice ({pct(e8_naive02['naive_expected'], 1)} at the same error); the design of Section 6.6 reaches "
    f"an expected coverage of 0.99 with {int(e8_naive02['robust_nodes'])} nodes.")
d.figure(os.path.join(FIG, "paper_fig8_baselines.png"), "Coverage against node count for the proposed lattice and eight baselines (500 m field, sensing radius 62.5 m, " + f"{n_seeds} seeds)")
rows = [["Method", "{{N}} = 25", "{{N}} = 30", "{{N}} = 33"]]
for m in ["Random", "VFA", "PSO", "GA", "GWO", "ICGWO", "VASF-PSO", "DAR-SSA", "Proposed lattice"]:
    f_ = lambda q: f"{100*q['mean']:.1f} ± {100*q['std']:.1f}"
    rows.append([m.replace("Proposed lattice", "Proposed"), f_(e10q(m, 25)), f_(e10q(m, 30)), f_(e10q(m, 33))])
d.table(f"Coverage (%) of the proposed lattice and the baselines, mean ± std over {n_seeds} seeds (the lattice is deterministic)", rows,
        [1150, 1160, 1160, 1160])
# sensitivity (E24): defaults on the same ten seeds from E10
_e10raw = load(os.path.join("raw", "E10_runs.csv"))
_sens_seeds = sorted({int(q["seed"]) for q in load(os.path.join("raw", "E24_runs.csv"))})
_default = {}
for m in ("VASF-PSO", "ICGWO", "DAR-SSA"):
    x = [q for q in _e10raw if q["method"] == m and q["N"] == 33 and int(q["seed"]) in _sens_seeds]
    cov_ = [q["coverage"] for q in x]
    mu_ = sum(cov_) / len(cov_)
    sd_ = math.sqrt(sum((v - mu_) ** 2 for v in cov_) / (len(cov_) - 1))
    _default[m] = dict(mean=mu_, std=sd_, worst=min(cov_), full_cover_runs=sum(v >= 1 for v in cov_),
                       connected_share=sum(1 for q in x if str(q["connected_rc_sqrt3r"]) == "True") / len(x))
_best_var = max(e24, key=lambda q: q["mean"])
_gain_eq = max(((q["mean"] - _default[q["method"]]["mean"], q) for q in e24 if q["evals"] < 10000), key=lambda t: t[0])
_any_full = sum(int(q["full_cover_runs"]) for q in e24)
_sens_tests = {t["comparison"]: t for t in tests if t["family"].startswith("N.")}
_sens_sig = [c for c, t in _sens_tests.items() if t["p_holm"] < 0.05]
d.p(f"Table 12 repeats the three recent methods at 33 nodes with {len(e24)} other settings on {len(_sens_seeds)} of "
    "the seeds of Table 11. The settings change the search factor floor of VASF-PSO, the decay of the control "
    "parameter of ICGWO, the safety threshold and repulsion step of DAR-SSA, the split of the budget between "
    "population and iterations, and the budget itself. "
    + ("No variant reached full coverage in any run. " if _any_full == 0 else
       f"Variants reached full coverage in {_any_full} runs in total. ")
    + f"The best, {_best_var['method']} with {_best_var['variant'].replace('(30 x 600)', '').strip()}, averaged "
    f"{pct(_best_var['mean'], 2)} (worst run {pct(_best_var['worst'], 2)}) with {int(_best_var['evals']):,} "
    f"evaluations. At the default budget the largest gain, {100 * _gain_eq[0]:.1f} percentage points, came from "
    f"{_gain_eq[1]['method']} with {_gain_eq[1]['variant']}. "
    + (f"After Holm correction {len(_sens_sig)} of the {len(_sens_tests)} paired Wilcoxon comparisons with the "
       "default setting were significant. " if _sens_tests else "")
    + "The ranking of Table 11 at 33 nodes, with the lattice ahead, did not change.")
_short = {"search factor floor 0.1": "search floor 0.1", "search factor floor 0.4": "search floor 0.4",
          "60 particles x 150 iterations": "60 × 150", "double budget (30 x 600)": "30 × 600",
          "linear decay of a": "{{a}} linear", "cubic decay of a": "{{a}} cubic", "ST = 0.9": "ST = 0.9",
          "repulsion step 0.3r": "step 0.3{{r}}", "60 sparrows x 150 iterations": "60 × 150"}
rows = [["Method, setting", "Coverage (%)", "Worst (%)", "Conn. (%)"]]
for m in ("VASF-PSO", "ICGWO", "DAR-SSA"):
    q0 = _default[m]
    rows.append([f"{m}, default", f"{100 * q0['mean']:.2f} ± {100 * q0['std']:.2f}", f"{100 * q0['worst']:.2f}",
                 f"{100 * q0['connected_share']:.0f}"])
    for q in [x for x in e24 if x["method"] == m]:
        rows.append([f"   {_short.get(q['variant'], q['variant'])}", f"{100 * q['mean']:.2f} ± {100 * q['std']:.2f}", f"{100 * q['worst']:.2f}",
                     f"{100 * q['connected_share']:.0f}"])
d.table(f"Parameter sensitivity of the re-implemented recent baselines ({{{{N}}}} = 33, {len(_sens_seeds)} seeds, mean ± std; "
        "population × iterations; connectivity at {{R_c}} = √3{{r}}); the lattice covers 100% and is connected",
        rows, [1800, 1250, 800, 750])
# run time (E23)
_rt = {q["task"]: q for q in e23}
_rtb = {}
for q in e23:
    if q["phase"] == "baseline":
        _rtb.setdefault(q["task"], []).append(q)
_med = lambda v: sorted(v)[len(v) // 2]


def _ts(t):
    """Seconds without exponent notation."""
    if t >= 1:
        return f"{t:.1f}"
    if t >= 0.01:
        return f"{t:.3g}"
    return f"{t:.5f}"
_fit = next(q for q in e23 if q["task"].startswith("one fitness evaluation"))
_cov1 = next(q for q in e23 if q["task"].startswith("coverage of one layout"))
_cert = next(q for q in e23 if q["task"].startswith("certification of the rule"))
_beta = next(q for q in e23 if q["task"].startswith("Beta sizing rule"))
_trib = next(q for q in e23 if q["task"].startswith("triangular lattice"))
_att = int(next(q for q in e17_cov if q["L"] == 200 and q["r"] == 20 and q["target"] == 0.95)["attempt"])
_e2e = _beta["median_s"] + _att * _cert["median_s"]
_pop_t = [_med([x["median_s"] for x in v]) for k, v in _rtb.items() if k in pop_methods]
d.p(f"Table 13 gives the run time and the peak of Python-tracked memory of every step on one core. The Beta rule "
    f"takes {_beta['median_s']:.1f} s and its certification with {CP_N:,} drops {_cert['median_s']:.0f} s per attempt, "
    f"so the certified design of Table 8 for this setting ({_att} attempts) is obtained in about {_e2e:.0f} s. Building "
    f"and pruning the lattice takes {_trib['median_s']:.2f} s and the exact coverage test well under a second. One run "
    f"of a population method takes {min(_pop_t):.1f} to {max(_pop_t):.1f} s, most of it in the 9,030 fitness "
    f"evaluations at about {1e3 * _fit['median_s']:.2f} ms each on the 80 × 80 raster; evaluating one layout on the "
    f"final 250 × 250 raster takes {1e3 * _cov1['median_s']:.1f} ms. The design steps are offline costs paid once per "
    "site; the online cost of checking a layout is the same for all methods.")
_rows_rt = [["Step", "Time (s)", "Memory (MiB)"]]
_label = {
    "Beta sizing rule": "Beta rule, Eq. (8)",
    "joint coverage-connectivity rule": "Joint rule, Eq. (10)",
    "certification of the rule": f"Certification, {CP_N:,} drops",
    "triangular lattice": "Triangular lattice, offsets and pruning",
    "exact (raster-free) coverage test": "Exact coverage test",
    "square lattice": "Square lattice",
    "lattice for a fixed budget": "Lattice for {{N}} = 33",
    "error-tolerant lattice search": "Error-tolerant search, {{σ}} = 0.2{{r}}",
}
for q in e23:
    if q["phase"] != "offline":
        continue
    lab = next((v for k, v in _label.items() if q["task"].startswith(k)), q["task"])
    _rows_rt.append([lab, _ts(q['median_s']), f"{q['peak_traced_MiB']:.1f}"])
for grp in (("VFA",), ("PSO", "GA", "GWO"), ("ICGWO", "VASF-PSO", "DAR-SSA")):
    v = [x for m in grp for x in _rtb.get(m, [])]
    if not v:
        continue
    meds = [_med([x["median_s"] for x in _rtb[m]]) for m in grp if m in _rtb]
    _rows_rt.append([", ".join(grp) + " (per run)", f"{_ts(min(meds))}-{_ts(max(meds))}" if len(meds) > 1 else _ts(meds[0]),
                     f"{max(x['peak_traced_MiB'] for x in v):.1f}"])
_rows_rt.append([f"Random drop end to end: rule + {_att} certification attempts", _ts(_e2e), "–"])
for q in e23:
    if q["phase"] == "online":
        lab = ("One coverage evaluation, 250²" if q["task"].startswith("coverage") else
               "One fitness evaluation, 80²" if q["task"].startswith("one fitness") else "Connectivity check")
        _rows_rt.append([lab, _ts(q['median_s']), f"{q['peak_traced_MiB']:.1f}"])
d.table(f"Run time and peak memory on one core ({e23hw['cpu'].split(' @')[0]}, Python {e23hw['python']}, "
        f"NumPy {e23hw['numpy']}; median of 3 calls, 500 m field, {{{{r}}}} = 62.5 m, rules in the 200 m field)",
        _rows_rt, [2600, 1000, 1000])

# ---- 6.8 extensions
d.h2("6.8 Accuracy of the extensions")
d.p(f"The models of Section 4.4 had mean absolute errors of {e9err['k-coverage'][0]:.4f} for k-coverage ({{{{k}}}} = 1 to 3), "
    f"{e9err['failures-coverage'][0]:.4f} for coverage with failure rates of 0.1 to 0.3, and "
    f"{e9err['probabilistic-sensing'][0]:.4f} for the Elfes model ({{{{r_e}}}} = 5 m, {{{{λ}}}} = 0.1, "
    f"{{{{γ}}}} = 1). For connectivity under failures, the isolated-node approximation of Eq. (9) behaves as in Fig. 5: it is "
    f"optimistic at low probabilities and within {conn_hi_gap:.3f} of the simulated connectivity once it predicts "
    "more than 0.9, so a small margin is advisable.")

# ---- 6.9 environment
d.h2("6.9 Obstacles and shadowing")
o_, s8, u0, u8 = env_cfg_names
E_ = lambda sc, rule: env[(sc, rule)]
u0_open_p = env_tests[f"{u0}, open_field_rule, N={int(E_(u0, 'open_field_rule')['N'])}"]["p_holm"]
d.p("We repeated the joint design of Section 6.4 in four environments: an open and an urban field (nine 40 m blocks, "
    f"36% of the field), each without and with 8 dB shadowing (Table 3). Over seven node counts each, Section 4.7 predicted the mean coverage within "
    f"{env_mean_err:.4f}, its standard deviation within {pct(env_std_rel, 0)} on "
    f"average and the probability of no isolated node within {env_iso_err:.4f} on average.")
S_ = lambda sc: E_(sc, "simulated_connectivity_rule")
A_ = lambda sc: E_(sc, "environment_aware_rule")
O_ = lambda sc: E_(sc, "open_field_rule")
u0_aware_p = env_tests[f"{u0}, environment_aware_rule, N={int(A_(u0)['N'])}"]["p_holm"]
u0_rows = [q for q in e11m if q["scenario"] == u0 and q["mc_p_no_isolated"] >= 0.9]
u0_gap = max(u0_rows, key=lambda q: q["mc_p_no_isolated"] - q["mc_p_conn"])
d.p(f"Fig. 8 compares the open-field rule of Section 4.4 ({int(O_(o_)['N'])} nodes everywhere) with the aware "
    "rule, analytical and with simulated connectivity. Shadowing alone raises the mean degree at a fixed median "
    f"range [@bettstetterhartmann], so the coverage term set the count of both aware rules ({int(A_(s8)['N'])} nodes; "
    f"{pct(A_(s8)['p_both'], 1)} and {pct(S_(s8)['p_both'], 1)} of drops met both targets). Buildings without shadowing cut the links that cross them: the open-field rule "
    f"reached only {pct(O_(u0)['p_both'], 1)} (Holm-corrected {{{{p}}}} = {sci(u0_open_p)}) and the analytical aware rule, with "
    f"{int(A_(u0)['N'])} nodes, {pct(A_(u0)['p_both'], 1)} (Holm-corrected {{{{p}}}} = {sci(u0_aware_p)}). The blocks split the "
    f"network into corridors in which every node keeps a neighbor; at {int(u0_gap['N'])} nodes "
    f"{pct(u0_gap['mc_p_no_isolated'], 1)} of drops had no isolated node but only {pct(u0_gap['mc_p_conn'], 1)} were "
    f"connected. With simulated connectivity, {int(S_(u0)['N'])} nodes reached {pct(S_(u0)['p_both'], 1)} "
    f"[{pct(S_(u0)['lo'], 1)}, {pct(S_(u0)['hi'], 1)}]. With 8 dB shadowing, links through buildings rejoin the "
    f"corridors and all three rules reached {pct(S_(u8)['p_both'], 1)}. The simulated rule reached at least 95% of "
    f"the validation drops in all four environments, at {int(S_(o_)['N']) - int(O_(o_)['N'])} extra nodes in the open field and "
    f"{int(S_(u0)['N']) - int(O_(u0)['N'])} in the unshadowed urban layout; with new drops, Algorithm 3 certified "
    "the four designs at " + ", ".join(str(int(_env_rows[s]['N_certified'])) if _env_rows[s]['N_certified'] != "" else "n.c."
                                       for s in env_cfg_names) + " nodes (Table 8).")
d.figure(os.path.join(FIG, "paper_fig10_environment.png"), "Share of 500 drops meeting both targets under three rules (200 m field, sensing radius 20 m, communication range 40 m, target 0.9), with Wilson intervals; bar labels are node counts, the dashed line is 0.95")

# ---- 6.10 stress study
_cal_dev = [q["observed"] - q["predicted"] for q in e19c]
_sgn = lambda v: f"{v:+.3f}".replace("-", "−")
_cal_out = sum(1 for q in e19c if not (q["lower"] <= q["predicted"] <= q["upper"]))
_at_rule = sorted(e19, key=lambda q: q["observed_at_rule"])
_worst = _at_rule[0]
_ok_rule = [q for q in e19 if q["lower_at_rule"] <= 0.95]
_bad_rule = [q for q in e19 if q["lower_at_rule"] > 0.95 or q["observed_at_rule"] < 0.95 and q["lower_at_rule"] < 0.95 and
             sst.binomtest(int(round(q["observed_at_rule"] * 1000)), 1000, 0.95, alternative="less").pvalue < 0.05]
_stress_tests = {t["comparison"]: t for t in tests if t["family"].startswith("P.")}
_stress_rej_lo = [c for c, t in _stress_tests.items() if t["p_holm"] < 0.05 and t["statistic"] < 0.95]
_stress_rej_hi = [c for c, t in _stress_tests.items() if t["p_holm"] < 0.05 and t["statistic"] > 0.95]
_q01 = min(q["q01_at_rule"] - q["target"] for q in e19)
_q01row = min(e19, key=lambda q: q["q01_at_rule"] - q["target"])
_e19raw = [q for q in load(os.path.join("raw", "E19_runs.csv")) if q["part"] == "calibration"]
_minrow = min(((min(x["coverage"] for x in _e19raw if int(x["setting"]) == int(q["setting"]) and int(x["N"]) == int(q["N_rule"]))
                - q["target"], q["name"], q["target"]) for q in e19), key=lambda t: t[0])
_nm = lambda name: name.replace("small N", "small {{N}}")
_lab = lambda c: _nm(c.split(", N=")[0].replace("Ct=", "{{C_t}} = "))
_calib_ok = [c for c, t in _stress_tests.items() if t["p_holm"] >= 0.05]
_irregular = [q for q in e19 if q["name"] in ("rectangle 2:1", "rectangle 4:1", "L-shaped field", "field with a hole")]
_irr_ok = all(_stress_tests[f"{q['name']}, Ct={q['target']:g}, N={int(q['N_rule'])}"]["p_holm"] >= 0.05 or
              _stress_tests[f"{q['name']}, Ct={q['target']:g}, N={int(q['N_rule'])}"]["statistic"] > 0.95 for q in _irregular)
_stress_extra = [int(q["N_certified"]) / int(q["N_rule"]) - 1 for q in e19 if q["N_certified"] != ""]
_region_text = (
    f"Holm-corrected binomial tests found no significant departure from 95% at the rule value in {len(_calib_ok)} "
    f"of the 14 settings" + (", including all elongated and irregular fields" if _irr_ok else "")
    + ("; the rule was optimistic for " + "; ".join(_lab(c) for c in _stress_rej_lo) if _stress_rej_lo else "")
    + ("; it was conservative for " + "; ".join(_lab(c) for c in _stress_rej_hi) if _stress_rej_hi else "")
    + ". "
    + ("Where it is optimistic, the coverage of a few large disks is lumpy and two moments no longer describe the "
       "tail, so the rule should serve only as the starting point of Algorithm 3. " if _stress_rej_lo else
       "Calibration within sampling error is not a certificate, however: Algorithm 3 certified "
       + (f"all 14 designs" if _stress_cert == len(e19) else f"{_stress_cert} of the 14 designs")
       + f" and added up to {pct(max(_stress_extra), 0)} more nodes. Within the tested range the rule is thus a "
       "reliable starting point, and Algorithm 3 supplies the probability statement. "))
d.h2("6.10 Stress study")
d.p("Fig. 9 and Table 14 test the Beta rule outside the settings in which it was developed: small networks "
    "({{r}} = 40 m in a 200 m field, 22 to 74 nodes), very high targets (0.995 and 0.999), rectangles with aspect "
    "ratios of 2 and 4, an L-shaped field and a field with a central hole. For the last four, Eqs. (4) and (5) were "
    "evaluated on rasters of the actual field, and nodes fell uniformly over it. For each setting the node count "
    "was set to 0.9, 0.95, 1, 1.05 and 1.1 times the rule value, giving 70 calibration points of 1,000 drops each. "
    f"The observed share differed from the predicted probability by {_sgn(min(_cal_dev))} to {_sgn(max(_cal_dev))}, and "
    f"the predicted value fell outside the 95% Clopper-Pearson interval of the observed share at {_cal_out} of the "
    f"70 points. At the rule value the lowest observed share was {pct(_worst['observed_at_rule'], 1)} "
    f"({_nm(_worst['name'])}, {{{{C_t}}}} = {_worst['target']:g}). The 1% quantile of coverage lay at most "
    f"{100 * -_q01:.1f} percentage points below the target ({_nm(_q01row['name'])}, {{{{C_t}}}} = {_q01row['target']:g}), "
    f"and the worst single drop of all 14,000 at the rule values fell {100 * -_minrow[0]:.1f} points short "
    f"({_nm(_minrow[1])}, {{{{C_t}}}} = {_minrow[2]:g}); these measure the undercoverage a planner should expect in one "
    "drop out of a hundred and in the worst case. "
    + _region_text)
d.figure(os.path.join(FIG, "paper_fig11_calibration.png"), "Calibration of the Beta rule: predicted {{P(C ≥ C_t)}} against the share of 1,000 drops, with 95% Clopper-Pearson intervals, at 0.9 to 1.1 times the rule value in 14 stress settings")
rows = [["Setting", "{{C_t}}", "{{N}} rule", "Pred. / obs. (%) [95% CI]", "{{N}} cert."]]
_cal = {(int(q["setting"]), q["factor"]): q for q in e19c}
for q in e19:
    c_ = _cal[(int(q["setting"]), 1.0)]
    rows.append([_nm(q["name"]), f"{q['target']:g}", f"{int(q['N_rule'])}",
                 f"{100 * q['predicted_at_rule']:.1f} / {100 * q['observed_at_rule']:.1f} [{100 * c_['lower']:.1f}–{100 * c_['upper']:.1f}]",
                 f"{int(q['N_certified'])}" if q["N_certified"] != "" else "n.c."])
d.table("Stress study of the Beta rule ({{δ}} = 0.05): predicted and observed share at the rule value (1,000 drops) and the "
        f"certified count ({CP_N:,} drops per attempt; n.c. = not certified within 10 attempts)", rows,
        [1200, 600, 550, 1500, 750])
_cs = sorted(e19s_final.values(), key=lambda q: q["rho"])


def _corr_need(q):
    if q["N_certified"] != "":
        return f"{int(q['N_certified'])} nodes ({pct(int(q['N_certified']) / int(q['N_rule']) - 1, 0)} more than the rule)"
    if q["N_design"] == "":
        n_max = max(n for n, _ in eval(q["design_path"]))
        return f"more than {n_max} nodes, since no count up to {n_max} reached the design share"
    return f"more than {int(q['N'])} nodes (the design of {int(q['N_design'])} nodes was not certified)"
d.p("Shadowing on links that share a node is correlated in measurements, with correlation coefficients of up to "
    "about 0.33 [@agrawal]. We repeated the open-field joint design with 8 dB shadowing after splitting the shadowing "
    "of each link into a part shared by its two end nodes and an independent part, so that two links with a common "
    "node have correlation " + ", ".join(f"{q['link_correlation']:g}" for q in _cs[:-1]) + f" or {_cs[-1]['link_correlation']:g}"
    + f". At the {int(_cs[0]['N_rule'])} nodes of the independent rule, both targets held in "
    + ", ".join(f"{pct(q['rule_share'], 1)}" for q in _cs)
    + " of 2,000 drops, respectively, and the connected share fell from " + pct(_cs[0]["rule_p_conn"], 1) + " to "
    + " and ".join(f"{pct(q['rule_p_conn'], 1)}" for q in _cs[1:])
    + ": a node whose links all suffer from poor shadowing becomes isolated. We then sized the network on a separate "
    "design sample (1,000 drops per step, the node count raised in steps of 5% of the rule value until 96.5% of the "
    "drops met both targets) and certified the result: " + "; ".join(f"the case with correlation {q['link_correlation']:g} needed {_corr_need(q)}"
                                   for q in _cs[1:])
    + ". The isolated-node rule therefore holds for independent shadowing only; when link shadowing is correlated, "
    "the connectivity term has to be sized by simulation with the correlation included.")

# ---- 6.11 risk, heterogeneous, scheduling
d.h2("6.11 Risk level, heterogeneous radii and sleep scheduling")
d.p(f"Table 15 repeats the sizing study of Section 6.2 at risk levels of 1% and 10% with 1,000 drops per setting. "
    f"The Beta rule met the target in {pct(e12_lo[0.01], 1)} to {pct(e12_hi[0.01], 1)} of drops at {{{{δ}}}} = 0.01 "
    f"and in {pct(e12_lo[0.1], 1)} to {pct(e12_hi[0.1], 1)} at {{{{δ}}}} = 0.10. Holm-corrected binomial tests "
    + ("rejected the nominal share in no setting." if not e12_rej else
       f"rejected the nominal share only in {['no', 'one', 'two', 'three', 'four'][len(e12_rej)]} setting{'s' if len(e12_rej) > 1 else ''}, on the "
       "conservative side (" + ", ".join(f"{pct(e12_tests[c]['statistic'], 1)} at {{{{C_t}}}} = {float(c.split('Ct=')[1].split(',')[0]):.2f}" for c in e12_rej) + ").")
    + " Lowering the risk from 10% to 1% costs "
    f"{min(int(a['N']) - int(c['N']) for a in e12 for c in e12 if a['delta'] == 0.01 and c['delta'] == 0.1 and a['target'] == c['target'])} to "
    f"{max(int(a['N']) - int(c['N']) for a in e12 for c in e12 if a['delta'] == 0.01 and c['delta'] == 0.1 and a['target'] == c['target'])} nodes.")
rows = [["{{C_t}}", "Mean rule {{N}}", "{{δ}} = 0.01: {{N}}, met (%)", "{{δ}} = 0.10: {{N}}, met (%)"]]
for t_ in (0.8, 0.9, 0.95, 0.99):
    a_ = next(q for q in e12 if q["delta"] == 0.01 and q["target"] == t_)
    c_ = next(q for q in e12 if q["delta"] == 0.1 and q["target"] == t_)
    rows.append([f"{t_:.2f}", f"{int(a_['N_mean_rule'])}", f"{int(a_['N'])}, {100 * a_['p_meet']:.1f}",
                 f"{int(c_['N'])}, {100 * c_['p_meet']:.1f}"])
d.table("Beta rule at other risk levels (200 m field, {{r}} = 20 m, 1,000 drops per setting)", rows, [700, 1100, 1400, 1400])
_m, _a, _r = e15r("mixture"), e15r("mean radius"), e15r("rms radius")
_rms_rej = [q for q in _r if e15_tests[f"rms radius, Ct={q['target']:g}, N={int(q['N'])}"]["p_holm"] < 0.05]
_fx = [q for q in e22 if q["rule"] == "fixed-count rule"]
_mx = [q for q in e22 if q["rule"] == "mixture rule"]
_e22d = list({(int(q["N"]), q["counts"]): q for q in e22}.values())          # distinct designs
_fx_std = sum(abs(q["model_std_fixed"] - q["mc_std"]) / q["mc_std"] for q in _e22d) / len(_e22d)
_mx_std = sum(abs(q["model_std_mixture"] - q["mc_std"]) / q["mc_std"] for q in _e22d) / len(_e22d)
d.p("For heterogeneous nodes that draw {{r}} = 15 m or 25 m with equal probability, Eqs. (4)-(6) with Eq. (23) predicted the "
    f"standard deviation of coverage within {pct(e15_std_rel, 1)} on average over the twelve node counts tested "
    f"(at most {pct(e15_std_max, 1)}). The mixture rule needed "
    f"{', '.join(str(int(q['N'])) for q in _m)} nodes for {{{{C_t}}}} = 0.80 to 0.99 and met the target in "
    f"{pct(min(q['p_meet'] for q in _m), 1)} to {pct(max(q['p_meet'] for q in _m), 1)} of 500 drops. Sizing for the "
    f"mean radius of 20 m used up to {max(int(a['N']) - int(m['N']) for a, m in zip(_a, _m))} more nodes, and sizing "
    "for the radius with the same mean area (20.6 m) used fewer nodes but "
    + (f"met the target in only {pct(min(q['p_meet'] for q in _r), 1)} of drops at {{{{C_t}}}} = "
       f"{min(_r, key=lambda q: q['p_meet'])['target']:.2f}" if _rms_rej else "came close to the limit")
    + ", because equal mean area does not imply equal overlap. These drops sampled the radii independently and so "
    "tested the mixture model. With exactly half of the nodes of each radius, Eq. (24) predicted the standard "
    f"deviation within {pct(_fx_std, 1)} on average, against {pct(_mx_std, 1)} for the mixture expressions, which "
    "include the variation of the class counts. The fixed-count rule needed "
    + ", ".join(f"{int(a['N'])}" for a in _fx) + " nodes, against " + ", ".join(f"{int(b['N'])}" for b in _mx)
    + " for the mixture rule, and met the target in "
    f"{pct(min(q['p_meet'] for q in _fx), 1)} to {pct(max(q['p_meet'] for q in _fx), 1)} of 1,000 fixed-count "
    "drops; the two rules differ by at most one node here, because the class-count variation is small next to the "
    "positional variation.")
_e20 = {q["multiplier"]: q for q in e20}
_sched = [q for q in e20 if q["multiplier"] > 1]
d.p(f"Table 16 applies the schedule of Section 4.8 to the joint design of Section 6.4 ({{{{C_t}}}} = 0.9, "
    f"{{{{R_c}}}} = 40 m, {int(e14[0]['N_joint'])} nodes). Dropping 1.5, 2 and 3 times as many nodes let each node "
    f"sleep in {pct(1 - e14[1]['q'], 0)}, {pct(1 - e14[2]['q'], 0)} and {pct(1 - e14[3]['q'], 0)} of the rounds. In "
    "500 independent drops, each with one random wake-up pattern, the awake set "
    f"met both targets in {pct(min(q['p_both'] for q in e14[1:]), 1)} to {pct(max(q['p_both'] for q in e14[1:]), 1)} "
    f"of cases; the always-on row repeats the {int(e14[0]['N_joint'])}-node design of Sections 6.4 and 6.9 with new "
    f"seeds. This is the ensemble reliability of Eq. (25). A deployment, once dropped, is used for many rounds, so "
    f"we also followed {int(e20[0]['deployments'])} deployments per row for {int(e20[0]['rounds'])} rounds each. "
    f"Without sleeping, a deployment either meets the targets in every round or in none, and "
    f"{pct(_e20[1.0]['share_below'], 1)} of them never did. With sleeping, the rounds of one deployment vary, and "
    f"the share of deployments whose own success rate was below 95% was "
    + ", ".join(pct(q["share_below"], 1) for q in _sched)
    + "; for " + ", ".join(pct(q["share_certainly_below"], 1) for q in _sched)
    + " of them the one-sided 95% upper bound of that rate was below 95% as well. The schedule thus meets its "
    "target on average over deployments, not for every deployment; a planner who needs the per-deployment statement "
    "must add nodes or wake more of them. With 0.5 J "
    "per node, 2,000-bit packets, {{E_elec}} = 50 nJ/bit and {{ε_amp}} = 100 pJ/bit/m², the first-order radio "
    f"model allows {round(e14[0]['rounds_always_on'])} rounds of communication energy for the always-on network and "
    f"{round(e14[3]['rounds']):,} at three times the node count, a factor of {e14[3]['lifetime_gain']:.2f}; these are "
    "energy budgets computed from the expected number of awake rounds, not simulated battery lifetimes.")
rows = [["{{N}} / {{N^⋆}}", "{{N}}", "{{q^⋆}}", "Energy factor", "Met (%) [95% CI]", "Below 95% (%)"]]
for q in e14:
    q20 = _e20[q["multiplier"]]
    rows.append([f"{q['multiplier']:.1f}", f"{int(q['N'])}", f"{q['q']:.2f}", f"{q['lifetime_gain']:.2f}",
                 f"{100 * q['p_both']:.1f} [{100 * q['lo']:.1f}–{100 * q['hi']:.1f}]", f"{100 * q20['share_below']:.1f}"])
d.table("Randomized sleep scheduling (200 m field, {{C_t}} = 0.9, {{R_c}} = 40 m): ensemble share of 500 drops meeting both "
        f"targets, and share of {int(e20[0]['deployments'])} deployments whose own success rate over "
        f"{int(e20[0]['rounds'])} rounds was below 95% (last column)", rows, [500, 450, 500, 700, 1450, 1000])

# ============================================================================= 7. Limitations
d.h1("7. Threats to validity")
d.p("**Internal validity.** Coverage is measured on rasters of 0.5 m to 3.3 m; Eq. (18) and the simulations agree "
    "to within 0.001, and full coverage of the lattices is confirmed by an exact test without raster. Monte Carlo "
    "shares are tested with exact binomial tests, every family of comparisons is corrected for multiplicity, and "
    "certified designs rest on drops that played no part in choosing them. The certificate holds under the "
    "simulation model; it is only as good as the geometric and radio models behind it. The Bonferroni correction over "
    "ten attempts is conservative, and the upward search may overstate the smallest sufficient node count. The three recent "
    "baselines were re-implemented from their papers, so the original code or problem-specific tuning could do "
    "better at small node counts; Table 12 varies their main parameters, and our implementations are public. The "
    "integer program solves a restricted problem on candidate grids, so its counts bound only that problem.")
d.p("**Construct validity.** Sensing follows the binary disk model except in the Elfes experiment, and the "
    "isolated-node term is a proxy for connectivity that is accurate only at high probabilities and can be "
    "optimistic when obstacles partition the field or when link shadowing is correlated; in both cases the "
    "simulated term should be used. Energy figures count communication energy only and come from the expected "
    "number of awake rounds; battery depletion was not simulated.")
d.p("**External validity.** All results come from geometric and link-level simulation, not from a packet-level "
    "simulator or a field trial. Fields are flat; the stress study covers rectangles, an L-shape and a field with a "
    "hole, but not terrain or moving obstacles, and correlated shadowing was modeled with a node-shared component "
    "only.")

# ============================================================================= 8. Conclusion
d.h1("8. Conclusion")
d.p("Sizing a random drop for the expected coverage misses the target about half of the time. An edge-aware "
    "variance for a fixed node count and a Beta approximation turn the target into a design rule that met a 95% "
    f"requirement in {pct(beta_lo, 0)} to {pct(beta_hi, 0)} of drops over sixteen settings, at {pct(extra_lo, 0)} to "
    f"{pct(extra_hi, 0)} more nodes than the mean rule. Because the rule is an approximation, we certify every design "
    "on independent drops with a one-sided Clopper-Pearson bound and a Bonferroni correction over the attempts; "
    f"this added {pct(min(_cov_extra), 0)} to {pct(max(_cov_extra), 1)} more nodes to the coverage designs and turned "
    "their reliability into a statement with a known error probability. A joint rule adds connectivity, and the same "
    "expressions give the expected coverage under failures, k-coverage and probabilistic sensing, and extend to "
    "obstacles, shadow fading and heterogeneous radii with fixed class counts. Among buildings, and when link "
    "shadowing is correlated, the isolated-node term is optimistic and connectivity must be sized by simulation. "
    f"For planned drops at an error of 0.3{{{{r}}}}, a certified triangular lattice needed {_lat03_nodes} nodes where a "
    f"certified random drop needed {_rc_n}; at errors comparable to the radius the advantage of planning vanishes. "
    "With the node count set by these rules, the lattice reached full coverage without fitness evaluations and was "
    "not beaten by any tested setting of eight baselines at that count. "
    + (f"The stress study found the rule calibrated within sampling error in {len(_calib_ok)} of 14 settings, "
       "including small networks, very high targets and elongated and irregular fields, but optimistic for "
       + "; ".join(_lab(c) for c in _stress_rej_lo) + ", where certification is indispensable. " if _stress_rej_lo else
       f"The stress study, with small networks, very high targets and elongated and irregular fields, found no "
       f"significant miscalibration in {len(_calib_ok)} of 14 settings, and certification added at most "
       f"{pct(max(_stress_extra), 0)} more nodes there. ")
    + "A randomized sleep schedule meets its target on average over deployments but "
    "not in every deployment. Future work will add terrain, validate the rules in a packet-level simulator, and test "
    "them in a field deployment.")

d.h1("Code availability")
d.p(f"The implementation code is publicly available at: {GITHUB}. It includes all parameters, seeds, per-drop "
    "outcomes, layouts, statistical scripts and unit tests, and one script that reproduces every table and figure; "
    "Table 4 maps each result to its experiment. The version used in this article (v1.3.0) is archived at Zenodo, "
    f"DOI: {ZENODO_DOI}.")
d.h1("Funding")
d.p("This research received no external funding.")
d.h1("Conflicts of interest")
d.p("The authors declare no conflict of interest.")
d.h1("Author contributions")
d.p(f"Conceptualization, {AUTHORS[0]} and {AUTHORS[1]}; methodology, {AUTHORS[0]}; software, {AUTHORS[0]}; "
    f"validation, {AUTHORS[0]} and {AUTHORS[1]}; formal analysis, {AUTHORS[0]}; investigation, {AUTHORS[0]}; "
    f"data curation, {AUTHORS[0]}; writing—original draft preparation, {AUTHORS[0]}; writing—review and editing, "
    f"{AUTHORS[1]}; visualization, {AUTHORS[0]}; supervision, {AUTHORS[1]}.")

d.h1("References")
for i, k in enumerate(ORDER, 1):
    d.add(para(run(f"[{i}]\t", 22) + run(REFS[k], 22), jc="both", first_line=0, ind_left=454, hanging=454))
unused = [k for k in REFS if k not in ORDER]
assert not unused, unused
assert d.tab_count == 16 and d.fig_count == 9, (d.tab_count, d.fig_count)

d.save(OUT, front)
print("saved", OUT, "refs", len(ORDER), "figs", d.fig_count, "tables", d.tab_count, "eqs", d.eq_count)

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ijies_docx import Doc, blank, para, rich, run  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
_ap = argparse.ArgumentParser(description="Build the IJIES manuscript from the experiment results.")
_ap.add_argument("--root", default=os.path.dirname(HERE), help="repository root (contains results/ and figures/)")
_ap.add_argument("--template", default=os.path.join(HERE, "IJIES_Format.docx"),
                 help="IJIES Word template (download from the journal web site)")
_ap.add_argument("--out", default=os.path.join(HERE, "IJIES_Manuscript_Reliable_WSN_Deployment.docx"))
_ap.add_argument("--doi", default="10.5281/zenodo.23717649", help="Zenodo DOI of the archived code version")
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
    "nakka2025": "K. Nakka and H. M. Ammari, “Hierarchical Deployment and Square Tessellation for Connected k-Coverage in Heterogeneous Planar Wireless Sensor Networks”, ACM Transactions on Sensor Networks, Vol. 21, No. 2, Article 15, pp. 1-27, 2025.",
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

# ----------------------------------------------------------------------------- document
d = Paper(TEMPLATE)
TITLE = "Reliability-Guaranteed Sensor Deployment for Wireless Sensor Networks Using Edge-Corrected Coverage Statistics and Drop-Error-Tolerant Lattices"

ABSTRACT = (
    "Sensor networks are usually sized with formulas for the expected coverage, so about half of random drops sized "
    "this way miss the target. We present a framework in which coverage and connectivity targets "
    "hold with a stated probability. It combines an edge-corrected mean and variance of area coverage, a Beta "
    "approximation of its distribution, an edge-corrected connectivity condition, and a lattice shrunk to tolerate "
    "aerial drop errors. In sixteen settings with 300 Monte Carlo runs each, the rule met a 95 percent reliability "
    f"target in {beta_lo*100:.0f} to {beta_hi*100:.0f} percent of drops; the mean rule reached {mean_lo*100:.0f} to "
    f"{mean_hi*100:.0f} percent. With drop errors of 30 percent of the sensing radius, a tolerant lattice of "
    f"{int(e16q('triangular', 0.3)['nodes'])} nodes reached 99 percent coverage in "
    f"{100 * e16q('triangular', 0.3)['p_meet']:.0f} percent of 1,000 test drops; a random drop needed {n_rand_guar}. Against eight baselines, including three optimizers from 2025 and 2026, the lattice reached full "
    "coverage without fitness evaluations."
)
KEYWORDS = ("Wireless sensor networks, Sensor deployment, Coverage reliability, Network connectivity, Boundary effects, "
            "Metaheuristic optimization")


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
    "taken into account? The contributions are as follows.")
for item in [
    f"An edge-corrected expression for the mean and the variance of the covered fraction of a square field, with the variance computed as an exact double integral. The predicted standard deviation is within {pct(std_rel_exact, 1)} of simulation on average, against {pct(std_rel_stat, 1)} for the usual stationary approximation.",
    f"A probabilistic sizing rule built on a moment-matched Beta distribution. With a risk level of 5%, the rule met the target in {pct(beta_lo, 0)} to {pct(beta_hi, 0)} of drops over sixteen settings, and the Wilson interval contained 95% in {beta_ci_ok} of them; at risk levels of 1% and 10% it met {pct(e12_lo[0.01], 1)} to {pct(e12_hi[0.01], 1)} and {pct(e12_lo[0.1], 1)} to {pct(e12_hi[0.1], 1)} of 1,000 drops.",
    "A joint coverage and connectivity rule based on an edge-corrected isolated-node probability, expected-coverage expressions for node failures, k-coverage and probabilistic (Elfes) sensing, and extensions of the rule to heterogeneous sensing radii, obstacles with line-of-sight sensing and log-normal shadowing of the links, and a simulated connectivity term for fields that obstacles partition. The same rule sets a randomized sleep schedule that turns extra nodes into lifetime at the stated reliability.",
    "A drop-error-tolerant lattice whose expected coverage under Gaussian placement error is evaluated in closed form through the non-central chi-square distribution, and which can also be sized so that the target holds with a stated probability. It is compared with eight baselines, including three optimizers published after 2024, under a shared evaluation budget for the population-based methods, and with the best cover that integer linear programming found within a time limit. All code, seeds and raw results are public.",
]:
    d.add(para(rich(cite(item)), jc="both", first_line=0, ind_left=300, hanging=300))
d.p("The rest of the paper is organized as follows. Section 2 reviews related work. Section 3 states the system model. "
    "Section 4 derives the proposed framework. Section 5 describes the experimental setup and the baselines. Section 6 "
    "reports the results, Section 7 discusses threats to validity, and Section 8 concludes the paper.")

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
    "for k-coverage that include border effects and obstacles [@liuz]. None of "
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
d.p("**Scheduling and lifetime.** Redundant nodes can sleep without losing coverage: coverage-preserving "
    "schedules switch off nodes whose disks are covered by neighbors [@tian, @peas], randomly duty-cycled networks "
    "have analytically tractable coverage dynamics [@hsin], and lifetime can be maximized over disjoint coverage sets "
    "[@luo] or measured with coverage-differentiated metrics [@nurcan]. These schedules start from a given deployment; "
    "none of them states how many nodes must be dropped so that the schedule meets a coverage target with a stated "
    "probability.")
d.p("**Aerial deployment.** Unmanned aerial vehicles now routinely deploy sensor networks in "
    "remote areas [@hydher], which makes the drop error a design variable that is rarely included in "
    "coverage design. Table 1 summarizes where this work sits.")
d.table("Comparison with related deployment studies",
        [["Study", "Finite-field statistics", "Guarantee", "Connected", "Drop error"],
         ["[@liutowsley]", "No", "No", "No", "No"],
         ["[@bai, @zhanghou, @nakka2024, @nakka2025]", "No", "No", "Yes", "No"],
         ["[@fan, @liuz]", "Mean only", "No", "No", "No"],
         ["[@tossa, @siamantas]", "No", "No", "Yes", "No"],
         ["[@haris, @shaikh, @kheam]", "No", "No", "Partly", "No"],
         ["[@priyadarshi]", "No", "No", "Yes", "No"],
         ["This work", "Mean and variance", "Yes", "Yes", "Yes"]],
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

# ============================================================================= 4. Framework
d.h1("4. Proposed framework")
d.p("Fig. 1 shows the framework: two rules size a random drop, and planned drops use the error-tolerant lattice "
    "of Section 4.5.")
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
d.p("We evaluate {{a(x)}} by one-dimensional quadrature over a 240 × 240 grid of points.")

d.h2("4.2 Variance of the covered fraction")
d.p("Let {{a(x, y)}} be the probability that one node covers both {{x}} and {{y}}, that is, the area of the "
    "lens {{D(x, r) ∩ D(y, r) ∩ F}} divided by {{A}}. The coverage indicators of two points are correlated only "
    "through this lens, and the variance of {{C}} is")
d.eq(r"\mathrm{Var}\left(C\right)=\frac{1}{A^{2}}\int_{F}\int_{F}\left[u(\mathbf{x},\mathbf{y})^{N}-\left(1-a(\mathbf{x})\right)^{N}\left(1-a(\mathbf{y})\right)^{N}\right]d\mathbf{x}\,d\mathbf{y}")
d.eq(r"u(\mathbf{x},\mathbf{y})=1-a(\mathbf{x})-a(\mathbf{y})+a(\mathbf{x},\mathbf{y})")
d.p("The usual stationary shortcut replaces {{a(x)}} by its interior value and integrates the covariance against "
    "the distance density of two random points in a square [@mathai]. It is fast, but it ignores the fact that "
    "border points have both smaller and more variable coverage. We instead discretize Eq. (5) on an {{M × M}} grid "
    "({{M}} = 50 to 80) and obtain all {{a(x, y)}} at once from a sparse incidence matrix between the grid points and "
    "200 × 200 area elements of the field; one evaluation takes about one second.")

d.h2("4.3 Probabilistic sizing rule")
d.p("{{C}} is bounded in [0, 1] and becomes strongly skewed as it approaches 1, so a normal approximation puts too "
    "much mass above the target. We match a Beta distribution to the mean {{μ_N}} and variance {{s_N^2}} from "
    "Eqs. (4) and (5),")
d.eq(r"\alpha_{N}=\mu_{N}\nu_{N},\quad \beta_{N}=\left(1-\mu_{N}\right)\nu_{N},\quad \nu_{N}=\frac{\mu_{N}\left(1-\mu_{N}\right)}{s_{N}^{2}}-1")
d.p("and take the smallest node count whose upper tail clears the risk level,")
d.eq(r"N_{\mathrm{cov}}=\min\left\{N:\;1-I_{C_{t}}\left(\alpha_{N},\beta_{N}\right)\geq 1-\frac{\delta}{2}\right\}")
d.p("where {{I_x(α, β)}} is the regularized incomplete beta function. Half of the risk is reserved for connectivity "
    "(Section 4.4). Because Eq. (8) is monotone in {{N}} in practice, a doubling search followed by bisection needs "
    "about fifteen evaluations of Eqs. (4) and (5). When only coverage matters, {{δ/2}} is replaced by {{δ}}.")

d.h2("4.4 Connectivity, failures and extensions")
d.p("A network with an isolated node cannot be connected, and for large node counts the converse holds as well "
    "[@penrose, @bettstetter]. With {{b(x)}} defined like {{a(x)}} but for radius {{R_c}}, the expected number of "
    "isolated nodes and the resulting Poisson approximation are")
d.eq(r"\mathrm{E}\left[N_{\mathrm{iso}}\right]=\frac{N}{A}\int_{F}\left(1-b(\mathbf{x})\right)^{N-1}d\mathbf{x},\qquad P_{\mathrm{conn}}\approx e^{-\mathrm{E}\left[N_{\mathrm{iso}}\right]}")
d.p("The connectivity rule {{N_conn}} is the smallest {{N}} with {{P_conn ≥ 1 − δ/2}}, and the union bound gives the "
    "joint rule")
d.eq(r"N^{\star}=\max\left(N_{\mathrm{cov}},\,N_{\mathrm{conn}}\right)\;\Rightarrow\;P\left(C\geq C_{t}\wedge\mathrm{connected}\right)\geq 1-\delta")
d.p("Random failures thin a uniform drop into another uniform drop, so they multiply {{a(x)}}, {{a(x, y)}} and "
    "{{b(x)}} by {{1 − f}} in every expression above, and in Eq. (9) the prefactor {{N}} becomes {{(1 − f)N}}. The expected k-covered fraction and the expected detection "
    "probability under the Elfes sensing model, in the form used in [@zou], follow the same pattern:")
d.eq(r"\mathrm{E}\left[C_{k}\right]=\frac{1}{A}\int_{F}\sum_{i=k}^{N}\binom{N}{i}a(\mathbf{x})^{i}\left(1-a(\mathbf{x})\right)^{N-i}d\mathbf{x}")
d.eq(r"p(d)=\begin{cases}1, & d\leq r-r_{e}\\ e^{-\lambda\left(d-r+r_{e}\right)^{\gamma}}, & r-r_{e}<d<r+r_{e}\\ 0, & d\geq r+r_{e}\end{cases}")
d.eq(r"\mathrm{E}\left[P_{\mathrm{det}}\right]=\frac{1}{A}\int_{F}\left[1-\left(1-\frac{1}{A}\int_{F}p\left(\left|\mathbf{x}-\mathbf{y}\right|\right)d\mathbf{y}\right)^{N}\right]d\mathbf{x}")
d.p("The inner integral in Eq. (13) is a convolution of the field indicator with {{p(d)}} and is computed with one "
    "fast Fourier transform.")

d.h2("4.5 Lattices and drop errors")
d.p("An intuitive planned layout is a square grid whose spacing equals the sensing diameter, so that neighboring "
    "disks just touch: {{n = ⌈L/(2r)⌉ + 1}} nodes per side, including the field boundary, with spacing "
    "{{L/(n − 1) ≤ 2r}}. When {{L/(2r)}} is an integer the spacing is exactly {{2r}}, the center of each cell is "
    "{{√2r}} from the nearest node, and this diameter-spaced grid covers only")
d.eq(r"C_{\mathrm{grid}}=\frac{\pi r^{2}}{\left(2r\right)^{2}}=\frac{\pi}{4}\approx 0.785")
d.p("of the field, whatever its size; otherwise the spacing is somewhat shorter and the coverage higher, but still "
    "below 1. Placing nodes at the centers of square cells of side {{h ≤ √2r}} covers every point, because no point "
    "of a cell is farther than {{h/√2}} from its center:")
d.eq(r"n=\left\lceil \frac{L}{\sqrt{2}\,r}\right\rceil ,\qquad h=\frac{L}{n},\qquad R_{c}\geq h")
d.p("The triangular lattice, with neighbors {{√3r}} apart and rows {{1.5r}} apart, is the least dense full cover of "
    "the plane [@kershner] and needs {{R_c ≥ √3r}} for connectivity [@bai]. We search over lattice offsets and drop "
    "border nodes whose disks are already covered, which removes the nodes that only graze a corner.")
d.p("For a planned drop, {{|g_j + e_j − x|^2/σ^2}} follows a non-central chi-square law with two degrees of freedom "
    "and non-centrality {{|g_j − x|^2/σ^2}} [@simon]. The node covers {{x}} with probability {{P_j(x)}}, and "
    "independence across nodes gives the exact expected coverage")
d.eq(r"P_{j}(\mathbf{x})=F_{\chi'^{2}_{2}}\left(\frac{r^{2}}{\sigma^{2}};\,\frac{\left|\mathbf{g}_{j}-\mathbf{x}\right|^{2}}{\sigma^{2}}\right)")
d.eq(r"\mathrm{E}\left[C_{\sigma}\right]=\frac{1}{A}\int_{F}\left[1-\prod_{j}\left(1-P_{j}(\mathbf{x})\right)\right]d\mathbf{x}")
d.p("The error-tolerant lattice is designed for a shrunken radius {{κr}}, and {{κ}} is lowered in steps of 0.02 until "
    "Eq. (17) reaches the target. Eq. (17) controls only the mean. When the target must hold with probability "
    "{{1 − δ}}, {{κ}} is lowered instead until the lower end of the 95% Wilson interval of the share of 500 simulated "
    "drops with {{C ≥ C_t}} reaches {{1 − δ}}; the same random-number seed is used for every {{κ}} (common random "
    "numbers). Table 2 gives both "
    "procedures.")
d.table("Pseudocode of the two design procedures",
        [["Algorithm 1: random drop"],
         ["Input {{L, r, R_c, C_t, δ, f}}\n1: {{N_cov}} ← doubling and bisection on Eq. (8)\n2: {{N_conn}} ← doubling and bisection on Eq. (9)\n3: return {{N^⋆}} = max({{N_cov}}, {{N_conn}})"],
         ["Algorithm 2: planned drop"],
         ["Input {{L, r, σ, C_t}} (and {{δ}})\n1: {{κ}} ← 1\n2: build triangular (or square) lattice for radius {{κr}}, prune border nodes\n3: mean design: if Eq. (17) ≥ {{C_t}} return lattice;\n    reliability design: if the Wilson lower bound of P({{C ≥ C_t}}) over 500 simulated drops ≥ {{1 − δ}} return lattice\n4: {{κ}} ← {{κ}} − 0.02 and go to 2"]],
        [4600], header_rows=0, align=["left"])

d.h2("4.6 Obstacles and shadowing")
d.p("Practical sites contain buildings and other obstacles [@liuz, @ahmed]. Let {{F_f}} be the part of the field outside the obstacles {{O}}, let nodes "
    "fall uniformly over {{F_f}}, and let a node sense a point only when the segment between them crosses no "
    "obstacle. Eq. (3) then becomes")
d.eq(r"a(\mathbf{x})=\frac{\left|\left\{\mathbf{y}\in F_{f}:\,\left|\mathbf{x}-\mathbf{y}\right|\leq r,\ \left[\mathbf{x},\mathbf{y}\right]\cap O=\emptyset\right\}\right|}{\left|F_{f}\right|}")
d.p("and every integral over {{F}} in Eqs. (4)-(6) runs over {{F_f}}. For the radio we use log-distance path loss "
    "with exponent {{η}} and log-normal shadowing with standard deviation {{σ_s}} dB, independent across links "
    "[@rappaport, @bettstetterhartmann]. With {{R_c}} the median range and an extra loss {{L_o}} for a link that "
    "crosses an obstacle, two nodes at {{x}} and {{y}} are linked with probability")
d.eq(r"\ell(\mathbf{x},\mathbf{y})=\Phi\left(\frac{10\eta\log_{10}\left(R_{c}/\left|\mathbf{x}-\mathbf{y}\right|\right)-L_{o}\,o_{\mathbf{x}\mathbf{y}}}{\sigma_{s}}\right)")
d.eq(r"b(\mathbf{x})=\frac{1}{\left|F_{f}\right|}\int_{F_{f}}\ell(\mathbf{x},\mathbf{y})\,d\mathbf{y}")
d.p("where {{o_xy}} is 1 when the segment crosses an obstacle and 0 otherwise. Eq. (19) reduces to the unit disk as "
    "{{σ_s → 0}}, and with Eq. (20) in place of the disk area, Eqs. (9) and (10) apply unchanged. Both "
    "{{a(x)}} and {{b(x)}} are computed on rasters with an exact segment-rectangle test. Eq. (9) counts isolated "
    "nodes only. Buildings can split the network into large pieces in which every node still has a neighbor, so "
    "in obstructed fields Eq. (9) may overstate connectivity. We therefore also size the connectivity term by "
    "simulation: starting from the {{N_conn}} given by Eqs. (9) and (20), {{N}} is raised in steps of five until the "
    "connected share of 2,000 simulated link graphs reaches {{1 − δ/2}}, and the smallest qualifying {{N}} within "
    "the last step of five is kept; when the starting value already qualifies, the four counts below it are checked "
    "as well. The coverage term stays analytical.")

d.p("**Complexity.** Eq. (4) costs {{O(G^2 Q)}} on a {{G × G}} grid with {{Q}} quadrature nodes, Eq. (5) {{O(M^4)}} on an "
    "{{M × M}} grid and Eq. (17) {{O(G^2 K)}}, with {{K}} the nodes within {{r + 6σ}} of a grid point. None of these "
    "needs a fitness evaluation. The reliability design of the lattice (Section 4.5) adds 500 simulated drops per "
    f"{{{{κ}}}} step, {500 * (int(round((1 - e16q('triangular', 0.3)['kappa']) / 0.02)) + 1):,} coverage evaluations at "
    "{{σ}} = 0.3{{r}}.")

d.h2("4.7 Heterogeneous radii and sleep scheduling")
d.p("If each node draws its sensing radius from {{r_m}} with probability {{w_m}}, one node covers {{x}} with "
    "probability")
d.eq(r"a(\mathbf{x})=\sum_{m}w_{m}\,a_{m}(\mathbf{x}),\qquad a(\mathbf{x},\mathbf{y})=\sum_{m}w_{m}\,a_{m}(\mathbf{x},\mathbf{y})")
d.p("where {{a_m}} uses radius {{r_m}}, so Eqs. (4)-(8) apply unchanged [@lazos]. For scheduling, every node "
    "wakes independently with probability {{q}} in each round [@hsin]. The awake nodes form a thinned uniform drop, "
    "so they enter every expression above through {{a(x) → q a(x)}}, as failures do with {{f = 1 − q}}. For a "
    "deployment of {{N}} nodes the schedule uses the smallest {{q}} that keeps both conditions of Eq. (10),")
d.eq(r"q^{\star}=\min\left\{q:\;P\left(C_{q}\geq C_{t}\right)\geq 1-\frac{\delta}{2},\;P_{\mathrm{conn},q}\geq 1-\frac{\delta}{2}\right\}")
d.p("found by bisection on a 0.01 grid. Each node is then active in a share {{q^⋆}} of the rounds, so with the "
    "first-order radio model [@heinzelman] the expected communication-energy lifetime in rounds grows by the factor {{1/q^⋆}} over an "
    "always-on network, while each round meets both targets with probability at least {{1 − δ}} until batteries "
    "begin to run out. In each round every awake node sends and receives one packet over the distance {{R_c}}.")

# ============================================================================= 5. Setup
d.h1("5. Experimental setup")
d.p("All methods were implemented in Python 3 with NumPy and SciPy, and each run used one processor core. Coverage of a "
    "layout is the share of cell centers of a regular raster that fall inside at least one disk, with a resolution between "
    "0.5 m and 3.3 m depending on the field size and the experiment (all rasters are listed in the code). Means are reported with "
    "standard deviations or Student t intervals; Wilson 95% intervals [@wilson] are shown for the key shares (Tables 6, 8 "
    "and 11, Figs. 4 and 8) and can be computed for every share from the raw per-run files in the repository. Shares of "
    "successful drops are tested against their nominal value with the exact binomial test, paired comparisons use "
    "the Wilcoxon signed-rank test [@wilcoxon] with the matched-pairs rank-biserial correlation as effect size, and "
    "the nine deployment methods are compared with the Friedman test, using seeds as blocks. Within each family of "
    "tests the p-values are corrected with the Holm-Bonferroni procedure. Table 3 lists the settings of each "
    "experiment.")
d.table("Simulation settings",
        [["Experiment", "Field (m)", "Parameters", "Runs"],
         ["Mean model", "200", "{{r}} = 10-25 m, {{N}} = 10-200", "100"],
         ["Variance, sizing", "200, 400", "{{r}} = 15-25 m, {{C_t}} = 0.80-0.99, {{δ}} = 0.05", "300"],
         ["Connectivity", "200", "{{r}} = 20 m, {{R_c}} = 30, 40 m", "300 / 500"],
         ["Lattices", "500", "{{r}} = 25-100 m", "exact"],
         ["Drop error", "500", "{{r}} = 62.5 m, {{σ/r}} = 0-0.5, {{C_t}} = 0.99, {{δ}} = 0.05", "100; 500 / 1,000"],
         ["Baselines", "500", "{{r}} = 62.5 m, {{N}} = 25-36", f"{n_seeds} seeds"],
         ["Extensions", "200", "{{r}} = 20 m, {{R_c}} = 40 m, {{k}} = 1-3, {{f}} = 0.1-0.3, Elfes", "100"],
         ["Risk level", "200", "{{r}} = 20 m, {{C_t}} = 0.80-0.99, {{δ}} = 0.01, 0.10", "1,000"],
         ["Heterogeneous", "200", "{{r}} = 15 / 25 m in equal shares, {{C_t}} = 0.80-0.99", "500"],
         ["Scheduling", "200", "{{r}} = 20 m, {{R_c}} = 40 m, {{C_t}} = 0.9, {{N}} = 1-3 × {{N^⋆}}", "500"],
         ["ILP", "500", "{{r}} = 62.5 m, 10 m grids", "20 min limit"],
         ["Environment", "200", "{{r}} = 20 m, {{R_c}} = 40 m, {{C_t}} = 0.9, {{η}} = 3, {{σ_s}} = 0/8 dB, {{L_o}} = 20 dB", "300 / 500"]],
        [1300, 750, 2000, 600])
d.p("**Baselines.** We compared the proposed lattice with random placement, VFA [@zou], PSO [@kennedy], GWO "
    "[@mirjalili], a real-coded genetic algorithm (GA) [@holland, @eshelman], and three methods published after 2024: VASF-PSO "
    "[@haris], ICGWO [@shaikh] and DAR-SSA [@kheam]. "
    "The last three were re-implemented from their published descriptions; details that the papers leave open were "
    "set to common default values and are listed in Table 4 and in the code. All population methods used 30 agents "
    "and 300 iterations, that is, the same budget of 9,030 fitness evaluations, the same 80 × 80 fitness raster, the "
    "same field-boundary clipping and the same final 250 × 250 evaluation raster. Every method returns the best layout "
    "found during its run; GWO and ICGWO keep the three best solutions found so far as leaders, as in the reference "
    "implementation [@mirjalili]. No method was tuned to this problem: each used its published or default parameters, "
    "and all methods received the same 30 seeds per node count. VFA uses no fitness function and ran for 400 iterations. "
    "For a fixed node count {{N}}, the proposed layout is the pruned triangular lattice built for the smallest design "
    "radius that needs at most {{N}} nodes, found by bisection over [0.3{{r}}, 3{{r}}]. When {{N}} exceeds the count of a "
    "full cover, the design radius falls below {{r}} and the spare nodes become overlap.")
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
    f"Over the 80 settings of Table 5 its mean absolute error is {exa['MAE']:.4f}, against {poi['MAE']:.3f} for the "
    f"Poisson model and {lin['MAE']:.3f} for the linear estimator.")
d.figure(os.path.join(FIG, "paper_fig2_models.png"), "Mean coverage of the three models against simulation (200 m field, sensing radius 20 m)")
d.table("Error of the mean models against 100-run simulation means (200 m field, {{r}} = 10-25 m, {{N}} = 10-200; 80 settings)",
        [["Model", "MAE", "RMSE", "Max error"],
         ["Linear estimator", f"{lin['MAE']:.3f}", f"{lin['RMSE']:.3f}", f"{lin['MaxAbs']:.3f}"],
         ["Poisson model", f"{poi['MAE']:.3f}", f"{poi['RMSE']:.3f}", f"{poi['MaxAbs']:.3f}"],
         ["Edge-corrected, Eq. (4)", f"{exa['MAE']:.4f}", f"{exa['RMSE']:.4f}", f"{exa['MaxAbs']:.4f}"]],
        [1900, 900, 900, 900])

d.h2("6.2 Variance and the probabilistic rule")
d.p(f"Fig. 3 shows that the edge-aware variance of Eq. (5) tracks the spread of 300 simulated drops, with a mean "
    f"relative error of {pct(std_rel_exact, 1)}. The stationary approximation is off by {pct(std_rel_stat, 1)} on "
    f"average and underestimates the spread at {'every' if stat_all_under else 'almost every'} node count, by "
    f"{pct(stat_n10, 0)} at {{{{N}}}} = {int(stat_nmin_val)} and {pct(stat_nmax, 0)} at {{{{N}}}} = {int(stat_nmax_N)}: "
    "with few nodes the border cells hold much of the covered area, and with many nodes they hold most of the "
    "uncovered area.")
d.figure(os.path.join(FIG, "paper_fig3_variance.png"), "Standard deviation of the covered fraction against node count (200 m field, sensing radius 20 m, 300 simulated drops per point)")
d.p(f"Fig. 4 and Table 6 show what this means for sizing. Choosing {{{{N}}}} so that the mean equals the target "
    f"met the target in only {pct(mean_lo, 0)} to {pct(mean_hi, 0)} of drops. The normal approximation reached "
    f"{pct(norm_lo, 0)} to {pct(norm_hi, 0)}; at the 0.99 targets, where the distribution is most skewed, it "
    f"stayed between {pct(norm99_lo, 0)} and {pct(norm99_hi, 0)} in all four settings. The Beta rule reached {pct(beta_lo, 0)} to {pct(beta_hi, 0)}, and its Wilson interval contained the "
    f"intended 95% in {beta_ci_ok} of the 16 settings (normal rule: {norm_ci_ok}). Holm-corrected exact binomial tests "
    f"rejected the nominal 95% for the mean rule in {mean_rej} of 16 settings and for the Beta rule in "
    f"{'none' if beta_not_rej == 16 else 16 - beta_not_rej}. The price of the guarantee is "
    f"{pct(extra_lo, 0)} to {pct(extra_hi, 0)} more nodes than the mean rule.")
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
        rows, [700, 480, 960, 760, 1700])

d.h2("6.3 Connectivity and the joint rule")
d.p("Fig. 5 compares the isolated-node model of Eq. (9) with simulation. The model tracks the simulated "
    "probability of no isolated node closely. Full connectivity needs more nodes at low and medium probabilities, "
    "because small groups can split off together, but the curves meet above about 0.95.")
d.figure(os.path.join(FIG, "paper_fig5_connectivity.png"), "Connectivity of random drops against node count (200 m field, sensing radius 20 m, 300 drops per point; distances are the communication range, markers are simulations)")
jr = lambda rc, t, rule: joint[(rc, t, rule)]
joint_p40 = next(t["p_holm"] for t in tests if t["family"].startswith("D.") and t["comparison"] == "joint, Rc=40, Ct=0.9")
d.p(f"With {{{{R_c}}}} = 40 m and {{{{C_t}}}} = 0.9, sizing for coverage alone gave "
    f"{int(jr(40.0, 0.9, 'coverage_only')['N'])} nodes and both targets held in {pct(jr(40.0, 0.9, 'coverage_only')['p_both'], 1)} "
    f"of 500 drops; the joint rule added {int(jr(40.0, 0.9, 'joint')['N'] - jr(40.0, 0.9, 'coverage_only')['N'])} nodes "
    f"and raised this to {pct(jr(40.0, 0.9, 'joint')['p_both'], 1)}, which does not differ significantly from the "
    f"promised 95% (one-sided binomial test, Holm-corrected {{{{p}}}} = {joint_p40:.2f}). With the shorter range of 30 m, coverage-only sizing "
    f"left the network connected in only {pct(jr(30.0, 0.9, 'coverage_only')['p_conn'], 1)} of drops, while the joint "
    f"rule ({int(jr(30.0, 0.9, 'joint')['N'])} nodes) met both targets in {pct(jr(30.0, 0.9, 'joint')['p_both'], 1)}. "
    "The rule of thumb that {{R_c}} ≥ 2{{r}} ensures connectivity [@zhanghou] presupposes full coverage; at a 90% "
    f"target with {{{{R_c}}}} = 2{{{{r}}}} = 40 m, {pct(1 - jr(40.0, 0.9, 'coverage_only')['p_conn'], 1)} of the "
    "coverage-sized drops were still disconnected.")

d.h2("6.4 Lattice layouts")
d.p(f"For {{{{L}}}} = 500 m and {{{{r}}}} = 62.5 m the diameter-spaced grid leaves "
    f"{pct(1 - g625['diameter_coverage'], 1)} of the field uncovered, in line with Eq. (14): a four-pointed gap sits at the "
    "center of every grid cell. Over the seven radii of Table 7 it never reaches full coverage, while the corrected "
    "square and pruned triangular lattices always do; the triangular lattice needs "
    f"{int(g625['triangular_nodes'])} instead of {int(g625['square_nodes'])} nodes in the example case and "
    f"{pct(tri_saving_min, 0)} to {pct(tri_saving, 0)} fewer nodes over the seven radii.")
rows = [["{{r}} (m)", "Diameter grid nodes, coverage", "Square nodes", "Triangular nodes"]]
for q in e5:
    rows.append([f"{q['r']:g}", f"{int(q['diameter_nodes'])}, {pct(q['diameter_coverage'], 1)}", f"{int(q['square_nodes'])}",
                 f"{int(q['triangular_nodes'])}"])
d.table("Lattice rules in a 500 m field (square and triangular cover 100%)", rows, [800, 1650, 1050, 1100])
_ig, _id = e13["ILP, guaranteed"], e13["ILP, demand points"]
d.p("How far is the triangular lattice from the fewest possible nodes? We solved the set-cover program of "
    f"[@chakrabarty] on a 10 m grid of {int(_ig['candidates']):,} candidate positions and {int(_ig['demand_points']):,} "
    f"demand points with the HiGHS solver [@huangfu], {int(_ig['seconds'] // 60)} min per run. Requiring every demand "
    f"cell to be covered entirely (radius reduced by half a cell diagonal), the best layout found used "
    f"{int(_ig['nodes'])} nodes, and the solver proved that no grid layout meeting this conservative condition "
    f"needs fewer than {int(_ig['dual_bound'])}. Covering only the demand points gave {int(_id['nodes'])} nodes (bound "
    f"{int(_id['dual_bound'])}), but that layout covered {pct(_id['coverage'], 2)} of the field. The "
    f"{int(e13['Triangular lattice']['nodes'])}-node lattice thus covers the whole field with fewer nodes than the "
    "best grid layout that the integer program found in 20 minutes, and with only "
    f"{['no', 'one', 'two', 'three'][int(e13['Triangular lattice']['nodes']) - int(_ig['dual_bound'])]} node more than the program's lower bound for "
    "grid layouts meeting this condition, while the Kershner density "
    f"bound for the interior alone is {int(e13['Kershner density bound (interior)']['nodes'])} nodes [@kershner].")

d.h2("6.5 Drop errors")
_t02, _t03, _t05 = e16q("triangular", 0.2), e16q("triangular", 0.3), e16q("triangular", 0.5)
_s05 = e16q("square", 0.5)
_e8share = {}
for _q in load(os.path.join("raw", "E8_runs.csv")):
    _k = (round(_q["sigma_over_r"], 1), _q["lattice"])
    _e8share.setdefault(_k, []).append(_q["coverage"] >= 0.99)
_e8share = {k: sum(v) / len(v) for k, v in _e8share.items()}
d.p(f"Fig. 6 and Table 8 show the node counts needed when every node lands with a Gaussian error, for the mean "
    f"design ({{{{E[C] ≥ 0.99}}}}) and for the reliability design ({{{{C ≥ 0.99}}}} in at least 95% of drops). "
    f"Without correction, the 33-node triangular lattice drops to {pct(e8_naive02['naive_expected'], 1)} expected "
    f"coverage at {{{{σ}}}} = 0.2{{{{r}}}}. The mean design restores 0.99 with {int(e8_naive02['robust_nodes'])} nodes "
    f"({{{{κ}}}} = {e8_naive02['kappa']:.2f}), but reaches 0.99 in only {pct(_e8share[(0.2, 'triangular')], 0)} of 100 drops; the "
    f"reliability design needs {int(_t02['nodes'])} nodes ({{{{κ}}}} = {_t02['kappa']:.2f}). At {{{{σ}}}} = 0.3{{{{r}}}}, "
    f"about 19 m, the triangular lattice needs {int(e8_03['triangular']['robust_nodes'])} nodes for the mean and "
    f"{int(_t03['nodes'])} for the reliability target, against {n_rand_mean} and {n_rand_guar} for a random drop sized "
    f"by the mean rule and by the Beta rule; the field-to-radius ratio is the same as in the 200 m, {{{{r}}}} = 25 m "
    f"setting of Table 6, where the {n_rand_guar}-node Beta design met the 0.99 target in "
    f"{pct(next(q for q in beta_rows if q['L'] == 200 and q['r'] == 25 and q['target'] == 0.99)['p_meet'], 1)} of drops. "
    f"On 1,000 new drops per layout the reliability designs met 0.99 in "
    f"{pct(min(q['p_meet'] for q in e16), 1)} to {pct(max(q['p_meet'] for q in e16), 1)} of cases; the lowest share "
    f"({pct(_t03['p_meet'], 1)}, Wilson interval {pct(_t03['lo'], 1)} to {pct(_t03['hi'], 1)}) is slightly below the "
    f"search estimate of {pct(_t03['search_share'], 1)}, because choosing {{{{κ}}}} on one set of drops is mildly "
    f"optimistic, but it does not differ significantly from 95%. The square lattice is the cheaper reliability design "
    f"at {{{{σ}}}} = 0.2{{{{r}}}} ({int(e16q('square', 0.2)['nodes'])} against {int(_t02['nodes'])} nodes). At "
    f"{{{{σ}}}} = 0.5{{{{r}}}} the square lattice needs fewer nodes than the triangular one in the mean design "
    f"({int(e8_05['square']['robust_nodes'])} against {int(e8_05['triangular']['robust_nodes'])}), because the "
    "triangular advantage relies on accurate positions. The 100-run simulations of the mean designs agree with "
    f"Eq. (17) to within {e8_gap:.3f}.")
d.figure(os.path.join(FIG, "paper_fig7_placement.png"), "Nodes needed for 99% coverage against the drop error: error-tolerant lattices sized for the mean (solid) and for 99% coverage in 95% of drops (dashed), and random drops (500 m field, sensing radius 62.5 m)")
rows = [["{{σ/r}}", "{{E[C] ≥ 0.99}}: tri. / sq.", "{{P(C ≥ 0.99) ≥ 0.95}}: tri. / sq.", "Met (%), reliable tri. [95% CI]"]]
for s_ in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
    t_ = next(q for q in e8 if abs(q["sigma_over_r"] - s_) < 1e-9 and q["kind"] == "triangular")
    q_ = next(q for q in e8 if abs(q["sigma_over_r"] - s_) < 1e-9 and q["kind"] == "square")
    if s_ == 0.0:
        rel_ = f"{int(t_['robust_nodes'])} / {int(q_['robust_nodes'])}"
        met_ = "100.0 (exact)"
    else:
        a_, b_ = e16q("triangular", s_), e16q("square", s_)
        rel_ = f"{int(a_['nodes'])} / {int(b_['nodes'])}"
        met_ = f"{100 * a_['p_meet']:.1f} [{100 * a_['lo']:.1f}–{100 * a_['hi']:.1f}]"
    rows.append([f"{s_:.1f}", f"{int(t_['robust_nodes'])} / {int(q_['robust_nodes'])}", rel_, met_])
d.table("Error-tolerant lattices for 99% coverage (500 m field, {{r}} = 62.5 m): node counts of the mean and the reliability design; shares from 1,000 validation drops", rows,
        [500, 1250, 1350, 1500])

d.h2("6.6 Comparison with optimization methods")
lat25, lat30, lat33 = (e10q("Proposed lattice", n) for n in (25, 30, 33))
pop_methods = ["PSO", "GA", "GWO", "ICGWO", "VASF-PSO", "DAR-SSA"]
best25 = max((e10q(m, 25) for m in pop_methods + ["VFA"]), key=lambda q: q["mean"])
best30 = max((e10q(m, 30) for m in pop_methods + ["VFA"]), key=lambda q: q["mean"])
best_pop33 = max((e10q(m, 33) for m in pop_methods), key=lambda q: q["mean"])
vfa33 = e10q("VFA", 33)
lat_conn = all(e10q("Proposed lattice", n)["connected_share"] == 1 for n in (33, 36))
lat_time = e10q("Proposed lattice", 33)["seconds"]
pop_time = sum(e10q(m, 33)["seconds"] for m in pop_methods) / len(pop_methods)
d.p(f"Fig. 7 and Table 9 compare the lattice with the eight baselines for a fixed node count. With 33 nodes, the "
    f"count that the triangular lattice needs for a full cover, the lattice covered {pct(lat33['mean'], 1)} of the "
    f"field. The best population method, {best_pop33['method']}, reached {pct(best_pop33['mean'], 1)} on average "
    f"(worst run {pct(best_pop33['worst'], 1)}) after 9,030 fitness evaluations, and VFA reached "
    f"{pct(vfa33['mean'], 1)}. With 30 nodes the lattice still led ({pct(lat30['mean'], 1)} against "
    f"{pct(best30['mean'], 1)} for {best30['method']}). With only 25 nodes it did not: stretching the lattice opens "
    f"regular gaps, and {best25['method']} covered {pct(best25['mean'], 1)} against {pct(lat25['mean'], 1)}. An "
    "optimizer thus remains useful when the budget is fixed below the count of Section 4. The Friedman test rejected equal performance of the "
    f"nine methods at every node count (largest Holm-corrected {{{{p}}}} = {sci(fried_max_p)}), and after Holm "
    f"correction {wil_sig} of the {len(wil)} Wilcoxon comparisons with the lattice were significant at the 0.05 level (at 25 nodes in favor of the baselines that covered more).")
d.p(("At 33 and 36 nodes the lattice was connected for {{R_c}} = √3{{r}} by construction, while many optimized "
     "layouts were not. " if lat_conn else "")
    + f"A tight layout has a cost: when the 33-node "
    f"layouts were dropped with an error of 0.2{{{{r}}}} (20 draws per run), the lattice kept {pct(lat33['noisy_mean'], 1)} coverage, "
    f"VFA {pct(vfa33['noisy_mean'], 1)} and {best_pop33['method']} {pct(best_pop33['noisy_mean'], 1)}, because VFA "
    "keeps more overlap. The fixed-count lattice here is built for a design radius of about 0.95{{r}} and is slightly "
    f"denser than the full-cover lattice of Section 6.5, which keeps only {pct(e8_naive02['naive_expected'], 1)} at the same "
    f"error; the error-tolerant lattice of Section 6.5 restores an expected coverage of 0.99 with "
    f"{int(e8_naive02['robust_nodes'])} nodes.")
d.figure(os.path.join(FIG, "paper_fig8_baselines.png"), "Coverage against node count for the proposed lattice and eight baselines (500 m field, sensing radius 62.5 m, " + f"{n_seeds} seeds)")
rows = [["Method", "{{N}} = 25", "{{N}} = 30", "{{N}} = 33"]]
for m in ["Random", "VFA", "PSO", "GA", "GWO", "ICGWO", "VASF-PSO", "DAR-SSA", "Proposed lattice"]:
    f_ = lambda q: f"{100*q['mean']:.1f} ± {100*q['std']:.1f}"
    rows.append([m.replace("Proposed lattice", "Proposed"), f_(e10q(m, 25)), f_(e10q(m, 30)), f_(e10q(m, 33))])
d.table(f"Coverage (%) of the proposed lattice and the baselines, mean ± std over {n_seeds} seeds (the lattice is deterministic)", rows,
        [1150, 1160, 1160, 1160])

d.h2("6.7 Accuracy of the extensions")
d.p(f"The models of Section 4.4 had mean absolute errors of {e9err['k-coverage'][0]:.4f} for k-coverage ({{{{k}}}} = 1 to 3), "
    f"{e9err['failures-coverage'][0]:.4f} for coverage with failure rates of 0.1 to 0.3, and "
    f"{e9err['probabilistic-sensing'][0]:.4f} for the Elfes model ({{{{r_e}}}} = 5 m, {{{{λ}}}} = 0.1, "
    f"{{{{γ}}}} = 1). For connectivity under failures, Eq. (9) again behaves as an isolated-node bound: it is "
    f"optimistic at low probabilities and within {conn_hi_gap:.3f} of the simulated connectivity once it predicts "
    "more than 0.9, so a small margin is advisable. "
    "")

d.h2("6.8 Obstacles and shadowing")
o_, s8, u0, u8 = env_cfg_names
E_ = lambda sc, rule: env[(sc, rule)]
u0_open_p = env_tests[f"{u0}, open_field_rule, N={int(E_(u0, 'open_field_rule')['N'])}"]["p_holm"]
d.p("We repeated the joint design of Section 6.3 in four environments: an open and an urban field (nine 40 m blocks, "
    f"36% of the field), each without and with 8 dB shadowing (Table 3). Over seven node counts each, Section 4.6 predicted the mean coverage within "
    f"{env_mean_err:.4f}, its standard deviation within {pct(env_std_rel, 0)} on "
    f"average and the probability of no isolated node within {env_iso_err:.3f} on average.")
S_ = lambda sc: E_(sc, "simulated_connectivity_rule")
A_ = lambda sc: E_(sc, "environment_aware_rule")
O_ = lambda sc: E_(sc, "open_field_rule")
u0_aware_p = env_tests[f"{u0}, environment_aware_rule, N={int(A_(u0)['N'])}"]["p_holm"]
u0_rows = [q for q in e11m if q["scenario"] == u0 and q["mc_p_no_isolated"] >= 0.9]
u0_gap = max(u0_rows, key=lambda q: q["mc_p_no_isolated"] - q["mc_p_conn"])
d.p(f"Fig. 8 compares the open-field rule of Section 4.4 ({int(O_(o_)['N'])} nodes everywhere) with the aware "
    "rule, analytical and with simulated connectivity. Shadowing alone raises the mean degree at a fixed median "
    f"range [@bettstetterhartmann], so both aware rules fell to the coverage term ({int(A_(s8)['N'])} nodes; "
    f"{pct(A_(s8)['p_both'], 1)} and {pct(S_(s8)['p_both'], 1)} of drops met both targets). Buildings without shadowing cut the links that cross them: the open-field rule "
    f"reached only {pct(O_(u0)['p_both'], 1)} (Holm-corrected {{{{p}}}} = {sci(u0_open_p)}) and the analytical aware rule, with "
    f"{int(A_(u0)['N'])} nodes, {pct(A_(u0)['p_both'], 1)} (Holm-corrected {{{{p}}}} = {sci(u0_aware_p)}). The blocks split the "
    f"network into corridors in which every node keeps a neighbor; at {int(u0_gap['N'])} nodes "
    f"{pct(u0_gap['mc_p_no_isolated'], 1)} of drops had no isolated node but only {pct(u0_gap['mc_p_conn'], 1)} were "
    f"connected. With simulated connectivity, {int(S_(u0)['N'])} nodes reached {pct(S_(u0)['p_both'], 1)} "
    f"[{pct(S_(u0)['lo'], 1)}, {pct(S_(u0)['hi'], 1)}]. With 8 dB shadowing, links through buildings rejoin the "
    f"corridors and all three rules reached {pct(S_(u8)['p_both'], 1)}. The simulated rule met the 95% requirement "
    f"in all four environments, at {int(S_(o_)['N']) - int(O_(o_)['N'])} extra nodes in the open field and "
    f"{int(S_(u0)['N']) - int(O_(u0)['N'])} in the unshadowed urban layout.")
d.figure(os.path.join(FIG, "paper_fig10_environment.png"), "Share of 500 drops meeting both targets under three rules (200 m field, sensing radius 20 m, communication range 40 m, target 0.9), with Wilson intervals; bar labels are node counts, the dashed line is 0.95")

d.h2("6.9 Risk level, heterogeneous radii and sleep scheduling")
d.p(f"Table 10 repeats the sizing study of Section 6.2 at risk levels of 1% and 10% with 1,000 drops per setting. "
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
d.p("For heterogeneous nodes, half with {{r}} = 15 m and half with 25 m, Eqs. (4)-(6) with Eq. (21) predicted the "
    f"standard deviation of coverage within {pct(e15_std_rel, 1)} on average over the twelve node counts tested "
    f"(at most {pct(e15_std_max, 1)}). The mixture rule needed "
    f"{', '.join(str(int(q['N'])) for q in _m)} nodes for {{{{C_t}}}} = 0.80 to 0.99 and met the target in "
    f"{pct(min(q['p_meet'] for q in _m), 1)} to {pct(max(q['p_meet'] for q in _m), 1)} of 500 drops. Sizing for the "
    f"mean radius of 20 m used up to {max(int(a['N']) - int(m['N']) for a, m in zip(_a, _m))} more nodes, and sizing "
    "for the radius with the same mean area (20.6 m) used fewer nodes but "
    + (f"met the target in only {pct(min(q['p_meet'] for q in _r), 1)} of drops at {{{{C_t}}}} = "
       f"{min(_r, key=lambda q: q['p_meet'])['target']:.2f}" if _rms_rej else "came close to the limit")
    + ", because equal mean area does not imply equal overlap.")
d.p(f"Table 11 applies the schedule of Section 4.7 to the joint design of Section 6.3 ({{{{C_t}}}} = 0.9, "
    f"{{{{R_c}}}} = 40 m, {int(e14[0]['N_joint'])} nodes). Dropping 1.5, 2 and 3 times as many nodes let each node "
    f"sleep in {pct(1 - e14[1]['q'], 0)}, {pct(1 - e14[2]['q'], 0)} and {pct(1 - e14[3]['q'], 0)} of the rounds, so "
    f"the lifetime grew by factors of {e14[1]['lifetime_gain']:.2f}, {e14[2]['lifetime_gain']:.2f} and "
    f"{e14[3]['lifetime_gain']:.2f}. In 500 independent drops, each with one random wake-up pattern, the awake set "
    f"met both targets in {pct(min(q['p_both'] for q in e14[1:]), 1)} to {pct(max(q['p_both'] for q in e14[1:]), 1)} "
    f"of cases; the always-on row repeats the {int(e14[0]['N_joint'])}-node design of Sections 6.3 and 6.8 with new "
    f"seeds, and its {pct(e14[0]['p_both'], 1)} agrees with the values found there within sampling error. With 0.5 J "
    "per node, 2,000-bit packets, {{E_elec}} = 50 nJ/bit and {{ε_amp}} = 100 pJ/bit/m², the first-order radio "
    f"model gives an expected communication-energy lifetime of {round(e14[0]['rounds_always_on'])} rounds for the always-on network and "
    f"{round(e14[3]['rounds']):,} rounds at three times the node count; these lifetimes are computed, not "
    "simulated.")
rows = [["{{N}} / {{N^⋆}}", "{{N}}", "{{q^⋆}}", "Lifetime gain (comm. energy)", "Both targets met (%) [95% CI]"]]
for q in e14:
    rows.append([f"{q['multiplier']:.1f}", f"{int(q['N'])}", f"{q['q']:.2f}", f"{q['lifetime_gain']:.2f}",
                 f"{100 * q['p_both']:.1f} [{100 * q['lo']:.1f}–{100 * q['hi']:.1f}]"])
d.table("Randomized sleep scheduling at a stated reliability (200 m field, {{C_t}} = 0.9, {{R_c}} = 40 m, 500 drops)",
        rows, [800, 600, 600, 1000, 1600])

# ============================================================================= 7. Limitations
d.h1("7. Threats to validity")
d.p("**Internal validity.** Coverage is measured on rasters of 0.5 m to 3.3 m; Eq. (17) and the simulations agree "
    "to within 0.001, so the raster error is small against the effects reported. Monte Carlo shares are tested with exact "
    "binomial tests and every comparison is corrected for multiplicity. The three recent baselines were re-implemented "
    "from their papers and run with default parameters, so the original code or problem-specific tuning could do "
    "better at small node counts; the baseline settings of Table 4 were not varied, and our implementations are public for that reason. The integer program stopped at a "
    "time limit, so its node counts are upper bounds and its dual bounds are lower bounds.")
d.p("**Construct validity.** Sensing follows the binary disk model except in the Elfes experiment, and the "
    "isolated-node term is a proxy for connectivity that is accurate only at high probabilities and can be "
    "optimistic when obstacles partition the field, where the simulated term should be used. Lifetime counts "
    "communication energy only and is computed from the expected number of awake rounds; battery depletion was not "
    "simulated.")
d.p("**External validity.** All results come from geometric and link-level simulation, not from a packet-level "
    "simulator or a field trial. Shadowing is independent across links and obstacles are rectangles on flat ground; "
    "correlated shadowing, three-dimensional terrain and moving obstacles were not studied.")

# ============================================================================= 8. Conclusion
d.h1("8. Conclusion")
d.p("Sizing a random drop for the expected coverage misses the target about half of the time. With an "
    "edge-aware variance and a Beta approximation, the proposed rule turned that into a stated probability that held "
    f"within simulation error in {beta_ci_ok} of 16 settings, at the cost of {pct(extra_lo, 0)} to {pct(extra_hi, 0)} "
    "more nodes. A joint rule adds connectivity, and the same expressions give the expected coverage under failures, "
    "k-coverage and probabilistic sensing, and extend to obstacles and shadow fading. Among buildings the isolated-node term can be optimistic; sizing "
    "connectivity by simulation kept the promised 95% in all four environments tested. For planned drops at an "
    f"error of 0.3{{{{r}}}}, a triangular lattice shrunk to absorb the error reached 99% coverage in "
    f"{pct(e16q('triangular', 0.3)['p_meet'], 1)} of 1,000 test drops with {int(e16q('triangular', 0.3)['nodes'])} nodes, where a random drop needed {n_rand_guar}; sized for the mean only, "
    f"it needed {int(e8_03['triangular']['robust_nodes'])} nodes against {n_rand_mean}. With the node count set by these rules, the lattice matched or beat all eight baselines without a single fitness evaluation, "
    f"and it needed fewer nodes than an integer program run for 20 minutes. Extra nodes can be turned into lifetime: tripling the drop let "
    f"each node sleep {pct(1 - e14[3]['q'], 0)} of the time at the same reliability. Future work "
    "will add terrain and correlated shadowing, validate the rules in a packet-level simulator, and test them in a "
    "field deployment.")

d.h1("Code availability")
d.p(f"The implementation code is publicly available at: {GITHUB}. It includes all parameters, seeds, raw runs, layouts, "
    "statistical scripts and unit tests, and one script that reproduces every table and figure. The version used in "
    f"this article (v1.2.0) is archived at Zenodo, DOI: {ZENODO_DOI}.")
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

d.save(OUT, front)
print("saved", OUT, "refs", len(ORDER), "figs", d.fig_count, "tables", d.tab_count, "eqs", d.eq_count)

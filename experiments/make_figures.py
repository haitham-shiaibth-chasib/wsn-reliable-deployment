"""Single-panel, column-width figures for the manuscript (10 pt text, 300 dpi).

Reads results/*.csv and writes figures/paper_fig*.png. Run after experiments/run_experiments.py.
The published figures used Liberation Serif (metric-compatible with Times New Roman).
"""
from __future__ import annotations

import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from wsndeploy import grid, sim  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
RES, FIG = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

C1, C2, C3, C4, C5, C6 = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#e87ba4", "#008300"
INK, MUTED, GRIDC = "#0b0b0b", "#52514e", "#dddcd8"
W, H = 3.0, 1.9                          # inserted at 7.6 cm, one IJIES column

from matplotlib import font_manager  # noqa: E402

_AVAILABLE = {f.name for f in font_manager.fontManager.ttflist}
SERIF = next((f for f in ("Times New Roman", "Liberation Serif", "TeX Gyre Termes", "DejaVu Serif") if f in _AVAILABLE),
             "serif")
plt.rcParams.update({
    "font.family": SERIF, "font.size": 10, "axes.titlesize": 10, "axes.labelsize": 10,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "axes.grid": True,
    "grid.color": GRIDC, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "lines.linewidth": 1.6, "savefig.dpi": 300, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03, "mathtext.fontset": "custom", "mathtext.it": f"{SERIF}:italic",
    "mathtext.rm": SERIF, "mathtext.cal": SERIF, "mathtext.bf": SERIF,
})


def load(name):
    with open(os.path.join(RES, name)) as f:
        rows = list(csv.DictReader(f))
    out = []
    for q in rows:
        d = {}
        for k, v in q.items():
            try:
                d[k] = float(v)
            except ValueError:
                d[k] = v
        out.append(d)
    return out


MAX_W_IN = 3.10                          # 7.87 cm: inserted at 100 % in one IJIES column, so 10 pt stays 10 pt


def save(fig, name):
    """Save at 300 dpi; shrink the canvas until the tight bounding box fits one column.

    The manuscript inserts every figure at its native size (pixels / 300 dpi), so lettering is
    printed at exactly 10 pt only if the saved image is not wider than MAX_W_IN.
    """
    pad = plt.rcParams["savefig.pad_inches"]
    for _ in range(8):
        fig.canvas.draw()
        bb = fig.get_tightbbox(fig.canvas.get_renderer())
        width = bb.width + 2 * pad
        if width <= MAX_W_IN + 1e-3:
            break
        fig.set_size_inches(fig.get_figwidth() - (width - MAX_W_IN) - 0.01, fig.get_figheight())
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print(f"   {name}  width {width:.2f} in")


# ----------------------------------------------------------------------------- Fig 1 framework
def fig_framework():
    fig, ax = plt.subplots(figsize=(W, 3.6))
    ax.set_xlim(-0.2, 10.2)
    ax.set_ylim(0, 15.95)
    ax.axis("off")
    boxes = [
        (13.4, "Inputs: field side L, sensing radius r,\ncommunication range $R_c$, target $C_t$,\nrisk level δ, failure rate f, drop error σ"),
        (10.8, "Edge-corrected statistics: mean E[C]\nand variance Var(C), Eqs. (3)-(6)"),
        (8.2, "Coverage rule: smallest N with\nP(C ≥ $C_t$) ≥ 1 − δ/2 (Beta model)"),
        (5.6, "Connectivity rule: smallest N with\nP(no isolated node) ≥ 1 − δ/2"),
        (3.0, "Random drop: N = max of both rules\nPlanned drop: error-tolerant lattice"),
        (0.4, "Output: node count, layout and\npredicted reliability"),
    ]
    for i, (y, text) in enumerate(boxes):
        fc = "#eaf1fb" if i not in (0, 5) else "#f3f2ee"
        hgt = 2.4 if i == 0 else 1.75
        ax.add_patch(FancyBboxPatch((0.0, y - 0.05), 10.0, hgt, boxstyle="round,pad=0.08",
                                    fc=fc, ec=C1 if i not in (0, 5) else MUTED, lw=1.0))
        ax.text(5, y + hgt / 2 - 0.05, text, ha="center", va="center", fontsize=10, color=INK)
        if i < len(boxes) - 1:
            ax.annotate("", xy=(5, boxes[i + 1][0] + 1.85), xytext=(5, y - 0.15),
                        arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.0))
    save(fig, "paper_fig1_framework.png")


# ----------------------------------------------------------------------------- Fig 2 model accuracy
def fig_models():
    rows = [q for q in load("E2_physical.csv") if q["r"] == 20]
    N = [q["N"] for q in rows]
    fig, ax = plt.subplots(figsize=(W, H))
    ax.plot(N, [q["linear_no_overlap"] for q in rows], color=C2, ls="--", label="Linear estimator")
    ax.plot(N, [q["poisson_exp"] for q in rows], color=C3, ls=":", lw=2, label="Poisson model")
    ax.plot(N, [q["exact_edge"] for q in rows], color=C4, label="Edge-corrected model")
    ax.plot(N, [q["mc_mean"] for q in rows], "o", ms=4, color=C1, mec="white", mew=0.6, label="Simulation mean")
    ax.set_xlabel("Number of sensors N")
    ax.set_ylabel("Coverage")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right")
    save(fig, "paper_fig2_models.png")


# ----------------------------------------------------------------------------- Fig 3 variance
def fig_variance():
    rows = load("E6a_variance.csv")
    N = [q["N"] for q in rows]
    fig, ax = plt.subplots(figsize=(W, H))
    ax.plot(N, [q["model_std_stationary"] for q in rows], color=C2, ls="--", label="Stationary approx.")
    ax.plot(N, [q["model_std_exact"] for q in rows], color=C4, label="Edge-aware model")
    ax.plot(N, [q["mc_std"] for q in rows], "o", ms=4, color=C1, mec="white", mew=0.6, label="Simulation")
    ax.set_xlabel("Number of sensors N")
    ax.set_ylabel("Standard deviation of C")
    ax.set_ylim(top=0.054)
    ax.legend(loc="upper right", ncol=1, borderaxespad=0.1)
    save(fig, "paper_fig3_variance.png")


# ----------------------------------------------------------------------------- Fig 4 sizing
def fig_sizing():
    rows = [q for q in load("E6b_sizing.csv") if q["L"] == 200 and q["r"] == 20]
    tg = sorted({q["target"] for q in rows})
    fig, ax = plt.subplots(figsize=(W, H))
    w = 0.26
    for i, (rule, col, lab) in enumerate([("mean", C2, "Mean rule"), ("normal", C3, "Normal rule"),
                                          ("beta", C4, "Beta rule (proposed)")]):
        vals = [next(q for q in rows if q["target"] == t and q["rule"] == rule) for t in tg]
        xs = np.arange(len(tg)) + (i - 1) * w
        ax.bar(xs, [v["p_meet"] for v in vals], width=w - 0.03, color=col, label=lab,
               yerr=[[v["p_meet"] - v["p_lo"] for v in vals], [v["p_hi"] - v["p_meet"] for v in vals]],
               error_kw=dict(ecolor=INK, lw=0.8, capsize=2))
    ax.axhline(0.95, color=INK, lw=1, ls="--", label="Required 1 − δ")
    ax.set_xticks(np.arange(len(tg)), [f"{t:.2f}" for t in tg])
    ax.set_xlabel("Target coverage $C_t$")
    ax.set_ylabel("Share with C ≥ $C_t$")
    ax.set_ylim(0, 1.12)
    ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2, handlelength=1.2,
              columnspacing=0.8, handletextpad=0.4)
    save(fig, "paper_fig4_sizing.png")


# ----------------------------------------------------------------------------- Fig 5 connectivity
def fig_connectivity():
    rows = load("E7a_connectivity.csv")
    fig, ax = plt.subplots(figsize=(W, H))
    for rc, col in ((30.0, C2), (40.0, C1)):
        q = [x for x in rows if x["rc"] == rc]
        N = [x["N"] for x in q]
        ax.plot(N, [x["model_p_no_isolated"] for x in q], color=col, label=f"Model, {int(rc)} m")
        ax.plot(N, [x["mc_p_no_isolated"] for x in q], "o", ms=4, color=col, mec="white", mew=0.6,
                label=f"No isolated, {int(rc)} m")
        ax.plot(N, [x["mc_p_conn"] for x in q], "x", ms=4.5, color=col, mew=1.1,
                label=f"Connected, {int(rc)} m")
    ax.set_xlabel("Number of sensors N")
    ax.set_ylabel("Probability")
    ax.set_ylim(-0.02, 1.02)
    from matplotlib.lines import Line2D
    hs = [Line2D([], [], color=C2, lw=3), Line2D([], [], color=MUTED),
          Line2D([], [], color=C1, lw=3), Line2D([], [], ls="", marker="o", ms=4, color=MUTED),
          Line2D([], [], ls="", marker="", color="none"), Line2D([], [], ls="", marker="x", ms=4.5, mew=1.1, color=MUTED)]
    ls = ["$R_c$ = 30 m", "Model, Eq. (9)", "$R_c$ = 40 m", "Sim., no isolated", "", "Sim., connected"]
    ax.legend(hs, ls, loc="upper center", bbox_to_anchor=(0.42, -0.24), ncol=2, handlelength=1.2,
              columnspacing=1.0, handletextpad=0.4)
    save(fig, "paper_fig5_connectivity.png")


# ----------------------------------------------------------------------------- Fig 6 grid gaps
def fig_grid_gaps():
    L, r = 500.0, 62.5
    s = grid.diameter_grid(L, r)
    g = np.linspace(0, L, 501)
    xx, yy = np.meshgrid(g, g)
    from scipy.spatial import cKDTree
    d, _ = cKDTree(s).query(np.column_stack([xx.ravel(), yy.ravel()]))
    gap = (d > r).reshape(xx.shape)
    fig, ax = plt.subplots(figsize=(W, W * 0.92))
    ax.imshow(np.where(gap, 1.0, np.nan), extent=(0, L, 0, L), origin="lower",
              cmap=matplotlib.colors.ListedColormap(["#e34948"]), alpha=0.85)
    for p in s:
        ax.add_patch(Circle(p, r, fill=False, ec=C1, lw=0.8))
    ax.plot(s[:, 0], s[:, 1], "o", ms=3, color=C1)
    ax.plot([0, L, L, 0, 0], [0, 0, L, L, 0], color=INK, lw=1)
    ax.set_xlim(-r, L + r)
    ax.set_ylim(-r, L + r)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    save(fig, "paper_fig6_grid_gaps.png")


# ----------------------------------------------------------------------------- Fig 7 placement error
def fig_placement():
    rows = load("E8_placement_error.csv")
    rel = load("E16_reliable_lattice.csv")
    fig, ax = plt.subplots(figsize=(W, 2.2))
    for kind, col, mk in (("triangular", C4, "o"), ("square", C3, "s")):
        q = [x for x in rows if x["kind"] == kind]
        ax.plot([x["sigma_over_r"] for x in q], [x["robust_nodes"] for x in q], color=col, marker=mk, ms=4)
        z = [x for x in rows if x["kind"] == kind and x["sigma_over_r"] == 0] + \
            sorted([x for x in rel if x["kind"] == kind], key=lambda x: x["sigma_over_r"])
        ax.plot([x["sigma_over_r"] for x in z], [x.get("nodes", x.get("robust_nodes")) for x in z], color=col,
                marker=mk, ms=4, ls="--", mfc="white")
    n_beta, n_mean = rows[0]["random_guaranteed_rule"], rows[0]["random_mean_rule"]
    ax.axhline(n_beta, color=C2, ls="--")
    ax.axhline(n_mean, color=C2, ls="-")
    ax.text(0.0, n_beta + 3, "Random drop, P(C ≥ 0.99) ≥ 0.95", ha="left", va="bottom", color=INK)
    ax.text(0.0, n_mean + 3, "Random drop, E[C] ≥ 0.99", ha="left", va="bottom", color=INK)
    ax.set_xlabel("Drop error σ / r")
    ax.set_ylabel("Sensors needed")
    ax.set_ylim(0, n_beta * 1.18)
    ax.set_xlim(-0.02, 0.52)
    ax.text(0.0, 46, "Square", ha="left", va="bottom", color=C3)
    ax.text(0.0, 27, "Triangular", ha="left", va="top", color=C4)
    from matplotlib.lines import Line2D
    ax.legend([Line2D([], [], color=MUTED), Line2D([], [], color=MUTED, ls="--")],
              ["E[C] ≥ 0.99", "P(C ≥ 0.99) ≥ 0.95"], loc="lower right", bbox_to_anchor=(1.04, -0.03), borderaxespad=0.0,
              handlelength=1.2, handletextpad=0.4, frameon=False)
    save(fig, "paper_fig7_placement.png")


# ----------------------------------------------------------------------------- Fig 8 baselines
def fig_baselines():
    rows = load("E10_baselines_summary.csv")
    methods = [("Random", C2, "v"), ("VFA", C5, "D"), ("GWO", C6, "^"), ("VASF-PSO", C3, "s"),
               ("PSO", "#eda100", "P"), ("ICGWO", MUTED, "X"), ("DAR-SSA", C1, "o"), ("GA", "#8a5a2b", "h"),
               ("Proposed", C4, "*")]
    fig, ax = plt.subplots(figsize=(W, 2.1))
    for m, col, mk in methods:
        q = sorted([x for x in rows if x["method"] == ("Proposed lattice" if m == "Proposed" else m)], key=lambda x: x["N"])
        if not q:
            continue
        ax.errorbar([x["N"] for x in q], [x["mean"] for x in q], yerr=[x["std"] for x in q], color=col,
                    marker=mk, ms=6 if mk == "*" else 4, capsize=2, lw=1.4, label=m)
    ax.set_xlabel("Number of sensors N")
    ax.set_ylabel("Coverage (mean ± std)")
    ax.set_xticks(sorted({int(x["N"]) for x in rows}))
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.24), ncol=3, columnspacing=0.6,
              handletextpad=0.3, handlelength=1.3)
    save(fig, "paper_fig8_baselines.png")


# ----------------------------------------------------------------------------- Fig 9 extensions
def fig_extensions():
    rows = load("E9_extensions.csv")
    fig, ax = plt.subplots(figsize=(W, 2.6))
    styles = {"k-coverage": (C1, "o", "k-coverage"), "failures-coverage": (C2, "s", "Coverage with failures"),
              "probabilistic-sensing": (C4, "D", "Probabilistic sensing")}
    for case, (col, mk, lab) in styles.items():
        q = [x for x in rows if x["case"] == case]
        ax.plot([x["model"] for x in q], [x["mc_mean"] for x in q], mk, ms=5, color=col, mec="white", mew=0.5,
                label=lab)
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1)
    ax.set_xlabel("Model prediction")
    ax.set_ylabel("Simulation")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right", fontsize=10)
    save(fig, "paper_fig9_extensions.png")


# ----------------------------------------------------------------------------- Fig 10 environment
def fig_environment():
    rows = load("E11_rules.csv")
    scen = list(dict.fromkeys(q["scenario"] for q in rows))
    labels = {"Open, unit disk": "Open\nfield", "Open, shadowing 8 dB": "Open\n8 dB",
              "Urban, no shadowing": "Urban\n0 dB", "Urban, shadowing 8 dB": "Urban\n8 dB"}
    fig, ax = plt.subplots(figsize=(W, 2.0))
    w = 0.27
    for i, (rule, col, lab) in enumerate([("open_field_rule", C2, "Open-field"),
                                          ("environment_aware_rule", C4, "Aware, analytic"),
                                          ("simulated_connectivity_rule", C3, "Aware, simulated")]):
        q = [next(x for x in rows if x["scenario"] == s and x["rule"] == rule) for s in scen]
        xs = np.arange(len(scen)) + (i - 1) * w
        ax.bar(xs, [x["p_both"] for x in q], width=w - 0.04, color=col, label=lab,
               yerr=[[x["p_both"] - x["lo"] for x in q], [x["hi"] - x["p_both"] for x in q]],
               error_kw=dict(ecolor=INK, lw=0.8, capsize=2))
        for xx, x in zip(xs, q):
            ax.text(xx, 0.04, f"{int(x['N'])}", ha="center", va="bottom", color="white", fontsize=10, rotation=90)
    ax.axhline(0.95, color=INK, lw=1, ls="--")
    ax.set_xticks(np.arange(len(scen)), [labels.get(s, s) for s in scen])
    ax.set_ylabel("Share meeting both targets")
    ax.set_ylim(0, 1.1)
    ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2, handlelength=1.0,
              columnspacing=0.8, handletextpad=0.4, frameon=False)
    save(fig, "paper_fig10_environment.png")


if __name__ == "__main__":
    which = sys.argv[1:] or ["all"]
    table = {"1": fig_framework, "2": fig_models, "3": fig_variance, "4": fig_sizing, "5": fig_connectivity,
             "6": fig_grid_gaps, "7": fig_placement, "8": fig_baselines, "9": fig_extensions,
             "10": fig_environment}
    for k, fn in table.items():
        if "all" in which or k in which:
            try:
                fn()
            except FileNotFoundError as e:
                print("  skipped", k, e)

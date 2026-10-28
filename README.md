# wsn-reliable-deployment

Code, configuration, raw data and figures for the article

> H. S. Chasib and I. J. K. Al-Ogaili, *Reliability-Guaranteed Sensor Deployment for Wireless Sensor Networks Using
> Edge-Corrected Coverage Statistics and Drop-Error-Tolerant Lattices*, International Journal of
> Intelligent Engineering and Systems (submitted, 2026).

The study answers one design question: **how many sensors, and in what layout, are needed so that a
coverage target and network connectivity hold with a stated probability**, once border effects, node
failures and aerial drop errors are taken into account. All results come from simulation; no field
data are involved.

## Contents

```
config/experiments.yaml      every parameter, grid and seed rule used in the article
wsndeploy/                   the library
  models.py                  linear and Poisson models, edge-corrected mean coverage
  reliability.py             coverage variance, Beta/normal sizing, connectivity, k-coverage, failures, Elfes
  grid.py                    diameter-spaced grid, square lattice, pruned triangular lattice
  placement.py               coverage under drop error, error-tolerant lattice, all baselines
  environment.py             obstacles with line-of-sight sensing, log-normal shadowing, environment-aware rules
  ilp.py                     minimum-node full cover as an integer linear program (HiGHS)
  sim.py, stats.py           Monte Carlo coverage and connectivity; confidence intervals and errors
experiments/
  run_experiments.py         runs E2, E5-E16 (and supplementary S2), writes results/ and results/raw/
  statistics.py              every statistical test of the article -> results/statistical_tests.*
  make_figures.py            the eight manuscript figures -> figures/paper_fig*.png
                             (paper_fig6_grid_gaps.png and paper_fig9_extensions.png are supplementary)
manuscript/                  scripts that build the Word manuscript from results/ (template not included)
results/                     aggregated tables, DATA_DICTIONARY.md, CHECKSUMS.sha256
results/raw/                 one row per simulation run or optimiser run, seed manifest, layouts
tests/                       unit tests of the models and helpers
tools/verify_results.py      checks that a re-run reproduced the published files
reproduce_all.sh             one command for the whole pipeline
```

## Installation

Python 3.13 on Linux x86-64 was used for E2-E11; E10 (GA, GWO, ICGWO, DAR-SSA) and E12-E15 were run on Windows x86-64 with the pinned versions, and the unchanged files reproduced bit-identically there. Any recent Python 3 should work, but bit-identical results
are only guaranteed with the pinned versions.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # or: conda env create -f environment.yml
python -m pytest -q                      # 37 tests, about two minutes
```

The manuscript build (optional) also needs `pandoc` 3.x on the system path.

## Reproducing the article

```bash
./reproduce_all.sh                        # full pipeline, about 3.5 h on 2 cores
./reproduce_all.sh --quick                # 10 % of the runs, about 20 min, for a smoke test
WORKERS=4 ./reproduce_all.sh              # more processes for E10
TEMPLATE=/path/IJIES_Format.docx ./reproduce_all.sh   # also rebuild the Word manuscript
```

Single experiments: `python experiments/run_experiments.py --exp E6 E7`. After a full run,
`python tools/verify_results.py` compares SHA-256 checksums of every result file (wall-clock
columns removed) with `results/CHECKSUMS.sha256`. A different processor or library build may change
the last digits of floating-point numbers; the conclusions are unaffected, but the checksums will then
differ.

Published runs were produced on 2-vCPU Linux and Windows x86-64 machines. The `seconds` columns (wall-clock
time) depend on the machine and are excluded from the checksums.

## Where each result comes from

| Article | Experiment | Result file(s) | Code |
|---|---|---|---|
| Sec. 6.1, Fig. 2, Table 5 | E2 | `E2_physical.csv`, `summary_errors.csv` | `run_E2` |
| Sec. 6.2, Fig. 3 | E6a | `E6a_variance.csv`, `raw/E6a_runs.csv` | `run_E6` |
| Sec. 6.2, Fig. 4, Table 6 | E6b | `E6b_sizing.csv`, `raw/E6b_runs.csv` | `run_E6` |
| Sec. 6.3, Fig. 5 | E7 | `E7a_connectivity.csv`, `E7b_joint.csv`, `raw/E7*_runs.csv` | `run_E7` |
| Sec. 6.4, Table 7 | E5 | `E5_grids.csv`, `raw/layouts/E5_*` | `run_E5` |
| Sec. 6.5, Fig. 6, Table 8 | E8 | `E8_placement_error.csv`, `raw/E8_runs.csv`, `raw/layouts/E8_*` | `run_E8` |
| Sec. 6.5, Fig. 6, Table 8 (reliability design) | E16 | `E16_reliable_lattice.csv`, `raw/E16_runs.csv`, `raw/layouts/E16_*` | `run_E16`, `placement.reliable_lattice` |
| Sec. 6.6, Fig. 7, Table 9 | E10 | `E10_baselines_summary.csv`, `raw/E10_runs.csv`, `raw/layouts/E10_*` | `run_E10` |
| Sec. 6.7 | E9 | `E9_extensions.csv`, `raw/E9_runs.csv` | `run_E9` |
| Sec. 6.8, Fig. 8 | E11 | `E11_model_check.csv`, `E11_rules.csv`, `E11_conn_sizing.csv`, `raw/E11*_runs.csv` | `run_E11` |
| Sec. 6.4 (ILP paragraph) | E13 | `E13_ilp.csv`, `raw/layouts/E13_*` | `run_E13`, `ilp.min_cover_ilp` |
| Sec. 6.9, Table 10 | E12 | `E12_risk_sensitivity.csv`, `raw/E12_runs.csv` | `run_E12` |
| Sec. 6.9 (heterogeneous radii) | E15 | `E15_heterogeneous.csv`, `raw/E15_runs.csv` | `run_E15` |
| Sec. 6.9, Table 11 | E14 | `E14_sleep_scheduling.csv`, `raw/E14_runs.csv` | `run_E14` |
| All p-values and effect sizes | – | `statistical_tests.csv`, `statistical_tests.md` | `experiments/statistics.py` |
| Fig. 1 (framework) | – | – | `make_figures.py` |

| Equation / algorithm | Function |
|---|---|
| Eq. (1) linear estimator | `models.linear_no_overlap` (computed inline in `run_E2`) |
| Eq. (2) Poisson model | `models.poisson_exp` |
| Eqs. (3)-(4) edge-corrected mean | `models._disk_area_inside`, `models.exact_edge`, `reliability.mean_cov` |
| Eqs. (5)-(6) variance | `reliability.var_cov_exact` (stationary approximation: `reliability.var_cov`) |
| Eqs. (7)-(8) Beta rule | `reliability.p_meet`, `reliability.n_guaranteed` |
| Eq. (9) isolated nodes | `reliability.p_no_isolated` |
| Eq. (10), Algorithm 1 | `reliability.n_joint` |
| Eqs. (11)-(13) k-coverage, Elfes | `reliability.mean_k_cov`, `reliability.elfes`, `reliability.mean_detection` |
| Eqs. (14)-(15) lattices | `grid.diameter_grid`, `grid.square_grid`, `grid.triangular_grid` |
| Eqs. (16)-(17) drop error | `placement.expected_coverage_perturbed` |
| Algorithm 2 | `placement.robust_lattice` (mean design), `placement.reliable_lattice` (reliability design) |
| Eqs. (18)-(20) obstacles, shadowing | `environment.Field`, `environment.Radio.link_prob`, `environment.EnvironmentModel` |
| Eq. (21) heterogeneous radii | `reliability.mean_cov_mix`, `var_cov_exact_mix`, `n_guaranteed_mix` |
| Eq. (22) sleep schedule | `reliability.min_awake_share` |
| Sec. 4.6 simulated connectivity term | `environment.EnvironmentModel.n_conn_mc`, `n_joint_mc` |

## Randomness and seeds

Each configuration (one cell of a parameter grid) owns a NumPy PCG64 generator created with
`numpy.random.default_rng(seed)`; its runs draw from it in order. The seed rules are written in
`config/experiments.yaml`, and every realised seed is stored in each raw row and in
`results/raw/seed_manifest.csv`. In E10 every method uses the same 30 seeds per node count, so the
comparison is paired.

## Baselines

All population methods share one budget: 30 agents × 300 iterations (9,030 fitness evaluations), an
80 × 80 fitness raster, clipping to the field, and a 250 × 250 evaluation raster. VFA (Zou and
Chakrabarty, 2003) uses no fitness function and runs 400 iterations. VASF-PSO (Haris and Nam, *Sensors*
2025), ICGWO (Shaikh et al., *Scientific Reports* 2025) and DAR-SSA (Kheam et al., *Sensors* 2026) were
re-implemented from their published descriptions; every setting that the papers leave open is listed
in `config/experiments.yaml` and in the docstrings of `wsndeploy/placement.py`. Our re-implementations
may differ in details from the original authors' code. GWO and ICGWO keep the best three solutions found
so far as leaders (elitist, as in the reference GWO), and DAR-SSA keeps an archive of the best layout found,
so every optimiser returns the best layout found during its run.

## Changes in version 1.2.0

* The naive square grid whose spacing equals the sensing diameter is `grid.diameter_grid`; its columns in
  `E5_grids.csv` are `diameter_*` and its layouts are `raw/layouts/E5_diameter_*`.
* The mean-model comparison (E2, Table 5) covers the linear, Poisson and edge-corrected models.
* E2 and E5 were re-run with the same seeds; their simulated values did not change.
* New experiment E16: error-tolerant lattices sized so that P(C ≥ 0.99) ≥ 0.95 holds with 95 % confidence
  (`placement.reliable_lattice`), validated on 1,000 independent drops per layout.

## Changes in version 1.1.0

* `placement.gwo` and `placement.icgwo` are now elitist: alpha, beta and delta are the three best solutions found
  so far. Version 1.0.0 recomputed the leaders from the current pack only, which discarded good layouts and
  under-reported both baselines (for example GWO at N = 33: 89.7 % in 1.0.0, 98.3 % in 1.1.0).
* `placement.dar_ssa` returns the best layout found during the run (archive); its search dynamics are unchanged.
* E10 was re-run for GWO, ICGWO and DAR-SSA with the same seeds; all other methods and experiments are unchanged.
* `run_experiments.py --workers 1` runs E10 without a process pool (useful on restricted Windows hosts).
* Figures are saved no wider than one IJIES column, so all lettering prints at 10 pt.
* New baseline: a real-coded genetic algorithm (`placement.ga`) under the same 9,030-evaluation budget.
* New experiments: E12 (risk level δ = 0.01 and 0.10), E13 (integer-programming minimum cover),
  E14 (randomized sleep scheduling and lifetime), E15 (heterogeneous sensing radii).
* Full reproduction takes about 5 h on 2 cores; E13 alone runs two 20-minute HiGHS solves.

## License and citation

Code is released under the MIT License (`LICENSE`); data and figures under the same terms. Citation
metadata are in `CITATION.cff`.

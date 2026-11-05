# wsn-reliable-deployment

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23717648.svg)](https://doi.org/10.5281/zenodo.23717648)

Code, configuration, raw data and figures for the article

> H. S. Chasib and I. J. K. Al-Ogaili, *Statistically Certified Sensor Deployment for Wireless Sensor Networks Using
> Edge-Corrected Coverage Statistics and Drop-Error-Tolerant Lattices*, International Journal of
> Intelligent Engineering and Systems (revised version, 2026).

The study answers one design question: **how many sensors, and in what layout, are needed so that a
coverage target and network connectivity hold with a stated probability**, once border effects, node
failures and aerial drop errors are taken into account. Analytical rules propose a design; because they
are approximations, every design is then certified on independent simulated drops with a one-sided
Clopper-Pearson bound and a Bonferroni correction over the attempts of the search
(`wsndeploy/certify.py`). All results come from simulation; no field data are involved.

## Contents

```
config/experiments.yaml      every parameter, grid and seed rule used in the article
wsndeploy/                   the library
  models.py                  linear and Poisson models, edge-corrected mean coverage
  reliability.py             coverage variance, Beta/normal sizing, connectivity, k-coverage, failures, Elfes
  grid.py                    diameter-spaced grid, square lattice, pruned triangular lattice,
                             exact (raster-free) coverage test of a square field
  certify.py                 one-sided Clopper-Pearson certification with fresh samples (Bonferroni over attempts)
  domain.py                  coverage mean, variance and Beta rule for rectangles, L-shapes and fields with holes
  placement.py               coverage under drop error, error-tolerant lattice, all baselines
  environment.py             obstacles with line-of-sight sensing, log-normal shadowing, environment-aware rules
  ilp.py                     minimum-node full cover as an integer linear program (HiGHS)
  sim.py, stats.py           Monte Carlo coverage and connectivity; confidence intervals and errors
experiments/
  run_experiments.py         runs E2, E5-E25 (and the additional scan S2), writes results/ and results/raw/
  statistics.py              every statistical test of the article -> results/statistical_tests.*
  make_figures.py            the nine manuscript figures -> figures/paper_fig*.png
                             (paper_fig6_grid_gaps.png and paper_fig9_extensions.png are not used in the article)
manuscript/                  scripts that build the Word manuscript from results/ (template not included);
                             mark_changes.py sets the revisions in red against a submitted version
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
python -m pytest -q                      # 45 tests, about three minutes
```

The manuscript build (optional) also needs `pandoc` 3.x on the system path.

## Reproducing the article

```bash
./reproduce_all.sh                        # full pipeline, about 8 h on 2 cores
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

Section, table and figure numbers refer to the revised manuscript. Every experiment runs with
`python experiments/run_experiments.py --exp <ID>`; its rasters, quadrature and seed rules are in
`config/experiments.yaml` under the same key. Table 4 of the manuscript gives the same map in short form.

| Article | Experiment | Result file(s) | Code |
|---|---|---|---|
| Sec. 6.1, Fig. 2, Table 6 | E2 | `E2_physical.csv`, `summary_errors.csv` | `run_E2` |
| Sec. 6.2, Fig. 3 | E6a | `E6a_variance.csv`, `raw/E6a_runs.csv` | `run_E6` |
| Sec. 6.2, Fig. 4, Table 7 | E6b | `E6b_sizing.csv`, `raw/E6b_runs.csv` | `run_E6` |
| Sec. 6.3, Table 8 (certification of all random-drop designs) | E17 | `E17_certification.csv`, `raw/E17_runs.csv` | `run_E17`, `certify.certify_sequence` |
| Sec. 6.4, Fig. 5 | E7, S2 | `E7a_connectivity.csv`, `E7b_joint.csv`, `raw/E7*_runs.csv` | `run_E7` |
| Sec. 6.5, Table 9 | E5, E25 | `E5_grids.csv`, `E25_checks.csv`, `raw/layouts/E5_*` | `run_E5`, `run_E25`, `grid.covers_square_exactly` |
| Sec. 6.5 (integer program) | E13, E21 | `E13_ilp.csv`, `E21_ilp_resolution.csv`, `raw/layouts/E13_*`, `raw/layouts/E21_*` | `run_E13`, `run_E21`, `ilp.min_cover_ilp` |
| Sec. 6.6, Fig. 6, Table 10 | E8, E16, E18 | `E8_placement_error.csv`, `E16_reliable_lattice.csv`, `E18_certified_lattice.csv`, `raw/E8_runs.csv`, `raw/E16_runs.csv`, `raw/E18_runs.csv`, `raw/layouts/E8_*`, `E16_*`, `E18_*` | `run_E8`, `run_E16`, `run_E18` |
| Sec. 6.7, Fig. 7, Table 11 | E10 | `E10_baselines_summary.csv`, `raw/E10_runs.csv`, `raw/layouts/E10_*` | `run_E10` |
| Sec. 6.7, Table 12 (parameter sensitivity) | E24 | `E24_baseline_sensitivity.csv`, `raw/E24_runs.csv`, `raw/layouts/E24_*` | `run_E24` |
| Sec. 6.7, Table 13 (run time and memory) | E23 | `E23_runtime.csv`, `E23_hardware.csv` | `run_E23` (run alone) |
| Sec. 6.8 | E9 | `E9_extensions.csv`, `raw/E9_runs.csv` | `run_E9` |
| Sec. 6.9, Fig. 8 | E11 | `E11_model_check.csv`, `E11_rules.csv`, `E11_conn_sizing.csv`, `raw/E11*_runs.csv` | `run_E11` |
| Sec. 6.10, Fig. 9, Table 14 (stress study, correlated shadowing) | E19 | `E19_stress.csv`, `E19_calibration.csv`, `E19_correlated_shadowing.csv`, `raw/E19_runs.csv` | `run_E19`, `domain.DomainModel`, `environment.connectivity_shadow_corr` |
| Sec. 6.11, Table 15 | E12 | `E12_risk_sensitivity.csv`, `raw/E12_runs.csv` | `run_E12` |
| Sec. 6.11 (heterogeneous radii) | E15, E22 | `E15_heterogeneous.csv`, `E22_fixed_counts.csv`, `raw/E15_runs.csv`, `raw/E22_runs.csv` | `run_E15`, `run_E22` |
| Sec. 6.11, Table 16 | E14, E20 | `E14_sleep_scheduling.csv`, `E20_schedule_conditional.csv`, `raw/E14_runs.csv`, `raw/E20_runs.csv` | `run_E14`, `run_E20` |
| All p-values and effect sizes | – | `statistical_tests.csv`, `statistical_tests.md` | `experiments/statistics.py` |
| Fig. 1 (framework) | – | – | `make_figures.py` |

| Equation / algorithm | Function |
|---|---|
| Eq. (1) linear estimator | `models.linear_no_overlap` (computed inline in `run_E2`) |
| Eq. (2) Poisson model | `models.poisson_exp` |
| Eqs. (3)-(4) edge-corrected mean | `models._disk_area_inside`, `models.exact_edge`, `reliability.mean_cov` |
| Eqs. (5)-(6) variance (all pairs, including the negative far-pair terms) | `reliability.var_cov_exact` (stationary approximation: `reliability.var_cov`) |
| Eqs. (7)-(8) Beta rule | `reliability.p_meet`, `reliability.n_guaranteed` |
| Eq. (9) isolated nodes | `reliability.p_no_isolated` |
| Eqs. (10)-(11), Algorithm 1 | `reliability.n_joint` |
| Eqs. (12)-(14) k-coverage, Elfes | `reliability.mean_k_cov`, `reliability.elfes`, `reliability.mean_detection` |
| Eqs. (15)-(16) lattices, Algorithm 2 steps (i)-(vi) | `grid.diameter_grid`, `grid.square_grid`, `grid.triangular_grid`, `grid.prune_redundant`, `grid.covers_square_exactly` |
| Eqs. (17)-(18) drop error | `placement.expected_coverage_perturbed` |
| Algorithm 2 (design) | `placement.robust_lattice` (mean design), `placement.reliable_lattice` (reliability design) |
| Eq. (19), Algorithm 3 (certification) | `certify.cp_lower`, `certify.certify_sequence` |
| Eqs. (20)-(22) obstacles, shadowing | `environment.Field`, `environment.Radio.link_prob`, `environment.EnvironmentModel` |
| Sec. 4.7 simulated connectivity term | `environment.EnvironmentModel.n_conn_mc`, `n_joint_mc` |
| Eq. (23) heterogeneous radii, independent mixture | `reliability.mean_cov_mix`, `var_cov_exact_mix`, `n_guaranteed_mix` |
| Eq. (24) heterogeneous radii, fixed class counts | `reliability.mean_cov_fixed`, `var_cov_exact_fixed`, `n_guaranteed_fixed` |
| Eq. (25) sleep schedule | `reliability.min_awake_share` |
| Stress study on general fields | `domain.Domain`, `domain.DomainModel` |

### Design, validation and certification samples

Samples are never reused. A design sample chooses a design (the lattice search of E16/E18, the simulated
connectivity search of E11, the design step of the correlated-shadowing study in E19); a validation sample
describes calibration (E6b, E7b, E11, E12, E15, E16, the calibration points of E19); a certification sample
(E17, E18, E19) is drawn afresh for every attempt of Algorithm 3. The seed of every certification sample
differs from the seeds of the samples that chose or validated the same design; `tools/check_seed_separation.py`
checks this on `results/raw/seed_manifest.csv`. The seed rules are written in `config/experiments.yaml`.

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

## Changes in version 1.3.0 (revision after review)

* Certification layer (`wsndeploy/certify.py`): one-sided Clopper-Pearson lower bound on fresh drops, at most
  ten attempts at level 0.005 each (Bonferroni), "not certified" when no attempt passes. Experiments E17
  (all random-drop designs) and E18 (error-tolerant lattices, now also for sigma/r = 0.75 and 1).
* Exact, raster-free coverage test of a square field (`grid.covers_square_exactly`, perimeter criterion of
  Huang and Tseng); connectivity of every pruned lattice checked after pruning (E25).
* Heterogeneous radii with fixed class counts (`reliability.*_fixed`, E22).
* Stress study on rectangles, an L-shaped field and a field with a hole (`wsndeploy/domain.py`), with
  calibration curves and correlated link shadowing (`environment.connectivity_shadow_corr`), E19.
* Deployment-conditional reliability of the sleep schedule over 300 rounds (E20).
* Integer program at 20 m and 12.5 m spacing and the continuous lower bound of Fejes Tóth (E21).
* Run time and memory of every step on one machine (E23) and parameter sensitivity of VASF-PSO, ICGWO and
  DAR-SSA (E24; `placement.vasf_pso` and `placement.icgwo` gained parameters whose defaults reproduce v1.2.0
  bit for bit).
* E2-E16 are unchanged; their files and checksums are those of v1.2.0.
* E19 can be split into parallel parts (`E19_PART`, `E19_SETTINGS`, `E19_CORR`) and merged with `--exp E19merge`.

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

The version used in the revised article (v1.3.0) is archived at Zenodo; the concept DOI
https://doi.org/10.5281/zenodo.23717648 always resolves to the latest version (v1.2.0, the submitted version:
https://doi.org/10.5281/zenodo.23717649).

Code is released under the MIT License (`LICENSE`); data and figures under the same terms. Citation
metadata are in `CITATION.cff`.

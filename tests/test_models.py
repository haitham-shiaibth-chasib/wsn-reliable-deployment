"""Unit tests of the analytical models, the layouts and the statistics helpers.

Run with:  python -m pytest -q
The tests check mathematical identities and limits, not the stored results, so they are fast
(about one minute) and independent of the experiment runs.
"""
import math
import os
import sys

import numpy as np
import pytest
import yaml
from scipy.integrate import quad

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from wsndeploy import environment as ENV, grid, models, placement, reliability as R, sim  # noqa: E402
from wsndeploy.stats import errors, mean_ci, wilson  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


# ----------------------------------------------------------------------------- geometry
def test_square_distance_pdf_is_a_density():
    L = 1.0
    total = quad(lambda d: R.square_distance_pdf(d, L), 0, 1)[0] + quad(lambda d: R.square_distance_pdf(d, L), 1, math.sqrt(2))[0]
    assert total == pytest.approx(1.0, abs=1e-8)


def test_square_distance_pdf_mean_matches_known_constant():
    # mean distance between two uniform points in the unit square (Robbins constant)
    robbins = (2 + math.sqrt(2) + 5 * math.log(1 + math.sqrt(2))) / 15
    m = quad(lambda d: d * R.square_distance_pdf(d, 1.0), 0, 1)[0] + quad(lambda d: d * R.square_distance_pdf(d, 1.0), 1, math.sqrt(2))[0]
    assert m == pytest.approx(robbins, abs=1e-8)


@pytest.mark.parametrize("r", [1.0, 7.5, 20.0])
def test_lens_area_limits(r):
    assert R.lens_area(0.0, r) == pytest.approx(math.pi * r * r)
    assert R.lens_area(2 * r, r) == pytest.approx(0.0, abs=1e-9)
    assert R.lens_area(3 * r, r) == pytest.approx(0.0, abs=1e-9)


def test_disk_area_inside_interior_and_corner():
    L, r = 200.0, 20.0
    p = models._disk_area_inside(L, r)
    interior = math.pi * r * r / (L * L)
    assert p[len(p) // 2, len(p) // 2] == pytest.approx(interior, rel=1e-3)
    # the first grid point sits h = L/480 from both edges: a quarter disk plus two strips of width h
    h = L / (2 * p.shape[0])
    corner = (math.pi * r * r / 4 + 2 * h * r + h * h) / (L * L)
    assert p[0, 0] == pytest.approx(corner, rel=2e-3)


# ----------------------------------------------------------------------------- mean models
def test_edge_corrected_mean_is_below_poisson_and_converges_for_large_fields():
    r = 10.0
    for L in (100.0, 400.0, 2000.0):
        n = int(1.5 * L * L / (math.pi * r * r))
        exact = models.exact_edge(n, r, L)
        pois = float(models.poisson_exp(n, r, L * L))
        assert exact < pois
    assert models.exact_edge(n, r, 2000.0) == pytest.approx(pois, abs=2e-3)


def test_edge_corrected_mean_matches_simulation():
    L, r, n = 200.0, 20.0, 60
    rng = np.random.default_rng(1)
    pts = sim.raster(L, 200)
    x = [sim.coverage_fraction(sim.random_deployment(n, L, rng), pts, r) for _ in range(200)]
    m, s, h = mean_ci(x)
    assert abs(models.exact_edge(n, r, L) - m) < max(3 * h, 0.006)


def test_linear_estimator_saturates():
    assert float(models.linear_no_overlap(10 ** 6, 1.0, 40000.0)) == 1.0


# ----------------------------------------------------------------------------- variance and sizing
def test_exact_variance_matches_simulation():
    L, r, n = 200.0, 20.0, 60
    rng = np.random.default_rng(2)
    pts = sim.raster(L, 200)
    x = np.array([sim.coverage_fraction(sim.random_deployment(n, L, rng), pts, r) for _ in range(300)])
    assert math.sqrt(R.var_cov_exact(n, r, L)) == pytest.approx(x.std(ddof=1), rel=0.15)


def test_probabilistic_rule_needs_more_nodes_than_mean_rule():
    L, r = 200.0, 20.0
    for c in (0.8, 0.95):
        n_mean = R.n_mean(c, r, L)
        n_beta = R.n_guaranteed(c, 0.05, r, L)
        assert n_beta > n_mean
        assert R.p_meet(n_beta, c, r, L) >= 0.95
        assert R.p_meet(n_beta - 1, c, r, L) < 0.95


def test_failures_thin_the_coverage():
    L, r = 200.0, 20.0
    assert R.mean_cov(100, r, L, f=0.3) < R.mean_cov(100, r, L)
    assert R.mean_cov(100, r, L, f=0.0) == pytest.approx(models.exact_edge(100, r, L), abs=1e-9)


def test_k_coverage_is_decreasing_in_k():
    vals = [R.mean_k_cov(120, k, 20.0, 200.0) for k in (1, 2, 3)]
    assert vals[0] > vals[1] > vals[2] > 0
    assert vals[0] == pytest.approx(R.mean_cov(120, 20.0, 200.0), abs=1e-9)


def test_isolated_node_probability_is_monotone():
    p = [R.p_no_isolated(n, 40.0, 200.0) for n in (20, 60, 100, 140)]
    assert all(0 <= a < b <= 1 for a, b in zip(p, p[1:]))


def test_elfes_model_reduces_to_disk_without_uncertainty():
    d = np.array([0.0, 19.9, 20.1, 30.0])
    np.testing.assert_allclose(R.elfes(d, 20.0, 1e-9, 0.1, 1.0), [1, 1, 0, 0])


# ----------------------------------------------------------------------------- lattices and drop error
def test_diameter_spaced_grid_covers_pi_over_4():
    L, r = 500.0, 62.5
    cov = sim.coverage_fraction(grid.diameter_grid(L, r), sim.raster(L, 500), r)
    assert cov == pytest.approx(math.pi / 4, abs=0.003)


@pytest.mark.parametrize("r", [50.0, 62.5, 100.0])
def test_corrected_lattices_cover_the_field(r):
    L = 500.0
    fine = sim.raster(L, 500)
    assert sim.coverage_fraction(grid.square_grid(L, r), fine, r) == 1.0
    assert sim.coverage_fraction(grid.triangular_grid(L, r, sim.raster(L, 250), phases=4), fine, r) == 1.0


def test_perturbed_coverage_limits():
    L, r = 500.0, 62.5
    lay = grid.square_grid(L, r)
    exact = sim.coverage_fraction(lay, sim.raster(L, 150), r)
    assert placement.expected_coverage_perturbed(lay, r, 0.0, L, 150) == pytest.approx(exact)
    assert placement.expected_coverage_perturbed(lay, r, 1e-3, L, 150) == pytest.approx(exact, abs=1e-3)


def test_perturbed_coverage_matches_simulation():
    L, r, sigma = 500.0, 62.5, 15.0
    lay = grid.triangular_grid(L, r, sim.raster(L, 250), phases=4)
    model = placement.expected_coverage_perturbed(lay, r, sigma, L, 150)
    x = placement.mc_coverage_perturbed(lay, r, sigma, L, 40, np.random.default_rng(3), 150)
    assert model == pytest.approx(x.mean(), abs=0.006)


# ----------------------------------------------------------------------------- statistics helpers
def test_wilson_interval_known_value():
    p, lo, hi = wilson(5, 10)
    assert (p, round(lo, 4), round(hi, 4)) == (0.5, 0.2366, 0.7634)


def test_error_metrics():
    e = errors([1.0, 2.0, 4.0], [1.0, 1.0, 1.0])
    assert e["MAE"] == pytest.approx(4 / 3)
    assert e["MaxAbs"] == 3.0
    assert e["RMSE"] == pytest.approx(math.sqrt(10 / 3))


# ----------------------------------------------------------------------------- configuration
def test_configuration_reproduces_published_seed_rules():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "experiments.yaml")))
    e2 = cfg["E2_mean_models"]
    assert e2["seed_base"] + 1000 * 20 + 30 == 22030
    assert cfg["E10_baselines"]["budget"]["population"] * (cfg["E10_baselines"]["budget"]["iterations"] + 1) == 9030


# ----------------------------------------------------------------------------- environment (obstacles, shadowing)
def test_segment_blocking():
    fld = ENV.Field(10.0, [(4, 4, 6, 6)])
    P = np.array([[0, 5], [0, 0], [5, 0], [0, 4]])
    Q = np.array([[10, 5], [10, 10], [5, 3], [10, 4]])
    np.testing.assert_array_equal(fld.blocked(P, Q), [True, True, False, False])


def test_shadowing_reduces_to_unit_disk():
    radio = ENV.Radio(40.0, 3.0, 0.0)
    np.testing.assert_array_equal(radio.link_prob([10.0, 39.9, 40.1, 80.0], [False] * 4), [1, 1, 0, 0])
    assert ENV.Radio(40.0, 3.0, 8.0).link_prob([40.0], [False])[0] == pytest.approx(0.5)


def test_open_field_environment_model_matches_open_field_framework():
    m = ENV.EnvironmentModel(ENV.Field(200.0), 20.0, ENV.Radio(40.0))
    assert m.mean(100) == pytest.approx(R.mean_cov(100, 20.0, 200.0), abs=1e-3)
    assert math.sqrt(m.var(100)) == pytest.approx(math.sqrt(R.var_cov_exact(100, 20.0, 200.0)), rel=0.05)
    assert m.p_no_isolated(100) == pytest.approx(R.p_no_isolated(100, 40.0, 200.0), abs=5e-3)


def test_uniform_sampling_avoids_obstacles():
    fld = ENV.Field(100.0, [(20, 20, 60, 60)])
    s = fld.sample(2000, np.random.default_rng(0))
    assert not fld.in_obstacle(s).any()
    assert fld.free_area == 100.0 ** 2 - 40.0 ** 2


def test_simulated_connectivity_rule_meets_its_target():
    """n_conn_mc starts at the analytical count and returns a count whose estimated P(connected) meets 1 - eps."""
    from wsndeploy import environment as E
    fld = E.Field(100.0, [(30, 30, 70, 70)])
    m = E.EnvironmentModel(fld, 10.0, E.Radio(30.0, 3.0, 0.0, 20.0), coarse=30, fine=60, mean_grid=60,
                           conn_coarse=30, conn_fine=60)
    n0 = m.n_conn(0.1)
    n, p, trace = m.n_conn_mc(0.1, runs=200, seed_base=1)
    assert n >= n0 and p >= 0.9
    assert all(v < 0.9 for k, v in trace.items() if k < n)


# ----------------------------------------------------------------------------- optimiser baselines
@pytest.mark.parametrize("name", ["gwo", "icgwo", "dar_ssa"])
def test_optimisers_return_best_layout_found(name, monkeypatch):
    """GWO and ICGWO are elitist and DAR-SSA uses greedy selection, so the returned layout must be the
    best one evaluated during the run (version 1.0.0 could return a worse, final-population layout)."""
    seen = []

    class Recording(placement.CoverageFitness):
        def __call__(self, x):
            v = super().__call__(x)
            seen.append(v)
            return v

    monkeypatch.setattr(placement, "CoverageFitness", Recording)
    fn = getattr(placement, name)
    kw = {"wolves": 8} if name in ("gwo", "icgwo") else {"pop": 8}
    L, r, n, res = 100.0, 15.0, 6, 30
    s, evals = fn(L, r, n, np.random.default_rng(3), iters=15, res=res, **kw)
    assert evals == len(seen) == 8 * 16
    best = sim.coverage_fraction(np.clip(s, 0, L), sim.raster(L, res), r)
    assert best == pytest.approx(max(seen), abs=1e-12)


# ----------------------------------------------------------------------------- version 1.1 extensions
def test_mixture_with_one_radius_equals_homogeneous_model():
    L, r, n = 100.0, 10.0, 40
    assert R.mean_cov_mix(n, [r], [1.0], L) == pytest.approx(R.mean_cov(n, r, L), rel=1e-12)
    assert R.var_cov_exact_mix(n, [r], [1.0], L, coarse=40, fine=100) == pytest.approx(
        R.var_cov_exact(n, r, L, coarse=40, fine=100), rel=1e-10)


def test_heterogeneous_coverage_matches_simulation_mean():
    L, radii, w, n = 100.0, [6.0, 12.0], [0.5, 0.5], 40
    rng = np.random.default_rng(5)
    pts = sim.raster(L, 100)
    x = [sim.coverage_fraction_hetero(rng.uniform(0, L, (n, 2)), rng.choice(radii, n, p=w), pts) for _ in range(300)]
    assert np.mean(x) == pytest.approx(R.mean_cov_mix(n, radii, w, L), abs=0.006)


def test_awake_share_is_monotone_and_bounded():
    L, r, rc = 100.0, 10.0, 20.0
    n0 = R.n_joint(0.8, 0.1, r, rc, L)
    q1 = R.min_awake_share(n0, 0.8, 0.1, r, rc, L, step=0.05)
    q2 = R.min_awake_share(2 * n0, 0.8, 0.1, r, rc, L, step=0.05)
    assert q1 is not None and q2 is not None and 0 < q2 < q1 <= 1


def test_ilp_cover_is_feasible_on_its_demand_points():
    from wsndeploy import ilp
    out = ilp.min_cover_ilp(100.0, 25.0, h_demand=10.0, h_cand=10.0, guaranteed=True, time_limit=60)
    assert out["nodes"] > 0
    assert sim.coverage_fraction(out["layout"], sim.raster(100.0, 200), 25.0) == 1.0


def test_reliable_lattice_meets_its_confidence_criterion():
    """reliable_lattice returns the first kappa whose lower Wilson bound reaches 1 - delta."""
    from wsndeploy.stats import wilson
    L, r, sigma = 100.0, 20.0, 4.0
    lay, kappa, share, lo = placement.reliable_lattice(L, r, sigma, 0.95, 0.2, "square", design_res=100,
                                                       sim_res=100, runs=60, seed=3)
    assert lo >= 0.8 and kappa <= 1.0
    x = placement.mc_coverage_perturbed(lay, r, sigma, L, 60, np.random.default_rng(3), 100)
    assert wilson(int(np.sum(x >= 0.95)), 60)[1] == pytest.approx(lo)

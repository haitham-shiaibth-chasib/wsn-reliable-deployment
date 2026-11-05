"""Statistical certification of a deployment design by independent Monte Carlo drops.

The analytical rules of the article (the Beta approximation of the coverage tail, the isolated-node
approximation of connectivity, the closed-form expected coverage under drop error) are design rules:
they are accurate in the tested settings but they are approximations, so they do not by themselves
bound the probability that a design meets its target. This module adds a certification layer that
does.

Inferential objective
    A design d (a node count, or a planned layout) succeeds in one drop when the event S holds
    (for example C >= C_t, or C >= C_t and the network is connected). Its reliability is
    p(d) = P(S). The requirement is p(d) >= 1 - delta.

Certificate
    Draw n independent drops of d with seeds that were not used to choose d, count the k successes
    and compute the one-sided Clopper-Pearson lower confidence bound LB(k, n; alpha'). The design is
    certified when LB >= 1 - delta. If p(d) < 1 - delta, the probability of certifying d is at most
    alpha'.

Adaptive search
    When a design fails, the search moves to a larger design (more nodes, or a smaller lattice
    factor) and certifies it with a fresh, independent sample. At most K attempts are made and each
    uses alpha' = alpha / K (Bonferroni). Because every attempt uses new drops, the union bound gives
    P(the returned design has p(d) < 1 - delta) <= K alpha' = alpha, whatever rule chose the
    sequence of designs. If none of the K attempts succeeds, the search reports that no design was
    certified; it never returns an uncertified design as certified.
"""
from __future__ import annotations

from scipy import stats


def cp_lower(k: int, n: int, alpha: float) -> float:
    """One-sided (1 - alpha) Clopper-Pearson lower bound of a binomial proportion."""
    if k <= 0:
        return 0.0
    return float(stats.beta.ppf(alpha, k, n - k + 1))


def cp_upper(k: int, n: int, alpha: float) -> float:
    """One-sided (1 - alpha) Clopper-Pearson upper bound of a binomial proportion."""
    if k >= n:
        return 1.0
    return float(stats.beta.ppf(1 - alpha, k + 1, n - k))


def binom_p_greater(k: int, n: int, p0: float) -> float:
    """Exact one-sided p-value of H0: p <= p0 against H1: p > p0."""
    return float(stats.binom.sf(k - 1, n, p0))


def certify_sequence(designs, sample, n_cert, delta, alpha=0.05, max_attempts=10, seed_of=None):
    """Certify the first design of `designs` that passes, with fresh drops for every attempt.

    designs      iterable of designs, tried in order (at most max_attempts are used)
    sample       function (design, n, seed) -> list of booleans, one per independent drop
    seed_of      function attempt_index -> seed of that attempt's certification sample
    Returns (certified design or None, list of attempt records).
    """
    a_ = alpha / max_attempts
    log = []
    for j, d in enumerate(designs):
        if j >= max_attempts:
            break
        seed = seed_of(j) if seed_of else j
        ok = sample(d, n_cert, seed)
        k = int(sum(ok))
        lb = cp_lower(k, n_cert, a_)
        rec = dict(attempt=j + 1, seed=seed, runs=n_cert, met=k, share=k / n_cert, lower_bound=lb,
                   alpha_attempt=a_, certified=lb >= 1 - delta)
        log.append((d, rec))
        if rec["certified"]:
            return d, log
    return None, log

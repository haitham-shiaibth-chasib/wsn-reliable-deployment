"""Check that no certification sample reuses a seed of a sample that chose or validated a design.

    python tools/check_seed_separation.py

The certification of Algorithm 3 is valid only if its drops are independent of the drops that chose
the design. Each check below compares the seeds of a certification experiment with the seeds of the
design and validation samples of the same designs; an empty intersection is required.
"""
from __future__ import annotations

import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(ROOT, "results", "raw")


def seeds(fname, where=lambda q: True):
    path = os.path.join(RAW, fname)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return {int(float(q["seed"])) for q in csv.DictReader(f) if q.get("seed") not in (None, "") and where(q)}


def manifest(prefix):
    with open(os.path.join(RAW, "seed_manifest.csv")) as f:
        return {int(float(q["seed"])) for q in csv.DictReader(f) if q["experiment"].startswith(prefix)}


CHECKS = [
    ("E17 coverage certification vs E6b validation", lambda: seeds("E17_runs.csv", lambda q: q["part"] == "coverage"),
     lambda: seeds("E6b_runs.csv")),
    ("E17 joint certification vs E7b validation", lambda: seeds("E17_runs.csv", lambda q: q["part"] == "joint"),
     lambda: seeds("E7b_runs.csv")),
    ("E17 environment certification vs E11 design and validation",
     lambda: seeds("E17_runs.csv", lambda q: q["part"] == "environment"),
     lambda: manifest("E11") | (seeds("E11a_runs.csv") or set()) | (seeds("E11b_runs.csv") or set())),
    ("E18 lattice certification vs E16 search and validation", lambda: seeds("E18_runs.csv"),
     lambda: manifest("E16") | manifest("E18-search") | (seeds("E16_runs.csv") or set())),
    ("E19 stress certification vs E19 calibration", lambda: seeds("E19_runs.csv", lambda q: q["part"] == "certification"),
     lambda: seeds("E19_runs.csv", lambda q: q["part"] == "calibration")),
    ("E19 correlated-shadowing certification vs its design and rule samples",
     lambda: seeds("E19_runs.csv", lambda q: q["part"] == "correlated-certification"),
     lambda: seeds("E19_runs.csv", lambda q: q["part"] in ("correlated-design", "correlated-rule"))),
]


def main():
    bad = 0
    for name, a, b in CHECKS:
        sa, sb = a(), b()
        if not sa:
            print(f"  skipped  {name} (no data)")
            continue
        both = sa & (sb or set())
        print(f"  {'ok' if not both else 'FAIL':7s}  {name}: {len(sa)} certification seeds, {len(sb or [])} others, "
              f"{len(both)} shared")
        bad += bool(both)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

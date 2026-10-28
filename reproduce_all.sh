#!/usr/bin/env bash
# Reproduce every table and figure of the manuscript.
#
#   ./reproduce_all.sh                 full run (about 5 h on a 2-core machine)
#   ./reproduce_all.sh --quick         10 % of the runs, about 20 min (smoke test only)
#   WORKERS=4 ./reproduce_all.sh       more processes for the optimiser comparison (E10)
#   TEMPLATE=path/IJIES_Format.docx ./reproduce_all.sh   also rebuild the Word manuscript
set -euo pipefail
cd "$(dirname "$0")"
WORKERS="${WORKERS:-2}"
QUICK=""
if [[ "${1:-}" == "--quick" ]]; then QUICK="--quick"; fi

echo "== 1/5 unit tests"
python -m pytest -q tests

echo "== 2/5 experiments (results/ and results/raw/)"
python experiments/run_experiments.py --exp all --workers "$WORKERS" $QUICK

echo "== 3/5 statistical tests (results/statistical_tests.csv)"
python experiments/statistics.py

echo "== 4/5 figures (figures/)"
python experiments/make_figures.py

if [[ -z "$QUICK" ]]; then
  echo "== 5/5 checksums of the deterministic result files"
  python tools/verify_results.py
else
  echo "== 5/5 checksums skipped in --quick mode"
fi

if [[ -n "${TEMPLATE:-}" ]]; then
  echo "== manuscript"
  python manuscript/build_paper.py --template "$TEMPLATE"
fi
echo "done"

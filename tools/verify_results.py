"""Check that a re-run reproduced the published result files.

    python tools/verify_results.py            compare with results/CHECKSUMS.sha256
    python tools/verify_results.py --write    record new checksums (maintainers only)

Each CSV is hashed after removing the columns that depend on the machine rather than
on the computation (wall-clock times). Identical hashes mean bit-identical numbers.
Different processors or library builds can change the last digits of floating-point
results; in that case compare the aggregated tables with a tolerance instead.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(ROOT, "results")
LIST = os.path.join(RES, "CHECKSUMS.sha256")
MACHINE_DEPENDENT = {"seconds"}


def canonical_hash(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return hashlib.sha256(b"").hexdigest()
    keep = [i for i, h in enumerate(rows[0]) if h not in MACHINE_DEPENDENT]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for r in rows:
        w.writerow([r[i] for i in keep])
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def files():
    out = []
    for folder in (RES, os.path.join(RES, "raw"), os.path.join(RES, "raw", "layouts")):
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith(".csv"):
                out.append(os.path.relpath(os.path.join(folder, name), RES).replace(os.sep, "/"))
    return out


def main():
    if "--write" in sys.argv:
        with open(LIST, "w", newline="\n") as f:
            for rel in files():
                f.write(f"{canonical_hash(os.path.join(RES, rel))}  {rel}\n")
        print(f"wrote {LIST}")
        return
    expected = dict(reversed(line.split()) for line in open(LIST) if line.strip())
    bad = []
    for rel, h in expected.items():
        path = os.path.join(RES, rel)
        if not os.path.exists(path):
            bad.append((rel, "missing"))
        elif canonical_hash(path) != h:
            bad.append((rel, "different"))
    for rel, why in bad:
        print(f"  {why:9s} {rel}")
    print(f"{len(expected) - len(bad)} of {len(expected)} result files reproduced exactly")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Bambu Studio's output varies from run to run (README, "Determinism"). For one case, slices it N times with the
reference and N times with a candidate and reports both sets of plate G-code hashes and their overlap: the same
program gives overlapping distributions; a different one does not.
Usage: distribution.py <case inputs dir> <runs> [x86_64|aarch64|device:SERIAL]"""
import collections
import concurrent.futures as cf
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pandy_equiv import runners  # noqa: E402
from run import plate_hashes  # noqa: E402

inputs, n = Path(sys.argv[1]), int(sys.argv[2])
arch = sys.argv[3] if len(sys.argv) > 3 else "x86_64"
args = json.loads((inputs / "case.json").read_text()) and None
from pandy_equiv import cases  # noqa: E402
case = json.loads((inputs / "case.json").read_text())
argv = cases.materialise(case, Path(tempfile.mkdtemp()))
ref = runners.Reference()
cand = (runners.Device(Path(__file__).resolve().parents[1] / "build" / "aarch64" / "package", arch.split(":", 1)[1])
        if arch.startswith("device:") else runners.Engine(Path(__file__).resolve().parents[1] / "build" / arch / "package", arch))
tmp = Path(tempfile.mkdtemp(prefix="dist-", dir=Path(__file__).resolve().parents[1] / "build"))


def one(job):
    who, k = job
    runners.set_cpu(2 + (k * 2 + (who == "cand")) % 20)
    r = (ref if who == "ref" else cand).run(inputs, argv, tmp / f"{who}{k}")
    p = tmp / f"{who}{k}" / "out.gcode.3mf"
    return who, (plate_hashes(p)[0][:12] if p.exists() else f"failed rc={r.returncode}")


counts = {"ref": collections.Counter(), "cand": collections.Counter()}
# A phone runs one slice at a time; the reference runs alongside it on the PC.
with cf.ThreadPoolExecutor(10) as ex, cf.ThreadPoolExecutor(1 if arch.startswith("device:") else 10) as cx:
    futures = [ex.submit(one, ("ref", k)) for k in range(n)] + [cx.submit(one, ("cand", k)) for k in range(n)]
    for f in futures:
        who, h = f.result()
        counts[who][h] += 1
shared = set(counts["ref"]) & set(counts["cand"])
print(json.dumps({"case": case["note"], "runs": n, "reference": counts["ref"], "candidate": counts["cand"],
                  "shared_variants": sorted(shared),
                  "candidate_runs_matching_a_reference_variant": sum(v for k, v in counts["cand"].items() if k in shared)}, indent=1))

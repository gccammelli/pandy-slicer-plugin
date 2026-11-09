#!/usr/bin/env python3
"""Pandy Studio engine equivalence test: slices every case with the reference (official Bambu Studio) and with a
candidate (the Pandy Studio engine), then requires byte-identical G-code.

  run.py profiles                                  refresh profiles.json from the reference's resources
  run.py check --suite smoke --candidate x86_64   [--package build/x86_64/package] [--jobs 6]
  run.py check --suite sweep --candidate device:SERIAL --package build/aarch64/package
  run.py check --suite random:SEED:COUNT --candidate aarch64

A case passes when both runs succeed and every plate's G-code is identical, or when both fail with the same
return code (an invalid setting must be refused the same way). Results: build/equiv/<run>/results.jsonl and
report.md, plus cached reference outputs under build/equiv/reference/. Multiple reference runs reveal the official
slicer's own run-to-run variation; byte equivalence requires a match to at least one reference run."""
import argparse
import concurrent.futures as cf
import datetime
import hashlib
import json
import platform
import shutil
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pandy_equiv import cases, compare, profiles, runners, verify_settings  # noqa: E402

BUILD = HERE.parent / "build" / "equiv"


def suite(name: str):
    if name == "smoke":
        return cases.smoke()
    if name == "sweep":
        return cases.sweep()
    if name == "benchy":
        return [cases.make(objects=cases.plate("benchy"), note="3DBenchy, X1 Carbon standard PLA")]
    if name.startswith("random:"):
        _, seed, count = name.split(":")
        return cases.random_cases(int(seed), int(count))
    if name.startswith("case:"):
        wanted = set(name[5:].split(","))
        return [c for c in cases.smoke() + cases.sweep() if c["id"] in wanted]
    raise SystemExit(f"unknown suite {name}")


def candidate(spec: str, package: str):
    if spec == "reference":
        return runners.Reference()
    if spec in ("x86_64", "aarch64"):
        return runners.Engine(Path(package or HERE.parent / "build" / spec / "package"), spec)
    if spec.startswith("device:"):
        return runners.Device(Path(package or HERE.parent / "build" / "aarch64" / "package"), spec.split(":", 1)[1])
    raise SystemExit(f"unknown candidate {spec}")


def outcome(run_dir: Path, rc: int, inputs=None, case=None) -> dict:
    res = {}
    if (run_dir / "result.json").exists():
        try:
            res = json.loads((run_dir / "result.json").read_text())
            if not isinstance(res, dict):
                res = {}
        except (OSError, ValueError):
            res = {}
    output = run_dir / "out.gcode.3mf"
    errors = verify_settings.verify(output, inputs, case) if output.exists() and inputs is not None and case is not None else []
    if output.exists() and res.get("return_code") != 0:
        errors.append("output exists without a successful slicer result")
    return {"returncode": rc, "cli_return_code": res.get("return_code"), "error": res.get("error_string"),
            "sliced": output.exists(), "profile_errors": errors}


def reference_run(ref, case, inputs, args, k=0):
    """The reference's k-th slice of [case], cached (k > 0: extra runs, to see Bambu Studio's own variation)."""
    image = ref.describe().get("image_id")
    if not image:
        raise RuntimeError("Cannot identify the official reference image")
    ref_key = hashlib.sha256(image.encode()).hexdigest()[:16]
    d = BUILD / "reference" / ref_key / case["id"] / f"run{k}"
    meta = d / "run.json"
    if meta.exists():
        cached = json.loads(meta.read_text())
        current = outcome(d, cached.get("returncode", -1), inputs, case) | {"seconds": cached.get("seconds", 0)}
        meta.write_text(json.dumps(current))
        return d, current
    r = ref.run(inputs, args, d)
    o = outcome(d, r.returncode, inputs, case) | {"seconds": round(r.seconds, 2)}
    meta.write_text(json.dumps(o))
    return d, o


def plate_hashes(path: Path) -> tuple:
    import zipfile
    with zipfile.ZipFile(path) as z:
        hashes = tuple(compare.sha(z.read(n)) for n in sorted(z.namelist()) if compare.GCODE.search(n))
        if not hashes:
            raise ValueError(f"No G-code plates in {path}")
        return hashes


REF_RUNS = 1


def check_case(case, ref, cand, run_dir):
    inputs = run_dir / "inputs" / case["id"]
    args = cases.materialise(case, inputs)
    rdir, ro = reference_run(ref, case, inputs, args)
    cdir = run_dir / "candidate" / case["id"]
    cr = cand.run(inputs, args, cdir)
    co = outcome(cdir, cr.returncode, inputs, case) | {"seconds": round(cr.seconds, 2)}
    row = {"id": case["id"], "note": case["note"], "args": args, "reference": ro, "candidate": co}
    if ro["profile_errors"] or co["profile_errors"]:
        row["status"] = "FAIL"
    elif ro["sliced"] and co["sliced"]:
        settings_diff = verify_settings.compare_outputs(rdir / "out.gcode.3mf", cdir / "out.gcode.3mf")
        if settings_diff:
            row["status"] = "FAIL"
            row["settings_diff"] = settings_diff
            return row
        cmp = compare.compare(rdir / "out.gcode.3mf", cdir / "out.gcode.3mf")
        row["compare"] = cmp
        row["status"] = "pass" if cmp["gcode_identical"] else "FAIL"
        if not cmp["gcode_identical"] and REF_RUNS > 1:
            # Bambu Studio varies from run to run: the candidate passes if it equals any output the reference gave.
            mine, seen = plate_hashes(cdir / "out.gcode.3mf"), {plate_hashes(rdir / "out.gcode.3mf")}
            for k in range(1, REF_RUNS):
                d, o = reference_run(ref, case, inputs, args, k)
                if o["sliced"] and not o["profile_errors"] and not verify_settings.compare_outputs(d / "out.gcode.3mf", cdir / "out.gcode.3mf"):
                    seen.add(plate_hashes(d / "out.gcode.3mf"))
            row["reference_variants"] = len(seen)
            if mine in seen:
                row["status"] = "pass-matches-reference-variant"
    elif not ro["sliced"] and not co["sliced"]:
        same = ro["cli_return_code"] not in (None, 0) and ro["cli_return_code"] == co["cli_return_code"]
        row["status"] = "pass-both-refused" if same else "FAIL"
    else:
        row["status"] = "FAIL"
    if row["status"] != "FAIL":
        shutil.rmtree(cdir, ignore_errors=True)  # keep only failing candidate outputs
    return row


def report(run_dir: Path, meta: dict, rows: list):
    rows = sorted(rows, key=lambda r: r["note"])
    passed = sum(r["status"].startswith("pass") for r in rows)
    lines = [f"# Engine equivalence: {meta['suite']} on {meta['candidate']['runner']}", "",
             f"- Run: {meta['started']} → {meta['finished']} (UTC)",
             f"- Reference: `{meta['reference'].get('image')}` image `{meta['reference'].get('image_id', '')[:19]}`",
             f"- Candidate: `{json.dumps(meta['candidate'])}`",
             f"- **{passed} / {len(rows)} cases identical** "
             f"({sum(r['status'] == 'pass' for r in rows)} sliced with byte-identical G-code, "
             f"{sum(r['status'] == 'pass-both-refused' for r in rows)} refused identically by both, "
             f"{sum(r['status'] == 'pass-matches-reference-variant' for r in rows)} equal to one of the reference's own varying outputs)", "",
             "| Status | Case | Note | Plates | G-code SHA-256 (reference = candidate) | Reference s | Candidate s |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        g = r.get("compare", {}).get("gcode", {})
        shas = ", ".join(v["reference_sha256"][:16] + ("" if v["identical"] else " ≠ " + v["candidate_sha256"][:16]) for v in g.values()) or (r["reference"].get("error") or "")
        lines.append(f"| {r['status']} | `{r['id']}` | {r['note']} | {len(g)} | {shas} | {r['reference'].get('seconds', '')} | {r['candidate'].get('seconds', '')} |")
    fails = [r for r in rows if r["status"] == "FAIL"]
    if fails:
        lines += ["", "## Failures", ""]
        for r in fails:
            lines += [f"### `{r['id']}` {r['note']}", "", "```json", json.dumps({k: r[k] for k in r if k != "args"}, indent=1)[:4000], "```", ""]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n")
    return passed, len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["profiles", "check"])
    ap.add_argument("--suite", default="smoke")
    ap.add_argument("--candidate", default="x86_64")
    ap.add_argument("--package")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--name")
    ap.add_argument("--ref-runs", type=int, default=1, help="reference slices per case to learn its own variation")
    a = ap.parse_args()
    if a.command == "profiles":
        profiles.write(HERE.parent / "build" / "reference" / "resources", HERE / "profiles.json")
        return
    global REF_RUNS
    REF_RUNS = a.ref_runs
    todo = suite(a.suite)
    ref, cand = runners.Reference(), candidate(a.candidate, a.package)
    runners.verify_resources(ref, cand)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = BUILD / (a.name or f"{stamp}-{a.suite.replace(':', '-')}-{cand.name}")
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {"suite": a.suite, "cases": len(todo), "started": stamp, "host": platform.node(),
            "reference": ref.describe(), "candidate": cand.describe()}
    rows, lock = [], threading.Lock()
    out = (run_dir / "results.jsonl").open("w")
    jobs = 1 if a.candidate.startswith("device:") else a.jobs
    counter = iter(range(1, 1000))
    with cf.ThreadPoolExecutor(jobs, initializer=lambda: runners.set_cpu(next(counter) * 2 % 24)) as ex:
        for i, row in enumerate(ex.map(lambda c: check_case(c, ref, cand, run_dir), todo), start=1):
            with lock:
                rows.append(row)
                out.write(json.dumps(row) + "\n")
                out.flush()
            print(f"[{i}/{len(todo)}] {row['status']:18} {row['id']} {row['note']}", flush=True)
    meta["finished"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (run_dir / "run.json").write_text(json.dumps(meta, indent=1))
    passed, total = report(run_dir, meta, rows)
    print(f"{passed}/{total} identical. Report: {run_dir / 'report.md'}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()

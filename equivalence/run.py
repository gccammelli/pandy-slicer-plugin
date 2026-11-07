#!/usr/bin/env python3
"""Pandy Studio engine equivalence test: slices every case with the reference (official Bambu Studio) and with a
candidate (the Pandy Studio engine), then requires byte-identical G-code.

  run.py profiles                                  refresh profiles.json from the reference's resources
  run.py check --suite smoke --candidate x86_64   [--package build/x86_64/package] [--jobs 6]
  run.py check --suite sweep --candidate device:SERIAL --package build/aarch64/package
  run.py check --suite random:SEED:COUNT --candidate aarch64

A case passes when both runs succeed and every plate's G-code is identical, or when both fail with the same
return code (an invalid setting must be refused the same way). Results: build/equiv/<run>/results.jsonl and
report.md, plus the reference outputs cached in build/equiv/reference/<case id>/ (the reference is deterministic:
`check --candidate reference` re-slices and compares the reference with itself)."""
import argparse
import concurrent.futures as cf
import datetime
import json
import platform
import shutil
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pandy_equiv import cases, compare, profiles, runners  # noqa: E402

BUILD = HERE.parent / "build" / "equiv"


def suite(name: str):
    if name == "smoke":
        return cases.smoke()
    if name == "sweep":
        return cases.sweep()
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


def outcome(run_dir: Path, rc: int) -> dict:
    res = {}
    if (run_dir / "result.json").exists():
        res = json.loads((run_dir / "result.json").read_text())
    return {"returncode": rc, "cli_return_code": res.get("return_code"), "error": res.get("error_string"),
            "sliced": (run_dir / "out.gcode.3mf").exists()}


def reference_run(ref, case, inputs, args, k=0):
    """The reference's k-th slice of [case], cached (k > 0: extra runs, to see Bambu Studio's own variation)."""
    d = BUILD / "reference" / case["id"] / (f"run{k}" if k else "")
    meta = d / "run.json"
    if meta.exists():
        return d, json.loads(meta.read_text())
    r = ref.run(inputs, args, d)
    o = outcome(d, r.returncode) | {"seconds": round(r.seconds, 2)}
    meta.write_text(json.dumps(o))
    return d, o


def plate_hashes(path: Path) -> tuple:
    import zipfile
    with zipfile.ZipFile(path) as z:
        return tuple(compare.sha(z.read(n)) for n in sorted(z.namelist()) if compare.GCODE.search(n))


REF_RUNS = 1


def check_case(case, ref, cand, run_dir):
    inputs = run_dir / "inputs" / case["id"]
    args = cases.materialise(case, inputs)
    rdir, ro = reference_run(ref, case, inputs, args)
    cdir = run_dir / "candidate" / case["id"]
    cr = cand.run(inputs, args, cdir)
    co = outcome(cdir, cr.returncode) | {"seconds": round(cr.seconds, 2)}
    row = {"id": case["id"], "note": case["note"], "args": args, "reference": ro, "candidate": co}
    if ro["sliced"] and co["sliced"]:
        cmp = compare.compare(rdir / "out.gcode.3mf", cdir / "out.gcode.3mf")
        row["compare"] = cmp
        row["status"] = "pass" if cmp["gcode_identical"] else "FAIL"
        if not cmp["gcode_identical"] and REF_RUNS > 1:
            # Bambu Studio varies from run to run: the candidate passes if it equals any output the reference gave.
            mine, seen = plate_hashes(cdir / "out.gcode.3mf"), {plate_hashes(rdir / "out.gcode.3mf")}
            for k in range(1, REF_RUNS):
                d, o = reference_run(ref, case, inputs, args, k)
                if o["sliced"]:
                    seen.add(plate_hashes(d / "out.gcode.3mf"))
            row["reference_variants"] = len(seen)
            if mine in seen:
                row["status"] = "pass-matches-reference-variant"
    elif not ro["sliced"] and not co["sliced"]:
        same = ro["cli_return_code"] == co["cli_return_code"]
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

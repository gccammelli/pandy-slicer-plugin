#!/usr/bin/env python3
"""The equivalence matrix: reference models (rows) x printers and settings (columns), each cell sliced on a phone and
by the official Bambu Studio, classified and drawn as a colour grid in docs/equivalence/.

  green   1:1  the phone's G-code is byte-identical to an output of the official build, or geometrically within the
               official build's own run-to-run variation (or both refused the settings identically)
  yellow  part 1:1, supports differ: the part's walls are identical; differences only in supports and in the
               layers resting on them (support interface, bridges and solid infill over supports, skirt/brim/purge
               around a support footprint)
  red     the part differs beyond the official build's own variation, or only one side sliced
  grey    not verified (not run)

Each column changes one thing from the baseline (X1 Carbon 0.4 nozzle, 0.20mm Standard, Bambu PLA Basic), so the
grid stays sparse but covers every printer, nozzle sizes, layer heights, infill, walls, supports and surface options.

  matrix.py run --device SERIAL [--ref-runs 5] [--only ROWS] [--cols N]   slice and classify (resumable)
  matrix.py recheck [--ref-runs 20]                                        non-green cells against more official runs
  matrix.py report                                                          write docs/equivalence/{README.md,matrix.svg}
"""
import argparse
import concurrent.futures as cf
import datetime
import hashlib
import html
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from pandy_equiv import cases, compare, models, runners  # noqa: E402
from run import plate_hashes, outcome  # noqa: E402

OUT = ROOT / "build" / "matrix"
DOCS = ROOT / "docs" / "equivalence"
ROWS = ["cube", "cylinder", "tube", "sphere", "torus", "gear", "bridge", "overhangs", "thin", "tower"]
X1C = "Bambu Lab X1 Carbon 0.4 nozzle"


def columns():
    """(label, group, case kwargs). Printer columns use each printer's default process and PLA."""
    cols = [("baseline", "Baseline", {})]
    for model in sorted(cases.PRINTERS):
        if model != "X1 Carbon":
            cols.append((model, "Printer", {"printer": model}))
    for n, proc in (("0.2", "0.10mm Standard @BBL X1C 0.2 nozzle"), ("0.6", "0.30mm Standard @BBL X1C 0.6 nozzle"), ("0.8", "0.40mm Standard @BBL X1C 0.8 nozzle")):
        cols.append((f"nozzle {n} mm", "Nozzle", {"nozzle": n, "process": proc}))
    for lh, proc in (("0.08", "0.08mm Extra Fine @BBL X1C"), ("0.12", "0.12mm Fine @BBL X1C"), ("0.16", "0.16mm Optimal @BBL X1C"),
                     ("0.24", "0.24mm Draft @BBL X1C"), ("0.28", "0.28mm Extra Draft @BBL X1C")):
        cols.append((f"layer {lh} mm", "Layer height", {"process": proc}))
    for v in ("0%", "40%", "100%"):
        cols.append((f"infill {v}", "Infill", {"overrides": {"sparse_infill_density": v}}))
    for v in ("gyroid", "grid", "honeycomb", "lightning", "adaptivecubic"):
        cols.append((f"pattern {v}", "Infill", {"overrides": {"sparse_infill_pattern": v}}))
    for v in ("1", "4"):
        cols.append((f"walls {v}", "Walls", {"overrides": {"wall_loops": v}}))
    cols.append(("classic walls", "Walls", {"overrides": {"wall_generator": "classic"}}))
    cols.append(("normal supports", "Supports", {"overrides": {"enable_support": "1", "support_type": "normal(auto)"}}))
    cols.append(("tree supports", "Supports", {"overrides": {"enable_support": "1", "support_type": "tree(auto)"}}))
    cols.append(("no brim", "Adhesion", {"overrides": {"brim_type": "no_brim"}}))
    cols.append(("outer brim", "Adhesion", {"overrides": {"brim_type": "outer_only"}}))
    cols.append(("ironing", "Surface", {"overrides": {"ironing_type": "top"}}))
    cols.append(("seam back", "Surface", {"overrides": {"seam_position": "back"}}))
    cols.append(("fuzzy skin", "Surface", {"overrides": {"fuzzy_skin": "external"}}))
    return cols


def cell_case(row, kw):
    printer = kw.get("printer", "X1 Carbon")
    obj = cases.plate(row)
    c = cases.make(printer, objects=obj, overrides=kw.get("overrides"), process=kw.get("process"), note=f"{row} | {kw}")
    if "nozzle" in kw:
        c["printer"] = f"Bambu Lab X1 Carbon {kw['nozzle']} nozzle"
        c["filaments"] = [f"Bambu PLA Basic @BBL X1C {kw['nozzle']} nozzle"]
        c["id"] = cases.case_id(c)
    return c


# --- geometry (see geometry.py): per feature and layer, nearest-point distances between path sets
def paths(p):
    import geometry as G
    G.group_of = lambda f: f
    return G.parse(p)


def max_dist(a, b):
    import numpy as np
    from scipy.spatial import cKDTree
    if len(a) == 0 and len(b) == 0:
        return 0.0
    if len(a) == 0 or len(b) == 0:
        return math.inf
    return float(max(cKDTree(b).query(a)[0].max(), cKDTree(a).query(b)[0].max()))


def diffs(x, y):
    """(layer, feature) -> distance, for every pair of path sets that differ by more than 1 micron."""
    out = {}
    for layer in set(x) | set(y):
        for f in set(x.get(layer, {})) | set(y.get(layer, {})):
            import numpy as np
            a = x.get(layer, {}).get(f, (np.zeros((0, 2)), 0))[0]; b = y.get(layer, {}).get(f, (np.zeros((0, 2)), 0))[0]
            d = max_dist(a, b)
            if d > 0.001:
                out[(layer, f)] = d
    return out


SUPPORT = ("Support", "Support interface", "Support transition")
NEAR_SUPPORT = ("Bridge", "Internal Bridge", "Internal solid infill", "Bottom surface", "Skirt", "Brim", "Custom", "Prime tower")
WALLS = ("Outer wall", "Inner wall", "Overhang wall")


def classify(ref_dirs, cand_dir):
    """Status and details for one cell."""
    ro = [json.loads((d / "run.json").read_text()) for d in ref_dirs]
    co = json.loads((cand_dir / "run.json").read_text())
    if not co["sliced"] and not ro[0]["sliced"]:
        return ("green" if co["cli_return_code"] == ro[0]["cli_return_code"] else "red"), {"both_refused": True, "code": co["cli_return_code"]}
    if co["sliced"] != ro[0]["sliced"]:
        return "red", {"only_one_sliced": True, "candidate": co, "reference": ro[0]}
    ref_files = [d / "out.gcode.3mf" for d in ref_dirs if (d / "out.gcode.3mf").exists()]
    cand = cand_dir / "out.gcode.3mf"
    if plate_hashes(cand) in {plate_hashes(f) for f in ref_files}:
        return "green", {"byte_identical": True, "official_variants": len({plate_hashes(f) for f in ref_files})}
    R = [paths(f) for f in ref_files]
    C = paths(cand)
    # The official build's own variation, per feature: the largest distance between any two official runs.
    tol = {}
    for i in range(len(R)):
        for j in range(i + 1, len(R)):
            for (layer, f), d in diffs(R[i], R[j]).items():
                tol[f] = max(tol.get(f, 0.0), d)
    best = None
    for r in R:
        dd = {k: d for k, d in diffs(C, r).items() if d > tol.get(k[1], 0.0) + 0.01}
        if best is None or len(dd) < len(best):
            best = dd
    if not best:
        return "green", {"within_official_variation": True, "official_tolerance_mm": {k: round(v, 3) for k, v in tol.items()}}
    support_layers = {layer for (layer, f) in best if f in SUPPORT} | {l for l in range(0, 1 + max(l for l, _ in best))
                                                                       if any(f in SUPPORT for f in C.get(l, {}))}
    part = {k: v for k, v in best.items() if k[1] not in SUPPORT}
    walls = {k: v for k, v in part.items() if k[1] in WALLS}
    near = all(f in NEAR_SUPPORT and any(l - k in support_layers for k in range(0, 4)) for (l, f) in part)
    detail = {"max_mm": round(max(best.values()), 3), "differing": len(best),
              "features": sorted({f for _, f in best}), "layers": [min(l for l, _ in best), max(l for l, _ in best)]}
    if not walls and near and any(f in SUPPORT for _, f in best):
        return "yellow", detail
    return "red", detail


def run(args):
    import threading
    cols = columns()
    if args.cols:
        cols = cols[: args.cols]
    rows = args.only.split(",") if args.only else ROWS
    ref, dev = runners.Reference(), runners.Device(ROOT / "build" / "aarch64" / "package", args.device)
    OUT.mkdir(parents=True, exist_ok=True)
    results_file = OUT / "results.json"
    results = json.loads(results_file.read_text()) if results_file.exists() else {}
    lock = threading.Lock()
    todo = [(row, label, kw) for row in rows for (label, _, kw) in cols]
    todo = [t for t in todo if f"{t[0]}|{t[1]}" not in results or results[f"{t[0]}|{t[1]}"]["engine"] != dev.ident["engine_sha256"]]

    def reference(c, inputs, argv, k):
        d = OUT / "cells" / c["id"] / f"ref{k}"
        if not (d / "run.json").exists():
            runners.set_cpu(2 + k * 2)
            r = ref.run(inputs, argv, d)
            (d / "run.json").write_text(json.dumps(outcome(d, r.returncode)))
        return d

    def cell(t):
        row, label, kw = t
        c = cell_case(row, kw)
        base = OUT / "cells" / c["id"]
        inputs = base / "inputs"
        argv = cases.materialise(c, inputs)
        with cf.ThreadPoolExecutor(args.ref_runs) as ex:
            refs = list(ex.map(lambda k: reference(c, inputs, argv, k), range(args.ref_runs)))
        with lock:  # one phone, one slice at a time
            cd = base / "phone"
            r = dev.run(inputs, argv, cd)
            (cd / "run.json").write_text(json.dumps(outcome(cd, r.returncode) | {"seconds": round(r.seconds, 1)}))
        status, detail = classify(refs, cd)
        with lock:
            results[f"{row}|{label}"] = {"row": row, "column": label, "case": c["id"], "status": status, "detail": detail,
                                         "printer": c["printer"], "process": c["process"], "filament": c["filaments"],
                                         "overrides": c["process_overrides"], "engine": dev.ident["engine_sha256"],
                                         "phone_seconds": json.loads((cd / "run.json").read_text()).get("seconds")}
            results_file.write_text(json.dumps(results, indent=1, default=str))
        print(f"{status:7} {row:10} {label}", flush=True)

    with cf.ThreadPoolExecutor(3) as ex:  # references of the next cells run while the phone slices
        list(ex.map(cell, todo))


def recheck(args):
    """Non-green cells again, against more official runs (--ref-runs, default 20): a difference the official build also
    produces in some run is its own variation, not the phone's. The phone's output is not re-sliced."""
    results = json.loads((OUT / "results.json").read_text())
    ref = runners.Reference()
    for key, r in results.items():
        if r["status"] == "green":
            continue
        base = OUT / "cells" / r["case"]
        inputs = base / "inputs"
        argv = cases.materialise(json.loads((inputs / "case.json").read_text()), base / "inputs-recheck")
        def one(k):
            d = base / f"ref{k}"
            if not (d / "run.json").exists():
                runners.set_cpu(2 + (k % 10) * 2)
                rr = ref.run(inputs, argv, d)
                (d / "run.json").write_text(json.dumps(outcome(d, rr.returncode)))
            return d
        with cf.ThreadPoolExecutor(10) as ex:
            refs = list(ex.map(one, range(args.ref_runs)))
        status, detail = classify(refs, base / "phone")
        print(f"{r['status']:7} -> {status:7} {key} {json.dumps(detail)[:150]}", flush=True)
        r["status"], r["detail"] = status, detail | {"official_runs": args.ref_runs}
        (OUT / "results.json").write_text(json.dumps(results, indent=1, default=str))


COLOURS = {"green": "#2FB344", "yellow": "#F2C94C", "red": "#E5484D", "grey": "#C9CDD3"}


def svg(results):
    cols = columns()
    cw, ch, left, top = 16, 16, 92, 120
    w, h = left + cw * len(cols) + 10, top + ch * len(ROWS) + 10
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="Helvetica,Arial,sans-serif" font-size="10">',
           f'<rect width="{w}" height="{h}" fill="white"/>']
    for j, (label, group, _) in enumerate(cols):
        x = left + j * cw + cw / 2 + 3
        out.append(f'<text transform="translate({x},{top - 6}) rotate(-90)" fill="#333">{html.escape(label)}</text>')
    for i, row in enumerate(ROWS):
        y = top + i * ch
        out.append(f'<text x="{left - 6}" y="{y + 12}" text-anchor="end" fill="#333">{row}</text>')
        for j, (label, _, _) in enumerate(cols):
            r = results.get(f"{row}|{label}")
            st = r["status"] if r else "grey"
            tip = f"{row} / {label}: {st}" + (f" ({json.dumps(r['detail'])[:160]})" if r else " (not run)")
            out.append(f'<rect x="{left + j * cw + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="2" fill="{COLOURS[st]}">'
                       f'<title>{html.escape(tip)}</title></rect>')
    out.append("</svg>")
    return "\n".join(out)


def report(_):
    results = json.loads((OUT / "results.json").read_text()) if (OUT / "results.json").exists() else {}
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "matrix.svg").write_text(svg(results))
    cols = columns()
    total = len(cols) * len(ROWS)
    counts = {k: sum(1 for r in results.values() if r["status"] == k) for k in ("green", "yellow", "red")}
    counts["grey"] = total - sum(counts.values())
    pkg = runners.package_identity(ROOT / "build" / "aarch64" / "package")
    image = subprocess.run(["sudo", "-n", "docker", "image", "inspect", "-f", "{{.Id}}", runners.REFERENCE_IMAGE], capture_output=True, text=True).stdout.strip()
    dev = next(iter(results.values()), {}) if results else {}
    lines = [
        "# Equivalence report", "",
        "Does Pandy Studio's phone slicer write the same G-code as the official Bambu Studio? Each cell below is one",
        "plate sliced on a phone and by the official Bambu Studio, compared as described in",
        "[equivalence/README.md](../../equivalence/README.md). Regenerate with `equivalence/matrix.py run` and `report`.", "",
        f"*Generated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.*", "",
        "| | |", "|---|---|",
        f"| 🟩 **1:1** | the phone's G-code is byte-identical to an output of the official build, or within the official build's own run-to-run variation |",
        f"| 🟨 **Part 1:1, supports differ** | the part's walls are identical; only supports and the layers resting on them differ |",
        f"| 🟥 **Differs** | the part differs beyond the official build's own variation |",
        f"| ⬜ **Not verified** | not run yet |", "",
        f"**{counts['green']} green · {counts['yellow']} yellow · {counts['red']} red · {counts['grey']} not verified** "
        f"(of {total}: {len(ROWS)} models × {len(cols)} configurations)", "",
        "![Equivalence matrix](matrix.svg)", "",
        "Hover a cell (open the SVG) for its details. Columns change one thing from the baseline: X1 Carbon, 0.4 mm nozzle,",
        "0.20mm Standard @BBL X1C, Bambu PLA Basic; printer columns use that printer's own default process and PLA.", "",
        "## What was compared", "",
        "| | |", "|---|---|",
        "| Official build | Bambu Studio 02.08.02.61 Linux AppImage (SHA-256 pinned in Pandy Slicer's Dockerfile), x86-64, "
        f"Docker image `{image[:19]}` |",
        f"| Phone engine | `pandy-engine` arm64, SHA-256 `{pkg['engine_sha256']}` |",
        f"| Profiles | the official release's `resources/`, tree SHA-256 `{pkg['resources_sha256']}` ({pkg['resources_files']} files) |",
        "| Compiler | GCC 13.3.0 (Ubuntu 24.04), both builds |",
        "| C library | glibc 2.39 (Ubuntu 24.04), static on the phone |",
        "| Maths functions | arm64 glibc, except `hypot`, `cbrt`, `pow`, `tanf`, `asinf`, `acosf`, `atanf`, `atan2f`: glibc 2.39's "
        "source compiled as x86-64 compiles it ([engine/x86-libm](../../engine/x86-libm/README.md)); bit-identical to x86-64 on 2M inputs each |",
        "| Phone | Sony Xperia 10 IV (XQ-CC54), Android 14, Snapdragon 695 |",
        "| Runs | each cell: 5 official runs (the official build varies from run to run), 1 phone run; all pinned to one CPU |", "",
        "Models are generated (`equivalence/pandy_equiv/models.py`): cube 20 mm, cylinder, tube (hole), sphere, torus, gear,",
        "bridge (32 mm span), overhangs (45°/60°/75°), thin walls (0.4–2 mm), tower 80 mm.", "",
    ]
    others = sorted((r for r in results.values() if r["status"] != "green"), key=lambda r: (r["status"], r["row"], r["column"]))
    if others:
        lines += ["## Cells that are not green", "",
                  "| | Model | Configuration | Largest difference | Features | Layers |", "|---|---|---|---|---|---|"]
        icon = {"yellow": "🟨", "red": "🟥"}
        for r in others:
            d = r["detail"]
            lines.append(f"| {icon[r['status']]} | {r['row']} | {r['column']} | {d.get('max_mm', '–')} mm | {', '.join(d.get('features', [])) or json.dumps(d)[:80]} | "
                         f"{'–'.join(map(str, d.get('layers', []))) or '–'} |")
        lines.append("")
    lines += ["## Known differences", "",
              "* **Tree supports** take different branch decisions on ARM (a systematic difference still being traced). The part's walls are identical; supports and the layers resting on them differ by up to about 1.5 mm. The app marks tree-supported slices as not verified.",
              "* **NaN signs**: an invalid floating-point operation gives `-nan` on x86-64 and `nan` on ARM (the processors' default). It only shows if a NaN were printed into the G-code.",
              "* **Fuzzy skin** is random in Bambu Studio itself: no two official runs are alike either.", ""]
    (DOCS / "README.md").write_text("\n".join(lines))
    print(f"{DOCS / 'README.md'}: {counts}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["run", "report", "recheck"])
    ap.add_argument("--device")
    ap.add_argument("--ref-runs", type=int, default=5)
    ap.add_argument("--only")
    ap.add_argument("--cols", type=int)
    a = ap.parse_args()
    if a.command == "recheck" and a.ref_runs == 5:
        a.ref_runs = 20
    {"run": run, "report": report, "recheck": recheck}[a.command](a)

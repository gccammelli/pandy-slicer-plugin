#!/usr/bin/env python3
"""The equivalence matrix: reference models (rows) x printers and settings (columns), each cell sliced on a phone and
by the official Bambu Studio, classified and drawn as a colour grid in docs/equivalence/.

  green        G-code is byte-identical to an official run, or both engines refuse identically
  dark green   bytes differ, but continuous paths are within observed official variation
  light green  only supports differ; model paths and extrusion stay within observed variation
  yellow  small bounded model-path differences, with consistent material and outline
  red     significant model differences or a failed bounded safety check
  grey    not verified or insufficient reference variation data

Each column changes one thing from the baseline (X1 Carbon 0.4 nozzle, 0.20mm Standard, Bambu PLA Basic), so the
grid stays sparse but covers every printer, nozzle sizes, layer heights, infill, walls, supports and surface options.

  matrix.py run --device SERIAL [--ref-runs 5] [--only ROWS] [--cols N]   slice and classify (resumable)
  matrix.py recheck [--ref-runs 20]                                        non-green cells against more official runs
  matrix.py reclassify [--only ROWS] [--columns LABELS]                  revalidate and reclassify saved outputs
  matrix.py report                                                          write docs/equivalence/{README.md,matrix.svg}
"""
import argparse
import concurrent.futures as cf
import datetime
import hashlib
import html
import json
import math
import re
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from pandy_equiv import cases, compare, models, runners, safety, toolpaths, verify_settings  # noqa: E402
from run import plate_hashes, outcome  # noqa: E402

OUT = ROOT / "build" / "matrix"
DOCS = ROOT / "docs" / "equivalence"
ROWS = ["cube", "cylinder", "tube", "sphere", "torus", "gear", "bridge", "overhangs", "thin", "tower", "benchy"]
X1C = "Bambu Lab X1 Carbon 0.4 nozzle"
CLASSIFICATION_VERSION = 12
VALIDATION_SHA256 = hashlib.sha256(b''.join(Path(p).read_bytes() for p in
    (verify_settings.__file__, safety.__file__, toolpaths.__file__, HERE / 'geometry.py'))).hexdigest()


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
    cols.append(("solid rectilinear", "Infill", {"overrides": {"sparse_infill_density": "100%", "sparse_infill_pattern": "zig-zag"}}))
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


# --- continuous line/arc geometry: per feature and layer, with a bounded numerical error
def paths(p):
    return toolpaths.parse(p)


def max_dist(a, b):
    import numpy as np
    from scipy.spatial import cKDTree
    if len(a) == 0 and len(b) == 0:
        return 0.0
    if len(a) == 0 or len(b) == 0:
        return math.inf
    if isinstance(a, toolpaths.PathGeometry) and isinstance(b, toolpaths.PathGeometry):
        # Exact primitive equality proves zero geometric distance, irrespective
        # of ordering or duplicate paths. Material is compared independently.
        for geometry in (a, b):
            if not hasattr(geometry, '_primitive_set'):
                geometry._primitive_set = frozenset(geometry.primitives)
        if a._primitive_set == b._primitive_set:
            return 0.
        return toolpaths.distance(a, b)
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
WALLS = ("Outer wall", "Inner wall", "Overhang wall")
INTERNAL = ("Sparse infill", "Internal solid infill", "Floating vertical shell")
SURFACE = WALLS + ("Top surface", "Bottom surface", "Gap infill")


def amounts(paths):
    return {(layer, f): e for layer, features in paths.items() for f, (_, e) in features.items()}


def layer_heights(path):
    with zipfile.ZipFile(path) as z:
        text = z.read('Metadata/plate_1.gcode').decode(errors='replace')
    layers = re.findall(r'^; Z_HEIGHT:\s*(-?\d+(?:\.\d+)?)\s*$', text, re.M)
    if len(layers) != text.count('; CHANGE_LAYER') or not layers:
        return None
    return [float(z) for z in layers]


def seam_gap(path):
    with zipfile.ZipFile(path) as z:
        cfg = json.loads(z.read('Metadata/project_settings.config'))
    value = cfg.get('seam_gap', '')
    if not isinstance(value, str) or not value.endswith('%'):
        return 0.
    try:
        return min(float(n) for n in cfg['nozzle_diameter']) * float(value[:-1]) / 100
    except (KeyError, ValueError, TypeError):
        return 0.


def seam_differences(observed, candidate, reference, gap):
    """Recognize relocated configured seam gaps while preserving contour and material bounds."""
    import numpy as np
    accepted = {}
    if not 0 < gap <= .2:
        return accepted
    for (layer, f), raw in observed.items():
        if f not in WALLS or not .02 < raw <= gap + .02:
            continue
        a = candidate.get(layer, {}).get(f); b = reference.get(layer, {}).get(f)
        if not a or not b or not isinstance(a[0], toolpaths.PathGeometry) or not isinstance(b[0], toolpaths.PathGeometry):
            continue
        if abs(a[1] - b[1]) > max(.00002, .005 * max(a[1], b[1])):
            continue
        ca, ga = a[0].close_seams(gap + .002, max(0, gap - .002))
        cb, gb = b[0].close_seams(gap + .002, max(0, gap - .002))
        if not ga or not gb or len(ga) != len(gb):
            continue
        bounds = float(np.max(np.abs(np.r_[ca.min() - cb.min(), ca.max() - cb.max()])))
        if bounds > .002:
            continue
        d = toolpaths.distance(ca, cb)
        if d <= .02:
            accepted[(layer, f)] = {'completed_contour_mm': round(d, 6), 'raw_path_mm': round(raw, 6),
                                    'bounds_delta_mm': round(bounds, 6), 'configured_gap_mm': gap}
    return accepted


def geometry_grade(differences, candidate, reference, volume_tolerance):
    """Grade a single reference; fail closed for missing material and unknown features."""
    import numpy as np
    ca, ra = amounts(candidate), amounts(reference)
    volume_diff = {k: abs(ca.get(k, 0) - ra.get(k, 0)) for k in ca.keys() | ra.keys()}
    changed_volume = {k: v for k, v in volume_diff.items() if v > max(0.002, volume_tolerance.get(k, 0) + 0.002)}
    keys = differences.keys() | changed_volume.keys()
    if not sum(v for (l, f), v in ca.items() if f in SUPPORT) and sum(v for (l, f), v in ra.items() if f in SUPPORT):
        return 'red'
    if not keys:
        return 'variant'
    if all(f in SUPPORT for _, f in keys):
        return 'blue'
    for layer, f in keys:
        if f in SUPPORT:
            continue
        if f not in INTERNAL + SURFACE:
            return 'red'
        a, b = ca.get((layer, f), 0), ra.get((layer, f), 0)
        # A missing path, or >5% extra/missing material, is not a small change.
        if not a or not b or abs(a - b) > max(0.002, 0.05 * max(a, b), volume_tolerance.get((layer, f), 0) + 0.002):
            return 'red'
        d = differences.get((layer, f), 0)
        if not math.isfinite(d) or d > (0.4 if f in INTERNAL else 0.02):
            return 'red'
        if f in SURFACE:
            ap = candidate[layer][f][0]; bp = reference[layer][f][0]
            if not len(ap) or not len(bp):
                return 'red'
            # Seam starts may move; the surface bounding box must not grow or shrink materially.
            if np.max(np.abs(np.r_[ap.min(axis=0) - bp.min(axis=0), ap.max(axis=0) - bp.max(axis=0)])) > 0.02:
                return 'red'
    return 'yellow'


def classify(ref_dirs, cand_dir):
    """Status and details for one cell."""
    ro = [json.loads((d / "run.json").read_text()) for d in ref_dirs]
    co = json.loads((cand_dir / "run.json").read_text())
    invalid = [o.get("profile_errors") for o in [*ro, co] if o.get("profile_errors")]
    if invalid:
        return "red", {"invalid_effective_settings": invalid}
    if not co["sliced"] and not ro[0]["sliced"]:
        same = co["cli_return_code"] not in (None, 0) and all(r["cli_return_code"] == co["cli_return_code"] and not r["sliced"] for r in ro)
        return ("refused" if same else "red"), {"both_refused": True, "code": co["cli_return_code"]}
    if any(co["sliced"] != r["sliced"] for r in ro):
        return "red", {"only_one_sliced": True, "candidate": co, "reference": ro[0]}
    ref_files = [d / "out.gcode.3mf" for d in ref_dirs if (d / "out.gcode.3mf").exists()]
    cand = cand_dir / "out.gcode.3mf"
    try:
        safety_errors = safety.problems(cand)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        return 'red', {'safety_errors': [f'Cannot read candidate output: {e}']}
    if safety_errors:
        return "red", {"safety_errors": safety_errors}
    mismatches = [verify_settings.compare_outputs(f, cand) for f in ref_files]
    mismatches = [errors for errors in mismatches if errors]
    if mismatches:
        return "red", {"effective_settings_differ": mismatches}
    ref_variants = {plate_hashes(f): f for f in ref_files}
    if plate_hashes(cand) in ref_variants:
        return "green", {"byte_identical": True, "official_variants": len(ref_variants)}
    if len(plate_hashes(cand)) != 1:
        return 'unverified', {'reason': 'Geometry comparison currently supports one plate'}
    if len(ref_files) < 2:
        return "unverified", {"reason": "Non-identical G-code needs at least two official runs to assess variation"}
    # Repeated identical G-code cannot enlarge the reference envelope.
    ref_files = list(ref_variants.values())
    cz = layer_heights(cand)
    rz = [layer_heights(f) for f in ref_files]
    if cz is None or any(z is None for z in rz):
        return 'unverified', {'reason': 'Layer heights missing or incomplete'}
    try:
        R = [paths(f) for f in ref_files]
        C = paths(cand)
    except ValueError as e:
        return 'unverified', {'reason': f'Unsupported or invalid extrusion geometry: {e}'}
    # A displaced surface bound already proves failure of the absolute 0.02 mm
    # model-dimension rule. Avoid expensive whole-path work when every reference
    # has such a mismatch (particularly independently randomized fuzzy skin).
    import numpy as np
    envelope_failures = []
    for r in R:
        failure = None
        for layer in sorted(set(C) | set(r)):
            for f in SURFACE:
                a = C.get(layer, {}).get(f); b = r.get(layer, {}).get(f)
                if a is not None and b is not None and len(a[0]) and len(b[0]):
                    delta = float(np.max(np.abs(np.r_[a[0].min(axis=0) - b[0].min(axis=0), a[0].max(axis=0) - b[0].max(axis=0)])))
                    if delta > .02:
                        failure = {'reason': 'Surface bounds differ by more than 0.02 mm', 'bounds_delta_mm': round(delta, 6),
                                   'features': [f], 'layers': [layer, layer]}
                        break
            if failure: break
        envelope_failures.append(failure)
    if all(envelope_failures):
        return 'red', min(envelope_failures, key=lambda f: f['bounds_delta_mm'])
    # The official build's own variation, per feature: the largest distance between any two official runs.
    tol = {}
    volume_tolerance = {}
    ref_amounts = [amounts(r) for r in R]
    for i in range(len(R)):
        for j in range(i + 1, len(R)):
            for (layer, f), d in diffs(R[i], R[j]).items():
                tol[(layer, f)] = max(tol.get((layer, f), 0.0), d)
            for key in ref_amounts[i].keys() | ref_amounts[j].keys():
                volume_tolerance[key] = max(volume_tolerance.get(key, 0), abs(ref_amounts[i].get(key, 0) - ref_amounts[j].get(key, 0)))
    choices = []
    configured_gap = seam_gap(cand)
    for r, heights in zip(R, rz):
        if len(cz) != len(heights) or any(abs(a - b) > .001 for a, b in zip(cz, heights)):
            choices.append(('red', {}, {}, r, True, {}))
            continue
        observed = diffs(C, r)
        seams = seam_differences(observed, C, r, configured_gap)
        graded_observed = {k: seams[k]['completed_contour_mm'] if k in seams else v for k, v in observed.items()}
        unbounded = {k: d for k, d in observed.items() if math.isinf(tol.get(k, 0.0))}
        unbounded = {k: v for k, v in unbounded.items() if k not in seams}
        dd = {k: d for k, d in observed.items() if k not in unbounded and d > tol.get(k, 0.0) + 0.01}
        # A wide or unbounded official distribution must not excuse a large change
        # in the model relative to every individual reference output.
        graded_dd = {k: graded_observed[k] for k in dd}
        hard_grade = geometry_grade(graded_observed, C, r, {})
        status = 'red' if hard_grade == 'red' else geometry_grade(graded_dd, C, r, volume_tolerance)
        if hard_grade == 'red':
            dd = observed
        if status == 'variant' and hard_grade == 'blue':
            status = 'blue'
        if seams and status in ('variant', 'blue', 'yellow'):
            status = 'yellow'
        if unbounded and status != 'red':
            status = 'unverified'
        choices.append((status, dd, unbounded, r, False, seams))
    order = {'variant': 0, 'blue': 1, 'yellow': 2, 'unverified': 3, 'red': 4}
    status, best, unbounded, best_ref, z_mismatch, seams = min(choices, key=lambda x: (order[x[0]], len(x[1])))
    ca, ra = amounts(C), amounts(best_ref)
    changed_volume = {k for k in ca.keys() | ra.keys()
                      if abs(ca.get(k, 0) - ra.get(k, 0)) > max(0.002, volume_tolerance.get(k, 0) + 0.002)}
    changed = set(best) | changed_volume
    detail = {"max_mm": round(max(best.values(), default=0), 3), "differing": len(best),
              "features": sorted({f for _, f in changed}), "layers": [min(l for l, _ in changed), max(l for l, _ in changed)] if changed else [],
              "extrusion_differences": len(changed_volume)}
    if status == 'unverified': detail['reason'] = 'Official runs have unbounded variation for a differing layer and feature'
    if status == 'variant': detail['within_official_variation'] = True
    if z_mismatch: detail['reason'] = 'Layer Z positions differ by more than 0.001 mm or layer counts differ'
    if seams: detail['seam_differences'] = [{'layer': l, 'feature': f, **value} for (l, f), value in sorted(seams.items())]
    return status, detail


def run(args):
    import threading
    cols = columns()
    if getattr(args, 'columns', None):
        selected = set(args.columns.split(','))
        unknown = selected - {label for label, _, _ in cols}
        if unknown: raise ValueError(f'Unknown columns: {sorted(unknown)}')
        cols = [c for c in cols if c[0] in selected]
    if args.cols:
        cols = cols[: args.cols]
    rows = args.only.split(",") if args.only else ROWS
    ref, dev = runners.Reference(), runners.Device(ROOT / "build" / "aarch64" / "package", args.device)
    runners.verify_resources(ref, dev)
    description = dev.describe()
    device_info = {"phone_model": description["model"], "phone_abi": description["abi"], "phone_sdk": description["sdk"],
                   "phone_cpu": dev.fastest_cpu()}
    reference_image = ref.describe()["image_id"]
    if not reference_image:
        raise RuntimeError("Cannot identify the official reference image")
    ref_key = hashlib.sha256(reference_image.encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    results_file = OUT / "results.json"
    results = json.loads(results_file.read_text()) if results_file.exists() else {}
    lock = threading.Lock()
    todo = [(row, label, kw) for row in rows for (label, _, kw) in cols]
    todo = [t for t in todo if not current_result(results.get(f"{t[0]}|{t[1]}"), t, dev.ident, reference_image)
            or results[f"{t[0]}|{t[1]}"].get("reference_runs", 0) < args.ref_runs
            or any(results[f"{t[0]}|{t[1]}"].get(k) != v for k, v in device_info.items())]

    def reference(c, inputs, argv, k):
        d = OUT / "cells" / c["id"] / f"ref-{ref_key}-{k}"
        if not (d / "run.json").exists():
            runners.set_cpu(2 + k * 2)
            r = ref.run(inputs, argv, d)
            (d / "run.json").write_text(json.dumps(outcome(d, r.returncode, inputs, c)))
        else:
            cached = json.loads((d / "run.json").read_text())
            (d / "run.json").write_text(json.dumps(outcome(d, cached.get("returncode", -1), inputs, c)))
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
            (cd / "run.json").write_text(json.dumps(outcome(cd, r.returncode, inputs, c) | {"seconds": round(r.seconds, 1)}))
        status, detail = classify(refs, cd)
        with lock:
            results[f"{row}|{label}"] = {"row": row, "column": label, "case": c["id"], "status": status, "detail": detail,
                                         "printer": c["printer"], "process": c["process"], "filament": c["filaments"],
                                         "overrides": c["process_overrides"], "engine": dev.ident["engine_sha256"],
                                         "resources": dev.ident["resources_sha256"], "reference_image": reference_image,
                                         "input_format": cases.INPUT_FORMAT, "classification_version": CLASSIFICATION_VERSION,
                                         "validation_sha256": validation_hash(), "reference_runs": args.ref_runs,
                                         **device_info,
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
    reference_image = ref.describe()["image_id"]
    if not reference_image:
        raise RuntimeError("Cannot identify the official reference image")
    ref_key = hashlib.sha256(reference_image.encode()).hexdigest()[:16]
    ident = runners.package_identity(ROOT / "build" / "aarch64" / "package")
    runners.verify_resources(ref, runners.Engine(ROOT / "build" / "aarch64" / "package", "aarch64"))
    options = {(row, label): (row, label, kw) for row in ROWS for label, _, kw in columns()}
    for key, r in results.items():
        item = options.get((r.get("row"), r.get("column")))
        if item is None or not current_result(r, item, ident, reference_image):
            continue
        if r["status"] in ("green", "refused"):
            continue
        base = OUT / "cells" / r["case"]
        inputs = base / "inputs"
        case = json.loads((inputs / "case.json").read_text())
        argv = cases.materialise(case, base / "inputs-recheck")
        inputs = base / "inputs-recheck"
        def one(k):
            d = base / f"ref-{ref_key}-{k}"
            if not (d / "run.json").exists():
                runners.set_cpu(2 + (k % 10) * 2)
                rr = ref.run(inputs, argv, d)
                (d / "run.json").write_text(json.dumps(outcome(d, rr.returncode, inputs, case)))
            else:
                cached = json.loads((d / 'run.json').read_text())
                (d / 'run.json').write_text(json.dumps(cached | outcome(d, cached.get('returncode', -1), inputs, case)))
            return d
        with cf.ThreadPoolExecutor(10) as ex:
            refs = list(ex.map(one, range(args.ref_runs)))
        status, detail = classify(refs, base / "phone")
        print(f"{r['status']:7} -> {status:7} {key} {json.dumps(detail)[:150]}", flush=True)
        r["status"], r["detail"] = status, detail | {"official_runs": args.ref_runs}
        r['reference_runs'] = args.ref_runs
        (OUT / "results.json").write_text(json.dumps(results, indent=1, default=str))


COLOURS = {"green": "#2FB344", "variant": "#166534", "blue": "#A5D6A7", "refused": "#2FB344", "yellow": "#F2C94C", "red": "#E5484D", "unverified": "#C9CDD3", "grey": "#C9CDD3"}


def validation_hash():
    return VALIDATION_SHA256


def current_inputs(result, item, ident, reference_image):
    if (not result or result.get("input_format") != cases.INPUT_FORMAT
            or not all(result.get(k) for k in ("phone_model", "phone_abi", "phone_sdk"))
            or result.get("phone_cpu") is None):
        return False
    row, _label, kw = item
    return (result.get("case") == cell_case(row, kw)["id"] and result.get("engine") == ident.get("engine_sha256")
            and result.get("resources") == ident.get("resources_sha256") and result.get("reference_image") == reference_image)


def current_result(result, item, ident, reference_image):
    return (current_inputs(result, item, ident, reference_image)
            and result.get('classification_version') == CLASSIFICATION_VERSION
            and result.get('validation_sha256') == validation_hash())


def _reclassify_saved_cell(payload):
    key, r, ref_key, output_root = payload
    base = Path(output_root) / 'cells' / r['case']
    inputs = base / 'inputs'
    case = json.loads((inputs / 'case.json').read_text())
    if cases.case_id(case) != r['case']: raise ValueError(f'{key}: cached input identity differs')
    dirs = [base / f'ref-{ref_key}-{k}' for k in range(r['reference_runs'])]
    for d in [*dirs, base / 'phone']:
        cached = json.loads((d / 'run.json').read_text())
        checked = outcome(d, cached.get('returncode', -1), inputs, case)
        (d / 'run.json').write_text(json.dumps(cached | checked))
    status, detail = classify(dirs, base / 'phone')
    return key, r | {'status': status, 'detail': detail, 'classification_version': CLASSIFICATION_VERSION,
                     'validation_sha256': validation_hash()}


def reclassify(args):
    """Revalidate recorded inputs and outputs, then apply the current comparator without slicing."""
    ref = runners.Reference()
    image = ref.describe()['image_id']
    if not image: raise RuntimeError('Cannot identify official reference image')
    ref_key = hashlib.sha256(image.encode()).hexdigest()[:16]
    ident = runners.package_identity(ROOT / 'build/aarch64/package')
    options = {(row, label): (row, label, kw) for row in ROWS for label, _, kw in columns()}
    result_file = OUT / 'results.json'
    results = json.loads(result_file.read_text())
    wanted_rows = set(args.only.split(',')) if args.only else set(ROWS)
    wanted_columns = set(args.columns.split(',')) if args.columns else {c[0] for c in columns()}
    pending = [(key, r, ref_key, str(OUT)) for key, r in results.items()
               if r.get('row') in wanted_rows and r.get('column') in wanted_columns
               and (item := options.get((r.get('row'), r.get('column'))))
               and current_inputs(r, item, ident, image) and not current_result(r, item, ident, image)]

    print(f'Reclassifying {len(pending)} cached cells', flush=True)
    workers = getattr(args, 'jobs', 2)
    if workers < 1: raise ValueError('jobs must be positive')
    with cf.ProcessPoolExecutor(workers) as ex:
        for key, r in ex.map(_reclassify_saved_cell, pending):
            results[key] = r
            temp = result_file.with_suffix('.tmp')
            temp.write_text(json.dumps(results, indent=1, default=str))
            temp.replace(result_file)
            print(f"{r['status']:7} {key}", flush=True)


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
            display = {"variant": "dark green: within observed variation", "blue": "light green: support differences"}.get(st, st)
            tip = f"{row} / {label}: {display}" + (f" ({json.dumps(r['detail'])[:160]})" if r else " (not run)")
            out.append(f'<rect x="{left + j * cw + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="2" fill="{COLOURS[st]}">'
                       f'<title>{html.escape(tip)}</title></rect>')
    out.append("</svg>")
    return "\n".join(out)


def report(_):
    results = json.loads((OUT / "results.json").read_text()) if (OUT / "results.json").exists() else {}
    pkg = runners.package_identity(ROOT / "build" / "aarch64" / "package")
    image = subprocess.run(["sudo", "-n", "docker", "image", "inspect", "-f", "{{.Id}}", runners.REFERENCE_IMAGE], capture_output=True, text=True).stdout.strip()
    if not image:
        raise RuntimeError("Cannot identify the official reference image")
    options = {(row, label): (row, label, kw) for row in ROWS for label, _, kw in columns()}
    results = {key: result for key, result in results.items()
               if (item := options.get((result.get("row"), result.get("column")))) is not None
               and current_result(result, item, pkg, image)}
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "matrix.svg").write_text(svg(results))
    cols = columns()
    total = len(cols) * len(ROWS)
    counts = {k: sum(1 for r in results.values() if r["status"] == k) for k in ("green", "variant", "blue", "refused", "yellow", "red")}
    counts["grey"] = total - sum(counts.values())
    phones = sorted({f"{r['phone_model']} (Android SDK {r['phone_sdk']}, {r['phone_abi']}, CPU {r['phone_cpu']})" for r in results.values()})
    lines = [
        "# Equivalence report", "",
        "Does Pandy Studio's phone slicer write the same G-code as the official Bambu Studio? Each cell below is one",
        "plate sliced on a phone and by the official Bambu Studio, compared as described in",
        "[equivalence/README.md](../../equivalence/README.md). Regenerate with `equivalence/matrix.py run` and `report`.", "",
        f"*Generated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.*", "",
        "| | |", "|---|---|",
        f"| 🟩 **Byte-identical** | the phone's G-code is byte-identical to an observed official output |",
        f"| **Dark green — Within observed variation** | bytes differ; continuous paths are within the observed official variation |",
        f"| **Light green — Support differences** | support paths or extrusion differ; model paths and extrusion stay within observed variation |",
        f"| 🟨 **Small model differences** | bounded internal or surface changes with similar material and outline |",
        f"| 🟥 **Significant difference or failed safety check** | model differences exceed the bounds, a safety check fails, or slicing outcomes differ |",
        f"| 🟩 **Matching refusal** | both returned the same nonzero CLI error without slicing; expected rejection passes |",
        f"| ⬜ **Not verified** | not run or insufficient reference evidence |", "",
        f"**{counts['green']} byte-identical · {counts['variant']} within observed variation · {counts['blue']} support differences · {counts['yellow']} small model differences · {counts['red']} significant differences or failed checks · {counts['refused']} both refused · {counts['grey']} not verified** "
        f"(of {total}: {len(ROWS)} models × {len(cols)} configurations)", "",
        "![Equivalence matrix](matrix.svg)", "",
        "Hover a cell (open the SVG) for its details. Columns change one thing from the baseline: X1 Carbon, 0.4 mm nozzle,",
        "0.20mm Standard @BBL X1C, Bambu PLA Basic; printer columns use that printer's own default process and PLA.", "",
        "## What was compared", "",
        "| | |", "|---|---|",
        "| Official build | Bambu Studio 02.08.02.61 Linux AppImage (SHA-256 pinned in Pandy Slicer's Dockerfile), x86-64, "
        f"Docker image `{image[:19]}` |",
        f"| Phone engine | `pandy-engine` arm64, SHA-256 `{pkg['engine_sha256']}` |",
        f"| Profiles | the retained CLI resource subset of the official release, tree SHA-256 `{pkg['resources_sha256']}` ({pkg['resources_files']} files) |",
        "| Compiler | GCC 13.3.0 (Ubuntu 24.04), both builds |",
        "| C library | glibc 2.39 (Ubuntu 24.04), static on the phone |",
        "| Maths functions | arm64 glibc, except `hypot`, `cbrt`, `pow`, `tanf`, `asinf`, `acosf`, `atanf`, `atan2f`: glibc 2.39's "
        "source compiled as x86-64 compiles it ([engine/x86-libm](../../engine/x86-libm/README.md)); bit-identical to x86-64 on 2M inputs each |",
        f"| Phone | {', '.join(phones) if phones else 'Not yet tested'} |",
        "| Runs | Each recorded cell has one phone run and the number of official runs recorded in its result; all are pinned to one CPU. |", "",
        "Models are generated (`equivalence/pandy_equiv/models.py`): cube 20 mm, cylinder, tube (hole), sphere, torus, gear,",
        "bridge (32 mm span), overhangs (45°/60°/75°), thin walls (0.4–2 mm), tower 80 mm; Benchy uses the verified model bundled with the reference.", "",
        "A separate [Xperia Benchy cross-check](xperia-benchy.md) covers 39 configurations on a second phone; solid rectilinear was tested on OnePlus only.", "",
        "Fuzzy skin is excluded: its intentionally random surface texture is outside this matrix's equivalence comparison.", "",
        "The [difference investigation](difference-investigation.md) records the seam, curve, tower and fuzzy-skin diagnostics.", "",
    ]
    others = sorted((r for r in results.values() if r["status"] in ("blue", "yellow", "red")), key=lambda r: (r["status"], r["row"], r["column"]))
    if others:
        lines += ["## Cells that are not green", "",
                  "| | Model | Configuration | Largest difference | Features | Layers |", "|---|---|---|---|---|---|"]
        icon = {"blue": "Light green", "yellow": "🟨", "red": "🟥"}
        for r in others:
            d = r["detail"]
            lines.append(f"| {icon[r['status']]} | {r['row']} | {r['column']} | {d.get('max_mm', '–')} mm | {', '.join(d.get('features', [])) or json.dumps(d)[:80]} | "
                         f"{'–'.join(map(str, d.get('layers', []))) or '–'} |")
        lines.append("")
    lines += ["## Interpretation", "",
              "Geometric similarity is not byte equality. Unrun cells and results from older input formats or different engine, profile, or reference image identities are not counted.",
              "A matching refusal is recorded separately from a successful slice. A successful slice must also pass effective-settings checks.",
              "Reported distances compare continuous per-layer extrusion paths with a 0.0005 mm numerical error bound; they are not measurements of printed-part dimensional error.",
              "The safety check covers the start sequence and heater limits; it does not prove the absence of collisions or other hazards.", ""]
    (DOCS / "README.md").write_text("\n".join(lines))
    print(f"{DOCS / 'README.md'}: {counts}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["run", "report", "recheck", "reclassify"])
    ap.add_argument("--device")
    ap.add_argument("--ref-runs", type=int, default=5)
    ap.add_argument("--only")
    ap.add_argument("--cols", type=int)
    ap.add_argument('--columns', help='comma-separated exact column labels')
    ap.add_argument('--jobs', type=int, default=2, help='cached geometry reclassification workers')
    a = ap.parse_args()
    if a.command == "recheck" and a.ref_runs == 5:
        a.ref_runs = 20
    {"run": run, "report": report, "recheck": recheck, "reclassify": reclassify}[a.command](a)

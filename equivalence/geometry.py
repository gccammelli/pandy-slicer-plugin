#!/usr/bin/env python3
"""How far apart are two sliced plates, geometrically?

Byte-identical G-code is the goal, but Bambu Studio's own output varies from run to run, so this measures the size of
a difference: per layer and per feature (supports, walls, infill, ...), the extrusion paths are sampled every 0.1 mm
and compared with nearest-point distances (Hausdorff = the largest; also the 99.9th percentile), and extruded
filament per layer is compared. A candidate is "within Bambu Studio's own variation" when its distances to the
official outputs are no larger than the official outputs' distances to each other.

Usage: geometry.py <run dir from distribution.py>   (needs numpy and scipy)"""
import json
import math
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

STEP = 0.1  # mm between sample points
GROUPS = {"support": ("Support", "Support interface", "Support transition", "Support material", "Support material interface"),
          "walls": ("Outer wall", "Inner wall", "Overhang wall"),
          "infill": ("Sparse infill", "Internal solid infill", "Top surface", "Bottom surface", "Bridge", "Internal Bridge", "Gap infill", "Ironing")}


def group_of(feature):
    for g, names in GROUPS.items():
        if feature in names:
            return g
    return "other"


def parse(path):
    """layer index -> group -> (sample points Nx2, extruded mm of filament)."""
    text = zipfile.ZipFile(path).read("Metadata/plate_1.gcode").decode(errors="replace")
    layers = defaultdict(lambda: defaultdict(lambda: [[], 0.0]))
    layer, feature, x, y, rel_e, abs_xy = -1, "", 0.0, 0.0, True, True
    for line in text.split("\n"):
        if line.startswith(";"):
            if line.startswith("; CHANGE_LAYER"):
                layer += 1
            elif line.startswith("; FEATURE:"):
                feature = line[10:].strip()
            continue
        code = line.split(";", 1)[0].split()
        if not code:
            continue
        c = code[0]
        if c == "M83": rel_e = True
        elif c == "M82": rel_e = False
        elif c in ("G0", "G1", "G2", "G3"):
            args = {w[0]: float(w[1:]) for w in code[1:] if len(w) > 1 and w[0] in "XYZEIJ" and re.fullmatch(r"-?[0-9.]+", w[1:])}
            nx, ny = args.get("X", x), args.get("Y", y)
            e = args.get("E", 0.0)
            if layer >= 0 and e > 0 and rel_e and c != "G0":
                slot = layers[layer][group_of(feature)]
                slot[1] += e
                if c in ("G2", "G3") and ("I" in args or "J" in args):
                    cx, cy = x + args.get("I", 0.0), y + args.get("J", 0.0)
                    r = math.hypot(x - cx, y - cy)
                    a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
                    if c == "G2" and a1 >= a0: a1 -= 2 * math.pi
                    if c == "G3" and a1 <= a0: a1 += 2 * math.pi
                    n = max(1, int(abs(a1 - a0) * r / STEP))
                    slot[0] += [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
                else:
                    n = max(1, int(math.hypot(nx - x, ny - y) / STEP))
                    slot[0] += [(x + (nx - x) * k / n, y + (ny - y) * k / n) for k in range(n + 1)]
            x, y = nx, ny
    return {l: {g: (np.array(p) if p else np.zeros((0, 2)), e) for g, (p, e) in gs.items()} for l, gs in layers.items()}


def distance(a, b):
    """Per group: Hausdorff, 99.9th percentile of nearest-point distances (both directions), filament difference."""
    out = {}
    for g in set(GROUPS) | {"other"}:
        dmax, dists, ea, eb = 0.0, [], 0.0, 0.0
        for layer in set(a) | set(b):
            pa = a.get(layer, {}).get(g, (np.zeros((0, 2)), 0.0)); pb = b.get(layer, {}).get(g, (np.zeros((0, 2)), 0.0))
            ea += pa[1]; eb += pb[1]
            if len(pa[0]) == 0 and len(pb[0]) == 0: continue
            if len(pa[0]) == 0 or len(pb[0]) == 0: dmax = math.inf; continue
            d1, _ = cKDTree(pb[0]).query(pa[0]); d2, _ = cKDTree(pa[0]).query(pb[0])
            dmax = max(dmax, d1.max(), d2.max()); dists.append(d1); dists.append(d2)
        if ea == 0 and eb == 0: continue
        alld = np.concatenate(dists) if dists else np.zeros(1)
        out[g] = {"hausdorff_mm": round(float(dmax), 3), "p999_mm": round(float(np.percentile(alld, 99.9)), 3),
                  "filament_diff_pct": round(100 * abs(ea - eb) / max(ea, eb), 4)}
    return out


def main():
    run = Path(sys.argv[1])
    refs = sorted(p for p in run.iterdir() if p.name.startswith("ref") and (p / "out.gcode.3mf").exists())
    cands = sorted(p for p in run.iterdir() if p.name.startswith("cand") and (p / "out.gcode.3mf").exists())
    R = [parse(p / "out.gcode.3mf") for p in refs]
    C = [parse(p / "out.gcode.3mf") for p in cands]
    worst = lambda rows, key: {g: max(r[g][key] for r in rows if g in r) for g in {g for r in rows for g in r}}
    # Official vs official: every pair among the first 8 runs.
    base = [distance(R[i], R[j]) for i in range(min(8, len(R))) for j in range(i + 1, min(8, len(R)))]
    # Phone vs official: each phone run against its closest official run (smallest support Hausdorff, then walls).
    phone = []
    for c in C[:8]:
        ds = [distance(c, r) for r in R[:8]]
        phone.append(min(ds, key=lambda d: (d.get("support", {}).get("hausdorff_mm", 0), d.get("walls", {}).get("hausdorff_mm", 0))))
    report = {"official_vs_official_worst": {k: worst(base, k) for k in ("hausdorff_mm", "p999_mm", "filament_diff_pct")},
              "phone_vs_closest_official_worst": {k: worst(phone, k) for k in ("hausdorff_mm", "p999_mm", "filament_diff_pct")},
              "pairs": {"official": len(base), "phone": len(phone)}}
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

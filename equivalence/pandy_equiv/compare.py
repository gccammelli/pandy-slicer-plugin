"""Compares a candidate's sliced file with the reference's.

The verdict rests on the G-code: every Metadata/plate_N.gcode must be byte-identical (and so its .md5), and both
outputs must have the same set of plates. Nothing in the G-code is normalised: Bambu Studio writes no timestamp or
path into it. The rest of the 3MF (model, settings, slice info) is compared too and reported, with exactly one
normalisation, listed in NORMALISED: values that hold the time of the run."""
import hashlib
import io
import re
import zipfile
from pathlib import Path

GCODE = re.compile(r"Metadata/plate_\d+\.gcode$")
# Per file, the patterns whose matches are replaced before comparing. Each one is a value Bambu Studio fills with the
# current date or time; nothing else is ever normalised.
NORMALISED = {
    "3D/3dmodel.model": [r'<metadata name="(CreationDate|ModificationDate)">[^<]*</metadata>'],
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def normalise(name: str, data: bytes) -> bytes:
    for pattern in NORMALISED.get(name, []):
        data = re.sub(pattern.encode(), b"<normalised/>", data)
    return data


def first_difference(a: bytes, b: bytes) -> dict:
    la, lb = a.split(b"\n"), b.split(b"\n")
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y:
            return {"line": i + 1, "reference": x[:300].decode(errors="replace"), "candidate": y[:300].decode(errors="replace")}
    return {"line": min(len(la), len(lb)) + 1, "reference_lines": len(la), "candidate_lines": len(lb)}


def compare(reference: Path, candidate: Path) -> dict:
    ref, cand = read(reference), read(candidate)
    plates = sorted(n for n in ref if GCODE.search(n))
    result = {"plates": len(plates), "gcode": {}, "other": {}, "gcode_identical": True, "other_identical": True}
    if plates != sorted(n for n in cand if GCODE.search(n)):
        result["gcode_identical"] = False
        result["plate_sets"] = {"reference": plates, "candidate": sorted(n for n in cand if GCODE.search(n))}
    for n in plates:
        r, c = ref[n], cand.get(n, b"")
        same = r == c
        result["gcode"][n] = {"reference_sha256": sha(r), "candidate_sha256": sha(c), "bytes": len(r), "identical": same}
        if not same:
            result["gcode_identical"] = False
            result["gcode"][n]["first_difference"] = first_difference(r, c)
    for n in sorted(set(ref) | set(cand)):
        if GCODE.search(n):
            continue
        r, c = normalise(n, ref.get(n, b"")), normalise(n, cand.get(n, b""))
        if n not in ref or n not in cand or r != c:
            result["other_identical"] = False
            result["other"][n] = {"in_reference": n in ref, "in_candidate": n in cand,
                                  **({"first_difference": first_difference(r, c)} if n in ref and n in cand else {})}
    return result

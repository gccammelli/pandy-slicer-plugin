"""Test cases. A case is a plate of generated models, a printer, a process and filaments (Bambu's system presets),
plus setting overrides applied the way a user's edited preset applies them: a user preset that inherits the system
one. materialise() turns a case into input files and the exact command line given to every runner.

Suites:
  smoke   every printer model, its default process and Bambu PLA Basic, on a mixed plate; plus multi-colour,
          multi-object and multi-plate projects.
  sweep   every process and filament option in schema.json, one at a time, at each of its interesting values
          (both booleans, every enum choice, min, max, and values around the default), on the feature plate.
  random  seeded random combinations of many overrides at once; any seed can be re-run exactly.
Invalid values are kept on purpose: the engine must then fail exactly like the reference does."""
import hashlib
import json
import random
from pathlib import Path

from . import models

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE.parent / "schema.json").read_text())
PROFILES = HERE.parent / "profiles.json"   # written by `run.py profiles` from the reference's resources

PRINTERS = {k: tuple(v) for k, v in json.loads(PROFILES.read_text())["printers"].items()} if PROFILES.exists() else {}


def plate(*names, centre=(128.0, 128.0), spacing=40.0):
    """Objects in a row centred on the bed."""
    n = len(names)
    return [{"model": m, "x": centre[0] + (i - (n - 1) / 2) * spacing, "y": centre[1]} for i, m in enumerate(names)]


FEATURE_PLATE = plate("overhangs", "bridge", "tube", "thin", spacing=45.0)


def case_id(case: dict) -> str:
    body = json.dumps({k: v for k, v in case.items() if k not in ("id", "note")}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def make(printer="X1 Carbon", objects=None, overrides=None, filament_overrides=None, filaments=None, process=None, note="", args=None):
    p, default_process, pla = PRINTERS[printer]
    c = {"printer": p, "process": process or default_process, "filaments": filaments or [pla],
         "objects": objects or FEATURE_PLATE, "process_overrides": overrides or {},
         "filament_overrides": filament_overrides or {}, "args": args or [], "note": note}
    c["id"] = case_id(c)
    return c


def smoke():
    cases = [make(k, note=f"{k}: default process, PLA, feature plate") for k in PRINTERS]
    cases += [
        make("X1 Carbon", plate("cube", "cylinder", "sphere", "torus", "gear", spacing=36), note="five objects"),
        make("X1 Carbon", plate("tower"), note="tall thin tower (cooling, minimum layer time)"),
        make("X1 Carbon", plate("sphere"), overrides={"enable_support": "1", "support_type": "tree(auto)"}, note="tree supports"),
        make("X1 Carbon", plate("overhangs"), overrides={"enable_support": "1", "support_type": "normal(auto)"}, note="normal supports"),
        make("X1 Carbon", plate("cube", "cylinder"), filaments=["Bambu PLA Basic @BBL X1C", "Bambu PETG HF @BBL X1C"],
             note="two filaments (prime tower)"),
        make("A1", plate("cube"), overrides={"spiral_mode": "1", "wall_loops": "1", "top_shell_layers": "0", "sparse_infill_density": "0%"}, note="vase mode"),
        make("X1 Carbon", plate("cube", "cube", "cube"), overrides={"print_sequence": "by object"}, note="sequential printing"),
        make("X1 Carbon", plate("sphere"), overrides={"ironing_type": "top"}, note="ironing"),
        make("X1 Carbon", plate("torus"), overrides={"fuzzy_skin": "all"}, note="fuzzy skin (random: seeded?)"),
        make("X1 Carbon", plate("cylinder"), overrides={"wall_generator": "arachne"}, note="Arachne walls"),
        make("X1 Carbon", plate("cylinder"), overrides={"wall_generator": "classic"}, note="classic walls"),
        make("H2D", plate("cube", "cylinder"), filaments=[PRINTERS["H2D"][2]] * 2, note="H2D two nozzles"),
    ]
    return cases


def _values(key: str, default):
    """Interesting values of [key] given its schema and its default in the case's process or filament preset."""
    s = SCHEMA.get(key)
    if not s or s.get("readonly"):
        return []
    t = s["type"]
    vector = t.endswith("s") and t not in ("coPercents",) or t in ("coPercents",)
    scalar = default[0] if isinstance(default, list) and default else default
    out = []
    if t in ("coBool", "coBools"):
        out = ["0" if str(scalar) in ("1", "true") else "1"]
    elif t in ("coEnum", "coEnums"):
        out = [v for v in s.get("enum", []) if v != scalar]
    elif t in ("coInt", "coInts", "coFloat", "coFloats", "coPercent", "coPercents", "coFloatOrPercent", "coFloatsOrPercents"):
        pct = str(scalar).endswith("%")
        try:
            d = float(str(scalar).rstrip("%"))
        except ValueError:
            return []
        cands = {d * 0.5, d * 1.5, d + 1}
        if "min" in s:
            cands.add(s["min"])
        if "max" in s and s["max"] < 1e5:
            cands.add(s["max"])
        cands.discard(d)
        isint = t.startswith("coInt")
        for v in sorted(cands):
            v = int(round(v)) if isint else round(v, 4)
            out.append(f"{v}%" if pct else str(v))
        out = list(dict.fromkeys(out))
    if vector:
        n = len(default) if isinstance(default, list) and default else 1
        return [[v] * n for v in out]
    return out


def sweep(printer="X1 Carbon"):
    prof = json.loads(PROFILES.read_text())
    p, proc, fil = PRINTERS[printer]
    cases = []
    for key, default in sorted(prof["process"][proc].items()):
        for v in _values(key, default):
            cases.append(make(printer, overrides={key: v}, note=f"process {key}={v}"))
    for key, default in sorted(prof["filament"][fil].items()):
        for v in _values(key, default):
            cases.append(make(printer, filament_overrides={key: v}, note=f"filament {key}={v}"))
    return cases


def random_cases(seed: int, count: int, printer=None, per_case=12):
    prof = json.loads(PROFILES.read_text())
    rng = random.Random(seed)
    cases = []
    for i in range(count):
        pk = printer or rng.choice(sorted(PRINTERS))
        p, proc, fil = PRINTERS[pk]
        choices = []
        for key, default in sorted(prof["process"][proc].items()):
            choices += [("p", key, v) for v in _values(key, default)]
        for key, default in sorted(prof["filament"][fil].items()):
            choices += [("f", key, v) for v in _values(key, default)]
        picked = {}
        for kind, key, v in rng.sample(choices, min(per_case, len(choices))):
            picked.setdefault((kind, key), v)
        objs = plate(*rng.sample(sorted(models.MODELS), rng.randint(1, 3)), spacing=45.0)
        cases.append(make(pk, objects=objs, overrides={k: v for (kind, k), v in picked.items() if kind == "p"},
                          filament_overrides={k: v for (kind, k), v in picked.items() if kind == "f"},
                          note=f"random seed {seed} #{i}"))
    return cases


def materialise(case: dict, d: Path) -> list:
    """Writes the case's input files into [d] and returns the slicer arguments (relative to [d])."""
    d.mkdir(parents=True, exist_ok=True)
    objs = []
    for i, o in enumerate(case["objects"]):
        mesh = models.MODELS[o["model"]]()
        objs.append((f"{o['model']}_{i + 1}", mesh, models.centred(mesh, o["x"], o["y"])))
    models.write_3mf(d / "model.3mf", objs)
    machine = {"type": "machine", "name": "case printer", "from": "User", "inherits": case["printer"],
               "printer_settings_id": "case printer"}
    process = {"type": "process", "name": "case process", "from": "User", "inherits": case["process"],
               "print_settings_id": "case process", "compatible_printers": [case["printer"]], **case["process_overrides"]}
    (d / "machine.json").write_text(json.dumps(machine, indent=1))
    (d / "process.json").write_text(json.dumps(process, indent=1))
    fil_files = []
    for i, f in enumerate(case["filaments"], start=1):
        name = f"case filament {i}"
        fil = {"type": "filament", "name": name, "from": "User", "inherits": f, "filament_settings_id": [name],
               "compatible_printers": [case["printer"]], **case["filament_overrides"]}
        (d / f"filament{i}.json").write_text(json.dumps(fil, indent=1))
        fil_files.append(f"filament{i}.json")
    (d / "case.json").write_text(json.dumps(case, indent=1, sort_keys=True))
    return ["--load-settings", "machine.json;process.json", "--load-filaments", ";".join(fil_files),
            *case["args"], "--slice", "0", "--export-3mf", "out.gcode.3mf", "model.3mf"]

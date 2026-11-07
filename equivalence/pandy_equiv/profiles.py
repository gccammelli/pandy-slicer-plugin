"""Resolves Bambu's system presets (resources/profiles/BBL) the way their "inherits" chains read: parent first, then
each child's keys on top. Used only to know each option's default for the sweeps (cases.py); the slicer itself
always resolves presets on its own, from the same files."""
import json
from pathlib import Path

META = {"name", "inherits", "from", "instantiation", "setting_id", "type", "version", "compatible_printers",
        "compatible_printers_condition", "compatible_prints", "compatible_prints_condition", "filament_id",
        "description", "include", "renamed_from"}


class Presets:
    def __init__(self, resources: Path):
        self.by_name = {}
        for kind in ("machine", "process", "filament"):
            for f in (Path(resources) / "profiles" / "BBL" / kind).rglob("*.json"):
                try:
                    d = json.loads(f.read_text())
                except ValueError:
                    continue
                if isinstance(d, dict) and "name" in d:
                    self.by_name[d["name"]] = d

    def includes(self, name: str) -> dict:
        """The keys a machine preset gets from its "include" templates (start/end/filament-change/layer-change
        G-code), through its inheritance chain. Bambu Studio's CLI does not merge them into a user preset that
        inherits the system one, so a job's printer preset carries them itself (as Pandy Slicer's server does)."""
        d = self.by_name[name]
        out = self.includes(d["inherits"]) if d.get("inherits") else {}
        for inc in d.get("include", []):
            out.update({k: v for k, v in self.resolve(inc).items()})
        return out

    def resolve(self, name: str) -> dict:
        d = self.by_name[name]
        out = self.resolve(d["inherits"]) if d.get("inherits") else {}
        for inc in d.get("include", []):
            out.update({k: v for k, v in self.resolve(inc).items()})
        out.update({k: v for k, v in d.items() if k not in META})
        return out


def printers(p: Presets) -> dict:
    """Every instantiable Bambu Lab printer preset with a 0.4 mm nozzle -> (preset, its default process, its default
    filament, preferring Bambu PLA Basic), as Bambu Studio picks them when the printer is selected."""
    out = {}
    for name, d in sorted(p.by_name.items()):
        if d.get("type") != "machine" or d.get("instantiation") != "true" or not name.endswith(" 0.4 nozzle"):
            continue
        r = p.resolve(name)
        fil = r.get("default_filament_profile") or []
        fil = fil if isinstance(fil, list) else [fil]
        model = name.removeprefix("Bambu Lab ").removesuffix(" 0.4 nozzle")
        out[model] = (name, r.get("default_print_profile"), next((f for f in fil if f.startswith("Bambu PLA Basic")), fil[0] if fil else None))
    return out


def write(resources: Path, out: Path):
    p = Presets(resources)
    data = {"printers": printers(p), "process": {}, "filament": {}, "machine_includes": {}}
    for printer, process, filament in data["printers"].values():
        data["process"][process] = p.resolve(process)
        data["filament"][filament] = p.resolve(filament)
        data["machine_includes"][printer] = p.includes(printer)
    out.write_text(json.dumps(data, indent=1, sort_keys=True))

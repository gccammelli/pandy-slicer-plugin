"""Resolves Bambu's system presets (resources/profiles/BBL) the way their "inherits" chains read: parent first, then
each child's keys on top. These resolved values provide both sweep defaults and complete slicer inputs."""
import json
from pathlib import Path

# Match PresetLibrary: preserve actual setting values, including filament_id and compatibility metadata.
META = {"name", "inherits", "from", "instantiation", "setting_id", "type", "include", "renamed_from"}


class Presets:
    def __init__(self, resources: Path):
        self.by_name = {}
        root = Path(resources) / "profiles"
        index = json.loads((root / "BBL.json").read_text())
        for kind in ("machine_list", "process_list", "filament_list"):
            for item in index[kind]:
                name, path = item["name"], item["sub_path"]
                if name in self.by_name:
                    raise ValueError(f"Duplicate preset: {name}")
                target = (root / "BBL" / path).resolve()
                if not target.is_relative_to((root / "BBL").resolve()):
                    raise ValueError(f"Invalid preset path: {path}")
                d = json.loads(target.read_text())
                if d.get("name") != name:
                    raise ValueError(f"Preset name mismatch: {name}")
                self.by_name[name] = d

    def includes(self, name: str, _visiting=None) -> dict:
        """The keys a machine preset gets from its "include" templates (start/end/filament-change/layer-change
        G-code), through its inheritance chain. Bambu Studio's CLI does not merge them into a user preset that
        inherits the system one, so a job's printer preset carries them itself (as Pandy Slicer's server does)."""
        visiting = set() if _visiting is None else _visiting
        if name in visiting:
            raise ValueError(f"Cyclic preset inheritance: {name}")
        visiting.add(name)
        try:
            d = self.by_name[name]
            out = self.includes(d["inherits"], visiting) if d.get("inherits") else {}
            for inc in d.get("include", []):
                out.update(self.resolve(inc))
            return out
        finally:
            visiting.remove(name)

    def resolve(self, name: str, _visiting=None) -> dict:
        visiting = set() if _visiting is None else _visiting
        if name in visiting:
            raise ValueError(f"Cyclic preset inheritance: {name}")
        visiting.add(name)
        d = self.by_name[name]
        try:
            out = self.resolve(d["inherits"], visiting) if d.get("inherits") else {}
            for inc in d.get("include", []):
                out.update(self.resolve(inc, visiting))
            out.update({k: v for k, v in d.items() if k not in META})
            return out
        finally:
            visiting.remove(name)


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

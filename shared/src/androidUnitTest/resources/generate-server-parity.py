"""Regenerate synthetic expected values from Pandy Slicer 1.5.1 (d7bab2c).

Runs read-only against the other repository; its temporary profile files stay outside both projects.
"""
import io
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

SOURCE = Path.home() / "projects/pandy-slicer"
source = subprocess.check_output(["git", "show", "d7bab2c:pandy_slicer/server.py"], cwd=SOURCE, text=True)
module = {"__name__": "pandy_server_reference"}
exec(compile(source, "pandy_slicer/server.py", "exec"), module)

def pack(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return result.getvalue()

def unpack(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name).decode() for name in archive.namelist()}

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for folder in ("machine", "process", "filament"):
        (root / folder).mkdir()
    for path, value in {
        "machine/Demo Printer.json": {"name": "Demo Printer", "default_print_profile": "0.20mm Standard @Demo", "include": ["Demo template"]},
        "machine/Demo template.json": {"name": "Demo template", "machine_start_gcode": "G28\nG29"},
        "process/0.20mm Standard @Demo.json": {},
        "filament/Bambu PLA Basic @Demo.json": {"name": "PLA", "filament_colour": ["#FFFFFF"]},
        "filament/Generic PETG @Demo.json": {"name": "PETG", "filament_colour": ["#00FF00"]},
    }.items():
        (root / path).write_text(json.dumps(value))
    module["BBL"] = str(root)
    module["PROFILES"] = str(root / "machine")
    bare = pack({"3D/3dmodel.model": "<model/>"})
    source = module["as_project"](bare, "textured_plate")
    source = module["set_bed_type"](source, 1, "textured_plate")
    healed = module["heal"](source)
    args, _ = module["conversion"](source, "Demo Printer", "PLA", "#123456")
    machine_file, process_file = args[1].split(";")
    result = {
        "project": json.loads(unpack(healed)["Metadata/project_settings.config"]),
        "machine": json.loads(Path(machine_file).read_text()),
        "process": json.loads(Path(process_file).read_text()),
        "filament": json.loads(Path(args[3]).read_text()),
        "arguments": ["--load-settings", "machine.json;process.json", "--load-filaments", "filament.json", "--wall-loops=3", "--arrange", "1", "--slice", "1", "--export-3mf", "sliced.gcode.3mf", "--uptodate", "model.3mf"],
    }
    cfg = {"printer_settings_id": "Old Printer", "print_settings_id": "0.20mm Standard @Old", "filament_settings_id": ["Bambu PLA Basic @Old", "Generic PETG @Old"], "different_settings_to_system": ["wall_loops"], "wall_loops": "4"}
    xml = '<config><plate><metadata key="plater_id" value="1"/></plate><plate><metadata key="plater_id" value="2"/></plate></config>'
    project = pack({"3D/3dmodel.model": "<model/>", "Metadata/project_settings.config": json.dumps(cfg), "Metadata/model_settings.config": xml})
    prepared = module["set_bed_type"](project, 2, "textured_plate")
    healed_project = module["heal"](prepared)
    args, _ = module["conversion"](prepared, "Demo Printer")
    machine_file, process_file = args[1].split(";")
    contents = unpack(healed_project)
    result["project_conversion"] = {
        "project": json.loads(contents["Metadata/project_settings.config"]),
        "model_settings": contents["Metadata/model_settings.config"],
        "machine": json.loads(Path(machine_file).read_text()),
        "process": json.loads(Path(process_file).read_text()),
        "filaments": [Path(path).name for path in args[3].split(";")],
    }
    Path(__file__).with_name("server-parity.json").write_text(json.dumps(result, indent=2) + "\n")

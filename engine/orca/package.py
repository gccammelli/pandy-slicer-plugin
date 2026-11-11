#!/usr/bin/env python3
"""Package Orca independently; never modify the Bambu package or build artifacts."""
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'equivalence'))
from pandy_equiv.schema import parse
from pandy_equiv.layout import build

subprocess.run([sys.executable, str(ROOT / 'engine/orca/checkout.py')], check=True)
subprocess.run([sys.executable, str(ROOT / 'engine/orca/reference.py')], check=True)
subprocess.run([sys.executable, str(ROOT / 'engine/orca/headers.py')], check=True)
source = ROOT / 'third_party/orcaslicer'
exe = ROOT / 'build/orca/aarch64/engine/pandy-engine'
header = exe.read_bytes()[:64]
if header[:5] != b'\x7fELF\x02' or header[18:20] != b'\xb7\x00':
    raise SystemExit('Orca engine is not an ARM64 ELF executable.')
program_headers = subprocess.check_output(['readelf', '-l', str(exe)], text=True)
if 'INTERP' in program_headers:
    raise SystemExit('Orca Android engine must be statically linked.')
package = ROOT / 'build/orca/aarch64/package'
out = ROOT / 'build/android-orca'
for folder in (package, out):
    if folder.exists():
        shutil.rmtree(folder)
(package / 'bin').mkdir(parents=True)
shutil.copy2(exe, package / 'bin/pandy-engine')
resources = ROOT / 'build/orca/reference/squashfs-root/resources'
# Match the existing Bambu headless resource selection. Orca's full vendor
# catalog remains available to its CLI; the current editor offers BBL printers.
shutil.copytree(resources, package / 'resources', ignore=lambda directory, names: set(names) & {'web', 'hms', 'images', 'model', 'tooltip', 'i18n', 'shaders'} if Path(directory) == resources else set())
metadata = package / 'pandy'
metadata.mkdir()
# The release prunes JSON presets after generating .opc caches. Keep the source
# JSON for the editor in a separate tree so it cannot change CLI cache loading.
editor = metadata / 'editor/profiles'
editor.mkdir(parents=True)
index = json.loads((source / 'resources/profiles/BBL.json').read_text())
shutil.copy2(source / 'resources/profiles/BBL.json', editor / 'BBL.json')
for group in ('machine_list', 'process_list', 'filament_list'):
    for preset in index[group]:
        relative = Path('BBL') / preset['sub_path']
        target = editor / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / 'resources/profiles' / relative, target)
(metadata / 'schema.json').write_text(json.dumps(parse((source / 'src/libslic3r/PrintConfig.cpp').read_text()), sort_keys=True, indent=1))
tab = (source / 'src/slic3r/GUI/Tab.cpp').read_text()
(metadata / 'layout.json').write_text(json.dumps({'process': build(tab, 'TabPrint'), 'filament': build(tab, 'TabFilament')}, indent=1))
shutil.copy2(source / 'LICENSE.txt', metadata / 'LICENSE-OrcaSlicer.txt')
shutil.copy2(ROOT / 'build/orca/headers/NOTICE-wxInspector.md', metadata / 'NOTICE-wxInspector.md')
shutil.copy2(ROOT / 'build/orca/aarch64/deps/dep_wxWidgets-prefix/src/dep_wxWidgets/docs/licence.txt', metadata / 'LICENSE-wxWidgets.txt')
shutil.copy2(ROOT / 'engine/orca/source.json', metadata / 'source.json')
(out / 'jniLibs/arm64-v8a').mkdir(parents=True)
shutil.copy2(exe, out / 'jniLibs/arm64-v8a/libpandy_orca.so')
(out / 'assets').mkdir()
archive = out / 'assets/orca-resources.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for base in ('resources', 'pandy'):
        for path in sorted((package / base).rglob('*')):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(package).as_posix(), (1980, 1, 2, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
(out / 'assets/orca-resources.sha256').write_text(hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() + '\n')
print(out)

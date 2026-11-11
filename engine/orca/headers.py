#!/usr/bin/env python3
"""Fetch the exact upstream widget-inspector declarations, without its GUI implementation."""
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
archive = root / 'build/orca/downloads/wxInspector-v1.0.0.zip'
archive.parent.mkdir(parents=True, exist_ok=True)
data = archive.read_bytes() if archive.exists() else urllib.request.urlopen('https://github.com/Noisyfox/wxInspector/archive/refs/tags/v1.0.0.zip').read()
if hashlib.sha256(data).hexdigest() != '0ba163956f2d468b19a91b96c5aba66ee9610843ea41dda628ea44cdafde7db7':
    raise SystemExit('wxInspector header archive checksum mismatch.')
if not archive.exists():
    archive.write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:
    notice = root / 'build/orca/headers/NOTICE-wxInspector.md'
    notice.parent.mkdir(parents=True, exist_ok=True)
    notice.write_bytes(z.read('wxInspector-1.0.0/README.md'))
    prefix = 'wxInspector-1.0.0/include/'
    for name in z.namelist():
        if name.startswith(prefix) and not name.endswith('/'):
            relative = Path(name[len(prefix):])
            assert not relative.is_absolute() and '..' not in relative.parts
            target = root / 'build/orca/headers/include' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            contents = z.read(name)
            if not target.exists() or target.read_bytes() != contents:
                target.write_bytes(contents)
print('Verified wxInspector 1.0.0 headers')

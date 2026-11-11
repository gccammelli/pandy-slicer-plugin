#!/usr/bin/env python3
"""Download the official reference and verify GitHub's release asset digest."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
lock = json.loads((Path(__file__).parent / 'source.json').read_text())['reference']
folder = ROOT / 'build/orca/reference'
folder.mkdir(parents=True, exist_ok=True)
archive = folder / 'OrcaSlicer.AppImage'
if not archive.exists():
    partial = archive.with_suffix('.partial')
    subprocess.run(['curl', '-fL', '--retry', '2', '-o', str(partial), lock['url']], check=True)
    partial.rename(archive)
if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != lock['sha256']:
    raise SystemExit('Official Orca reference checksum mismatch.')
archive.chmod(0o755)
subprocess.run([str(archive), '--appimage-extract'], cwd=folder, stdout=subprocess.DEVNULL, check=True)
print(folder / 'squashfs-root')

#!/usr/bin/env python3
"""Fetch and verify the pinned Orca source without changing an existing checkout."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
lock = json.loads((Path(__file__).parent / 'source.json').read_text())
source = ROOT / 'third_party/orcaslicer'
if not source.exists():
    subprocess.run(['git', 'clone', '--depth', '1', '--branch', lock['tag'], lock['repository'], str(source)], check=True)
actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
if actual != lock['commit']:
    raise SystemExit(f'Orca checkout is {actual}; expected {lock["commit"]}. Refusing to change it.')
if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip():
    raise SystemExit('Orca checkout has changes; refusing to build an unverified source tree.')
subprocess.run(['git', '-C', str(source), 'submodule', 'update', '--init', '--recursive', '--depth', '1'], check=True)
print(f'OrcaSlicer {lock["tag"]}: {actual}')

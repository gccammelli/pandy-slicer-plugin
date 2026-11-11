#!/usr/bin/env python3
"""Adapt LLD diagnostics for the shared, reviewed GUI trap generator."""
import re
import subprocess
import sys
from pathlib import Path

log = Path(sys.argv[1])
out = Path(sys.argv[2])
text = log.read_text(errors='replace')
lines = [text]
for kind, name in re.findall(r'ld\.lld(?:-18)?: error: (undefined|duplicate) symbol: ([A-Za-z0-9_]+)(?:\r?\n|$)', text):
    diagnostic = 'undefined reference to' if kind == 'undefined' else 'multiple definition of'
    lines.append(f"{diagnostic} `{name}'")
normalized = log.with_name('gnu-link.log')
normalized.write_text('\n'.join(lines))
subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'tools/gen_traps.py'), str(normalized), str(out)], check=True)

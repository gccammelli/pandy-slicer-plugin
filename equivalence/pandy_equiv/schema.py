"""Every slicing option Bambu Studio defines, read from upstream's PrintConfig.cpp (the PrintConfigDef, where each
option is declared with `def = this->add("key", coType)` followed by its limits and choices). Writes schema.json:
key -> {type, min, max, enum, mode}. The sweeps in cases.py derive their values from it, so "every setting" means
every option in this list, and the list itself is reviewable."""
import json
import re
import sys
from pathlib import Path

ADD = re.compile(r'def\s*=\s*this->add(?:_nullable)?\(\s*"([A-Za-z0-9_]+)"\s*,\s*(co[A-Za-z]+)\s*\)')


def parse(src: str) -> dict:
    out = {}
    marks = list(ADD.finditer(src))
    for i, m in enumerate(marks):
        body = src[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(src)]
        # Stop at the end of the function holding the definitions.
        body = body.split("\n}\n", 1)[0]
        key, typ = m.group(1), m.group(2)
        e = {"type": typ}
        for name in ("min", "max"):
            mm = re.search(rf"def->{name}\s*=\s*([-0-9.eE+]+)\s*;", body)
            if mm:
                e[name] = float(mm.group(1))
        enum = re.findall(r'def->enum_values\.push_back\(\s*"([^"]*)"\s*\)', body)
        if enum:
            e["enum"] = enum
            labels = re.findall(r'def->enum_labels\.push_back\(\s*(?:_?L\(\s*)?"([^"]*)"', body)
            if len(labels) == len(enum):
                e["enum_labels"] = labels
        for name in ("label", "full_label", "category", "tooltip", "sidetext"):
            mm = re.search(rf'def->{name}\s*=\s*(?:_?L\(\s*)?"((?:[^"\\]|\\.)*)"', body)
            if mm:
                e[name] = mm.group(1).encode().decode("unicode_escape")
        mode = re.search(r"def->mode\s*=\s*(com[A-Za-z]+)", body)
        if mode:
            e["mode"] = mode.group(1)
        if re.search(r"def->readonly\s*=\s*true", body):
            e["readonly"] = True
        out.setdefault(key, e)
    return out


if __name__ == "__main__":
    src = Path(sys.argv[1]).read_text()
    schema = parse(src)
    Path(sys.argv[2]).write_text(json.dumps(schema, indent=1, sort_keys=True))
    print(f"{len(schema)} options -> {sys.argv[2]}")

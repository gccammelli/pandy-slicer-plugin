"""Bambu Studio's own settings layout: the pages, groups and option order of its process and filament tabs, read
from upstream's Tab.cpp (TabPrint::build, TabFilament::build). The app shows settings in this same arrangement.
Writes layout.json: {"process": [{"page", "groups": [{"title", "options": [...]}]}], "filament": [...]}"""
import json
import re
import sys
from pathlib import Path

TOKEN = re.compile(r'add_options_page\(\s*_?L\("([^"]+)"\)|new_optgroup\(\s*_?L\("([^"]+)"\)'
                   r'|append_single_option_line\(\s*"([A-Za-z0-9_]+)(?:#\d+)?"|get_option\(\s*"([A-Za-z0-9_]+)(?:#\d+)?"')


def build(src: str, func: str) -> list:
    start = src.index(f"void {func}::build()")
    end = src.index("\nvoid ", start + 10)
    pages = []
    for m in TOKEN.finditer(src, start, end):
        page, group, opt, opt2 = m.groups()
        if page:
            pages.append({"page": page, "groups": []})
        elif group and pages:
            pages[-1]["groups"].append({"title": group, "options": []})
        elif (opt or opt2) and pages and pages[-1]["groups"]:
            o = pages[-1]["groups"][-1]["options"]
            k = opt or opt2
            if k not in o:
                o.append(k)
    return [p for p in pages if any(g["options"] for g in p["groups"])]


if __name__ == "__main__":
    src = Path(sys.argv[1]).read_text()
    out = {"process": build(src, "TabPrint"), "filament": build(src, "TabFilament")}
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
    for k, v in out.items():
        print(k, [(p["page"], len(p["groups"]), sum(len(g["options"]) for g in p["groups"])) for p in v])

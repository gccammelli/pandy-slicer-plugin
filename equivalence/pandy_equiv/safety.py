"""The plugin's bounded start-sequence and heater checks for sliced G-code.

This is not a collision, motion, or comprehensive printer-safety analysis.
It applies the Kotlin Safety object's limits and catches compact heater commands and wait targets too.
"""
import re
import zipfile

COMMAND = re.compile(r'^([A-Za-z][0-9]+)(?=\s|[A-Za-z]|$)')
TEMPERATURE = re.compile(r'(?<![A-Za-z])([SR])(-?[0-9]+(?:\.[0-9]+)?)', re.I)
LIMITS = {'M104': 350, 'M109': 350, 'M140': 120, 'M190': 120, 'M141': 65, 'M191': 65}
PLATE = re.compile(r'Metadata/plate_\d+\.gcode$')


def problems(path):
    errors = []
    with zipfile.ZipFile(path) as z:
        plates = [n for n in z.namelist() if PLATE.fullmatch(n)]
        if not plates:
            return ['No G-code plates']
        for name in plates:
            text = z.read(name).decode(errors='replace')
            if '; CHANGE_LAYER' not in text:
                errors.append(f'{name}: missing first-layer marker')
            head = text.split('; CHANGE_LAYER', 1)[0]
            commands = [m.group(1).upper() for line in head.splitlines()
                        if (m := COMMAND.match(line.split(';', 1)[0].strip()))]
            if 'G28' not in commands or 'G29' not in commands or commands.index('G28') > commands.index('G29'):
                errors.append(f'{name}: missing or incorrectly ordered homing and levelling commands')
            for line in text.splitlines():
                code = line.split(';', 1)[0].strip()
                m = COMMAND.match(code)
                if not m or m.group(1).upper() not in LIMITS:
                    continue
                cmd = m.group(1).upper()
                values = TEMPERATURE.findall(code[m.end():])
                for param, number in values:
                    if param.upper() == 'R' and cmd not in ('M109', 'M190', 'M191'):
                        continue
                    if float(number) > LIMITS[cmd]:
                        errors.append(f'{name}: {cmd} {param.upper()}{number} exceeds {LIMITS[cmd]} C')
    return sorted(set(errors))

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'gen_traps.py'


class LldTrapTest(unittest.TestCase):
    def test_missing_gui_symbols_trap_and_real_definitions_replace_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            log, out = Path(tmp) / 'link.log', Path(tmp) / 'traps.c'
            log.write_text('ld.lld: error: undefined symbol: glfwInit\n'
                           '>>> referenced by GUI.cpp\n'
                           'ld.lld: error: undefined symbol: _ZTVN6Slic3r3GUI6PlaterE\n')
            subprocess.run([sys.executable, str(SCRIPT), str(log), str(out)], check=True, capture_output=True)
            text = out.read_text()
            self.assertIn('void glfwInit(void) { pandy_trap(', text)
            self.assertIn('char _ZTVN6Slic3r3GUI6PlaterE[4096]', text)
            log.write_text('ld.lld: error: duplicate symbol: glfwInit\n'
                           'ld.lld: error: undefined symbol: glfwTerminate\n')
            subprocess.run([sys.executable, str(SCRIPT), str(log), str(out)], check=True, capture_output=True)
            text = out.read_text()
            self.assertNotIn('void glfwInit(', text)
            self.assertIn('void glfwTerminate(void) { pandy_trap(', text)
            self.assertIn('char _ZTVN6Slic3r3GUI6PlaterE[4096]', text)


if __name__ == '__main__':
    unittest.main()

"""Offline checks for the historical-replay comparison tools (no simulator, no PDK)."""
from pathlib import Path
import importlib.util
import re
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / 'projects/ldo-130nm/scripts/historical_replay'
PSF = '''HEADER
"PSFversion" "1.00"
"simulator" "%s"
TYPE
VALUE
"vout" %s
"out_i" %s
"status" "ok"
END
'''


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, TOOLS / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PsfCompare(unittest.TestCase):
    def setUp(self):
        self.psfcmp = load('psfcmp', 'replay/psfcmp.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, side, simulator, vout, current):
        folder = self.root / side
        folder.mkdir()
        (folder / 'dcOp.dc').write_text(PSF % (simulator, vout, current), encoding='utf-8')
        return folder

    def test_header_ignored_and_identical_values(self):
        old = self.write('old', 'spectre 18.1', '1.2', '0')
        new = self.write('new', 'spectre 23.1', '1.2', '0')
        rep = self.psfcmp.compare_dirs(old, new)
        self.assertEqual(rep['max_d'], 0.0)
        self.assertEqual(rep['d_hist']['0'], 2)
        self.assertEqual(rep['string_diffs'], 0)

    def test_scaled_difference(self):
        old = self.write('old', 'a', '1.2', '1e-3')
        new = self.write('new', 'b', '1.2000012', '1e-3')
        rep = self.psfcmp.compare_dirs(old, new)
        self.assertAlmostEqual(rep['max_d'], 1.2e-6 / (1.2000012 + 1.2000012e-9), places=12)
        self.assertEqual(rep['worst']['key'], 'vout')

    def test_missing_file_reported(self):
        old = self.write('old', 'a', '1', '1')
        new = self.root / 'new'
        new.mkdir()
        rep = self.psfcmp.compare_dirs(old, new)
        self.assertEqual(rep['files_missing'], ['dcOp.dc'])


class DeIdentified(unittest.TestCase):
    def test_no_account_paths_or_site_installs(self):
        bad = re.compile(r'/home/|/opt/coe|@[a-z0-9.-]+\.(?:com|edu)', re.I)
        for path in sorted(TOOLS.rglob('*')):
            if path.is_file():
                text = path.read_text(encoding='utf-8')
                self.assertIsNone(bad.search(text), path.relative_to(REPO).as_posix())

    def test_all_python_compiles(self):
        for path in sorted(TOOLS.rglob('*.py')):
            compile(path.read_text(encoding='utf-8'), str(path), 'exec')


if __name__ == '__main__':
    unittest.main()

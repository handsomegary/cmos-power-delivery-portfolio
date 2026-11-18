"""Exercise offline verification from a download directory without Git metadata."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class DownloadVerification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='portfolio download ')
        self.addCleanup(self.temp.cleanup)
        self.outside = Path(self.temp.name)
        self.repo = self.outside / 'downloaded repository'
        (self.repo / 'tools').mkdir(parents=True)
        (self.repo / 'docs').mkdir()
        for name in ('verify_repository.py', 'verify_release.py'):
            shutil.copyfile(REPO / 'tools' / name, self.repo / 'tools' / name)
        (self.repo / 'README.md').write_text('[Design](docs/design.md)\n', encoding='utf-8')
        (self.repo / 'docs/design.md').write_text('[Home](../README.md)\n', encoding='utf-8')
        self.refresh()

    def refresh(self):
        entries = []
        for path in sorted(self.repo.rglob('*')):
            if path.is_file() and path.name != 'release_manifest.json':
                data = path.read_bytes()
                entries.append({'path': path.relative_to(self.repo).as_posix(),
                                'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        self.manifest = {'files': entries, 'file_count': len(entries),
                         'total_bytes': sum(item['bytes'] for item in entries)}
        self.save_manifest()

    def save_manifest(self):
        (self.repo / 'release_manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def run_verifier(self, script='verify_repository.py'):
        return subprocess.run([sys.executable, '-B', str(self.repo / 'tools' / script)],
                              cwd=self.outside, text=True, capture_output=True, timeout=30)

    def test_both_entry_points_work_without_git_and_outside_cwd(self):
        for script in ('verify_repository.py', 'verify_release.py'):
            with self.subTest(script=script):
                result = self.run_verifier(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('2 local documentation links', result.stdout)

    def test_modified_published_bytes_fail(self):
        (self.repo / 'docs/design.md').write_text('changed\n', encoding='utf-8')
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('File differs from release: docs/design.md', result.stderr)

    def test_duplicate_manifest_path_fails(self):
        self.manifest['files'].append(dict(self.manifest['files'][0]))
        self.save_manifest()
        self.assertIn('Duplicate', self.run_verifier().stderr)

    def test_parent_path_fails(self):
        self.manifest['files'][0]['path'] = '../outside.txt'
        self.save_manifest()
        self.assertIn('Invalid manifest path', self.run_verifier().stderr)

    def test_unlisted_source_file_fails(self):
        (self.repo / 'docs/unlisted.md').write_text('unexpected\n', encoding='utf-8')
        self.assertIn('Unlisted release file', self.run_verifier().stderr)

    def test_broken_link_fails_even_when_hashes_match(self):
        (self.repo / 'README.md').write_text('[Missing](docs/missing.md)\n', encoding='utf-8')
        self.refresh()
        self.assertIn('Missing link target', self.run_verifier().stderr)

    def test_generated_output_does_not_invalidate_download(self):
        (self.repo / 'reproduced').mkdir()
        (self.repo / 'reproduced/summary.json').write_text('{}\n', encoding='utf-8')
        result = self.run_verifier()
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

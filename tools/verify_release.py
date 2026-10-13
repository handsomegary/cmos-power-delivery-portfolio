"""Check that the published release files match their recorded SHA256 values."""
from pathlib import Path
import hashlib
import json
import sys


def main():
    repo = Path(__file__).resolve().parents[1]
    manifest = json.loads((repo / 'release_manifest.json').read_text(encoding='utf-8'))
    failures = []
    for entry in manifest['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            failures.append('Invalid manifest path')
            continue
        path = repo / relative
        if not path.is_file() or path.is_symlink():
            failures.append(f'Missing release file: {relative.as_posix()}')
            continue
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            failures.append(f'File differs from release: {relative.as_posix()}')
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        return 1
    print(f'Verified {len(manifest["files"])} release files.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

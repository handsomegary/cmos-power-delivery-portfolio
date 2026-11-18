"""Verify release bytes, inventory and local documentation links without Git."""
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import fnmatch
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET


MANIFEST = 'release_manifest.json'
# Local working material is outside the published release inventory.
LOCAL_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', 'reproduced', 'runs',
    'private', 'local', 'raw', 'raw_results', 'psf', '.ssh',
}
LOCAL_FILES = (
    '*.pyc', '*.pyo', '.DS_Store', 'Thumbs.db', 'technology.local.json',
    'models.local.*', '*.log', '*.log.*', '.env', '.env.*',
)
LINK = re.compile(r'!?\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\)')


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        return False
    path = PurePosixPath(value)
    return (not path.is_absolute() and '..' not in path.parts
            and path.as_posix() == value and value != '.' and '\x00' not in value)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def release_inventory(repo):
    """Return non-generated files and any unsafe symlink encountered."""
    files, errors = set(), []
    for folder, directories, filenames in os.walk(repo, followlinks=False):
        base = Path(folder)
        kept = []
        for name in directories:
            path = base / name
            if name in LOCAL_DIRS:
                continue
            if path.is_symlink():
                errors.append(f'Symlink in release: {path.relative_to(repo).as_posix()}')
            else:
                kept.append(name)
        directories[:] = kept
        for name in filenames:
            path = base / name
            relative = path.relative_to(repo).as_posix()
            if relative == MANIFEST or any(fnmatch.fnmatchcase(name, p) for p in LOCAL_FILES):
                continue
            if path.is_symlink():
                errors.append(f'Symlink in release: {relative}')
            files.add(relative)
    return files, errors


def check_links(repo, relative, published):
    """Check inline Markdown destinations; heading fragments are not validated."""
    path = repo / relative
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'^\s*(`{3,}|~{3,}).*?^\s*\1\s*$', '', text,
                  flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'`[^`\n]*`', '', text)
    errors, count = [], 0
    for match in LINK.finditer(text):
        target = match.group(1) or match.group(2)
        try:
            parsed = urlsplit(target)
        except ValueError:
            errors.append(f'Invalid link in {relative}: {target}')
            continue
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        count += 1
        destination = (path.parent / unquote(parsed.path)).resolve()
        if not destination.is_relative_to(repo):
            errors.append(f'Link outside repository in {relative}: {target}')
        elif not destination.exists():
            errors.append(f'Missing link target in {relative}: {target}')
        elif destination.is_file() and destination.relative_to(repo).as_posix() not in published:
            errors.append(f'Link target is outside release inventory in {relative}: {target}')
    return errors, count


def verify(repo):
    repo = Path(repo).resolve()
    errors, entries, link_count = [], [], 0
    try:
        manifest = json.loads((repo / MANIFEST).read_text(encoding='utf-8'))
        entries = manifest['files']
        if not isinstance(entries, list):
            raise ValueError('files must be a list')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f'Cannot read release manifest: {exc}'], 0, 0

    seen, names, readable, total_bytes = set(), set(), set(), 0
    for entry in entries:
        if not isinstance(entry, dict) or not safe_relative(entry.get('path')):
            errors.append('Invalid manifest path')
            continue
        relative = entry['path']
        if relative == MANIFEST or relative.casefold() in seen:
            errors.append(f'Duplicate or self-referential manifest path: {relative}')
            continue
        seen.add(relative.casefold())
        names.add(relative)
        size, digest = entry.get('bytes'), entry.get('sha256')
        if (type(size) is not int or size < 0 or not isinstance(digest, str)
                or not re.fullmatch('[0-9a-f]{64}', digest)):
            errors.append(f'Invalid size or SHA-256: {relative}')
            continue
        total_bytes += size
        path = repo / relative
        if (not path.is_file() or path.is_symlink()
                or any(parent.is_symlink() for parent in path.parents if parent != repo)
                or not path.resolve().is_relative_to(repo)):
            errors.append(f'Missing or unsafe release file: {relative}')
            continue
        readable.add(relative)
        try:
            if path.stat().st_size != size or file_hash(path) != digest:
                errors.append(f'File differs from release: {relative}')
        except OSError as exc:
            errors.append(f'Cannot read {relative}: {exc}')

    if manifest.get('file_count') != len(entries):
        errors.append('Manifest file_count does not match its entries')
    if manifest.get('total_bytes') != total_bytes:
        errors.append('Manifest total_bytes does not match its entries')
    actual, inventory_errors = release_inventory(repo)
    errors.extend(inventory_errors)
    for relative in sorted(actual - names):
        errors.append(f'Unlisted release file: {relative}')
    for relative in sorted(readable):
        if relative.lower().endswith('.md'):
            try:
                link_errors, count = check_links(repo, relative, names | {MANIFEST})
                errors.extend(link_errors)
                link_count += count
            except (OSError, UnicodeError) as exc:
                errors.append(f'Cannot read Markdown {relative}: {exc}')
    drawing_manifest = repo / 'report/figures/drawing_manifest.json'
    if drawing_manifest.is_file():
        try:
            drawing = json.loads(drawing_manifest.read_text(encoding='utf-8'))
            for relative, field in (
                    ('report/circuit-style.tex', 'style_sha256'),
                    ('report/build_circuits.py', 'builder_sha256'),
                    ('report/circuit-atlas.tex', 'atlas_source_sha256'),
                    ('report/circuit-atlas.pdf', 'atlas_pdf_sha256')):
                if file_hash(repo / relative) != drawing[field]:
                    errors.append(f'Drawing build is stale: {relative}')
            for figure in drawing['figures']:
                name = figure['name']
                if not re.fullmatch('[a-z0-9-]+', name):
                    raise ValueError('Unsafe figure name')
                for extension, field in (('tex', 'source_sha256'), ('pdf', 'pdf_sha256'),
                                         ('svg', 'svg_sha256'), ('png', 'png_sha256')):
                    path = repo / 'report/figures' / (name+'.'+extension)
                    if file_hash(path) != figure[field]:
                        errors.append(f'Drawing source/export mismatch: {name}.{extension}')
                root = ET.parse(repo / 'report/figures' / (name+'.svg')).getroot()
                background = root[0]
                view = root.attrib.get('viewBox', '').split()
                if (not background.tag.endswith('}rect') or background.get('fill') != '#ffffff'
                        or [background.get(k) for k in ('x','y','width','height')] != view):
                    errors.append(f'SVG has no full white background: {name}')
        except (OSError, ValueError, KeyError, TypeError, IndexError, ET.ParseError) as exc:
            errors.append(f'Cannot validate drawing exports: {exc}')
    return errors, len(entries), link_count


def main():
    errors, file_count, link_count = verify(Path(__file__).resolve().parents[1])
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Verified {file_count} release files and {link_count} local documentation links.')
    print('Offline integrity and navigation checks only; no simulator was launched.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

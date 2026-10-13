"""Reproduce published numerical analysis without launching any simulator."""
from pathlib import Path
import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, default=Path('reproduced'))
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    destination = args.outdir.resolve()
    protected = [repo / name for name in ('projects', 'docs', 'tools')]
    if destination == repo or any(destination == p or p in destination.parents for p in protected):
        parser.error('Choose a fresh output directory instead of a source directory.')
    if destination.exists() and any(destination.iterdir()):
        parser.error('The output directory must be empty or new.')
    commands = [
        ('ldo-130nm', repo / 'projects' / 'ldo-130nm' / 'scripts' / 'reproduce.py'),
        ('two-phase-buck', repo / 'projects' / 'two-phase-buck' / 'scripts' / 'reproduce.py'),
    ]
    for name, script in commands:
        if not script.is_file():
            raise SystemExit(f'Missing analysis entry point: {script.relative_to(repo)}')
        cmd = [sys.executable, '-B', str(script), '--outdir', str(destination / name)]
        if args.no_plots:
            cmd.append('--no-plots')
        print(f'Reproducing {name}', flush=True)
        subprocess.run(cmd, cwd=repo, check=True)
    print(f'Analysis complete: {destination}', flush=True)


if __name__ == '__main__':
    main()

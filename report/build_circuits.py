"""Compile the shared American CircuitikZ sources to PDF, white SVG and PNG."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'report'
FIGURES = (
    ('ldo-architecture', 'LDO regulation architecture', 'Historical r6. The reference and output capacitor are ideal testbench elements. Compensation is shown functionally; the next figure preserves its complete connections.'),
    ('ldo-core', 'LDO transistor-level implementation', 'Historical r6, all nine MOS instances. Matching net labels denote electrical connections. Junction dots indicate connection; unmarked crossings do not. Dimensions use micrometers; m is parallel multiplicity and nf is finger count.'),
    ('buck-architecture', 'Two-phase Buck and remote-load assist', 'Historical r8/r9. Transistor-level power, driver and detector blocks operate with behavioral PI/PWM control and ideal current sensing. External passives and the PDN are parameterized test conditions.'),
    ('buck-power', 'Buck power bridges and source/sink assist', 'Parallel-bank labels enumerate the implemented devices. r9 retains MOS geometry and adds the stated assist gate resistances. All dimensions and connections remain available in the device and hardware inventories.'),
    ('buck-driver', 'Two-stage gate drivers', 'The template is instantiated six times with the mapped signal names and device dimensions. Named instances remain distinct; the two stages preserve command polarity.'),
    ('buck-detector', 'Low/high voltage-window detectors', 'The shared template represents the two ten-MOS detector circuits. Matching labels are connected. Detector thresholds and reference sources are explicit bench conditions.'),
)
PREAMBLE = r'''\documentclass[border=2mm]{standalone}
\usepackage[T1]{fontenc}
\usepackage{helvet}
\usepackage{mathptmx}
\usepackage[american]{circuitikz}
\usetikzlibrary{arrows.meta,calc,positioning,fit,backgrounds}
\input{circuit-style.tex}
\begin{document}
'''


def run(command, cwd, logfile):
    result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    logfile.write_bytes(result.stdout)
    if result.returncode:
        raise SystemExit(f'Command failed ({result.returncode}); see {logfile}')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def white_svg(path):
    # Poppler emits outlined vector glyphs. Put a white page below every object.
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    tree = ET.parse(path)
    root = tree.getroot()
    view = root.attrib.get('viewBox', '').split()
    if len(view) != 4:
        raise ValueError('SVG has no valid viewBox')
    background = ET.Element('{http://www.w3.org/2000/svg}rect', {
        'x': view[0], 'y': view[1], 'width': view[2], 'height': view[3],
        'fill': '#ffffff', 'id': 'page-background'})
    root.insert(0, background)
    tree.write(path, encoding='utf-8', xml_declaration=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdflatex', default='pdflatex')
    p.add_argument('--pdftocairo', default='pdftocairo')
    p.add_argument('--build-dir', type=Path, default=ROOT/'reproduced/circuitikz-build')
    p.add_argument('--only', choices=[x[0] for x in FIGURES])
    args = p.parse_args()
    build = args.build_dir.resolve()
    if build == ROOT or any(build == ROOT / n or ROOT / n in build.parents
                           for n in ('projects', 'report', 'tools', 'docs', 'tests', '.git')):
        p.error('Use a generated-output directory for build intermediates.')
    build.mkdir(parents=True, exist_ok=True)
    output = REPORT/'figures'
    records = []
    for name, _, _ in FIGURES:
        if args.only and name != args.only:
            continue
        source = output/(name+'.tex')
        wrapper = build/(name+'.tex')
        wrapper.write_text(PREAMBLE + '\\input{figures/'+name+'.tex}\n\\end{document}\n', encoding='utf-8')
        run([args.pdflatex, '-no-shell-escape', '-interaction=nonstopmode',
             '-halt-on-error', '-output-directory='+str(build), str(wrapper)],
            REPORT, build/(name+'.compile.log'))
        pdf = output/(name+'.pdf')
        shutil.copyfile(build/(name+'.pdf'), pdf)
        svg = output/(name+'.svg')
        run([args.pdftocairo, '-svg', str(pdf), str(svg)], REPORT, build/(name+'.svg.log'))
        white_svg(svg)
        run([args.pdftocairo, '-png', '-singlefile', '-r', '180', str(pdf), str(output/name)],
            REPORT, build/(name+'.png.log'))
        records.append({'name': name, 'source_sha256': sha(source),
                        'pdf_sha256': sha(pdf), 'svg_sha256': sha(svg),
                        'png_sha256': sha(output/(name+'.png'))})
        print('Rendered '+name, flush=True)
    if not args.only:
        for pass_number in (1, 2):
            run([args.pdflatex, '-no-shell-escape', '-interaction=nonstopmode',
                 '-halt-on-error', '-output-directory='+str(build), 'circuit-atlas.tex'],
                REPORT, build/f'atlas-pass{pass_number}.compile.log')
        shutil.copyfile(build/'circuit-atlas.pdf', REPORT/'circuit-atlas.pdf')
        record = {'schema': 'circuitikz-exports-v1', 'style_sha256': sha(REPORT/'circuit-style.tex'),
                  'builder_sha256': sha(Path(__file__)), 'figures': records,
                  'atlas_source_sha256': sha(REPORT/'circuit-atlas.tex'),
                  'atlas_pdf_sha256': sha(REPORT/'circuit-atlas.pdf'),
                  'note': 'Drawing exports only; no new simulation.'}
        (output/'drawing_manifest.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()

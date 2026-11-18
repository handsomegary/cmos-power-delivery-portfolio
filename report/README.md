# Circuit atlas and technical report

**[Circuit atlas PDF](circuit-atlas.pdf)** · **[Technical report PDF](../docs/technical-brief.pdf)** · **[Portfolio](../README.md)**

The circuit atlas presents the historical LDO r6 and Buck r8/r9 circuits in six focused drawings. The six-page technical report presents their measurements, tradeoffs, FoM definitions and complete device-sizing tables. These are circuit-design documents in an engineering-paper format, not IEEE publications.

## Editable drawing sources

| Drawing | LaTeX source | Vector export |
| --- | --- | --- |
| LDO regulation architecture | [ldo-architecture.tex](figures/ldo-architecture.tex) | [PDF](figures/ldo-architecture.pdf) · [SVG](figures/ldo-architecture.svg) |
| Complete nine-MOS LDO circuit | [ldo-core.tex](figures/ldo-core.tex) | [PDF](figures/ldo-core.pdf) · [SVG](figures/ldo-core.svg) |
| Buck power/control architecture | [buck-architecture.tex](figures/buck-architecture.tex) | [PDF](figures/buck-architecture.pdf) · [SVG](figures/buck-architecture.svg) |
| Power bridges and source/sink assist | [buck-power.tex](figures/buck-power.tex) | [PDF](figures/buck-power.pdf) · [SVG](figures/buck-power.svg) |
| Six gate-driver instances | [buck-driver.tex](figures/buck-driver.tex) | [PDF](figures/buck-driver.pdf) · [SVG](figures/buck-driver.svg) |
| Low/high voltage-window detectors | [buck-detector.tex](figures/buck-detector.tex) | [PDF](figures/buck-detector.pdf) · [SVG](figures/buck-detector.svg) |

[circuit-style.tex](circuit-style.tex) supplies the shared symbol proportions and drawing styles. [circuit-atlas.tex](circuit-atlas.tex) places the compiled figures and Times-style captions in the atlas. [build_circuits.py](build_circuits.py) wraps each figure in the same LaTeX preamble, compiles its PDF and derives its SVG and PNG from that PDF.

## Drawing profile

The source uses American CircuitikZ with the following settings:

```latex
\usepackage[american]{circuitikz}
\ctikzset{
  transistors/scale=0.8,
  resistors/scale=0.5,
  capacitors/scale=0.5,
  sources/scale=0.8,
  logic ports/scale=0.6,
  flipflops/scale=0.6,
  tripoles/mos style=arrows,
  transistors/arrow pos=end,
  amplifiers/scale=0.7,
  blocks/scale=0.7
}
```

Black circuit lines, white functional blocks and bold Helvetica-style labels carry the diagrams. Light gray identifies related functional groups. Wires start at 0.60 pt and block outlines at 0.85 pt; voltage, current and device identifiers use mathematical notation. Body text and captions use Times-style serif typography.

Matching net labels denote electrical connections. Filled dots indicate junctions, while unmarked crossings remain unconnected. Repeated Buck circuits use explicit instance mappings to preserve readability; the [LDO inventory](../projects/ldo-130nm/design.md) and [Buck inventory](../projects/two-phase-buck/design.md) disclose every device's dimensions and terminals.

In the LDO drawings, mathematical labels V_EA, V_G and V_MIR map to the source nodes EAOUT, GATE and MIRROR. Ground is node 0. Bulk terminals are explicitly connected or identified by the shared body-connection legend. The [source preservation record](source_provenance.json) identifies the unchanged numerical inputs and historical result documents.

## Build

Install a TeX distribution containing CircuitikZ, TikZ/PGF, `standalone`, `helvet`, `mathptmx` and the standard font-encoding packages. Poppler provides `pdftocairo`. From the repository root:

```sh
python report/build_circuits.py
```

If the executables are not on PATH, provide their installed locations:

```sh
python report/build_circuits.py --pdflatex /path/to/pdflatex --pdftocairo /path/to/pdftocairo
```

The command writes PDF, SVG and PNG exports beside the six figure sources, builds `report/circuit-atlas.pdf`, and records source/output hashes in [drawing_manifest.json](figures/drawing_manifest.json). SVG exports include an explicit white background. Intermediate files and logs go to `reproduced/circuitikz-build/` by default. Use `--build-dir` to change that location, or `--only ldo-core` to rebuild one figure; a single-figure build does not refresh the complete atlas or its manifest.

The technical report is generated separately from the published measurements and figure exports:

```sh
python -m pip install -r requirements.txt
python tools/build_technical_brief.py --output reproduced/technical-brief.pdf
```

Its editable source is [build_technical_brief.py](../tools/build_technical_brief.py). The architecture drawings are embedded from their compiled PDFs as vectors; the existing measured-result plots retain their published data. ReportLab and pypdf are included in the repository requirements. The explicit output path preserves the committed report. Rebuilding figures or documents does not run a simulator or add verification coverage.

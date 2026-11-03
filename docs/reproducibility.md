# Reproduce the published analysis

[Portfolio](../README.md) · [Figure build guide](../report/README.md) · [Validation scope](validation-scope.md)

## Offline numerical path

Clone or download the repository. With Python 3.10 or later, run from its root:

```sh
python tools/verify_repository.py
python tests/test_download.py
python tools/reproduce_all.py --no-plots --outdir reproduced/numerical
```

The numerical path uses Python's standard library and does not start a simulator. The verifier checks the release inventory, recorded file sizes and hashes, and local documentation links. The downloaded-copy tests exercise verification without Git and check that changed evidence is rejected. Package integrity and electrical performance are separate checks.

The combined command runs the projects sequentially. Select a new or empty output directory; existing nonempty destinations are rejected. Individual entry points remain available:

```sh
python projects/ldo-130nm/scripts/reproduce.py --no-plots --outdir reproduced/ldo
python projects/two-phase-buck/scripts/reproduce.py --no-plots --outdir reproduced/buck
```

| Study | Published input | Reproduced analysis |
| --- | --- | --- |
| LDO r6 | Transient samples, native scalars and frequency-domain exports | Remeasures 20 events, checks saved expectations, compares refinement traces and recalculates FoMs |
| Buck r8/r9 | Measurement tables, controller parameters and device inventory | Checks asset hashes, pair arithmetic, case counts and device widths; regenerates comparison metrics |

Native LDO stability scalars remain retained simulator measurements. Buck display traces are decimated and cannot replace the original full-grid energy or recovery measurements. Analysis of these exports does not constitute a new Spectre run.

## Plots and documents

```sh
python -m pip install -r requirements.txt
python tools/reproduce_all.py --outdir reproduced/with-plots
python tools/build_technical_brief.py --output reproduced/technical-brief.pdf
```

Matplotlib generates the result plots and ReportLab builds the six-page technical report. The CircuitikZ circuit drawings have a separate LaTeX/Poppler build:

```sh
python report/build_circuits.py
```

That command updates the committed figure exports and circuit atlas from their editable sources. See [report/README.md](../report/README.md) for dependencies, executable options, output locations and figure conventions. The older `python tools/verify_release.py` verification command remains supported.

## New circuit simulations

This package contains numerical exports, circuit descriptions, analysis scripts and the behavioral Buck controller. It is not a complete portable Spectre/OA project. A new transistor simulation requires compatible device models, a licensed simulator and complete configured benches. Another installation with the same nominal process size does not establish electrical equivalence.

Keep new run outputs separate from the historical exports. Record the actual source and model versions, parameters, commands, stimulus and measurement windows before comparing new measurements with this release.

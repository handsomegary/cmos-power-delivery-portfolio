# Spectre, OCEAN and Virtuoso inputs

- [LDO](../projects/ldo-130nm/simulation/README.md) includes two r6 schematic-level decks, the v32 extracted load matrix and a portable v32 test fixture.
- [Buck](../projects/two-phase-buck/simulation/README.md) includes the r8 nominal OFF/ON decks, the authored controller and the r8/r9 case and pair definitions.
- [Historical replay](historical-replay.md) identifies the retained PFAST1 and B1 inputs and verifies their bytes against the archived cases.

Prepare `private/models.local.scs` with the `include` paths and model sections for your authorized technology installation. The file must expose the MOS models used by the selected deck with matching D/G/S/B order, geometry parameters and voltage ratings. The transistor models needed by the LDO example are `n12` and `p12`. The Buck also uses `n33` and `p33` for the I/O devices. Keep generated runs in a separate local directory.

[The Python staging tool](../tools/stage_spectre_case.py) creates a new run directory and binds the selected model file. The project's published measurements correspond to the original model versions and simulator settings. A rerun with different models is a separate measurement.

To export a saved transient signal, run [the OCEAN exporter](../tools/export_transient.ocn) from the repository root. Set `PORTFOLIO_SIGNAL` to the saved name. The LDO output is `VOUT` and the Buck load-side output is `VLOAD`.

```sh
export PORTFOLIO_RESULT_DIR="$PWD/runs/ldo-r6-10ns"
export PORTFOLIO_SIGNAL=VOUT
ocean -nograph -nocdsinit -restore "$PWD/tools/export_transient.ocn"
```

The CSV preserves the original saved time points. Use the [Python PSF reader](../tools/parse_spectre_psf.py) with `--help` for DC, transient, AC, stability and noise exports from Spectre PSF ASCII. Parser completion and circuit acceptance are separate checks.

For an existing Virtuoso schematic, load [the SKILL connectivity reader](../tools/audit_schematic.il) from the CIW. It reports each instance and terminal-to-net connection.

```lisp
load("/absolute/path/to/tools/audit_schematic.il")
portfolioAuditSchematic("myLocalLibrary" "myLocalCell")
```

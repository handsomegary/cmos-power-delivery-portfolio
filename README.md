# CMOS Power Delivery Portfolio

Two schematic-level power-management projects using licensed **130 nm CMOS** transistor models, Cadence Virtuoso, and Spectre. This repository contains original design descriptions, selected numerical simulation exports, measurement analysis, plots, and original behavioral controller code where applicable.

| Project | Implemented design | Evidence and limits |
| --- | --- | --- |
| [Analog LDO](projects/ldo-130nm/README.md) | Transistor-level error amplifier, buffer, PMOS pass device, feedback, and compensation | DC, native loop analysis, load transients, process/temperature exploration, and capacitance-boundary failures. Ideal reference and ideal external passives; pre-layout. |
| [Two-phase Buck with transient assist](projects/two-phase-buck/README.md) | Transistor power bridges, gate drivers, window detectors, and source/sink assist, combined with behavioral control | 47 main cases and 8 separate gate-resistor exploration cases completed. Matching OFF/ON comparisons include adverse outcomes. PI/PWM/timing and current sensing remain behavioral or ideal. |

## What to review

- The LDO shows sizing, bias/headroom, compensation, and load/capacitance tradeoffs. Small-capacitance failures remain in the dataset.
- The Buck shows the interaction between a switching regulator, a declared RLC power-delivery network, and a finite transient-assist path. Lower peak droop does not automatically mean shorter recovery or lower unload overshoot.
- Measurement definitions, actual operating conditions, and numerical sensitivity are stated alongside results. Completed cases are not a count of cases meeting all performance requirements.

Start with each project's README and figures, then inspect its numerical data and reproduce the analysis.

## Reproduce the published analysis

Use Python 3.10 or later. Core numerical checks use the standard library. Install the plotting dependency if plots are needed:

```sh
python -m pip install -r requirements.txt
python tools/verify_release.py
python tools/reproduce_all.py --outdir reproduced
```

The scripts read the published exports and write fresh analysis outputs. They do not launch Virtuoso, Spectre, a virtual machine, or any remote connection.

## Simulation scope

The original designs were simulated with real licensed transistor models. Connectivity and geometry tables describe the implemented circuits.

The included scripts reproduce analysis of the published simulation exports. A new transistor simulation requires an authorized technology setup, simulator, and configured design/netlist.

These results are pre-layout simulation. They do not establish silicon measurements, extracted package behavior, physical reliability, or complete switching-loop signoff. Full physical Buck efficiency is not reported because all controller, reference, and sensing power is not modeled.

See [validation scope](docs/validation-scope.md) and the project-specific measurement definitions for details.

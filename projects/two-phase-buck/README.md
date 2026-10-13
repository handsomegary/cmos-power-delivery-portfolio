# PDN-aware two-phase buck with fast transient assist

A 130 nm CMOS mixed-level design connects two MOS buck bridges to a remote load through a parameterized power-delivery network. The study measures load-transient droop, unload overshoot, recovery, current sharing and modeled supply-port energy.

The power switches, gate drivers, source/sink assist stage and voltage-window detectors use transistor models in the original simulations. PI/PWM control, assist arbitration, programmable reference and 1 V/A current sensing are behavioral Verilog-A. This is a pre-layout study with external ideal inductors/capacitors and assumed PDN RLC; it has no extracted package network or hardware measurements.

![Architecture](figures/architecture.png)

## Circuit and test conditions

Nominal settings are 1.8 V input, 0.9 V output, two phases at 5 MHz, 2.2 uH per phase and 1 uF output capacitance. The remote load has 10 nF capacitance and nominal PDN resistance/inductance of 0.1 ohm/0.5 nH. Each case records its actual DCR, ESR, ESL, load waveform and solver settings in [r8 measurements](data/r8_measurements.json).

The selected assist mode combines MOS charge injection/removal with a 40 mA PI-state handoff. The two-microsecond arbitration bound does not bound how long the state change influences subsequent PI dynamics. [Effective parameters](data/selected_parameters.json) override the module defaults in [controller source](controller/buck_control.va).

[r8 connectivity and geometry](data/r8_hardware.csv) records 90 components including 59 MOS instances, terminal connections and W/L/multiplicity. [r9 inventory](data/r9_hardware.csv) adds source/sink assist gate resistances of 1 kohm/2 kohm while retaining 59 MOS instances.

## Measured outcomes and counterexamples

The r8 matrix completed **47 cases and 24 matched comparisons**, with 94 measured events and 141 steady windows. Completion is not a claim that 47 cases passed performance or stability requirements. All steady-window means were within 0.9 V ±1%, but 127/141 finite-periodicity diagnostics were not accepted. The original runs also recorded 329 numerical warnings.

| r8 comparison | Assist OFF | Coordinated assist ON |
| --- | ---: | ---: |
| Nominal 100 ns load-up droop | 143.37 mV | 107.39 mV |
| Same event saved-grid recovery | 7.55 us | 13.74 us |
| Hard-PDN 10 ns unload overshoot | 86.89 mV | 110.30 mV |

The assist improves nominal droop while slowing that event's recovery. The hard-PDN unload case is a counterexample: overshoot worsens. All 47 cases, including unfavorable comparisons, remain in the published tables.

The r9 gate-resistance exploration completed **8 cases and 4 matched comparisons**, limited to nominal/hard-PDN conditions at nominal process and 27 °C, including two finer-solver cases. It does not inherit the r8 matrix coverage.

![Measured tradeoffs](figures/tradeoffs.png)

Four r8 and two r9 coarse/fine solver comparisons quantify sensitivity rather than certify convergence. In r8, event-peak differences reach 1.245 mV, saved-grid recovery differences reach 4.885 us, and event pointwise VLOAD differences reach 73.770 mV. Recovery and trajectories have not fully converged.

Physical overall efficiency is **N/A** because behavioral controller internal power is unmodeled. Finite-window supply-port energy ratios are not full converter efficiency. There is no switching-loop stability, device reliability, layout/PEX, EM/IR or product signoff claim. Saved-grid terminal-voltage envelopes can miss peaks between samples.

## Reproduce the analysis

From the repository root, run:

```sh
python -B projects/two-phase-buck/scripts/reproduce.py --outdir reproduced/buck
```

Python 3.10+ and Matplotlib reproduce the figures. For standard-library validation and numerical summaries only, add `--no-plots`. Choose a new or empty output directory. The command verifies asset hashes, case/pair counts, pair-delta arithmetic and MOS width arithmetic, then generates the summary and figures. It does not rerun simulations or independently reparse original simulator results.

`data/` includes all event/steady/comparison measurements, solver sensitivity and six selected waveform CSVs. The display waveforms are decimated with event extrema and endpoints retained; they must not be used to recalculate energy or recovery. Full-grid event measurements are recorded separately. Recovery means the last saved out-of-band violation followed by linear boundary interpolation, measured from the event start and limited to the finite observation window.

The r8 measurements retain three analysis method revisions: 41 cases before the endpoint roundoff patch, four using the endpoint patch, and two line cases using a separate PWL-tail roundoff patch. These narrowly bounded changes handle floating-point endpoint queries; the published analysis consumes the retained measurements instead of claiming a fresh raw-data parse.

Rerunning transistor simulations requires your own authorized technology setup.

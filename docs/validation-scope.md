# Validation scope

## Evidence levels

The published numbers were derived from completed Spectre runs in the original local project. This release includes selected numerical exports and analysis code. Regenerating a plot or derived measurement from these exports is different from rerunning the transistor simulation.

Reproducing the transistor simulations requires an authorized technology setup and simulator license.

## Analog LDO

- The error amplifier, buffer, and pass device are transistor-level circuits in 130 nm CMOS.
- The reference and passives are ideal. Output capacitance is an external test condition, not demonstrated integrated capacitance.
- The formal revision contains 164 static/DC configurations and 10 transient runs. These counts describe coverage and run completion.
- Small-output-capacitance failures and process/temperature headroom limitations are retained. An acceptable nominal condition does not validate every load, capacitance, or supply condition.
- Loop analysis, transient recovery, regulation, and sampled device headroom are distinct evidence. Startup of a physical reference, mismatch yield, layout parasitics, and hardware behavior remain outside scope.

## Two-phase Buck

- Power bridges, gate drivers, window detectors, and assist devices use real transistor models. PI/PWM/scheduling and some supervision are original Verilog-A; current sensing is ideal.
- Main revision r8: 47 completed cases and 24 configured comparison pairs. Separate revision r9: 8 completed cases and 4 pairs, limited to the declared nominal process and temperature.
- A comparison pair can reuse an existing OFF baseline for more than one strategy. Pair count is not half the number of cases.
- Inductors, capacitors, ESR/ESL/DCR, and the RLC network are declared external or assumed test conditions. The network is not extracted from a physical package.
- The selected strategy improves some peak deviations while worsening other outcomes. In particular, hard-network unload overshoot remains a counterexample.
- Solver comparisons change maximum step, output sampling, tolerance, and accuracy settings together. Peak sensitivity, recovery sensitivity, and pointwise waveform differences must be reported separately; they are not a blanket convergence pass.
- Energy at modeled supply ports is meaningful within its stated boundary. Complete physical efficiency is unavailable when behavior-controller/reference/sensor power is missing.
- Finite observation-window recovery and steady means are not periodic steady-state or switching-loop stability signoff. Nominal voltage classes are not absolute maximum ratings.


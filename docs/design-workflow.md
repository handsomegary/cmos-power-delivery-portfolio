# Design and verification workflow

[Portfolio](../README.md) · [Validation scope](validation-scope.md) · [Reproducibility](reproducibility.md) · [LDO engineering journal](../projects/ldo-130nm/ENGINEERING_JOURNAL.md)

This workflow governs continuing PMIC work in this portfolio: LDOs, single-phase and multiphase Buck converters, and related blocks. Work proceeds from quantitative evidence, with the shortest practical path from **hypothesis → verification → decision**. Each session starts from the brief below and moves through nine stages.

| Stage | Question it answers | Output |
| --- | --- | --- |
| [1. Actual state](#1-recover-the-actual-state) | What is valid, unfinished or running? | Status table and next experiment |
| [2. Specifications](#2-decidable-specifications-and-measurement-definitions) | What counts as a pass, and how is it measured? | Specification table with PASS / FAIL / Not measured |
| [3. Model level](#3-cheapest-sufficiently-accurate-model-level) | Which model level answers this question cheapest? | Chosen level and its stated limits |
| [4. Calibration](#4-calibrate-models-before-they-guide-design) | Can the model be trusted, and where? | Model-versus-transistor error and valid range |
| [5. Iteration](#5-hypothesis-driven-iteration) | What is the cause, and which experiment separates the candidates? | Hypothesis record and minimal comparison |
| [6. Resources](#6-budget-simulation-analysis-and-storage-together) | Does the run and its analysis fit the host? | Resource limits, saved signals and retention plan |
| [7. Traceability](#7-traceability) | Can every PASS be traced back to its source? | Per-run directory, hashes and receipts |
| [8. Physical verification](#8-physical-verification-after-circuit-convergence) | Does the extracted layout still meet the specification? | DRC, LVS, PEX and post-layout results |
| [9. Delivery](#9-delivery-and-communication) | What is handed over, and how is it reported? | Editable design, scripts, tables and limitations |

## Session brief

```text
Topic / architecture:   [LDO | Buck | multiphase Buck | other]
Project location:       [path]
Current checkpoint:     [path, or to be located]
Available tools:        [MATLAB, Python, Virtuoso, Spectre, Verilog-A, other]
Technology and models:  [local path, or to be located; confidential data stays local]
Target specifications:  [values; list undecided items as TBD]
Scope of this round:    [for example, one diagnosis only, or fix stability and transient]
```

## 1. Recover the actual state

Read the latest checkpoint, sources, analysis scripts, run logs and existing results. Establish:

- which version is the current valid baseline;
- which results are complete, failed, not yet analyzed, or only preparatory;
- which jobs are running and which work is paused;
- whether the schematic, models, netlist, layout, PEX and report all belong to the same version.

A file that exists, a process that exits with status zero, or one passing test does not make the design pass. Reuse prior results that have evidence behind them instead of rebuilding completed work.

Open each session with a short status table: what is complete, the main gaps, and the next most valuable experiment.

## 2. Decidable specifications and measurement definitions

Maintain one specification table:

| Metric | Target | Conditions | Method | Current value | Status |
| --- | --- | --- | --- | --- | --- |
| *example: load-step undershoot* | *≤ target mV* | *load step, edge time, COUT, corner* | *transient, defined window* | *measured value* | *PASS / FAIL / Not measured* |

Define at least:

- input, output, load, temperature, process corner and supply range;
- external and on-chip capacitance, ESR/ESL, and the package/PDN assumptions;
- load- and line-step amplitude, edge time, initial state and measurement window;
- the transient error band, the starting point of recovery time, and how long the output must stay in band after recovery;
- the loop-break point, measurement method, PM/GM and crossover frequency;
- the power boundary for quiescent current and efficiency;
- device ratings and the terminal voltages that must be checked for stress.

An item without a measurement stays **Not measured**. A specification change states its reason and impact; it is never relaxed silently to turn a failing result into a pass.

## 3. Cheapest sufficiently accurate model level

Not every tool is needed in every round. Choose the level from the current question.

| Level | Tools | Use it for | Limit |
| --- | --- | --- | --- |
| A. Analytical and numerical | MATLAB, Python | Design equations, gm/ro small-signal models, poles and zeros, control loops, parameter sensitivity, PDN impedance, Buck averaged models, phase current sharing | Not transistor-level evidence until calibrated |
| B. Behavioral system | Verilog-A with Spectre | Early full-system integration and isolating individual non-idealities | Does not establish the performance of the transistor implementation |
| C. Local transistor block | Spectre with the actual technology models | Verifying the block that currently limits performance | Does not establish whole-system behavior after integration |
| D. Digital and real-number models | SystemVerilog RTL / RNM | Digital control, state machines, protection, timing, calibration, large functional case sets | Does not establish analog stability, noise or efficiency |
| E. Mixed-signal co-simulation | AMS Designer | Actual digital RTL simulated together with the analog circuit | Introduced only when required and when the tool and license are available |
| F. Full transistor and PEX | Spectre, extraction | Confirming candidates and final specification verification | Reference level for final claims |

Level details:

- **A.** Calibrate against existing data first, then use the model to select a small number of candidate designs.
- **B.** Add only the non-idealities the question needs: finite gain, bandwidth, output impedance, slew rate, current limit, saturation, delay, hysteresis, startup and bias dependence. Mark which parts are idealized and the range over which the model is valid.
- **C.** Typical blocks: error amplifier, buffer, pass device, comparator, gate driver, current sensing, PWM and fast transient assist. Use bias, load and parasitic conditions close to the integrated system, so that a block does not pass in isolation and then fail when connected back.
- **D.** When a model has to represent loading, choose the interface and the resolution method explicitly. A simplified RNM result is not evidence of analog stability, noise or efficiency.
- **F.** A pass with a behavioral model or a single block is not a pass of the complete circuit.

Each move up or down a level states the question it answers, the non-idealities it keeps, and which conclusions still require verification at a higher level of accuracy.

## 4. Calibrate models before they guide design

From a few representative transistor-level cases, extract the DC operating point, gain and bandwidth, output impedance, dominant poles and zeros, slew rate, limiting currents and the main parasitics.

Compare the model with the transistor results and record the valid range and the error. Keep calibration cases and validation cases separate where possible, so that agreement is not limited to a single operating point.

When the model fails to predict a result, look first for a missing physical effect. An uncalibrated model can propose hypotheses; it cannot replace measured evidence.

## 5. Hypothesis-driven iteration

Each round begins with a written record:

1. the observed failure;
2. the most likely cause and the evidence for it;
3. the smallest experiment that separates the candidate causes;
4. the expected observation, the pass condition and the stop condition;
5. possible effects on other specifications.

Prefer a few comparisons that can tell causes apart. Avoid changing many coupled parameters at once or launching a broad sweep. The [LDO engineering journal](../projects/ldo-130nm/ENGINEERING_JOURNAL.md) uses this record format.

**LDO checks.** Feedback polarity, headroom, pass-gate capacitance, error-amplifier and driver output impedance, the compensation path, the poles and zeros at each load, and recovery after saturation. Stability and transient response are evaluated together; a larger PM or GM alone is not the goal.

**Buck and multiphase Buck checks.** Control mode, sampling effects and subharmonic risk where they apply, current balance, dead time, driver limits, inductor saturation and PDN resonance. Converge the control loop with an averaged model first, then confirm ripple, spikes, switching events and fast transients with a switching model.

**Assist and droop mitigation.** Every assist is compared ON against OFF under identical conditions, recording the improvement together with the added power, device stress and false triggering.

## 6. Budget simulation, analysis and storage together

Before launching on a shared host or VM, check available RAM, CPU, swap and disk space, the priority of other projects, and the peak RAM that post-simulation analysis and compression may need.

- Separate measured peaks, estimates and reserved margin. Do not judge only from the simulator's current usage, and do not treat an unknown peak as known.
- Analyze by streaming, in chunks or by selective reads; avoid turning large waveforms into large numbers of Python objects.

Set for every job:

- thread count and a reasonable resource ceiling;
- the nodes that must be saved and their time resolution;
- the expected waveform size and a stop threshold;
- the analysis method, the result location and the retention policy.

Save only the data the current question needs. Spikes, narrow pulses, faults and high-frequency noise need adequate time resolution; a decimated plot does not replace the original measurement.

When resources are short, first reduce the saved nodes, narrow the diagnostic window, improve the analysis method or defer the job, and quantify the shortfall. Other projects are not stopped and VM power state is not changed. When a round authorizes a single simulation, report as soon as its data is saved and analyzed instead of starting the next round automatically.

## 7. Traceability

Each experiment has its own directory, log, process information and results. Record the source/netlist and model hashes, versions, parameters, stimuli, seeds, tool versions, commands and measurement windows.

Every PASS traces back along one chain:

```text
circuit version → models and test conditions → original results → analysis method
```

Keep the valid baseline, the current candidate, important failure cases and the short waveforms that are needed. Before removing old outputs, confirm that no stimulus, replay, calibration or analysis depends on them, follow the cleanup authorization in force at that time, and leave a per-file receipt. A local backup is not deleted merely because the VM holds a copy.

## 8. Physical verification after circuit convergence

Reach the agreed schematic-level convergence threshold before updating the layout. Feed available parasitic evidence back into the design early.

Run DRC, LVS and PEX, and confirm that the extraction matches the actual layout, netlist and model versions. After layout, complete the DC, stability, transient, regulation, PSRR, noise and corner verification that the specification and the parasitic sensitivity require.

After any design change, identify the affected results and rerun the necessary tests. A pass table is never assembled from the best values of different versions.

## 9. Delivery and communication

Deliverables:

- editable schematics and, where needed, layout;
- generation, run and analysis scripts;
- the specification table, key waveforms and model calibration results;
- block functions, device sizes, bias and compensation tradeoffs;
- figures of merit with their conditions and equations;
- stated limitations, failure cases and next steps.

Public reports describe the technology by process node and name only the device types needed to read the circuit. They follow a professional paper style, and every figure and table states units, conditions and version. A report does not claim signoff or hardware results that were not actually completed.

Progress reports lead with the evidence obtained, the causes excluded, where the current limit lies, and the next most valuable action. Authorized, reasonable work continues to completion. A blocker is reported with the actual error, and the unblocked parts continue.

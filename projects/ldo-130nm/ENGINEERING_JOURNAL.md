# LDO engineering observation and decision journal

Append dated entries; preserve successful checks, adverse results and rejected explanations. Each entry records the hypothesis, actual change, reason, simulation/analysis evidence, observation, inference, decision and next validation. A numerical workflow result does not silently replace electrical acceptance criteria. New circuit/specification changes require model evidence and human approval.

## 2026-11-07 — isolate solver behavior before changing the circuit

**Hypothesis.** The later v32/Grid23 PEX study showed a high-load DC mismatch after changing the solver execution mode. The control question was whether the mismatch came from circuit inputs, reused generated AHDL artifacts or APS2 numerical behavior. This entry concerns that later verification study, not the historical r6 measurements published on the project front page.

**Actual change and reason.** Keep the same frozen circuit, extracted parasitics, model hashes, stimuli and DC physical gates. Run four cases sequentially: classic low/high, then APS with two requested threads low/high. Low/high loads are 0.1 mA/5 mA at the fixed 1.2 V input and −40 °C condition. No device, bias, compensation, transient or Grid24 change was made.

An earlier dependency checker missed the generated `polyres_hdl` module alongside `absrint_hdl`; its correction preserved the exact module allowlist and same-job ownership checks. Diagnostic739646 later stopped after both classic cases when APS2 tried to reuse a generated library from a different job. That failure remains recorded. The isolated-cache control set `CDS_AHDL_REUSE_LIB=NO` only in each simulator subprocess, following the actual tool log; it did not accept cross-job libraries or weaken the guard.

**Simulation and analysis evidence.** Isolated-cache diagnostic 739664 completed four DC cases. Each result was compared to both the retained 23.1 reference and the frozen 18.1 profile. APS2 was also compared directly to the new classic result. Counts below are failed voltage/current/terminal-pair comparisons; inventories contain 201 voltage nodes, 4 source currents and 402 terminal-pair stresses.

| Case | Against retained 23.1 | Against frozen 18.1 | APS2 against new classic |
| --- | --- | --- | --- |
| Classic low | 0/0/0 | 0/0/0 | — |
| Classic high | 0/0/0 | 0/0/0 | — |
| APS2 low | 0/0/0 | 0/0/0 | 0/0/0 |
| APS2 high | **27/0/0** | **27/0/0** | **27/0/0** |

The gates remained **1µV+1ppm** for voltage, **1nA+1ppm** for current and **2µV+1ppm** for terminal-pair stress. The original physical DC gates and all protected input/reference hashes were also retained.

**Observation.** Fresh-cache isolation allowed the control to finish, while the same high-load APS2 voltage mismatch remained. Classic agreed with both references; APS2 high failed the voltage predicate in 27 of 201 nodes even against classic within the same current tool build. There was no current/stress comparison failure. An earlier APS2 qualification attempt 739586 had already reported the 27-node high-load difference; the control reproduces rather than erases it.

**Inference.** The completed control supports a reproducible APS2-versus-classic DC numerical difference under these fixed inputs. It separates that issue from the earlier cross-job-cache rejection. It does not prove the circuit fails its electrical specifications, nor does it qualify APS2 for the retained numerical bridge. A successful scheduler exit means the diagnostic collected its cases, not that every comparison passed.

**Decision and stop checkpoint.** Preserve the original gates; do not relax the tolerance to accept APS2. The APS2 bridge remains unqualified. Do not continue to a transient/Grid24 run or start a circuit-design sweep on the basis of this diagnostic. Historical r6 results and the later layout/PEX evidence remain separate claims.

**Next validation.** Use the compact DC results and Python/MATLAB behavioral reasoning to identify sensitive operating-point quantities and formulate a falsifiable explanation before proposing any actual circuit change. Record the model/input/report hashes, intended change and predeclared numerical/electrical validation criteria. Human approval of that change precedes a limited, named transistor-level experiment. The current cache/solver control is a completed verification exception, not permission for blind Spectre parameter search.

**Public source context.** The existing [PSF reader at 19643ad](https://github.com/handsomegary/cmos-power-delivery-portfolio/blob/19643ad9dc15757851d6d914665ba8f075eb70aa/tools/parse_spectre_psf.py) and [reproduction entry at 19643ad](https://github.com/handsomegary/cmos-power-delivery-portfolio/blob/19643ad9dc15757851d6d914665ba8f075eb70aa/projects/ldo-130nm/scripts/reproduce.py) document the public historical analysis path; they are not the complete private v32 control-study environment. This journal publishes aggregated observations and decisions, without process-model payloads, netlists, raw waveforms, connection details or private execution artifacts.

## 2026-11-07 — explicitly authorized final classic Grid24 task (pending)

**Hypothesis/reason.** The completed control isolated an APS2 high-load numerical difference while classic agreed with the references. The user explicitly selected classic for one final predeclared Grid24 task; this choice does not qualify the APS2 bridge or relax its failed gate.

**Actual change/authorization.** Retain the original classic command and frozen Grid24 inputs/criteria, with per-process AHDL reuse disabled. Job `739751` was submitted with 2 CPUs/8 GiB and is pending at this update. It allows two DC cases and, only if their original gates permit continuation, one predeclared load transient. No Grid25 or later design iteration is allowed.

**Evidence/result status.** No final scientific result is available yet. A valid measured electrical failure will retain its failed values and false status; it is not a successful specification check. A tool/parser/integrity error stops with diagnostic data retained. An early DC stop must not silently launch a transient.

**Observation/inference/decision.** Submission and queue status provide execution evidence only. After valid analysis and full-rate OCEAN/compact-sample verification, cleanup is restricted to the new task's three bulk outputs; original references remain protected. Useful summaries, DC evidence, event/recovery samples and 402 terminal-pair peak witnesses remain.

**Next action.** Read and append the actual result, retain compact evidence, complete authorized scoped cleanup where analysis is valid, and stop. Do not schedule another task automatically, whether the result supports or rejects the desired behavior.

### Result appended — classic Grid24 completed, selected checks passed, task stopped

Job `739751` completed with exit0:0 in 7min17s. Both DC cases reproduced the original 201-node/4-current/402-stress comparisons with zero failures. The single transient condition was FNSP,27°C,1.2V input, ideal1nF output capacitance,0.1↔5mA load with10ns edges,60µs observation and1ns maximum step. It is a different specified condition from earlier historical measurements; this entry makes no unmatched before/after performance claim.

| Selected Grid24 criterion | Observed | Limit | Headroom | Result |
| --- | ---: | ---: | ---: | --- |
| Worst absolute output deviation | 106.614mV | 125mV | 18.386mV | Pass |
| Worst sustained-band recovery from edge end | 1.445711µs | 2.5µs | 1.054289µs | Pass |
| Unload secondary dip | 0mV | 9mV | 9mV | Pass |
| Maximum of402 terminal-pair stresses | 1.174401V | 1.2V | 25.599mV | Pass |

**Evidence/observation.** The analysis used 61,485 actual saved samples and 204 signals. Full-rate OCEAN VOUT matched the selected arrays; event extrema/recovery brackets and all 402 peak witnesses were verified. The job allocated 2 CPUs, while the preserved classic transient used about one core (182.573CPU-s/183.403elapsed-s); allocation is not an assertion of multithreading. Installed support/model dependencies were verified by the compute-node guard; independent postjob checks covered shared retained evidence, not an unavailable compute-only tool installation.

**Retention result.** Exactly three new-job bulk files were removed after validation: 640,483,985logical bytes and273,273,344allocated bytes (260.614MiB allocated). Retained compact evidence includes 3483 VOUT/current samples and 1152 witness rows covering 402 terminal pairs, plus scalar DC, metrics, source hashes, decks and logs. The original reference was rehashed unchanged; no full waveform backup was made locally.

**Inference/decision.** This completes the user-authorized classic execution/analysis/cleanup task and passes its four selected checks. `all_LDO_specs_passed` and whole-LDO qualification remain **false**; the earlier APS2 high-load bridge remains unqualified. No Grid25 or additional LDO task was launched. Stop here under the user's finite-task instruction; any future design change requires a new model-backed plan and approval.

## 2026-11-08 — newly authorized frozen Grid25 check (preparing)

**Hypothesis/reason.** The prior classic Grid24 case passed its four selected checks at10ns edges. The next original frozen matrix case changes only the load ramp to100ns at the same FNSP/27°C condition. This tests that named pre-existing condition; it is not a circuit-design optimization or a claim of complete qualification.

**Actual change/authorization.** The user explicitly resumed one finite LDO task today. Keep the original classic solver, circuit, model/source hashes, physical gates and numerical comparison tolerances. Grid25 uses1.2V, ideal1nF,0.1↔5mA,100ns edges,60µs observation and1ns maxstep, allocated2CPUs/8GiB. Native24/25 low/high DC input bytes are identical; the transient difference is confined to the original load-PWL edge endpoints. The original native25 manifest and independent-review hashes were checked before preparing this continuation.

**Evidence/result status.** Job `740068` has been submitted with2CPUs/8GiB; no new scientific result or cleanup outcome is available at this entry. Preserve the earlier APS2 high-load27-node mismatch as an unqualified bridge; this classic task does not erase it or relax the original tolerance. The previous selected Grid24 pass remains limited to its stated condition.

**Decision/next validation.** Seal the exact frozen inputs and criteria before submission, run two DC checks and only the named Grid25 transient if their gates permit continuation, then analyze and retain compact evidence. Clean only reviewed new-job bulk after valid analysis; tool/parser/integrity failure retains diagnostics. Original references stay protected. Append all measured pass/fail outcomes and stop after this single task. Yesterday's stop is preserved as history; today's explicit authorization permits this one new finite cycle, not an automatic design sweep.

### Result appended — frozen Grid25 completed; observed edge-rate sensitivity

Job `740068` completed 0:0 in 7 min 12 s. Both DC cases passed the unchanged 201-voltage/4-current/402-stress comparisons. The single frozen FNSP/27 °C, 1.2 V, ideal 1 nF, 0.1↔5 mA transient used 100 ns load edges, 60 µs observation and 1 ns maximum step. All four selected criteria passed; whole-LDO qualification remains **false**.

| Metric | Prior Grid24, 10 ns | Grid25, 100 ns | Grid25 limit | Grid25 headroom |
| --- | ---: | ---: | ---: | ---: |
| Worst absolute output deviation | 106.614 mV | 82.910630 mV | 125 mV | 42.089370 mV |
| Worst sustained-band recovery, from ramp end | 1.445711 µs | 1.410516 µs | 2.5 µs | 1.089484 µs |
| Unload secondary dip | 0 mV | 0 mV | 9 mV | 9 mV |
| Maximum 402-pair stress | 1.174401 V | 1.166996 V | 1.2 V | 33.004 mV |

**Observation/inference.** The slower frozen load ramp produced 23.703336 mV less peak deviation under the same circuit, PEX, corner, bias, model and classic solver. Recovery values retain the same definition, measured from each ramp's own end. This is **edge-rate sensitivity**, not a circuit redesign or matched-edge design improvement. The previous APS2 bridge failure and incomplete full-LDO qualification remain separate, unchanged findings.

**Evidence/retention.** Analysis covered 61,336 actual samples/204 signals. Independent compact replay reproduced both event extrema and recovery interpolation; 3651 VOUT/current samples plus 1152 rows witness all 402 terminal pairs. 98 protected and 94 retained-file hashes matched, including preserved original reference waveforms. Only three new bulk files were removed: 272,372,224 allocated bytes (259.754 MiB), separately 638,891,058 logical bytes. No full-waveform local archive or new process-model copy was made. Compute-only support was verified by the within-job guard; independent postjob checks covered available shared evidence.

**Decision/next action.** This one authorized Grid25 task has completed its analysis and scoped cleanup. No Grid26 or further LDO task was started. Stop this branch of the finite cycle; preserve the selected-pass result and its condition limits rather than extending it to all 30 conditions.

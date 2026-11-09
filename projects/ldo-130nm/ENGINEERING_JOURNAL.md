# LDO engineering observation and decision journal

## 2026-11-08 — historical POR 1 µs and 2 µs line replay

The old ideal POR R/C trials used 500 kΩ / 2 pF and 1 MΩ / 2 pF to study startup repair. This replay checked their **line response** at the original TT 27 °C, 100 µA, 1 nF, and 1.15→1.2→1.15 V input steps. Each trial kept its own two DC references and 100 ns edges; the original designs, model sections, and measurement definitions were preserved.

Job 740945 completed all six classic cases in 43 seconds with 2 CPUs / 8 GiB. Both profiles reproduced about 22.41 mV rise-edge overshoot, 18.93 mV fall-edge undershoot, and 0.94–0.95 µs recovery. Static VOUT, IQ and phase margin matched the old values. The maximum differences were 1.06e-14 V for line extrema, 1.09e-13 V for measured terminal peaks and 2.19e-5 dB for PSRR. These results preserve the historical line observations; startup and overall specification status are unchanged.

After full-rate analysis, Olympus kept compact witnesses and removed its four new bulk files. The two corresponding old VM raw files were then removed, preserving 16 small source, log, and scalar files per case. This removed 17,317,888 allocated bytes inside the guest. The earlier CTRL retirement is a separate entry; the broader local-output migration remains in progress.

<!-- PHASE2_CURRENT_STATE -->
## Current phase2 checkpoint — 2026-11-08

Historical CTRL740834 completed0:0 in21s; original selected metrics/flags were independently reviewed without a new tolerance. **Exactly one original VM raw was retired and independently rechecked**, with16 source/log/scalar hashes and stat identities unchanged. Guest-file allocation8,228,864bytes is not Windows/VMDK shrinking. Formal/all-LDO qualification remainsfalse. Probe740883 confirms tool versions only; no physical rebuild is validated yet. Earlier pending/preparing entries are history; current results and the final retirement entry take precedence. PAM4 old-local retirement is separately on HOLD after its raw-benefit counterexample.
<!-- END_PHASE2_CURRENT_STATE -->

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

## 2026-11-08 — separately authorized overnight original Grid26–29 coverage (preparing)

**Hypothesis/reason.** The next four entries are the remaining original indices in the frozen 30-condition load matrix: Grid26 SNFP/27 °C/10 ns, Grid27 SNFP/27 °C/100 ns, Grid28 SNFP/125 °C/10 ns, and Grid29 SNFP/125 °C/100 ns. They test the named source conditions and edge-rate/corner sensitivity; they are not new circuit variants or an assumed extension of earlier selected passes.

**Actual change/authorization.** After the completed daytime cycle, the user explicitly authorized these four server-queued tasks for overnight execution, analysis and scoped cleanup before reading results tomorrow. Each uses the unchanged classic solver, circuit/PEX/model sources, numerical tolerances and electrical gates, with 2 CPUs/8 GiB, 1.2 V input, ideal 1 nF, 0.1↔5 mA, 60 µs observation and 1 ns maxstep. Prior STOP entries remain historical; this separate authorization is limited to four predeclared cases, with no invented Grid30 or design sweep.

**Reference evidence.** SNFP/27 °C DC endpoints use the frozen original PEX static slot17; SNFP/125 °C endpoints use slot18. All 201 voltage, 4 current and 402 terminal-pair values are reconstructed from their original scalar PSFs and tied to the matching reviewed source, condition and snapshot. FNSP values and native schematic DC are not substituted. The original matrix function, native case manifests/reviews and native-to-PEX renderer pin the four load fixtures before execution.

**Decision/failure semantics.** Four jobs form an afterok chain. A valid measured electrical failure remains an explicit failed scientific result, with its values preserved; tool/parser/integrity/analysis or cleanup failure exits nonzero and blocks later jobs without retry. Each start checks more than 2 GiB available space. After valid analysis, retain compact event/recovery/current/402-pair witnesses and logs, delete only the new task's three reviewed bulk outputs, and protect original references. Do not copy full waveforms locally or clear unrelated files.

**Current status/next validation.** Preparation only; this entry declares no overnight result, selected pass or cleanup success. Actual submission IDs and frozen source fingerprints will be appended after submission. Read all four outcomes tomorrow, including failures, and stop at the original matrix boundary; full-LDO qualification and the earlier unqualified APS2 bridge remain separate questions.

### Submission appended — four original cases queued; results pending

The approved afterok chain is **Grid26 `740093` → Grid27 `740094` → Grid28 `740095` → Grid29 `740096`**. Submission receipts exist for all four; queue submission is not a scientific pass or cleanup-success claim. Deployment source manifest SHA256 is `a3c6f41c511dc5d290dbcc251636d9cef1765315e0f09c5f01f0acbc65233174`; the full private package passed23 source/scope/cleanup tests before staging, and compute-side Python3.6 staging reproduced the four exact source/reference contracts. The original26–29 conditions remain unchanged.

Read actual compact scientific results and scoped deletion receipts after these jobs run. No overnight metrics have been inferred from job IDs, queue state, or prior Grid24/25 outcomes.

### Results appended — original Grid26–29 selected checks passed; scoped cleanup verified

The four jobs completed `0:0` in 7 min 13 s, 7 min 11 s, 7 min 10 s and 7 min 11 s respectively (28 min 45 s of allocated job time in total). Completion was checked separately from the actual transient measurements and retention receipts. The unchanged classic solver, circuit, 1.2 V input, ideal 1 nF, 0.1↔5 mA load, 60 µs observation and 1 ns maxstep were retained.

| Grid / job | Frozen corner | Load edges | Worst deviation (limit125 mV) | Worst recovery (limit2.5 µs) | Unload secondary dip (limit9 mV) | Max402-pair stress (limit1.2 V) | Selected checks |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 26 /740093 | SNFP,27 °C | 10 ns | 102.025224 mV | 1.208842 µs | 0 mV | 1.171172 V | Pass |
| 27 /740094 | SNFP,27 °C | 100 ns | 78.903303 mV | 1.156503 µs | 0 mV | 1.164281 V | Pass |
| 28 /740095 | SNFP,125 °C | 10 ns | 114.450950 mV | 1.348512 µs | 0 mV | 1.162944 V | Pass |
| 29 /740096 | SNFP,125 °C | 100 ns | 94.151537 mV | 1.312805 µs | 0 mV | 1.158777 V | Pass |

**Observation/inference.** Grid28 is the closest selected peak-deviation result to its gate, retaining10.549050 mV headroom. Across these four cases the worst recovery has1.151488 µs headroom and the largest terminal stress has28.827868 mV headroom. At both temperatures, the slower original100 ns ramp reduces the measured peak relative to the matched10 ns condition. These are frozen edge-rate/corner sensitivities of the same circuit, not a design optimization; recovery is measured from each ramp's own end. They do not erase the earlier unqualified APS2 bridge or establish whole-LDO qualification.

**Evidence/retention.** Independent compact replay checked168 transferred file hashes,16 event extrema,8 recovery interpolations, and402 central pair witnesses per case with4600 total neighbor/witness rows. Retained VOUT/current rows are3477/3630/3465/3586. The completed compute jobs performed full-rate array/CSV and global402-peak checks before deletion; the later compact replay verifies the saved witnesses and interpolation rather than reconstructing deleted raw. Each remote audit reported159 protected and94 retained hashes unchanged, with the original reference hash map equal across all four audits; available local retained files were rehashed separately.

Exactly three new bulk files per case were removed after valid analysis: **1,055,746,048 allocated bytes (1006.838 MiB)** in total, separately2,515,224,970 logical bytes. No full waveform was downloaded or archived, and no original reference waveform was a cleanup target. This closes the four explicitly authorized matrix cases; there is no Grid30 or new design sweep, and `all_LDO_specs_passed=false` remains unchanged.


**Final source/DC closeout.** Independent source review reproduced all four original native-rendered SNFP fixtures, reparsed the scalar PSFs for all eight DC endpoints, and verified all eight endpoint comparisons against the correct frozen original PEX references:201 voltages,4 currents and402 stresses each, with the unchanged absolute-plus-relative tolerances and zero failures. Actual classic/AHDL command policies matched. Source manifest remains `a3c6f41c511dc5d290dbcc251636d9cef1765315e0f09c5f01f0acbc65233174`. The [sanitized combined closeout checkpoint](https://github.com/handsomegary/olympus-cadence-ocean-analog-notes/blob/main/expected/overnight_results_20261108.json) retains this limited qualification scope and source/report hashes. The collector submitted no job or Git update; journal publication is a separate workflow action. No new scientific task follows this check.

## 2026-11-08 — reconstructed trial-POR lineage and historical replay preparation

**Actual change and documented reason.** The 2026-10-22 `trial_por_v1` manifest explicitly isolates startup repair while separate real-native compensation profiles are prepared; existing hard limits stay unchanged and native full-network QZ proof remained pending simulator-crash repair. CTRL retains the13-MOS real-R8 core with no POR. POR1US/POR2US add the exact NSTART callback clone and ideal2pF POR target, using500kΩ/1MΩ for nominal1/2µs RC; the existing13 MOS and native R/C remain unchanged. The added ideal POR elements are feasibility targets, not a verified native implementation. The [filled lineage](results/trial-por-historical-lineage-20261108.json) preserves this contemporaneous motive and its limits.

**Original measured observation.** All27 expected historical cases were reviewed. At SS125/light startup, the original analyzer used peak overshoot≤125mV and recovery≤10µs, with finite saved-sample recovery. These original criteria are preserved rather than replaced by later v32 gates.

| Original candidate | Peak startup overshoot | Recovery from supply-ramp end | Original two-check flag |
| --- | ---: | ---: | --- |
| CTRL, no POR | 164.042762mV | 2.243502µs | **Fail** |
| POR1US, ideal RC1µs | 23.669923mV | 2.524419µs | Pass |
| POR2US, ideal RC2µs | 1.211808mV | 2.765201µs | Pass |

**Inference/decision.** In this bounded condition, increasing nominal POR RC reduced startup peak and lengthened recovery. It does not select a universal final POR or establish all-PVT/startup/powerdown/reliability qualification. The original known failures remain: SS125/heavy PSRR100kHz9.0225dB<10dB; SS125/10ns under127.145mV/over136.376mV/up recovery2.880µs; baseline light-startup overshoot at TT/SS/FF. Saved terminal pairs were within1.2V, but that sampled result is not reliability signoff. `formal_qualification=false` remains explicit.

**First actual-bulk replay.** The new authorization targets exact historical outputs, not new design exploration. The first current-VM bulk is CTRL TT27/light line transient: VIN1.15↔1.2V,100ns edges,30µs,2ns maxstep,0.1mA,ideal1nF,0.45V reference,17 saved signals. CTRL has **no POR**. Old up/down extrema are0.900491–0.922410V and0.881074–0.900529V, with original finite-window recovery0.939279/0.950951µs. Its13-MOS/78-pair sampled peak is0.859409V. The old runner assigned no transient performance verdict; completion/source/stimulus observations are not qualification. No original cross-version numeric tolerance was recorded for this line case, so the later1mV/20ns/2mV or201-node/402-PEX contract must not be imported.

**Traceability/status.** Historical manifest SHA`c64db94ec5368a976140196e741f0e73854bc3db58d2566f07874362c454ffe0`, actual27-case review SHA`cd0c96bdd9f9ec87ae372ffa3014ca2b696073fc0a56dacdf8f9328d1c0a0179`, analyzer SHA`18c173d3a890e1e8017f3bb3900f643446674c0282ee6ad8d1c3e5bd92bfeeda`; original project-relative locators and exact input/raw identities are recorded in the small lineage. Original18.1.0.077 versus Olympus23.1 differences require observed comparison. Replay is being prepared; this entry claims no fresh result or local deletion. Controller review joins exact case/source/model closure and preserved old/new results before root-only bulk cleanup. Sources, scripts, reports and failed flags remain; derived GDS/OA/PEX additionally need complete generation closure, a verified rebuild and retained DRC/LVS/extract plus pre/post evidence. New design/parameter exploration stays on hold until local cleanup eligibility is resolved.

### Phase2 appended — original-model compatibility checked; first CTRL replay terminal

The first exact historical CTRL job `740834` was submitted with2CPUs/8GiB for the two original TT27 static references and single line transient. The controller observed `COMPLETED0:0` in21seconds. All10 original SMIC model fingerprints from the fresh VM source proof matched the installed canonical references before staging. Independent compact old/new scientific verification and exact historical-local-bulk eligibility are still pending here; scheduler completion does not supply an absent original numerical tolerance or authorize local deletion.

A separate PAM4 replay exposed a real original-VM versus prior-site model-closure mismatch and stopped before submission. That does not invalidate this LDO ten-model identity proof, nor justify weakening either project's gates. Own wrapper/compact code is archived in the access-controlled workflow repository; original netlists, licensed model bodies and private source-map locators remain excluded. A separate read-only physical-tool availability probe is being prepared; visibility/version alone will not establish IL/generator, technology/masters/rules closure or verified GDS/OA/PEX rebuilding. No new LDO design or broad derived-file deletion follows this terminal job state.

### Independent result appended — original selected observations reproduced, local retirement separate

Independent review of `740834` completed. Both original static admission gates passed; VOUT/IQ equal the old values, maximum PM difference1.4211e-14degrees and PSRR difference1.8521e-5dB. The four line extrema differ by at most2.9976e-15V, the two original finite-window recoveries by3.1341e-19s, and all78 terminal-pair peaks by1.64091e-13V. These are reported observations, not a newly selected numerical acceptance tolerance; raw byte identity is not claimed. The original unassigned transient verdict and false formal/all-LDO qualification remain unchanged.

The audit replayed1880 compact17-signal samples and220 witness rows, checked156 retained and48 protected remote hashes and22 unchanged original local source proofs. Eight compute-only support dependencies were checked by the runtime guard, not independently rehashed from the login node. Exactly two new server bulk files were removed after valid analysis:9,600,458logical bytes and3,804,160allocated bytes. The original weak PSRR/startup/heavy-load flags stay preserved. A single original VM raw candidate still needs the controller's current exact-case/hash/consumer review and separate root-only deletion receipt; no original-local deletion is declared here. Independent report SHA`879c5a38be5b06d1b557e567450b0028d12a068f0640f6fa2698afa597ee20f6` records the evidence; source bodies and private locators remain outside this journal.

### Physical-readiness result appended — available versions, no layout-rebuild claim

The corrected read-only probe `740883` completed0:0 in1second and all three version-only commands exited0: VirtuosoIC23.1-64b.ISR17.40, strmoutIC23.1-64b and Calibre2024.2_29.16. The prior probe's canonical-wrapper invocation error was repaired by preserving the configured executable's basename/directory; it was not a missing-tool result. Visibility/version does not test license usability or establish an actual layout rebuild. Original generator/technology/masters/rules closure and geometry/DRC/LVS/PEX observations remain to be reproduced or audited. That comparison may faithfully preserve an original DRC failure; it does not require modifying every failed historical layout into DRC0 before authorized bulk retirement. No CAD-generated output is retired by this version probe.

### Actual local-retirement result — one original raw independently verified

The controller retired exactly one reproduced original CTRL-line `psf/tran.tran.tran`:8,225,219logical bytes and8,228,864allocated bytes in the guest filesystem. All16 preserved source/log/scalar hashes and stat identities remained unchanged. Independent post-delete verification confirmed the target absent, all16 identities unchanged and three durable proof hashes valid. Canonical VM receipt SHA`66c3f35679260fcd29ee16e9db08ced1156a0b2db696bf94e85b76839dcf167c`; controller JSON LF-normalized SHA`2170ae0288367cab1f3c2373e88cf5a2d32f12854efc23c2ae3a72bfbcaa5517`; verifier JSON LF-normalized SHA`e70b6ed37f13af8bef7e162e1e4046a885e4e403cd8a3f6c110b389d12f6e3c2`. Different serialization/newline hashes are labeled separately rather than claimed byte-identical.

No active case/EDA/controller or accessible target-FD consumer was observed; protected-service visibility gaps remain explicit and complete FD inspection is not claimed. Exact source/model/replay/hash and one-target gates remained unchanged. This is neither Windows/VMDK shrinking, all-local-output cleanup nor whole-LDO qualification. PAM4 old-local retirement is separately on HOLD after its raw-benefit counterexample.

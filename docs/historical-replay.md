# Historical Spectre replay

The [input inventory](historical-replay-inputs.json) records 16765 historical Spectre cases, including PFAST1, R28, LDO layout and load experiments, and Buck smoke and qualification suites. It binds each case to the exact retained input bytes and recorded test conditions. Use each group's simulator command and model dependency digests with the retained local sources. The current [LDO](../projects/ldo-130nm/simulation/README.md) and [Buck](../projects/two-phase-buck/simulation/README.md) templates cover their documented revisions and stimulus sets.

Pass the locally retained case directory and the installed model entry to the
[input checker](../tools/check_historical_replay_inputs.py). The case directory
contains the original `input.scs`, `config.json` and the listed companions
where applicable. The checker verifies these bytes and the model-entry digest.
The model installation must also provide its matching transitive includes.

```sh
python tools/check_historical_replay_inputs.py --list
python tools/check_historical_replay_inputs.py b1_smoke_off "$CASE_DIR" "$MODEL_ENTRY"
```

For a replay, prepare a separate run directory with the validated inputs. Keep
companion include files beside the deck and use the matching model installation
at the location referenced by the deck. Use the following command for PFAST1
and B1.

```sh
spectre input.scs +escchars -format psfascii -raw psf +log spectre.log
```

R28 v2b uses Spectre 18.1.0.077 and an additional licensed resistor model.
Match its SHA-256 against the R28 group entry in the inventory and verify
that the model installation resolves all transitive includes. The group
command records the original warning limits.

```sh
python tools/check_historical_replay_inputs.py r28v2formal_step_tt_t27_e10 "$CASE_DIR" "$MODEL_ENTRY"
spectre input.scs +escchars -format psfascii -raw psf +log spectre.log -maxwarns 10000 -maxwarnstolog 10000
```

The LDO inputs exercise historical schematic behavior under their recorded
load and testbench conditions.
Full PSF waveforms are large generated files that can be recreated from the
retained inputs and the matching licensed simulator and models.
The B1 case was interrupted during startup, before its first load transition.
Current extracted LDO work uses the separate
[v32 fixture and matrix](../projects/ldo-130nm/simulation/README.md).

The inventory's `physical_replay_cases` section records 44 Calibre extraction cases with GDS, CDL, runset and licensed-rule digests, tool versions, and PHDB/PDB/FMT commands. Retained local GDS, CDL, matching rules and runsets rebuild the large work databases; the completed PEX exports and DRC/LVS reports remain available.

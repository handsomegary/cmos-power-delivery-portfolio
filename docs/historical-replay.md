# Historical Spectre replay

The [input inventory](historical-replay-inputs.json) identifies 34 historical
PFAST1 LDO transient runs and the early B1 Buck startup case. It ties the case
identifiers to the exact original input bytes and to the separately installed
model entry. Use the inventory with the retained local inputs and the matching
licensed model installation. The public [LDO](../projects/ldo-130nm/simulation/README.md)
and [Buck](../projects/two-phase-buck/simulation/README.md) templates cover
different revisions and stimulus sets.

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
at the location referenced by the deck. The archived command was:

```sh
spectre input.scs +escchars -format psfascii -raw psf +log spectre.log
```

The LDO inputs exercise historical schematic feasibility with ideal passives.
The B1 case was interrupted during startup, before its first load transition.
Current extracted LDO work uses the separate
[v32 fixture and matrix](../projects/ldo-130nm/simulation/README.md).

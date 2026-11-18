# Buck simulator inputs

The r8 nominal 100 ns decks reproduce the two stimulus configurations for [assist OFF](r8_nominal_100ns_off.scs.in) and [assist ON](r8_nominal_100ns_on.scs.in). Each uses the [authored Verilog-A controller](../controller/buck_control.va). The ON condition enables both the local transient assist and the coordinated controller handoff.

From the repository root with a compatible [local model binding](../../../docs/simulation-inputs.md):

```sh
python tools/stage_spectre_case.py projects/two-phase-buck/simulation/r8_nominal_100ns_on.scs.in \
  runs/buck-r8-on --models private/models.local.scs \
  --controller projects/two-phase-buck/controller/buck_control.va
(cd runs/buck-r8-on && spectre input.scs -format psfascii -raw psf +log spectre.log)
```

- r8 includes [47 case definitions](validation_all.json), [24 matched comparisons](validation_pairs.json) and the [nominal settings](nominal_parameters.json).
- r9 includes [eight case definitions](slew_all_eight.json) and [four matched comparisons](slew_pairs_eight.json).

The case JSON stores the load levels, event timing, edge lengths, solver controls and measurement windows. The r9 gate-resistance hardware and measured results are documented in the [r9 study](../results.md).

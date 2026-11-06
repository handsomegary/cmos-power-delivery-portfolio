# LDO simulator inputs

The r6 [10 ns](r6_load_10ns.scs.in) and [100 ns](r6_load_100ns.scs.in) decks preserve the measured pre-layout topology, dimensions, compensation and load stimulus. Both use 1.2 V input, 0.45 V reference, external 1 nF output capacitance and a 0.1 ↔ 5 mA load step at 27 °C.

From the repository root with a compatible [local model binding](../../../docs/simulation-inputs.md):

```sh
python tools/stage_spectre_case.py projects/ldo-130nm/simulation/r6_load_10ns.scs.in \
  runs/ldo-r6-10ns --models private/models.local.scs
(cd runs/ldo-r6-10ns && spectre input.scs -format psfascii -raw psf +log spectre.log)
```

The [v32 extracted matrix](v32_extracted_load_matrix.json) records 30 fixed conditions and the load-domain acceptance limits. The [grid24 fixture](v32_grid24_fixture.scs.in) preserves its FNSP, 27 °C, 10 ns stimulus. Bind the corresponding model sections and a locally extracted `ldo_core_bleed67_v32_build1` with pin order `VSS VIN VOUT VREF` in the local binding file. The portable fixture saves the top-level voltages and source currents. Terminal stress qualification requires the mapped internal PEX signals used by the original analysis.

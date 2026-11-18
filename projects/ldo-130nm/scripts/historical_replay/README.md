# Historical replay tools

These scripts reran the archived LDO simulations on a newer Spectre release (18.1 on the old VM, 23.1 on the cluster). They compared each new output with the archived one. Each VM output was deleted only after its comparison was saved. The tools are published to document the method. No netlists, model files or PDK content are included, and the scripts do nothing without a licensed simulator and a PDK copy of your own.

## What was replayed

| Batch | Cases | Comparison | Outcome |
| --- | --- | --- | --- |
| PSF-bearing cases | 3,220 | `psfcmp.py` on psfascii | all compared; VM outputs retired |
| Special cases (project includes, `-I` paths, psfbin) | 36 | psfbin converted to ASCII by the same `psf` utility, then `psfcmp.py` | all compared; VM outputs retired |
| Remaining cases (raw PSF, `spectre.dc`, OCEAN TSV) | 1,297 | `sprest.py`, then a per-unit floor recheck of `spectre.dc` in `spdc.py` | 0 entries at or above 1e-3 after the floor recheck; VM outputs retired |

The comparison metric is the scaled difference d = |a−b| / (max(|a|,|b|) + 1e-9·max|key|). No pass/fail tolerance is invented: each case reports the full distribution, the worst entry and any missing or extra files, keys and strings. PSF `HEADER` sections (dates and versions) are ignored.

## Layout

- `replay/`: cluster-side runners and comparators. `ldorep.py` covers the PSF-bearing batch, `sp36.py` the special cases, and `sprest.py` with `spdc.py` the remaining batch. `psfcmp.py` holds the shared comparison code. The `.sbatch` files are the Slurm wrappers.
- `vm_side/`: scripts run on the old VM to list, pack and close each batch. The `vm_delete_*.py` scripts retire VM outputs. They are dry runs unless given `--delete`, they recheck each deck's SHA-256 against the packed manifest, and they write a receipt.
- `pex/`: a topology-insensitive comparison of an old and a rebuilt parasitic netlist (`pexcmp.py`, `netcmp.py`).

## Configuration

Machine-specific paths come from the environment:

| Variable | Meaning |
| --- | --- |
| `LDO_VM_PROJECT_ROOT` | project root on the old VM, as written in the archived decks |
| `LDO_VM_PDK_ROOT` | PDK root written in the archived decks |
| `LDO_REPLAY_PDK_ROOT` | PDK root on the replay machine. The only deck change is this reversible prefix swap. |
| `CADENCE_PSF_UTILITY` | Cadence `psf` converter (default `psf` on `PATH`) |
| `CADENCE_SETUP`, `SPECTRE_BIN` | used by the `.sbatch` wrappers |

The VM-side listing scripts pass intermediate case lists through `/tmp/ldo_*.json`. The Slurm partition, QOS and account are given on the `sbatch` command line.

The offline tests in `tests/test_historical_replay_tools.py` check the comparator on synthetic psfascii files. They also check that no account paths or site install paths remain.

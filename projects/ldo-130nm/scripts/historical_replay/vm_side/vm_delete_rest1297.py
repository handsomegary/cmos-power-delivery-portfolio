#!/usr/bin/env python3
"""Delete the VM simulator outputs of the 1297 LDO cases replayed and compared on Olympus
(jobs 747706 raw_psf/OCEAN TSV + 747804 spectre.dc recheck; 1297/1297 compared, 0 errors).
Targets per case, only those that were compared: raw_psf/ (dir), spectre.dc, ocean_ac_fullprecision.tsv.
Run ON THE VM:  python3 vm_delete_rest1297.py vm_manifest.json [--delete]
Per case: input.scs sha256 must equal the sha recorded when the case was streamed; dirs must not be symlinks.
input.scs, spectre.log, ocean_export.ocn and everything else stay. Receipt written next to this script."""
import hashlib, json, os, shutil, sys, time
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
TARGET = {'raw_psf': 'raw_psf', 'spectre.dc': 'spectre.dc', 'ocean_tsv': 'ocean_ac_fullprecision.tsv'}


def size(p):
    if os.path.isdir(p):
        return sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(p) for f in fs if not os.path.islink(os.path.join(a, f)))
    return os.path.getsize(p)


man = json.load(open(sys.argv[1]))['cases']
delete = '--delete' in sys.argv[2:]
ok, skipped, total = [], [], 0
for flat, m in sorted(man.items()):
    c = os.path.join(ROOT, m['src'])
    if hashlib.sha256(open(os.path.join(c, 'input.scs'), 'rb').read()).hexdigest() != m['input_sha256']:
        skipped.append([m['src'], 'input.scs changed']); continue
    for t in m['targets']:
        p = os.path.join(c, TARGET[t])
        if os.path.islink(p) or not os.path.exists(p):
            skipped.append([m['src'] + '/' + TARGET[t], 'absent or symlink']); continue
        b = size(p); total += b; ok.append([m['src'] + '/' + TARGET[t], b])
        if delete:
            shutil.rmtree(p) if os.path.isdir(p) else os.unlink(p)
rec = dict(mode='DELETED' if delete else 'DRY_RUN', time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), root=ROOT,
           evidence='Olympus ~/PMIC/LDO/historical_psf_rest1297_20261111.CtIc1L results.json + results_dc.json (1297/1297 compared, 0 errors)',
           items=len(ok), bytes=total, skipped=skipped, removed=ok)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vm_rest1297_delete_receipt_%s.json' % rec['mode'].lower())
json.dump(rec, open(out, 'w'), indent=0)
print(rec['mode'], 'items', len(ok), 'MB %.1f' % (total / 1e6), 'skipped', len(skipped), '->', out)
for s in skipped[:10]:
    print('  SKIP', *s)

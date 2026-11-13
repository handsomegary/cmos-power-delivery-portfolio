#!/usr/bin/env python3
"""Delete the VM simulator-output directories (psf/, raw_psf/, native_ascii/) of the 36 special LDO cases that were
replayed and compared on Olympus (jobs 747688 + 747695, 36/36 compared, 0 errors).
Run ON THE VM:  python3 vm_delete_special36.py vm_manifest.json [--delete]
Per case: input.scs sha256 must equal the sha recorded when the case was streamed; each target must be a real
directory (not a symlink). input.scs, spectre.log, stability/ and everything else stay. Receipt written next to it."""
import hashlib, json, os, shutil, sys, time
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
TARGETS = ('psf', 'raw_psf', 'native_ascii')


def size(d):
    return sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(d) for f in fs if not os.path.islink(os.path.join(a, f)))


man = json.load(open(sys.argv[1]))['cases']
delete = '--delete' in sys.argv[2:]
ok, skipped, total = [], [], 0
for flat, m in sorted(man.items()):
    c = os.path.join(ROOT, m['src'])
    if hashlib.sha256(open(os.path.join(c, 'input.scs'), 'rb').read()).hexdigest() != m['input_sha256']:
        skipped.append([m['src'], 'input.scs changed']); continue
    for t in TARGETS:
        p = os.path.join(c, t)
        if os.path.islink(p):
            skipped.append([m['src'] + '/' + t, 'symlink']); continue
        if os.path.isdir(p):
            b = size(p); total += b; ok.append([m['src'] + '/' + t, b])
            if delete:
                shutil.rmtree(p)
rec = dict(mode='DELETED' if delete else 'DRY_RUN', time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), root=ROOT,
           evidence='Olympus ~/PMIC/LDO/historical_psf_special36_20261111.LfI1A5/results.json (36/36 compared, 0 errors)',
           dirs=len(ok), bytes=total, skipped=skipped, removed=ok)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vm_special36_delete_receipt_%s.json' % rec['mode'].lower())
json.dump(rec, open(out, 'w'), indent=0)
print(rec['mode'], 'dirs', len(ok), 'MB %.1f' % (total / 1e6), 'skipped', len(skipped), '->', out)

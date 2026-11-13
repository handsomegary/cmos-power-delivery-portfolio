#!/usr/bin/env python3
"""Delete the VM psf/ directories of the 3220 LDO cases replayed and compared on Olympus (job 743487).

Run ON THE VM:  python3 vm_delete_analyzed_psf.py vm_manifest.json            (dry run, deletes nothing)
                python3 vm_delete_analyzed_psf.py vm_manifest.json --delete   (deletes)

Per case it requires: case dir exists, input.scs sha256 == the sha recorded when the case was streamed to
Olympus (so the deck that was replayed is the deck sitting next to this psf/), psf/ is a real directory
(not a symlink). Only <case>/psf is removed; input.scs, spectre.log and everything else stay.
A receipt JSON is written next to this script either way."""
import hashlib, json, os, shutil, sys, time

ROOT = os.environ['LDO_VM_PROJECT_ROOT']


def size(d):
    n = 0
    for a, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(a, f)
            if not os.path.islink(p):
                n += os.path.getsize(p)
    return n


def main():
    man = json.load(open(sys.argv[1]))
    delete = '--delete' in sys.argv[2:]
    ok, skipped, total = [], [], 0
    for flat, m in sorted(man.items()):
        c = os.path.join(ROOT, m['src'])
        psf = os.path.join(c, 'psf')
        try:
            sha = hashlib.sha256(open(os.path.join(c, 'input.scs'), 'rb').read()).hexdigest()
        except OSError as e:
            skipped.append([m['src'], 'input.scs unreadable: ' + str(e)]); continue
        if sha != m['input_sha256']:
            skipped.append([m['src'], 'input.scs changed since replay']); continue
        if os.path.islink(psf) or not os.path.isdir(psf):
            skipped.append([m['src'], 'psf/ absent or symlink']); continue
        b = size(psf); total += b
        if delete:
            shutil.rmtree(psf)
        ok.append([m['src'], b])
    rec = dict(mode='DELETED' if delete else 'DRY_RUN', time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), root=ROOT,
               evidence='Olympus job 743487, ~/PMIC/LDO/historical_psf_replay3220_20261110.CW7rfm/results.json (3220/3220 compared, 0 errors)',
               cases=len(ok), bytes=total, skipped=skipped, removed=ok)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vm_psf_delete_receipt_%s.json' % rec['mode'].lower())
    json.dump(rec, open(out, 'w'), indent=0)
    print(rec['mode'], 'cases', len(ok), 'MB %.1f' % (total / 1e6), 'skipped', len(skipped), '->', out)
    for s in skipped[:20]:
        print('  SKIP', *s)


if __name__ == '__main__':
    main()

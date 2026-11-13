#!/usr/bin/env python3
"""Historical LDO PSF-bearing case replay (VM Spectre 18.1 -> Olympus Spectre 23.1).
Each case directory under cases/ holds the ORIGINAL input.scs, spectre.log (for the original command line) and
old_psf/ (the original VM PSF copied for comparison only). The only deck change is the SMIC PDK-root prefix
(asserted present at least once and reversible); the 44-file model tree was verified identical on VM and Olympus.
Command = original flags (+escchars/-format psfascii/-raw psf/+log, maxwarns as originally), SPECTRE_DEFAULTS=-E.
The new PSF is compared with psfcmp.compare_dirs; then the new PSF and the copied old PSF are removed on Olympus.
Resumable: out/<case>.json per finished case; deadline-aware."""
import concurrent.futures, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
OLD = os.environ['LDO_VM_PDK_ROOT']
NEW = os.environ['LDO_REPLAY_PDK_ROOT']
BUILD = '23.1.0.722.isr15'


def wj(p, v):
    t = Path(str(p) + '.tmp'); t.write_text(json.dumps(v, indent=1, sort_keys=True, default=str) + '\n'); t.replace(p)


def flags(log):
    m = re.search(r'Command line:\s*\n(.+?)\n\s*\n', log, re.S)
    if not m:
        raise RuntimeError('no command line')
    toks = re.sub(r'\\\s*\n', ' ', m.group(1)).replace('\\', ' ').split()
    if not toks[0].endswith('/spectre') or toks[1:3] != ['-64', 'input.scs']:
        raise RuntimeError('unexpected command ' + ' '.join(toks[:3]))
    rest = toks[3:]
    if any(t.startswith('-I') for t in rest):
        raise RuntimeError('include-path case not in simple set')
    if rest[rest.index('-format') + 1] != 'psfascii' or rest[rest.index('-raw') + 1] != 'psf':
        raise RuntimeError('not psfascii/psf')
    return ['spectre', '-64', 'input.scs'] + rest


def main():
    run = Path.cwd().resolve(); sys.path.insert(0, str(run))
    import psfcmp
    (run / 'out').mkdir(exist_ok=True)
    t0 = time.time(); limit = int(os.environ.get('LDO_WALL_S', '40000'))
    cases = sorted(p.name for p in (run / 'cases').iterdir() if p.is_dir())
    env = dict(os.environ, SPECTRE_DEFAULTS='-E', LC_ALL='C', OMP_NUM_THREADS='1')

    def one(c):
        outp = run / 'out' / (c + '.json')
        if outp.exists():
            return 'done'
        if time.time() > t0 + limit:
            return 'deferred'
        d = run / 'cases' / c
        try:
            log = (d / 'orig_spectre.log').read_text(errors='replace')
            cmd = flags(log)
            src = (d / 'input.scs').read_text(errors='replace')
            need = src.count(OLD)
            if need < 1:
                raise RuntimeError('PDK prefix absent')
            w = run / 'work' / c
            if w.exists():
                shutil.rmtree(str(w))
            w.mkdir(parents=True)
            out = src.replace(OLD, NEW)
            if out.replace(NEW, OLD) != src or NEW in src:
                raise RuntimeError('non-reversible')
            (w / 'input.scs').write_text(out)
            s = time.monotonic()
            with (w / 'console.log').open('w') as f:
                rc = subprocess.run(cmd, cwd=str(w), env=env, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, timeout=3600).returncode
            nlog = (w / 'spectre.log').read_text(errors='replace') if (w / 'spectre.log').exists() else ''
            old_ok = re.findall(r'spectre completes with (\d+) errors?', log)
            new_ok = re.findall(r'spectre completes with (\d+) errors?', nlog)
            res = dict(case=c, rc=rc, build_ok=BUILD in nlog, seconds=round(time.monotonic() - s, 1),
                       old_completion=old_ok[-1:] , new_completion=new_ok[-1:],
                       old_terminated='terminated prematurely' in log, new_terminated='terminated prematurely' in nlog)
            if (w / 'psf').is_dir():
                res['cmp'] = psfcmp.compare_dirs(d / 'old_psf', w / 'psf')
            else:
                res['cmp'] = None
            wj(outp, res)
            shutil.rmtree(str(w)); shutil.rmtree(str(d / 'old_psf'))
            return 'ran'
        except Exception as e:
            wj(outp, dict(case=c, error=type(e).__name__ + ': ' + str(e)))
            w = run / 'work' / c
            if w.exists():
                shutil.rmtree(str(w))
            return 'error'
    counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get('LDO_WORKERS', '6'))) as pool:
        for r in pool.map(one, cases):
            counts[r] = counts.get(r, 0) + 1
    done = [json.loads(p.read_text()) for p in (run / 'out').glob('*.json')]
    hist = {}
    agg = dict(total=len(cases), finished=len(done), this_job=counts, errors=[x for x in done if 'error' in x][:30], n_errors=sum('error' in x for x in done),
               completion_mismatch=[x['case'] for x in done if 'error' not in x and (x['old_completion'] != x['new_completion'] or x['old_terminated'] != x['new_terminated'])][:50],
               files_or_keys_or_length_diff=[], string_diff_cases=[], max_d_cases={})
    for x in done:
        c = x.get('cmp')
        if not c:
            continue
        for k, v in c['d_hist'].items():
            hist[k] = hist.get(k, 0) + v
        if c['files_missing'] or c['files_extra'] or c['keys_missing'] or c['keys_extra'] or c['length_diffs']:
            agg['files_or_keys_or_length_diff'].append(x['case'])
        if c['string_diffs']:
            agg['string_diff_cases'].append(x['case'])
        b = '<1e-9' if c['max_d'] < 1e-9 else '<1e-6' if c['max_d'] < 1e-6 else '<1e-4' if c['max_d'] < 1e-4 else '<1e-3' if c['max_d'] < 1e-3 else '<1e-2' if c['max_d'] < 1e-2 else '>=1e-2'
        agg['max_d_cases'][b] = agg['max_d_cases'].get(b, 0) + 1
    agg['number_d_hist'] = hist
    agg['worst_cases'] = sorted(([x['case'], x['cmp']['max_d'], x['cmp']['worst']] for x in done if x.get('cmp')), key=lambda r: -r[1])[:25]
    agg['files_or_keys_or_length_diff_n'] = len(agg['files_or_keys_or_length_diff']); agg['files_or_keys_or_length_diff'] = agg['files_or_keys_or_length_diff'][:50]
    agg['string_diff_n'] = len(agg['string_diff_cases']); agg['string_diff_cases'] = agg['string_diff_cases'][:50]
    wj(run / 'results.json', agg)
    print('LDOREP_END', json.dumps({k: agg[k] for k in ('total', 'finished', 'n_errors', 'max_d_cases', 'files_or_keys_or_length_diff_n', 'string_diff_n')}), flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""spectre.dc re-comparison for the LDO rest-1297 replay (same decks/commands/substitutions as sprest.py).
Metric (per unit, as psfcmp does per key): d = |a-b| / (max(|a|,|b|) + 1e-9 * max|value| over the same unit in the old file).
Also keeps the plain relative difference. Every entry with d >= 1e-6 is stored (capped), not only the worst.
Old spectre.dc copies were re-streamed from the VM to cases/<c>/old_spectre.dc. Output: out_dc/<case>.json."""
import concurrent.futures, collections, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
OLD = os.environ['LDO_VM_PDK_ROOT']
NEW = os.environ['LDO_REPLAY_PDK_ROOT']
BUILD = '23.1.0.722.isr15'


def wj(p, v):
    t = Path(str(p) + '.tmp'); t.write_text(json.dumps(v, indent=1, sort_keys=True, default=str) + '\n'); t.replace(p)


def bucket(d):
    return '0' if d == 0 else '<1e-12' if d < 1e-12 else '<1e-9' if d < 1e-9 else '<1e-6' if d < 1e-6 else '<1e-4' if d < 1e-4 else '<1e-3' if d < 1e-3 else '<1e-2' if d < 1e-2 else '>=1e-2'


def read_dc(p):
    out = {}
    for line in Path(p).read_text(errors='replace').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        body, _, comment = line.partition('#')
        t = body.split()
        unit = 'V'
        m = re.search(r'unit\s+(\S+)', comment)
        if m:
            unit = m.group(1)
        try:
            out[t[0]] = (float(t[1]), unit)
        except (ValueError, IndexError):
            out[t[0]] = (' '.join(t[1:]), unit)
    return out


def cmp_dc(a, b):
    scale = collections.defaultdict(float)
    for v, u in a.values():
        if isinstance(v, float):
            scale[u] = max(scale[u], abs(v))
    h = collections.Counter(); hr = collections.Counter(); big = []; mx = 0.0; worst = None; strd = 0; units = collections.Counter()
    for k in sorted(set(a) & set(b)):
        (u, un), (v, _) = a[k], b[k]
        if isinstance(u, float) and isinstance(v, float):
            units[un] += 1
            rel = 0.0 if u == v else abs(u - v) / max(abs(u), abs(v))
            d = 0.0 if u == v else abs(u - v) / (max(abs(u), abs(v)) + 1e-9 * scale[un])
            h[bucket(d)] += 1; hr[bucket(rel)] += 1
            if d >= 1e-6:
                big.append([k, un, u, v, d])
            if d > mx:
                mx, worst = d, dict(key=k, unit=un, old=u, new=v, d=d, rel=rel)
        elif u != v:
            strd += 1
    big.sort(key=lambda r: -r[4])
    return dict(n=len(set(a) & set(b)), n_missing=len(set(a) - set(b)), n_extra=len(set(b) - set(a)), string_diffs=strd, units=dict(units),
                unit_scale=dict(scale), hist_floor=dict(h), hist_plain_rel=dict(hr), max_d=mx, worst=worst, n_d_ge_1e6=len(big), entries_d_ge_1e6=big[:200])


def main():
    run = Path.cwd().resolve()
    man = json.loads((run / 'vm_manifest.json').read_text())
    mirror = run / 'mirror'
    (run / 'out_dc').mkdir(exist_ok=True)
    env = dict(os.environ, SPECTRE_DEFAULTS='-E', LC_ALL='C', OMP_NUM_THREADS='1')
    cases = sorted(c for c, m in man['cases'].items() if 'spectre.dc' in m['targets'])

    def one(c):
        outp = run / 'out_dc' / (c + '.json')
        if outp.exists():
            return 'done'
        d = run / 'cases' / c; w = run / 'work_dc' / c; m = man['cases'][c]
        try:
            src = (d / 'input.scs').read_text(errors='replace')
            mr = str(mirror)
            out = src.replace(ROOT, mr).replace(OLD, NEW)
            if out.replace(NEW, OLD).replace(mr, ROOT) != src:
                raise RuntimeError('non-reversible substitution')
            cmd = ['spectre'] + [t.replace(ROOT, mr) if t.startswith('-I') else t for t in m['cmd'][1:]]
            if w.exists():
                shutil.rmtree(str(w))
            w.mkdir(parents=True); (w / 'input.scs').write_text(out)
            s = time.monotonic()
            with (w / 'console.log').open('w') as f:
                rc = subprocess.run(cmd, cwd=str(w), env=env, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, timeout=3600).returncode
            nlog = (w / 'spectre.log').read_text(errors='replace') if (w / 'spectre.log').exists() else ''
            res = dict(case=c, rc=rc, build_ok=BUILD in nlog, seconds=round(time.monotonic() - s, 1),
                       new_completion=re.findall(r'spectre completes with (\d+) errors?', nlog)[-1:])
            if not (w / 'spectre.dc').exists():
                res['dc_cmp'] = None; res['kept_for_diagnosis'] = True
                wj(outp, res); return 'kept'
            res['dc_cmp'] = cmp_dc(read_dc(d / 'old_spectre.dc'), read_dc(w / 'spectre.dc'))
            wj(outp, res)
            shutil.rmtree(str(w)); (d / 'old_spectre.dc').unlink()
            return 'ran'
        except Exception as e:
            wj(outp, dict(case=c, error=type(e).__name__ + ': ' + str(e)[:400]))
            return 'error'

    counts = collections.Counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get('SP_WORKERS', '6'))) as pool:
        for r in pool.map(one, cases):
            counts[r] += 1
    rows = [json.loads(p.read_text()) for p in (run / 'out_dc').glob('*.json')]
    ok = [x for x in rows if x.get('dc_cmp')]
    agg = dict(total=len(cases), finished=len(rows), this_job=dict(counts), errors=[(x['case'], x['error']) for x in rows if 'error' in x],
               kept=[x['case'] for x in rows if x.get('kept_for_diagnosis')], rc_nonzero=[x['case'] for x in rows if x.get('rc') not in (0, None)],
               max_d_hist=dict(collections.Counter(bucket(x['dc_cmp']['max_d']) for x in ok)),
               number_hist_floor=dict(sum((collections.Counter(x['dc_cmp']['hist_floor']) for x in ok), collections.Counter())),
               number_hist_plain=dict(sum((collections.Counter(x['dc_cmp']['hist_plain_rel']) for x in ok), collections.Counter())),
               cases_with_d_ge_1e3=[(x['case'], x['dc_cmp']['max_d'], x['dc_cmp']['worst']) for x in ok if x['dc_cmp']['max_d'] >= 1e-3][:60],
               missing_extra=[(x['case'], x['dc_cmp']['n_missing'], x['dc_cmp']['n_extra']) for x in ok if x['dc_cmp']['n_missing'] or x['dc_cmp']['n_extra']][:30])
    wj(run / 'results_dc.json', agg)
    print('SPDC_END', json.dumps(dict(total=agg['total'], finished=agg['finished'], errors=len(agg['errors']), kept=len(agg['kept']), max_d_hist=agg['max_d_hist'])), flush=True)


if __name__ == '__main__':
    main()

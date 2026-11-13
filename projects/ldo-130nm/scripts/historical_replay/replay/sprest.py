#!/usr/bin/env python3
"""Replay of the remaining historical LDO cases whose VM simulator outputs were never compared:
raw_psf/ directories outside the earlier sets, Spectre DC checkpoint files (spectre.dc) and OCEAN full-precision AC
exports (ocean_ac_fullprecision.tsv). Same rules as the 3220/36 replays: original input.scs; reversible substitutions
of the VM project root (-> mirror/) and SMIC PDK root only; original command (-I rewritten by the same substitution);
SPECTRE_DEFAULTS=-E. Comparisons, without invented tolerance:
  raw_psf    old vs new raw output dir, both converted to ASCII by the same Olympus IC23.1 psf utility, psfcmp;
  spectre.dc node-by-node numeric comparison;
  ocean_tsv  the original ocean_export.ocn re-run (paths only rewritten) on the new raw output with IC23.1 OCEAN,
             17-digit TSVs compared per (signal, frequency) point.
Resumable (out/<case>.json); new outputs and the Olympus copies of old outputs are removed after comparison."""
import concurrent.futures, hashlib, json, math, os, re, shutil, subprocess, sys, time, collections
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
OLD = os.environ['LDO_VM_PDK_ROOT']
NEW = os.environ['LDO_REPLAY_PDK_ROOT']
PSF = os.environ.get('CADENCE_PSF_UTILITY', 'psf')
BUILD = '23.1.0.722.isr15'


def wj(p, v):
    t = Path(str(p) + '.tmp'); t.write_text(json.dumps(v, indent=1, sort_keys=True, default=str) + '\n'); t.replace(p)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bucket(d):
    return '0' if d == 0 else '<1e-12' if d < 1e-12 else '<1e-9' if d < 1e-9 else '<1e-6' if d < 1e-6 else '<1e-4' if d < 1e-4 else '<1e-3' if d < 1e-3 else '<1e-2' if d < 1e-2 else '>=1e-2'


def to_ascii(src, dst):
    dst.mkdir(parents=True, exist_ok=True); conv = {}
    for f in sorted(src.iterdir()):
        if not f.is_file():
            continue
        if f.read_bytes()[:6].startswith(b'HEADER') or f.name == 'logFile' or f.suffix == '.json':
            shutil.copyfile(str(f), str(dst / f.name)); conv[f.name] = 'copied'; continue
        r = subprocess.run([PSF, '-i', str(f), '-o', str(dst / f.name)], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
        ok = r.returncode == 0 and (dst / f.name).exists() and (dst / f.name).read_bytes()[:6] == b'HEADER'
        conv[f.name] = 'converted' if ok else 'FAILED rc=%s %s' % (r.returncode, (r.stdout + r.stderr)[-300:])
    return conv


def read_dc(p):
    out = {}
    for line in Path(p).read_text(errors='replace').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        t = line.split()
        try:
            out[t[0]] = float(t[1])
        except (ValueError, IndexError):
            out[t[0]] = ' '.join(t[1:])
    return out


def cmp_dc(a, b):
    h = collections.Counter(); worst = None; mx = 0.0; strd = 0
    for k in sorted(set(a) & set(b)):
        u, v = a[k], b[k]
        if isinstance(u, float) and isinstance(v, float):
            d = 0.0 if u == v else abs(u - v) / max(abs(u), abs(v))
            h[bucket(d)] += 1
            if d > mx:
                mx, worst = d, dict(key=k, old=u, new=v)
        elif u != v:
            strd += 1
    return dict(n=len(set(a) & set(b)), missing=sorted(set(a) - set(b))[:10], n_missing=len(set(a) - set(b)), n_extra=len(set(b) - set(a)),
                string_diffs=strd, hist=dict(h), max_rel=mx, worst=worst)


def read_tsv(p):
    rows = {}; seen = collections.Counter()
    for line in Path(p).read_text().splitlines()[1:]:
        s, f, re_, im = line.split('\t')
        i = seen[s]; seen[s] += 1
        rows[(s, i)] = (float(f), complex(float(re_), float(im)))
    return rows


def cmp_tsv(a, b):
    h = collections.Counter(); mx = 0.0; worst = None; fmx = 0.0
    scale = collections.defaultdict(float)
    for (s, i), (f, z) in a.items():
        scale[s] = max(scale[s], abs(z))
    for k in sorted(set(a) & set(b)):
        (fa, za), (fb, zb) = a[k], b[k]
        fmx = max(fmx, abs(fa - fb) / max(abs(fa), abs(fb), 1e-300))
        den = max(abs(za), abs(zb)) + 1e-9 * scale[k[0]]
        d = 0.0 if za == zb else (abs(za - zb) / den if den > 0 else 0.0)
        h[bucket(d)] += 1
        if d > mx:
            mx, worst = d, dict(signal=k[0], index=k[1], freq=fa, old=[za.real, za.imag], new=[zb.real, zb.imag])
    return dict(points=len(set(a) & set(b)), n_missing=len(set(a) - set(b)), n_extra=len(set(b) - set(a)), freq_max_rel=fmx,
                hist=dict(h), max_d=mx, worst=worst)


def main():
    run = Path.cwd().resolve(); sys.path.insert(0, str(run))
    import psfcmp
    man = json.loads((run / 'vm_manifest.json').read_text())
    mirror = run / 'mirror'
    bad = [k for k, h in man['deps'].items() if sha(mirror / k) != h]
    if bad:
        raise SystemExit('mirror sha mismatch: %s' % bad[:5])
    (run / 'out').mkdir(exist_ok=True)
    t0 = time.time(); limit = int(os.environ.get('SP_WALL_S', '20000'))
    env = dict(os.environ, SPECTRE_DEFAULTS='-E', LC_ALL='C', OMP_NUM_THREADS='1')

    def one(c):
        outp = run / 'out' / (c + '.json')
        if outp.exists():
            return 'done'
        if time.time() > t0 + limit:
            return 'deferred'
        d = run / 'cases' / c; w = run / 'work' / c; m = man['cases'][c]
        try:
            src = (d / 'input.scs').read_text(errors='replace')
            if sha(d / 'input.scs') != m['input_sha256']:
                raise RuntimeError('deck sha differs from VM manifest')
            mr = str(mirror)
            if mr in src or NEW in src:
                raise RuntimeError('target prefixes already present')
            out = src.replace(ROOT, mr).replace(OLD, NEW)
            if out.replace(NEW, OLD).replace(mr, ROOT) != src:
                raise RuntimeError('non-reversible substitution')
            toks = list(m['cmd'])
            cmd = ['spectre'] + [t.replace(ROOT, mr) if t.startswith('-I') else t for t in toks[1:]]
            fmt = toks[toks.index('-format') + 1] if '-format' in toks else 'psfascii'
            raw = toks[toks.index('-raw') + 1] if '-raw' in toks else 'psf'
            if w.exists():
                shutil.rmtree(str(w))
            w.mkdir(parents=True); (w / 'input.scs').write_text(out)
            s = time.monotonic()
            with (w / 'console.log').open('w') as f:
                rc = subprocess.run(cmd, cwd=str(w), env=env, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, timeout=3600).returncode
            nlog = (w / 'spectre.log').read_text(errors='replace') if (w / 'spectre.log').exists() else ''
            olog = (d / 'orig_spectre.log').read_text(errors='replace')
            oc = re.findall(r'spectre completes with (\d+) errors?', olog); nc = re.findall(r'spectre completes with (\d+) errors?', nlog)
            res = dict(case=c, src=m['src'], targets=m['targets'], rc=rc, build_ok=BUILD in nlog, seconds=round(time.monotonic() - s, 1), fmt=fmt, raw=raw,
                       old_completion=oc[-1:], new_completion=nc[-1:], old_terminated='terminated prematurely' in olog, new_terminated='terminated prematurely' in nlog)
            ok = True
            if 'raw_psf' in m['targets']:
                if (w / raw).is_dir():
                    if fmt == 'psfbin':
                        res['convert_old'] = to_ascii(d / 'old_raw', w / 'cmp_old'); res['convert_new'] = to_ascii(w / raw, w / 'cmp_new')
                        res['raw_cmp'] = psfcmp.compare_dirs(w / 'cmp_old', w / 'cmp_new')
                        ok &= not any(str(v).startswith('FAILED') for k in ('convert_old', 'convert_new') for v in res[k].values())
                    else:
                        res['raw_cmp'] = psfcmp.compare_dirs(d / 'old_raw', w / raw)
                else:
                    ok = False; res['raw_cmp'] = None
            if 'spectre.dc' in m['targets']:
                if (w / 'spectre.dc').exists():
                    res['dc_cmp'] = cmp_dc(read_dc(d / 'old_spectre.dc'), read_dc(w / 'spectre.dc'))
                else:
                    ok = False; res['dc_cmp'] = None
            if 'ocean_tsv' in m['targets']:
                ocn = (d / 'ocean_export.ocn').read_text()
                case_root = ROOT + '/' + m['src']
                need_raw = ocn.count(case_root + '/raw_psf') + ocn.count(case_root + '/' + raw)
                new_ocn = ocn.replace(case_root + '/ocean_ac_fullprecision.tsv', str(w / 'new_ocean.tsv')).replace(case_root + '/' + raw, str(w / raw))
                if ROOT in new_ocn or need_raw < 1:
                    ok = False; res['tsv_cmp'] = dict(error='ocean script paths not as expected')
                else:
                    (w / 'replay.ocn').write_text(new_ocn)
                    od = w / 'ocean_cwd'; od.mkdir()
                    r = subprocess.run(['ocean', '-nograph', '-nocdsinit', '-restore', str(w / 'replay.ocn')], cwd=str(od), env=env, stdin=subprocess.DEVNULL,
                                       capture_output=True, text=True, timeout=900)
                    res['ocean_rc'] = r.returncode; res['ocean_tail'] = (r.stdout + r.stderr)[-300:]
                    if (w / 'new_ocean.tsv').exists():
                        res['tsv_cmp'] = cmp_tsv(read_tsv(d / 'old_ocean.tsv'), read_tsv(w / 'new_ocean.tsv'))
                    else:
                        ok = False; res['tsv_cmp'] = None
            if not ok:
                res['kept_for_diagnosis'] = True
                wj(outp, res); return 'kept'
            wj(outp, res)
            shutil.rmtree(str(w))
            for x in ('old_raw', 'old_spectre.dc', 'old_ocean.tsv'):
                p = d / x
                if p.is_dir():
                    shutil.rmtree(str(p))
                elif p.exists():
                    p.unlink()
            return 'ran'
        except Exception as e:
            wj(outp, dict(case=c, src=m.get('src'), error=type(e).__name__ + ': ' + str(e)[:600]))
            return 'error'

    cases = sorted(man['cases'], key=lambda c: ('ocean_tsv' not in man['cases'][c]['targets'], 'raw_psf' not in man['cases'][c]['targets'], c))
    if os.environ.get('SP_ONLY'):
        cases = cases[:int(os.environ['SP_ONLY'])]
    counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get('SP_WORKERS', '6'))) as pool:
        for r in pool.map(one, cases):
            counts[r] = counts.get(r, 0) + 1
    done = [json.loads((run / 'out' / (c + '.json')).read_text()) for c in cases if (run / 'out' / (c + '.json')).exists()]
    agg = dict(total=len(cases), finished=len(done), this_job=counts, errors=[(x['case'], x['error']) for x in done if 'error' in x][:50],
               n_errors=sum('error' in x for x in done), kept=[x['case'] for x in done if x.get('kept_for_diagnosis')],
               rc_nonzero=[x['case'] for x in done if x.get('rc') not in (0, None)],
               completion_mismatch=[x['case'] for x in done if 'error' not in x and (x['old_completion'] != x['new_completion'] or x['old_terminated'] != x['new_terminated'])])
    for key, field in (('raw_psf', 'raw_cmp'), ('spectre.dc', 'dc_cmp'), ('ocean_tsv', 'tsv_cmp')):
        rows = [x for x in done if 'error' not in x and x.get(field)]
        mx = [(x[field].get('max_d', x[field].get('max_rel', 0.0)) or 0.0, x['case']) for x in rows]
        h = collections.Counter(bucket(v) for v, _ in mx)
        agg[key] = dict(cases=len(rows), max_per_case_hist=dict(h), worst=sorted(mx, reverse=True)[:8],
                        structure=dict(files_missing=collections.Counter(f for x in rows for f in x[field].get('files_missing', [])),
                                       files_extra=collections.Counter(f for x in rows for f in x[field].get('files_extra', [])),
                                       n_missing=sum(x[field].get('n_missing', 0) for x in rows), n_extra=sum(x[field].get('n_extra', 0) for x in rows)))
    wj(run / 'results.json', agg)
    print('SPREST_END', json.dumps(dict(total=agg['total'], finished=agg['finished'], errors=agg['n_errors'], kept=len(agg['kept']))), flush=True)


if __name__ == '__main__':
    main()

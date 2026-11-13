#!/usr/bin/env python3
"""Replay of the 36 'special' historical LDO cases (project includes / -I search paths / psfbin) on Olympus.
Inputs per case: original input.scs, orig_spectre.log, old_psf/ (+ old_raw_psf/, old_native_ascii/ when present).
Project files referenced by the decks are mirrored under mirror/ with their VM-relative paths (sha256 checked
against vm_manifest.json). Only two reversible prefix substitutions are applied: the VM project root -> mirror/,
and the SMIC PDK root -> the Olympus copy (44-file model tree verified identical). The command is the original
one (same flags, -I rewritten by the same root substitution), SPECTRE_DEFAULTS=-E.
Comparison target = the directory Spectre originally wrote (-raw). psfbin outputs, old and new, are converted to
ASCII with the same Olympus IC23.1 'psf' utility and compared with psfcmp (no tolerance invented).
Resumable (out/<case>.json); new outputs and the Olympus copies of old outputs are removed after comparison."""
import concurrent.futures, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
OLD = os.environ['LDO_VM_PDK_ROOT']
NEW = os.environ['LDO_REPLAY_PDK_ROOT']
PSF = os.environ.get('CADENCE_PSF_UTILITY', 'psf')
BUILD = '23.1.0.722.isr15'
BS = chr(92)


def wj(p, v):
    t = Path(str(p) + '.tmp'); t.write_text(json.dumps(v, indent=1, sort_keys=True, default=str) + '\n'); t.replace(p)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def to_ascii(src, dst):
    """Convert every PSF file in src to ASCII in dst with the Olympus psf utility; ASCII files are copied."""
    dst.mkdir(parents=True, exist_ok=True); conv = {}
    for f in sorted(src.iterdir()):
        if not f.is_file():
            continue
        head = f.read_bytes()[:6]
        if head.startswith(b'HEADER') or f.name == 'logFile' or f.suffix == '.json':
            shutil.copyfile(str(f), str(dst / f.name)); conv[f.name] = 'copied'
            continue
        r = subprocess.run([PSF, '-i', str(f), '-o', str(dst / f.name)], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
        ok = r.returncode == 0 and (dst / f.name).exists() and (dst / f.name).read_bytes()[:6] == b'HEADER'
        conv[f.name] = 'converted' if ok else 'FAILED rc=%s %s' % (r.returncode, (r.stdout + r.stderr)[-300:])
    return conv


def main():
    run = Path.cwd().resolve(); sys.path.insert(0, str(run))
    import psfcmp
    man = json.loads((run / 'vm_manifest.json').read_text())
    mirror = run / 'mirror'
    bad = [k for k, h in man['deps'].items() if sha(mirror / k) != h]
    if bad:
        raise SystemExit('mirror sha mismatch: %s' % bad[:5])
    (run / 'out').mkdir(exist_ok=True)
    t0 = time.time(); limit = int(os.environ.get('SP_WALL_S', '6000'))
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
            if hashlib.sha256(src.encode('utf-8', 'surrogateescape')).hexdigest() != m['input_sha256'] and sha(d / 'input.scs') != m['input_sha256']:
                raise RuntimeError('deck sha differs from VM manifest')
            mr = str(mirror)
            if mr in src or NEW in src:
                raise RuntimeError('target prefixes already present')
            out = src.replace(ROOT, mr).replace(OLD, NEW)
            if out.replace(NEW, OLD).replace(mr, ROOT) != src:
                raise RuntimeError('non-reversible substitution')
            toks = list(m['cmd'])
            if not toks[0].endswith('/spectre') or toks[1:3] != ['-64', 'input.scs']:
                raise RuntimeError('unexpected command')
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
            res = dict(case=c, src=m['src'], rc=rc, build_ok=BUILD in nlog, seconds=round(time.monotonic() - s, 1), fmt=fmt, raw=raw,
                       old_completion=oc[-1:], new_completion=nc[-1:],
                       old_terminated='terminated prematurely' in olog, new_terminated='terminated prematurely' in nlog)
            old_dir = d / ('old_raw_psf' if raw == 'raw_psf' else 'old_psf')
            new_dir = w / raw
            if not old_dir.is_dir():
                raise RuntimeError('original output dir %s absent' % old_dir.name)
            if new_dir.is_dir():
                if fmt == 'psfbin':
                    res['convert_old'] = to_ascii(old_dir, w / 'cmp_old'); res['convert_new'] = to_ascii(new_dir, w / 'cmp_new')
                    a, b = w / 'cmp_old', w / 'cmp_new'
                else:
                    a, b = old_dir, new_dir
                res['cmp'] = psfcmp.compare_dirs(a, b)
                # converter check: VM-side ASCII copy (made with the VM 18.1 tool) vs Olympus conversion of the same old binary
                vm_ascii = d / ('old_psf' if raw == 'raw_psf' else 'old_native_ascii')
                if fmt == 'psfbin' and vm_ascii.is_dir():
                    res['converter_check'] = psfcmp.compare_dirs(vm_ascii, a)
            else:
                res['cmp'] = None
            failed = any(str(v).startswith('FAILED') for k in ('convert_old', 'convert_new') for v in res.get(k, {}).values())
            if failed or res['cmp'] is None:
                res['kept_for_diagnosis'] = True
                wj(outp, res)
                return 'kept'
            wj(outp, res)
            shutil.rmtree(str(w))
            for x in ('old_psf', 'old_raw_psf', 'old_native_ascii'):
                if (d / x).exists():
                    shutil.rmtree(str(d / x))
            return 'ran'
        except Exception as e:
            wj(outp, dict(case=c, src=m.get('src'), error=type(e).__name__ + ': ' + str(e)))
            return 'error'

    cases = sorted(man['cases'])
    counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get('SP_WORKERS', '2'))) as pool:
        for r in pool.map(one, cases):
            counts[r] = counts.get(r, 0) + 1
    done = [json.loads((run / 'out' / (c + '.json')).read_text()) for c in cases if (run / 'out' / (c + '.json')).exists()]
    agg = dict(total=len(cases), finished=len(done), this_job=counts, errors=[x for x in done if 'error' in x],
               rc_nonzero=[x['case'] for x in done if x.get('rc') not in (0, None)],
               completion_mismatch=[x['case'] for x in done if 'error' not in x and (x['old_completion'] != x['new_completion'] or x['old_terminated'] != x['new_terminated'])],
               convert_failures=[x['case'] for x in done if any(str(v).startswith('FAILED') for k in ('convert_old', 'convert_new') for v in x.get(k, {}).values())],
               rows=[])
    for x in done:
        c = x.get('cmp')
        if not c:
            continue
        cc = x.get('converter_check')
        agg['rows'].append(dict(case=x['case'], fmt=x['fmt'], max_d=c['max_d'], worst=c['worst'], numbers=c['numbers'], files_missing=c['files_missing'],
                                files_extra=c['files_extra'], keys_missing=c['keys_missing'], keys_extra=c['keys_extra'], length_diffs=len(c['length_diffs']),
                                string_diffs=c['string_diffs'], converter_max_d=cc['max_d'] if cc else None))
    wj(run / 'results.json', agg)
    print('SP36_END', json.dumps(dict(total=agg['total'], finished=agg['finished'], errors=len(agg['errors']), convert_failures=len(agg['convert_failures']),
                                      max_d=max((r['max_d'] for r in agg['rows']), default=None))), flush=True)


if __name__ == '__main__':
    main()

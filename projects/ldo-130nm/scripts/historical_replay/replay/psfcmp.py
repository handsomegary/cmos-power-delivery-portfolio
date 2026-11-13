#!/usr/bin/env python3
"""Generic psfascii comparator for historical LDO replays (old Spectre 18.1 PSF vs new 23.1 PSF).
Every analysis file (dc/ac/stb/noise/info/tran/margin...) is parsed from its VALUE section into
{signal/instance name: [values...]} (numbers, complex parts and quoted strings, in order, concatenated
over sweep points). HEADER (dates, versions) is ignored. Reported per case: missing/extra files and
keys, length differences, string (discrete) differences, and for numbers the scaled difference
d = |a-b| / (max(|a|,|b|) + 1e-9*max|key|)  (key-wise floor so exact zeros are not inflated).
No pass/fail tolerance is invented here; the distribution is reported."""
import json, math, os, re, sys
from pathlib import Path

TOK = re.compile(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()"]+')


def parse_value_section(text):
    i = text.find('\nVALUE')
    if i < 0:
        return None
    body = text[i + 6:]
    j = body.rfind('\nEND')
    if j >= 0:
        body = body[:j]
    out = {}
    depth, name, prev_quoted = 0, None, False
    for t in TOK.findall(body):
        if t == '(':
            depth += 1; prev_quoted = False; continue
        if t == ')':
            depth -= 1; prev_quoted = False; continue
        if t.startswith('"'):
            s = t[1:-1]
            if depth == 0:
                if prev_quoted:          # "name" "type" ...: second quoted at top level is the type
                    prev_quoted = False; continue
                name = s; out.setdefault(name, []); prev_quoted = True
            else:
                out.setdefault(name, []).append(s); prev_quoted = False
            continue
        prev_quoted = False
        try:
            v = float(t)
        except ValueError:
            out.setdefault(name, []).append(t); continue
        out.setdefault(name, []).append(v)
    return out


def load_dir(d):
    res = {}
    for f in sorted(Path(d).iterdir()):
        if not f.is_file() or f.name in ('logFile',) or f.name.endswith('.log'):
            continue
        t = f.read_text(errors='replace')
        if not t.startswith('HEADER'):
            res[f.name] = '__non_psfascii__'; continue
        res[f.name] = parse_value_section(t)
    return res


def compare_dirs(old, new):
    o, n = load_dir(old), load_dir(new)
    rep = dict(files_missing=sorted(set(o) - set(n)), files_extra=sorted(set(n) - set(o)), keys_missing=0, keys_extra=0,
               length_diffs=[], string_diffs=0, string_examples=[], numbers=0, max_d=0.0, worst=None, d_hist={})
    hist = {'0': 0, '<1e-9': 0, '<1e-6': 0, '<1e-4': 0, '<1e-3': 0, '<1e-2': 0, '>=1e-2': 0}
    for f in sorted(set(o) & set(n)):
        a, b = o[f], n[f]
        if not isinstance(a, dict) or not isinstance(b, dict):
            if a != b:
                rep['length_diffs'].append(dict(file=f, issue='unparsed')); continue
            continue
        rep['keys_missing'] += len(set(a) - set(b)); rep['keys_extra'] += len(set(b) - set(a))
        if set(a) - set(b) or set(b) - set(a):
            rep.setdefault('key_examples', []).append(dict(file=f, missing=sorted(set(a) - set(b))[:5], extra=sorted(set(b) - set(a))[:5]))
        for k in sorted(set(a) & set(b)):
            x, y = a[k], b[k]
            if len(x) != len(y):
                rep['length_diffs'].append(dict(file=f, key=k, old=len(x), new=len(y))); continue
            nums = [abs(v) for v in x + y if isinstance(v, float) and math.isfinite(v)]
            floor = 1e-9 * (max(nums) if nums else 0.0)
            for u, v in zip(x, y):
                if isinstance(u, float) and isinstance(v, float):
                    rep['numbers'] += 1
                    if u == v or (math.isnan(u) and math.isnan(v)):
                        hist['0'] += 1; continue
                    den = max(abs(u), abs(v)) + floor
                    dd = abs(u - v) / den if den > 0 else 0.0
                    key = '<1e-9' if dd < 1e-9 else '<1e-6' if dd < 1e-6 else '<1e-4' if dd < 1e-4 else '<1e-3' if dd < 1e-3 else '<1e-2' if dd < 1e-2 else '>=1e-2'
                    hist[key] += 1
                    if dd > rep['max_d']:
                        rep['max_d'] = dd; rep['worst'] = dict(file=f, key=k, old=u, new=v)
                elif u != v:
                    rep['string_diffs'] += 1
                    if len(rep['string_examples']) < 5:
                        rep['string_examples'].append(dict(file=f, key=k, old=u, new=v))
    rep['d_hist'] = hist
    rep['length_diffs'] = rep['length_diffs'][:20] + ([dict(more=len(rep['length_diffs']) - 20)] if len(rep['length_diffs']) > 20 else [])
    return rep


if __name__ == '__main__':
    print(json.dumps(compare_dirs(sys.argv[1], sys.argv[2]), indent=1, default=str))

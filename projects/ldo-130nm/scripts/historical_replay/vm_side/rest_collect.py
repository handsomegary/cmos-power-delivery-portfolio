import json, os, re, collections
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
PDK = os.environ['LDO_VM_PDK_ROOT']
os.chdir(ROOT)
BS = chr(92)
INC = re.compile(r'^\s*(?:include|ahdl_include)\s+"([^"]+)"', re.M)
REF = re.compile(re.escape(ROOT) + r'/[^\s"\'),]+')


def cmdline(log):
    m = re.search(r'Command line:\s*\n(.+?)\n\s*\n', log, re.S)
    return re.sub(re.escape(BS) + r'\s*\n', ' ', m.group(1)).replace(BS, ' ').split() if m else None


def closure(deck, idirs):
    seen, todo, unresolved = set(), [os.path.abspath(deck)], []
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        txt = open(f, errors='replace').read()
        for i in INC.findall(txt):
            if i.startswith(PDK):
                continue
            cands = [i] if i.startswith('/') else [os.path.join(os.path.dirname(f), i)] + [os.path.join(x, i) for x in idirs]
            hit = next((c for c in cands if os.path.isfile(c)), None)
            if hit:
                todo.append(os.path.abspath(hit))
            else:
                unresolved.append(i)
    refs = set()
    for f in seen:
        refs |= {p for p in REF.findall(open(f, errors='replace').read()) if os.path.isfile(p)}
    return seen, unresolved, refs


special = set(json.load(open('/tmp/ldo_special36.json'))['cases'])
cases = {}
problems = collections.Counter(); pex = []
for a, ds, fs in os.walk('.'):
    a2 = a[2:]
    parts = a2.split('/')
    if any(p in ('psf', 'raw_psf', 'native_ascii', 'stability') for p in parts):
        continue
    if 'verify' == os.path.basename(a2) and any(f.endswith(('.pex', '.pxi', '.rcx')) for f in fs):
        pex.append(a2)
    tg = []
    if 'raw_psf' in ds and a2 not in special:
        tg.append('raw_psf')
    if 'spectre.dc' in fs:
        tg.append('spectre.dc')
    if 'ocean_ac_fullprecision.tsv' in fs:
        tg.append('ocean_tsv')
    if not tg:
        continue
    if 'input.scs' not in fs or 'spectre.log' not in fs:
        problems['no input/log'] += 1; continue
    toks = cmdline(open(a2 + '/spectre.log', errors='replace').read())
    if not toks or not toks[0].endswith('/spectre') or toks[1:3] != ['-64', 'input.scs']:
        problems['cmd'] += 1; continue
    idirs = [t[2:] for t in toks if t.startswith('-I')]
    seen, unres, refs = closure(a2 + '/input.scs', idirs)
    if unres:
        problems['unresolved'] += 1; continue
    deps = sorted((set(seen) | refs) - {os.path.abspath(a2 + '/input.scs')})
    cases[a2] = dict(cmd=toks, targets=tg, deps=deps, dirs=sorted(d for d in ds), in_special=a2 in special)
c = collections.Counter(tuple(v['targets']) for v in cases.values())
print('cases', len(cases), dict(c), 'problems', dict(problems))
allf = set(f for v in cases.values() for f in v['deps'])
print('unique deps', len(allf), 'MB', round(sum(os.path.getsize(f) for f in allf) / 1e6, 1))
print('formats', collections.Counter((v['cmd'][v['cmd'].index('-format') + 1] if '-format' in v['cmd'] else 'none', v['cmd'][v['cmd'].index('-raw') + 1] if '-raw' in v['cmd'] else 'none') for v in cases.values()))
print('in special', sum(v['in_special'] for v in cases.values()))
print('pex verify dirs', len(pex), pex[:6])
json.dump(dict(cases=cases), open('/tmp/ldo_rest.json', 'w'))

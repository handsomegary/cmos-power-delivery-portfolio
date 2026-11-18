import json, os, re
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
PDK = os.environ['LDO_VM_PDK_ROOT']
os.chdir(ROOT)
d = json.load(open('/tmp/ldo_psf_cases.json'))
special = sorted(set(d['all']) - set(d['simple']))
INC = re.compile(r'^\s*(?:include|ahdl_include)\s+"([^"]+)"', re.M)
BS = chr(92)


def cmdline(log):
    m = re.search(r'Command line:\s*\n(.+?)\n\s*\n', log, re.S)
    return re.sub(re.escape(BS) + r'\s*\n', ' ', m.group(1)).replace(BS, ' ').split()


def closure(deck, idirs):
    seen, todo, unresolved = set(), [os.path.abspath(deck)], []
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        for i in INC.findall(open(f, errors='replace').read()):
            if i.startswith(PDK):
                continue
            cands = [i] if i.startswith('/') else [os.path.join(os.path.dirname(f), i)] + [os.path.join(x, i) for x in idirs]
            hit = next((c for c in cands if os.path.isfile(c)), None)
            if hit:
                todo.append(os.path.abspath(hit))
            else:
                unresolved.append((f, i))
    return seen, unresolved


out, files, fmt = {}, set(), {}
for c in special:
    toks = cmdline(open(c + '/spectre.log', errors='replace').read())
    idirs = [t[2:] for t in toks if t.startswith('-I')]
    seen, unres = closure(c + '/input.scs', idirs)
    deps = sorted(f for f in seen if f != os.path.abspath(c + '/input.scs'))
    files |= set(deps)
    f = toks[toks.index('-format') + 1] if '-format' in toks else 'default'
    fmt[f] = fmt.get(f, 0) + 1
    deck = open(c + '/input.scs', errors='replace').read()
    out[c] = dict(cmd=toks, deps=deps, unresolved=unres, psf_files=sorted(os.listdir(c + '/psf')),
                  pdk_in_deck=deck.count(PDK), root_in_deck=deck.count(ROOT))
print('cases', len(out), 'formats', fmt)
print('unique dep files', len(files), 'MB', round(sum(os.path.getsize(f) for f in files) / 1e6, 2))
print('outside ROOT', [f for f in files if not f.startswith(ROOT)][:5])
print('unresolved', [(c, v['unresolved'][:2]) for c, v in out.items() if v['unresolved']][:5])
for f in sorted(files):
    t = open(f, errors='replace').read()
    print('dep', round(os.path.getsize(f) / 1e3, 1), 'kB', f[len(ROOT) + 1:], 'PDK', t.count(PDK), 'ROOT', t.count(ROOT))
ex = special[0]
print('example', ex, json.dumps(out[ex])[:1200])
print('distinct cmd tails', sorted({' '.join(t for t in v['cmd'][3:] if not t.startswith('-I')) for v in out.values()}))
json.dump(dict(cases=out, files=sorted(files)), open('/tmp/ldo_special36.json', 'w'))

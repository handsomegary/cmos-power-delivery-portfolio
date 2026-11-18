import collections, json, re
exec(open('pexcmp.py').read().split('o, n = pexpex')[0])
nets = sorted({s.split('%', 1)[1] for s in pexpex('old/extracted.pex.pex')}, key=len, reverse=True)
def net(node):
    if not node.startswith('N_'): return node
    r = node[2:]
    for n in nets:
        if r.startswith(n + '_'): return n
    return '?' + r
def agg(p):
    c = collections.Counter()
    for l in lines(p):
        t = l.split()
        if t[0].lower().startswith('c'): c[tuple(sorted((net(t[1]), net(t[2]))))] += val(t[3])
    return c
a, b = agg('old/extracted.pex.ldo_core_bleed67_v32_build1.pxi'), agg('new/extracted.pex.ldo_core_bleed67_v32_build1.pxi')
ds = sorted(((rel(a.get(k, 0), b.get(k, 0)), k, a.get(k, 0) * 1e15, b.get(k, 0) * 1e15) for k in set(a) | set(b)), reverse=True)
print('netpairs', len(a), len(b), len(set(a) & set(b)), 'unresolved', [k for k in a if any(x.startswith('?') for x in k)][:3])
print('hist', hist([d for d, *_ in ds]))
print('worst (rel, pair, old fF, new fF):'); [print(' ', round(d, 4), k, round(x, 4), round(y, 4)) for d, k, x, y in ds[:10]]
big = [(d, k, x, y) for d, k, x, y in ds if max(x, y) > 1.0]
print('pairs >1fF:', len(big), 'max rel among them', max((d for d, *_ in big), default=0))
o, n = pexpex('old/extracted.pex.pex'), pexpex('new/extracted.pex.pex')
for s in ['PM_ldo_core_bleed67_v32_build1%VIN', 'PM_ldo_core_bleed67_v32_build1%5365', 'PM_ldo_core_bleed67_v32_build1%6693']:
    print(s.split('%')[1], 'sumR', round(sum(o[s]['R']), 3), round(sum(n[s]['R']), 3), 'Cg fF', round(o[s]['cg'] * 1e15, 3), round(n[s]['cg'] * 1e15, 3))

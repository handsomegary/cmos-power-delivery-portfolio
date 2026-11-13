import re, sys, json, math, collections
U = {'f': 1e-15, 'a': 1e-18, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'meg': 1e6}
def val(s):
    m = re.fullmatch(r'([-+0-9.eE]+)(meg|[fapnumk])?', s.lower())
    return float(m.group(1)) * U.get(m.group(2) or '', 1)
def lines(p):
    out, cur = [], ''
    for l in open(p, encoding='latin1'):
        l = l.rstrip('\n')
        if l.startswith('*') or not l.strip(): continue
        if l.startswith('+'): cur += ' ' + l[1:]
        else:
            if cur: out.append(cur)
            cur = l
    if cur: out.append(cur)
    return out
def pexpex(p):
    subs = {}; name = None
    for l in lines(p):
        t = l.split()
        if t[0].lower() == '.subckt': name = t[1]; subs[name] = dict(ports=t[2:], R=[], C=[], cg=0.0, el=[])
        elif t[0].lower() == '.ends': name = None
        elif name and t[0][0].lower() in 'rc':
            v = val(t[3]); k = t[0][0].lower()
            subs[name][k.upper()].append(v); subs[name]['el'].append((k, t[1], t[2], v))
            if k == 'c': subs[name]['cg'] += v
    return subs
def pxi(p):
    x, c = {}, collections.Counter(); n = 0
    for l in lines(p):
        t = l.split()
        if t[0].lower().startswith('x'): x[t[-1]] = t[1:-1]
        elif t[0].lower().startswith('c'): c[tuple(sorted(t[1:3]))] += val(t[3]); n += 1
    return x, c, n
def rel(a, b): return abs(a - b) / max(abs(a), abs(b), 1e-30)
def hist(ds):
    h = collections.Counter()
    for d in ds: h['0' if d == 0 else '<1e-6' if d < 1e-6 else '<1e-3' if d < 1e-3 else '<1e-2' if d < 1e-2 else '<5e-2' if d < 5e-2 else '>=5e-2'] += 1
    return dict(h)
o, n = pexpex('old/extracted.pex.pex'), pexpex('new/extracted.pex.pex')
rep = dict(subckts=(len(o), len(n)), missing=sorted(set(o) - set(n))[:5], extra=sorted(set(n) - set(o))[:5])
rd, cd, cg, shape, worst = [], [], [], [], []
for s in sorted(set(o) & set(n)):
    a, b = o[s], n[s]
    if len(a['R']) != len(b['R']) or len(a['C']) != len(b['C']) or len(a['ports']) != len(b['ports']):
        shape.append((s, len(a['R']), len(b['R']), len(a['C']), len(b['C']))); continue
    for u, v in zip(sorted(a['R']), sorted(b['R'])): rd.append(rel(u, v))
    for u, v in zip(sorted(a['C']), sorted(b['C'])): cd.append(rel(u, v))
    d = rel(a['cg'], b['cg']); cg.append(d); worst.append((d, s, a['cg'], b['cg']))
rep.update(total_R=(sum(len(v['R']) for v in o.values()), sum(len(v['R']) for v in n.values())),
           total_C=(sum(len(v['C']) for v in o.values()), sum(len(v['C']) for v in n.values())),
           shape_diff_subckts=len(shape), shape_examples=shape[:8],
           R_sorted_hist=hist(rd), C_sorted_hist=hist(cd), subckt_Cground_hist=hist(cg),
           max_R=max(rd, default=0), max_C=max(cd, default=0), max_Cground=max(cg, default=0),
           worst_Cground=sorted(worst, reverse=True)[:5],
           sum_Cground_fF=(sum(v['cg'] for v in o.values()) * 1e15, sum(v['cg'] for v in n.values()) * 1e15))
xo, co, no = pxi('old/extracted.pex.ldo_core_bleed67_v32_build1.pxi'); xn, cn, nn = pxi('new/extracted.pex.ldo_core_bleed67_v32_build1.pxi')
rep['pxi_x'] = (len(xo), len(xn)); rep['pxi_c_elements'] = (no, nn)
rep['pxi_netpairs'] = (len(co), len(cn), len(set(co) & set(cn)))
pd = [rel(co[k], cn[k]) for k in set(co) & set(cn)]
rep['pxi_pair_hist'] = hist(pd); rep['pxi_total_fF'] = (sum(co.values()) * 1e15, sum(cn.values()) * 1e15)
rep['pxi_only_old'] = sorted(set(co) - set(cn))[:5]; rep['pxi_only_new'] = sorted(set(cn) - set(co))[:5]
print(json.dumps(rep, indent=1, default=str))

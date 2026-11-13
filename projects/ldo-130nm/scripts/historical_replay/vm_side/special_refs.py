import hashlib, io, json, os, re, sys, tarfile
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
os.chdir(ROOT)
m = json.load(open('/tmp/ldo_special36.json'))
known = set(m['files'])
pat = re.compile(re.escape(ROOT) + r'/[^\s"\'),]+')
refs = {}
for c in m['cases']:
    for f in [c + '/input.scs'] + m['cases'][c]['deps']:
        for p in pat.findall(open(f, errors='replace').read()):
            refs.setdefault(p, set()).add(c)
extra = sorted(p for p in refs if os.path.isfile(p) and p not in known)
dirs = sorted(p for p in refs if os.path.isdir(p))
missing = sorted(p for p in refs if not os.path.exists(p))
sys.stderr.write(json.dumps(dict(extra_files=extra, dirs=dirs, missing=missing)) + '\n')
man = {}
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as t:
    for p in extra:
        rel = p[len(ROOT) + 1:]
        t.add(p, arcname='mirror/' + rel)
        man[rel] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    data = json.dumps(man).encode()
    ti = tarfile.TarInfo('extra_refs.json'); ti.size = len(data); t.addfile(ti, io.BytesIO(data))

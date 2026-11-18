import hashlib, io, json, os, sys, tarfile
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
os.chdir(ROOT)
m = json.load(open('/tmp/ldo_special36.json'))
man = dict(cases={}, deps={})
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as t:
    for c, v in sorted(m['cases'].items()):
        flat = c.replace('/', '__')
        t.add(c + '/input.scs', arcname='cases/' + flat + '/input.scs')
        t.add(c + '/spectre.log', arcname='cases/' + flat + '/orig_spectre.log')
        t.add(c + '/psf', arcname='cases/' + flat + '/old_psf')
        for extra in ('raw_psf', 'native_ascii'):
            if os.path.isdir(c + '/' + extra):
                t.add(c + '/' + extra, arcname='cases/' + flat + '/old_' + extra)
        man['cases'][flat] = dict(src=c, cmd=v['cmd'], dirs=sorted(x for x in os.listdir(c) if os.path.isdir(os.path.join(c, x))),
                                  input_sha256=hashlib.sha256(open(c + '/input.scs', 'rb').read()).hexdigest(),
                                  deps=[d[len(ROOT) + 1:] for d in v['deps']])
    for f in m['files']:
        rel = f[len(ROOT) + 1:]
        t.add(f, arcname='mirror/' + rel)
        man['deps'][rel] = hashlib.sha256(open(f, 'rb').read()).hexdigest()
    data = json.dumps(man, indent=0).encode()
    ti = tarfile.TarInfo('vm_manifest.json'); ti.size = len(data); t.addfile(ti, io.BytesIO(data))

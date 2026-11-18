import hashlib, io, json, os, sys, tarfile
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
os.chdir(ROOT)
m = json.load(open('/tmp/ldo_rest.json'))['cases']
man = dict(cases={}, deps={})
deps = set()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as t:
    for c, v in sorted(m.items()):
        flat = c.replace('/', '__')
        t.add(c + '/input.scs', arcname='cases/' + flat + '/input.scs')
        t.add(c + '/spectre.log', arcname='cases/' + flat + '/orig_spectre.log')
        if 'raw_psf' in v['targets']:
            t.add(c + '/raw_psf', arcname='cases/' + flat + '/old_raw')
        if 'spectre.dc' in v['targets']:
            t.add(c + '/spectre.dc', arcname='cases/' + flat + '/old_spectre.dc')
        if 'ocean_tsv' in v['targets']:
            t.add(c + '/ocean_ac_fullprecision.tsv', arcname='cases/' + flat + '/old_ocean.tsv')
            t.add(c + '/ocean_export.ocn', arcname='cases/' + flat + '/ocean_export.ocn')
        man['cases'][flat] = dict(src=c, cmd=v['cmd'], targets=v['targets'],
                                  input_sha256=hashlib.sha256(open(c + '/input.scs', 'rb').read()).hexdigest(),
                                  deps=[d[len(ROOT) + 1:] for d in v['deps']])
        deps |= set(v['deps'])
    for f in sorted(deps):
        rel = f[len(ROOT) + 1:]
        t.add(f, arcname='mirror/' + rel)
        man['deps'][rel] = hashlib.sha256(open(f, 'rb').read()).hexdigest()
    data = json.dumps(man, indent=0).encode()
    ti = tarfile.TarInfo('vm_manifest.json'); ti.size = len(data); t.addfile(ti, io.BytesIO(data))

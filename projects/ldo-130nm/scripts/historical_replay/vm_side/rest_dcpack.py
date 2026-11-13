import hashlib, io, json, os, sys, tarfile
ROOT = os.environ['LDO_VM_PROJECT_ROOT']
os.chdir(ROOT)
m = json.load(open('/tmp/ldo_rest.json'))['cases']
extra = ['iterations/closure_smoke_35503fc9004b/verify/extracted.pex.pex',
         'iterations/closure_smoke_35503fc9004b/verify/extracted.pex.passive_mos_smoke.pxi']
man = {}
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as t:
    n = 0
    for c, v in sorted(m.items()):
        if 'spectre.dc' in v['targets']:
            t.add(c + '/spectre.dc', arcname='cases/' + c.replace('/', '__') + '/old_spectre.dc'); n += 1
    for f in extra:
        t.add(f, arcname='mirror/' + f)
        man[f] = hashlib.sha256(open(f, 'rb').read()).hexdigest()
    data = json.dumps(dict(dc_files=n, extra_deps=man)).encode()
    ti = tarfile.TarInfo('dc_repack.json'); ti.size = len(data); t.addfile(ti, io.BytesIO(data))

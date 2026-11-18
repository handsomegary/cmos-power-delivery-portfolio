import json, os, re
os.chdir(os.environ['LDO_VM_PROJECT_ROOT'])
try:
    d = json.load(open('/tmp/ldo_psf_cases.json')); print('tmp list ok', len(d['all']), len(d['simple']))
except Exception as e:
    print('tmp list missing', e); d = None
cases = []
for a, ds, fs in os.walk('.'):
    if os.path.basename(a) == 'psf': continue
    if 'psf' in ds: cases.append(a[2:])
print('dirs with psf now', len(cases))
special = [c for c in cases if not d or c not in d['simple']]
tot = 0; rows = []
for c in sorted(special):
    s = sum(os.path.getsize(os.path.join(x, f)) for x, _, fs in os.walk(c + '/psf') for f in fs)
    tot += s
    log = open(c + '/spectre.log', errors='replace').read() if os.path.exists(c + '/spectre.log') else ''
    m = re.search(r'Command line:\s*\n(.+?)\n\s*\n', log, re.S)
    cmd = re.sub(r'\\s*\n', ' ', m.group(1)).split() if m else []
    deck = c + '/input.scs'
    inc = re.findall(r'^\s*(?:include|ahdl_include)\s+"([^"]+)"', open(deck, errors='replace').read(), re.M) if os.path.exists(deck) else ['NO input.scs']
    other = [i for i in inc if 'PDK_13mmrf' not in i]
    print(round(s / 1e6, 2), c, '| cmd:', ' '.join(cmd[1:])[:160], '| nonPDK inc:', other[:4], '| ver:', (re.findall(r'Version (\S+)', log) or ['?'])[0])
print('special', len(special), 'total MB', round(tot / 1e6, 1))

"""Validate published measurements and reproduce comparisons; no simulator is launched."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((PROJECT / 'data' / name).read_text(encoding='utf-8'))


def verify_manifest():
    path = PROJECT / 'asset_manifest.json'
    if not path.exists():
        raise ValueError('The published asset manifest is required.')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for entry in manifest['files']:
        relative = Path(entry['path'])
        target = PROJECT / relative
        if relative.is_absolute() or '..' in relative.parts or target.is_symlink():
            raise ValueError('Invalid asset path')
        content = target.read_bytes()
        if len(content) != entry['bytes'] or hashlib.sha256(content).hexdigest() != entry['sha256']:
            raise ValueError('Asset differs: ' + entry['path'])
    return len(manifest['files'])


def verify_measurements(data, ncase, npair):
    counts = data['counts']
    if len(data['cases']) != ncase or counts['verified_case_count'] != ncase:
        raise ValueError('Case count differs')
    if len(data['pairs']) != npair or counts['matched_pair_count'] != npair:
        raise ValueError('Pair count differs')
    if len(data['events']) != counts['measured_event_count'] or len(data['steady']) != counts['steady_window_count']:
        raise ValueError('Measurement count differs')
    if data['performance_pass'] is not None or data['physical_overall_efficiency'] is not None:
        raise ValueError('Dataset must retain unassigned performance/efficiency status')
    names = {c['name'] for c in data['cases']}
    if len(names) != ncase or any(e['case'] not in names for e in data['events'] + data['steady']):
        raise ValueError('Unknown or repeated case')
    for pair in data['pairs']:
        if pair['baseline'] not in names or pair['variant'] not in names:
            raise ValueError('Missing pair member')
        for event in pair['events']:
            for metric in ('droop_from_target_v', 'overshoot_from_target_v', 'raw_recovery_s', 'cycle_mean_recovery_s'):
                baseline, variant = event[metric + '_baseline'], event[metric + '_variant']
                delta = event[metric + '_delta_variant_minus_baseline']
                if baseline is not None and variant is not None:
                    if not math.isclose(variant - baseline, delta, rel_tol=1e-12, abs_tol=1e-15):
                        raise ValueError('Pair arithmetic differs')
    return counts


def event(data, pair, name):
    return next(e for p in data['pairs'] if p['name'] == pair for e in p['events'] if e['event'] == name)


def hardware_summary(revision):
    with (PROJECT/'data'/f'{revision}_hardware.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    mos = [r for r in rows if r['role'].endswith(('NMOS', 'PMOS'))]
    if len(rows) != (90 if revision == 'r8' else 92) or len(mos) != 59:
        raise ValueError('Hardware inventory differs')
    for row in mos:
        if not math.isclose(float(row['width_per_multiplier_m']) * float(row['multiplier']),
                            float(row['effective_total_width_m']), rel_tol=1e-12):
            raise ValueError('MOS width arithmetic differs')
    return {'components': len(rows), 'MOS_instances': len(mos),
            'qualification': 'Own connectivity and geometry inventory; technology setup is a separate dependency.'}


def sensitivity_summary(data):
    events = [e for c in data['comparisons'] for e in c['events']]
    waveform = [e for c in data['comparisons'] for e in c['waveform_errors']
                if e['role'] == 'vload_v' and e['window_name'] in ('load_up', 'load_down')]
    peaks = [abs(e[k]) for e in events for k in (
        'droop_from_target_v_delta_fine_minus_coarse', 'overshoot_from_target_v_delta_fine_minus_coarse')]
    recovery = [abs(e['raw_recovery_s_delta_fine_minus_coarse']) for e in events
                if e['raw_recovery_s_delta_fine_minus_coarse'] is not None]
    return {'comparison_count': len(data['comparisons']),
            'max_event_peak_delta_v': max(peaks),
            'max_raw_recovery_delta_s': max(recovery),
            'max_event_pointwise_vload_delta_v': max(e['max_abs_interpolated_error'] for e in waveform),
            'convergence_pass': None}


def plots(outdir, r8, r9, sensitivities):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none'})
    metadata = {'Date': None}
    colors = ['#2666a4', '#df7d2a']
    groups = [('r8 nominal\n100 ns up', event(r8, 'v3_nom100', 'load_up'), 'droop_from_target_v'),
              ('r8 nominal\n100 ns down', event(r8, 'v3_nom100', 'load_down'), 'overshoot_from_target_v'),
              ('r8 hard PDN\n10 ns up', event(r8, 'v3_pdn_hard_p0', 'load_up'), 'droop_from_target_v'),
              ('r8 hard PDN\n10 ns down', event(r8, 'v3_pdn_hard_p0', 'load_down'), 'overshoot_from_target_v')]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    for ax, metric, scale, ylabel in [(axes[0,0], None, 1e3, 'Target-referenced event peak (mV)'),
                                     (axes[0,1], 'raw_recovery_s', 1e6, 'Saved-grid recovery (us)')]:
        for j, mode in enumerate(('baseline','variant')):
            values = [(e[(metric or key)+'_'+mode] or 0)*scale for _,e,key in groups]
            bars = ax.bar([i+(j-.5)*.34 for i in range(4)], values, .34,
                          label='Assist OFF' if j==0 else 'Coordinated assist ON', color=colors[j])
            ax.bar_label(bars, fmt='%.1f', fontsize=8, padding=2)
        ax.set_xticks(range(4), [g[0] for g in groups], fontsize=8)
        ax.set_ylabel(ylabel); ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True)
        ax.set_ylim(0, max(max((e[(metric or key)+'_'+mode] or 0)*scale for _,e,key in groups)
                          for mode in ('baseline','variant')) * 1.3)
        ax.legend(fontsize=8)
    axes[0,0].set_title('Droop improvement has an unload counterexample')
    axes[0,1].set_title('Nominal load-up recovery becomes slower')
    for revision, data, style in [('r8', r8, '-'), ('r9', r9, '--')]:
        for mode, color in [('off',colors[0]),('on',colors[1])]:
            name = 'v3_pdn_hard_p0_'+mode if revision=='r8' else 'r9_pdn_hard_p0_'+mode
            with (PROJECT/'data/waveforms'/f'{name}.csv').open(encoding='utf-8', newline='') as f:
                rows = [r for r in csv.DictReader(f) if 99e-6 <= float(r['time_s']) <= 120e-6]
            axes[1,0].plot([(float(r['time_s'])-100e-6)*1e6 for r in rows],
                           [float(r['vload_v']) for r in rows], style, color=color,
                           label=revision+' assist '+mode.upper(), linewidth=.9)
    axes[1,0].axhline(.9,color='gray',linewidth=.6)
    axes[1,0].set(xlabel='Time from load decrease (us)',ylabel='VLOAD (V)',
                  title='Hard-PDN unload: selected display samples')
    axes[1,0].legend(fontsize=8);axes[1,0].grid(alpha=.2)
    labels = ['r8','r9']
    axes[1,1].bar(labels, [sensitivities[r]['max_event_pointwise_vload_delta_v']*1e3 for r in labels],color=colors)
    axes[1,1].set(ylabel='Maximum event pointwise VLOAD difference (mV)',
                  title='Solver sensitivity remains; no convergence PASS')
    axes[1,1].grid(axis='y',alpha=.2)
    fig.suptitle('130 nm CMOS two-phase buck | measured tradeoffs, not a performance pass',fontsize=13)
    fig.savefig(outdir/'tradeoffs.png',dpi=160)
    fig.savefig(outdir/'tradeoffs.svg',metadata=metadata)
    plt.close(fig)

    fig,ax=plt.subplots(figsize=(13,7),layout='constrained')
    ax.set(xlim=(0,13),ylim=(0,7));ax.axis('off')
    def box(x,y,w,h,text,color='#e9eef5'):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.1',facecolor=color,edgecolor='#283849'))
        ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=10)
    def arrow(a,b,color='#33475b'):
        ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','color':color,'lw':1.5})
    box(.3,4.4,2.2,1.5,'Algorithmic PI / PWM\n180-degree phases\nideal 1 V/A sensing','#e8f2e8')
    box(3.1,4.4,2.1,1.5,'I/O MOS drivers\n+ two MOS bridges\n1.8 V input')
    box(5.8,4.4,1.6,1.5,'External L\n2.2 uH / phase\nDCR 50 mohm')
    box(8.1,4.4,1.6,1.5,'VCONV\nCout 1 uF\nESR / ESL')
    box(10.3,4.4,2.2,1.5,'Parameterized PDN\nR / L + load C\nVLOAD: 0.9 V')
    for a,b in [((2.5,5.15),(3.1,5.15)),((5.2,5.15),(5.8,5.15)),((7.4,5.15),(8.1,5.15)),((9.7,5.15),(10.3,5.15))]:arrow(a,b)
    box(8.3,1.8,3.4,1.3,'Core-MOS voltage-window detectors\n+ I/O MOS source / sink assist')
    arrow((11.4,4.4),(10.8,3.1));arrow((9.4,3.1),(11.4,4.4),'#b66625')
    ax.plot([11.4,11.4,1.4,1.4],[4.4,.9,.9,4.4],color='#327447',lw=1.2)
    ax.text(5.8,1.0,'VLOAD feedback + event-driven PI-state handoff (mode 2, 40 mA)',ha='center',color='#327447',fontsize=10)
    ax.text(6.5,6.65,'Own mixed-level architecture | r8: 59 MOS, r9: assist gate R = 1k / 2k',ha='center',fontsize=14)
    ax.text(6.5,.2,'Pre-layout; external ideal L/C; assumed PDN. Controller internal power is unmodeled.',ha='center',fontsize=10)
    fig.savefig(outdir/'architecture.png',dpi=160)
    fig.savefig(outdir/'architecture.svg',metadata=metadata)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir',type=Path,required=True)
    parser.add_argument('--no-plots',action='store_true')
    args=parser.parse_args()
    outdir=args.outdir.resolve()
    if outdir==PROJECT or PROJECT/'data'==outdir or PROJECT/'scripts'==outdir or any(p in outdir.parents for p in [PROJECT/'data',PROJECT/'scripts',PROJECT/'controller']):
        parser.error('Choose a fresh output directory away from sources.')
    if outdir.exists() and any(outdir.iterdir()):
        parser.error('The output directory must be empty or new.')
    assets=verify_manifest()
    r8,r9=load('r8_measurements.json'),load('r9_measurements.json')
    counts={'r8':verify_measurements(r8,47,24),'r9':verify_measurements(r9,8,4)}
    sensitivities={r:sensitivity_summary(load(f'{r}_solver_sensitivity.json')) for r in ['r8','r9']}
    report={'schema':'buck-public-reproduction-v1','validated_asset_count':assets,
            'counts':counts,'hardware':{r:hardware_summary(r) for r in ['r8','r9']},
            'solver_sensitivity':sensitivities,'simulation_rerun':False,
            'scope':'Recomputed pair arithmetic and result figures from published measurements. No new raw-waveform parsing or transistor simulation.',
            'physical_overall_efficiency':None,'switching_stability_signoff':None}
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if not args.no_plots:plots(outdir,r8,r9,sensitivities)
    print('Reproduced r8: 47 cases/24 pairs; r9: 8 cases/4 pairs. Performance status remains unassigned.')


if __name__=='__main__':
    main()

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


def verify_dimensions():
    with (PROJECT/'data/mos_dimensions.csv').open(encoding='utf-8',newline='') as stream:
        dimensions=list(csv.DictReader(stream))
    with (PROJECT/'data/r8_hardware.csv').open(encoding='utf-8',newline='') as stream:
        hardware={r['instance']:r for r in csv.DictReader(stream) if r['role'].endswith(('NMOS','PMOS'))}
    if len(dimensions)!=59 or {r['instance'] for r in dimensions}!=set(hardware):
        raise ValueError('Device table must enumerate exactly all 59 MOS instances')
    for r in dimensions:
        h=hardware[r['instance']]
        expected=float(r['Wunit_um'])*float(r['m'])*float(r['nf'])
        if not math.isclose(expected,float(r['Wtotal_um']),rel_tol=1e-12):
            raise ValueError('Finger/multiplier width arithmetic differs')
        for actual,reference in [(float(r['Wtotal_um'])*1e-6,float(h['effective_total_width_m'])),
                                 (float(r['L_um'])*1e-6,float(h['length_m']))]:
            if not math.isclose(actual,reference,rel_tol=1e-12):raise ValueError('Dimension table differs from hardware')
        if [r[k] for k in ('D','G','S','B')]!=json.loads(h['connected_nodes']):
            raise ValueError('Terminal table differs from hardware')
    return {'complete_MOS_rows':59,'block_counts':{b:sum(r['block']==b for r in dimensions)
                for b in sorted({r['block'] for r in dimensions})}}


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


def comparison_metrics(datasets, assist_work):
    """Matched-condition diagnostics, not a universal or literature benchmark FoM."""
    work={(e['case'],e['event']):e for e in assist_work['events']}
    rows=[]
    for revision,data in datasets.items():
        cases={c['name']:c for c in data['cases']}
        events={(e['case'],e['event']):e for e in data['events']}
        for pair in data['pairs']:
            baseline,variant=pair['baseline'],pair['variant']
            bc,vc=cases[baseline]['config'],cases[variant]['config']
            for key in ('VOUT_REQ','FSW','COUT','CLOAD','R_PDN','L_PDN','L_PHASE','PHASES'):
                if bc['parameters'][key]!=vc['parameters'][key]:
                    raise ValueError('Comparison conditions differ: '+key)
            target=bc['parameters']['VOUT_REQ'];fsw=bc['parameters']['FSW']
            for event_row in pair['events']:
                name=event_row['event']
                be,ve=events[baseline,name],events[variant,name]
                bw,vw=work[baseline,name],work[variant,name]
                if be['window_s']!=ve['window_s'] or be['window_s']!=bw['window_s'] or ve['window_s']!=vw['window_s']:
                    raise ValueError('Event energy windows differ')
                metric='droop_from_target_v' if name in ('load_up','line_down') else 'overshoot_from_target_v'
                bp,vp=be[metric],ve[metric]
                bt,vt=be['raw_recovery_s'],ve['raw_recovery_s']
                row={'revision':revision,'pair':pair['name'],'event':name,'peak_definition':metric,
                     'baseline':baseline,'variant':variant,'target_v':target,'fsw_hz':fsw,
                     'window_s':be['window_s'],
                     'peak_v_baseline':bp,'peak_v_variant':vp,
                     'normalized_peak_pct_baseline':100*bp/target,
                     'normalized_peak_pct_variant':100*vp/target,
                     'relative_peak_reduction_pct':100*(bp-vp)/bp if bp else None,
                     'raw_recovery_cycles_baseline':bt*fsw if bt is not None else None,
                     'raw_recovery_cycles_variant':vt*fsw if vt is not None else None,
                     'raw_recovery_change_pct':100*(vt-bt)/bt if bt and vt is not None else None,
                     'modeled_supply_event_energy_delta_nj':(ve['input_energy_j']-be['input_energy_j'])*1e9}
                for mode,w in [('baseline',bw),('variant',vw)]:
                    row['source_VLOAD_port_work_nj_'+mode]=w['up_signed_energy_j']*1e9
                    row['sink_VLOAD_port_work_nj_'+mode]=w['down_signed_energy_j']*1e9
                    row['net_assist_VLOAD_work_nj_'+mode]=(w['up_signed_energy_j']-w['down_signed_energy_j'])*1e9
                rows.append(row)
    return rows


def metric_document(rows):
    return {'schema':'matched-transient-diagnostics-v1',
            'qualification':'Within matched cases only; derived diagnostics, not a literature FoM, composite score or efficiency estimate. Case conditions remain in r8/r9 measurements.',
            'definitions':{
                'normalized_peak_pct':'100 * target-referenced primary peak / target voltage',
                'relative_peak_reduction_pct':'100 * (baseline peak - variant peak) / baseline peak; negative is worse',
                'raw_recovery_cycles':'command switching frequency * finite saved-grid recovery time',
                'raw_recovery_change_pct':'100 * (variant recovery - baseline recovery) / baseline recovery; positive is slower',
                'source_VLOAD_port_work':'Integral of VLOAD * Iup over the stated event window; positive current enters VLOAD',
                'sink_VLOAD_port_work':'Integral of VLOAD * Idn over the stated event window; positive current leaves VLOAD',
                'net_assist_VLOAD_work':'source port work minus sink port work; not complete assist loss',
                'modeled_supply_event_energy_delta':'variant minus baseline exact VI event energy at the modeled VIN and VDDC ports; includes main-loop and stored-energy changes; excludes unmodeled controller internal power',
            },'rows':rows}


def plots(outdir, r8, r9, sensitivities):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'font.family':'DejaVu Sans', 'svg.fonttype': 'none',
                         'axes.spines.top':False,'axes.spines.right':False})
    metadata = {'Date': None}
    colors = ['#222222', '#24629a']
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

    from figures import draw_architecture, draw_block_diagram
    draw_architecture(outdir)
    draw_block_diagram(outdir)


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
    metrics=comparison_metrics({'r8':r8,'r9':r9},load('assist_port_work.json'))
    if load('comparison_metrics.json')!=metric_document(metrics):
        raise ValueError('Published comparison metrics differ from reproduced arithmetic')
    report={'schema':'buck-public-reproduction-v1','validated_asset_count':assets,
            'counts':counts,'hardware':{r:hardware_summary(r) for r in ['r8','r9']},
            'device_table':verify_dimensions(),
            'solver_sensitivity':sensitivities,'comparison_metrics':metrics,'simulation_rerun':False,
            'scope':'Recomputed pair arithmetic and result figures from published measurements. No new raw-waveform parsing or transistor simulation.',
            'physical_overall_efficiency':None,'switching_stability_signoff':None}
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (outdir/'comparison_metrics.json').write_text(json.dumps(metric_document(metrics),indent=2,allow_nan=False)+'\n',encoding='utf-8')
    with (outdir/'comparison_metrics.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(metrics[0]));writer.writeheader();writer.writerows(metrics)
    if not args.no_plots:plots(outdir,r8,r9,sensitivities)
    print('Reproduced r8: 47 cases/24 pairs; r9: 8 cases/4 pairs. Performance status remains unassigned.')


if __name__=='__main__':
    main()

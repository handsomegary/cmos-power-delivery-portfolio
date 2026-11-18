#!/usr/bin/env python3
"""Reproduce public LDO measurements and figures from exported numerical samples.

Python 3.10+; the measurements use the standard library. matplotlib is optional.
This script does not run a simulator or validate private simulator source files.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import analyze_results as general
from waveform_comparison import waveform_error

PROJECT = Path(__file__).resolve().parents[1]

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def strict_csv(path, kind):
    data=general.read_csv(path,kind)
    if data['status']!='loaded':
        raise ValueError('CSV is missing, incomplete, or nonfinite: '+path.relative_to(PROJECT).as_posix())
    return data

def close(actual, expected, tolerance=1e-12):
    if actual is None or expected is None:
        return actual is expected
    return math.isclose(actual,expected,rel_tol=1e-12,abs_tol=tolerance)

def check_event_parity(actual, expected):
    if actual['status'] != 'computed' or expected['status'] != 'computed':
        raise ValueError('Required event measurement unavailable')
    for key in ['minimum_v','maximum_v','undershoot_from_target_v','overshoot_from_target_v',
                'minimum_time_s','maximum_time_s']:
        if not close(actual[key],expected[key]):
            raise ValueError('Retained measurement mismatch: '+actual['name']+'.'+key)
    if actual['recovery']['status'] != expected['recovery']['status'] or not close(
            actual['recovery'].get('from_edge_end_s'),expected['recovery'].get('from_edge_end_s')):
        raise ValueError('Retained recovery mismatch: '+actual['name'])

def transient_case(entry, args):
    base=PROJECT/entry['directory']
    data=strict_csv(base/'waveform.csv','transient')
    points,error=general.series(data,'time_s',['vout_v'])
    if error:
        raise ValueError(error)
    meta=load(base/'metadata.json')
    result=general.transient_analysis(data,load(base/'events.json'),None,args)
    expected=load(base/'expected.json')['events']
    if len(result.get('events',[]))!=len(expected):
        raise ValueError('Event coverage mismatch')
    for event, retained in zip(result['events'],expected):
        check_event_parity(event,retained)
        for role in ['pre','post']:
            dc_role=event['definition'][role+'_dc_role']
            reference=meta['dc_references'][dc_role]
            window=event['definition'][role+'_window_s']
            samples,error=general.clipped(points,window)
            if error:
                raise ValueError(error)
            stats=general.window_stats(points,window)
            voltage=reference['dc']['vout_v']
            event[role+'_residual_to_dc']={
                'static_reference_case':reference['case'], 'static_dc_vout_v':voltage,
                'mean_residual_v':stats['mean_v']-voltage,
                'maximum_abs_residual_v':max(abs(p[1]-voltage) for p in samples),
                'native_stability_state':reference['native_stability_state']}
        after_peak,error=general.clipped(points,[event['maximum_time_s'],event['definition']['analysis_window_s'][1]])
        if error:
            raise ValueError(error)
        event['post_primary_peak_minimum_v']=min(p[1] for p in after_peak)
        event['post_primary_peak_undershoot_from_target_v']=max(0,args.target_v-event['post_primary_peak_minimum_v'])
        event['secondary_definition']='minimum after event global VOUT maximum; not whole-event minimum'
    return {'case':entry['case'],'condition':meta,'coverage_s':result['coverage_s'],
            'saved_samples':len(data['rows']),'events':result['events'],
            'retained_metric_parity':'matches_exported_measurements_with_1e-12_absolute_tolerance'},data

def native_table():
    table=[]
    for base in sorted((PROJECT/'data/stability').iterdir()):
        native=load(base/'native.json')
        strict_csv(base/'loop.csv','stb')
        if native['native_stability_state']=='unstable' and (
                native['phase_margin_deg'] is not None or native['gain_margin_db'] is not None):
            raise ValueError('Unstable native results must retain null margins')
        table.append({'case':base.name,**native,
                      'initial_screen_goals':{'pm_deg':60,'gm_db':10},
                      'screen_goals_are_exploratory_not_user_hard_specs':True})
    return table

def noise_rms(path):
    with path.open(newline='',encoding='utf-8') as handle:
        rows=list(csv.DictReader(handle))
    points=[(float(r['frequency_hz']),float(r['vout_noise_v_sqrthz'])) for r in rows]
    if any(not math.isfinite(x) or not math.isfinite(y) or x<=0 or y<0 for x,y in points):
        raise ValueError('Noise data must be finite, positive-frequency ASD')
    if any(b[0]<=a[0] for a,b in zip(points,points[1:])):
        raise ValueError('Noise frequency axis must be strictly increasing')
    selected,error=general.clipped(points,[10,1e8])
    if error:
        raise ValueError('Incomplete noise integration band')
    power=sum((b[0]-a[0])*(a[1]*a[1]+b[1]*b[1])/2 for a,b in zip(selected,selected[1:]))
    return {'rms_v':math.sqrt(power),'band_hz':[10,1e8],
            'method':'trapezoidal integration of sampled output ASD squared',
            'scope':'ideal reference noise excluded'}

def convergence(cases, data):
    results=[]
    for edge, fine_suffix in [('T100','T100_step2p5ns'),('T10','T10_step0p5ns')]:
        coarse='r6_load_C1000_'+edge
        fine='r6_convergence_'+fine_suffix
        channel_names=['vout_v','gate_v','fb_v','vin_v','load_a']
        rows=[]
        for name in [coarse,fine]:
            rows.append([(r['time_s'],*[r[k] for k in channel_names]) for r in data[name]['rows']])
        result=waveform_error(*rows)
        retained=load(PROJECT/'data'/('convergence_'+edge+'.json'))
        channels=dict(zip(channel_names,result.pop('channel_metrics')))
        for channel, metrics in channels.items():
            original=retained['full_waveform_error']['channels'][channel]
            for key in ['maximum_absolute_error','rms_error','mean_absolute_error']:
                if not close(metrics[key],original[key]):
                    raise ValueError('Retained full-wave comparison mismatch')
        events=[]
        for left,right in zip(cases[coarse]['events'],cases[fine]['events']):
            events.append({'event':left['name'],
                'undershoot_delta_v':left['undershoot_from_target_v']-right['undershoot_from_target_v'],
                'overshoot_delta_v':left['overshoot_from_target_v']-right['overshoot_from_target_v'],
                'recovery_delta_s':left['recovery']['from_edge_end_s']-right['recovery']['from_edge_end_s']})
        results.append({'coarse_case':coarse,'fine_case':fine,**result,'channels':channels,'events':events,
            'comparison_scope':'matched stimuli and model conditions verified in private source audit; only public samples compared here',
            'performance_pass':None})
    return results

def write_events(path, cases):
    fields=['case','event','minimum_v','maximum_v','undershoot_v','overshoot_v',
            'recovery_from_edge_end_s','observation_end_s','post_mean_residual_to_dc_v',
            'post_primary_peak_undershoot_v']
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fields); writer.writeheader()
        for name,case in cases.items():
            for event in case['events']:
                writer.writerow({'case':name,'event':event['name'],'minimum_v':event['minimum_v'],
                    'maximum_v':event['maximum_v'],'undershoot_v':event['undershoot_from_target_v'],
                    'overshoot_v':event['overshoot_from_target_v'],
                    'recovery_from_edge_end_s':event['recovery'].get('from_edge_end_s'),
                    'observation_end_s':event['definition']['analysis_window_s'][1],
                    'post_mean_residual_to_dc_v':event['post_residual_to_dc']['mean_residual_v'],
                    'post_primary_peak_undershoot_v':event['post_primary_peak_undershoot_from_target_v']})

def plots(out, static, cases, data):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return {'status':'unavailable','reason':'optional_matplotlib_not_installed'}
    dst=out/'figures'; dst.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
    for name,label in [('r6_load_C1000_T100','nominal, 100 ns'),('r6_load_C1000_T10','nominal, 10 ns'),
                       ('r6_corner_tran_ss_125','slow/slow, 125 C, 100 ns')]:
        values=data[name]['rows']; t=[r['time_s']*1e6 for r in values]
        for a,b,axis in [(4.9,11,ax[0,0]),(29.9,38,ax[0,1])]:
            chosen=[r for r in values if a<=r['time_s']*1e6<=b]
            axis.plot([r['time_s']*1e6 for r in chosen],[r['vout_v'] for r in chosen],label=label,lw=1)
        ax[1,0].plot(t,[r['gate_v'] for r in values],label=label,lw=1)
    for axis in ax[0]:
        axis.axhspan(.891,.909,color='gray',alpha=.15,label='0.9 V +/-1%')
        axis.set(xlabel='Time (us)',ylabel='VOUT (V)'); axis.legend(fontsize=7)
    ax[0,0].set_title('Load increase: 0.1 to 5 mA')
    ax[0,1].set_title('Unload: primary overshoot and secondary droop')
    ax[1,0].set(xlabel='Time (us)',ylabel='Pass gate (V)'); ax[1,0].legend(fontsize=7)
    for name,label in [('r6_line_light','0.1 mA'),('r6_line_heavy','5 mA')]:
        values=data[name]['rows']
        ax[1,1].plot([r['time_s']*1e6 for r in values],[r['vout_v'] for r in values],label=label,lw=1)
    ax[1,1].set(xlabel='Time (us)',ylabel='VOUT (V)',title='Input 1.1 to 1.2 to 1.1 V, 100 ns')
    ax[1,1].legend(fontsize=7)
    fig.suptitle('130 nm CMOS LDO: actual exported samples, external ideal Cout=1 nF')
    fig.savefig(dst/'transients.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
    for load,marker in [(1e-4,'o'),(1e-3,'s'),(5e-3,'^')]:
        chosen=[r for r in static if r['case'].startswith('r6_pvt_') and r['load_a']==load]
        for axis,key,scale in [(ax[0,0],'vout_v',1e3),(ax[0,1],'iq_a',1e6),
                               (ax[1,0],'phase_margin_deg',1),(ax[1,1],'gain_margin_db',1)]:
            values=[(r[key]-.9)*1e6 if key=='vout_v' else r[key]*scale for r in chosen]
            axis.scatter([r['temperature_c'] for r in chosen],values,
                         marker=marker,s=22,label=str(load*1e3)+' mA')
    for axis,label in zip(ax.flat,['VOUT - 0.9 V (uV)','Core IQ (uA)','Native PM (deg)','Native GM (dB)']):
        axis.set(xlabel='Temperature (C)',ylabel=label); axis.legend(fontsize=8)
    fig.suptitle('45 discrete PVT points at VIN=1.2 V; 5 process corners; external Cout=1 nF')
    fig.savefig(dst/'pvt.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
    for name,label in [('r6_pvt_tt_27_light','0.1 mA'),('r6_pvt_tt_27_heavy','5 mA')]:
        base=PROJECT/'data/nominal'/name
        stb=strict_csv(base/'loop.csv','stb')['rows']; ac=strict_csv(base/'ac.csv','ac')
        curve=general.ac_analysis(ac)['curve']
        ax[0,0].semilogx([r['frequency_hz'] for r in stb],[20*math.log10(math.hypot(r['loop_real'],r['loop_imag'])) for r in stb],label=label)
        phase=general.unwrap_phase([math.degrees(math.atan2(-r['loop_imag'],-r['loop_real'])) for r in stb])
        ax[0,1].semilogx([r['frequency_hz'] for r in stb],phase,label=label)
        ax[1,0].semilogx([r['frequency_hz'] for r in curve],[r['psrr_db'] for r in curve],label=label)
        with (base/'noise.csv').open(newline='') as handle:
            noise=list(csv.DictReader(handle))
        ax[1,1].loglog([float(r['frequency_hz']) for r in noise],[float(r['vout_noise_v_sqrthz']) for r in noise],label=label)
    for axis,label in zip(ax.flat,['Loop gain (dB)','Phase of -AF (deg)','PSRR (dB)','Output ASD (V/sqrt(Hz))']):
        axis.set(xlabel='Frequency (Hz)',ylabel=label); axis.legend(fontsize=8)
    fig.suptitle('Nominal TT / 27 C, ideal reference; positive PSRR is rejection')
    fig.savefig(dst/'loop_psrr_noise.png',dpi=160); plt.close(fig)
    with (PROJECT/'data/tt_vin_sweep.csv').open(newline='') as handle:
        sweep=list(csv.DictReader(handle))
    fig,ax=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for load in [1e-4,5e-3]:
        chosen=sorted([r for r in sweep if float(r['load_a'])==load],key=lambda r:float(r['vin_v']))
        ax[0].plot([float(r['vin_v']) for r in chosen],[float(r['vout_v']) for r in chosen],'.-',label=str(load*1e3)+' mA')
        ax[1].plot([float(r['vin_v']) for r in chosen],[float(r['iq_a'])*1e6 for r in chosen],'.-',label=str(load*1e3)+' mA')
    ax[0].set(xlabel='VIN (V)',ylabel='VOUT (V)'); ax[1].set(xlabel='VIN (V)',ylabel='Core IQ (uA)')
    for axis in ax: axis.legend(fontsize=8)
    fig.suptitle('Nominal DC sweep: 10 mV input increments; model outputs, no silicon claim')
    fig.savefig(dst/'dc_sweep.png',dpi=160); plt.close(fig)
    return {'status':'generated','files':[p.relative_to(out).as_posix() for p in sorted(dst.glob('*.png'))]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir',type=Path,required=True,help='Fresh output directory')
    parser.add_argument('--no-plots',action='store_true')
    cli=parser.parse_args()
    if cli.outdir.exists():
        raise SystemExit('Output directory already exists; choose a fresh directory.')
    args=general.parser().parse_args([])
    args.recovery_center='target'
    static=load(PROJECT/'data/static.json')['cases']
    if len(static)!=164:
        raise ValueError('Expected 164 published static conditions')
    cases={}; data={}
    for entry in load(PROJECT/'data/transients/index.json'):
        case,waves=transient_case(entry,args); cases[entry['case']]=case; data[entry['case']]=waves
    if len(cases)!=10 or sum(len(c['events']) for c in cases.values())!=20:
        raise ValueError('Expected 10 transient cases and 20 events')
    native=native_table()
    comparisons=convergence(cases,data)
    nominal={}
    for name in ['r6_pvt_tt_27_light','r6_pvt_tt_27_heavy']:
        base=PROJECT/'data/nominal'/name
        nominal[name]={'ac':general.ac_analysis(strict_csv(base/'ac.csv','ac')),
                       'noise':noise_rms(base/'noise.csv'),'native':load(base/'native.json')}
    result={'schema_version':1,'process':'130 nm CMOS','revision':6,
        'reproduction_scope':'exported samples and published native scalar results; private simulation not rerun',
        'simulation_completion_reverified_here':False,'automatic_performance_or_reliability_pass':None,
        'static_condition_count':len(static),'transient_case_count':len(cases),'event_count':20,
        'saved_transient_samples':sum(c['saved_samples'] for c in cases.values()),
        'data_sha256':{p.relative_to(PROJECT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted((PROJECT/'data').rglob('*')) if p.is_file()},
        'native_stability':native,'transients':list(cases.values()),'nominal':nominal}
    cli.outdir.mkdir(parents=True)
    result['plots']={'status':'disabled'} if cli.no_plots else plots(cli.outdir,static,cases,data)
    if not cli.no_plots and result['plots']['status']=='generated':
        from render_circuits import draw_all
        result['plots']['files'].extend('figures/'+name for name in draw_all(cli.outdir/'figures'))
    dump(cli.outdir/'summary.json',result)
    dump(cli.outdir/'convergence.json',comparisons)
    write_events(cli.outdir/'events.csv',cases)
    from figures_of_merit import write as write_figures_of_merit
    write_figures_of_merit(cli.outdir,result)
    print(json.dumps({'static':164,'transients':10,'events':20,
        'exported_measurement_parity':'verified','plots':result['plots']['status'],
        'saved_samples':result['saved_transient_samples']}))

if __name__=='__main__':
    main()

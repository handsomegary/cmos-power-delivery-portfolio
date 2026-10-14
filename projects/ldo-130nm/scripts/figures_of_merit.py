#!/usr/bin/env python3
"""Literature-defined LDO transient FoMs from this project's exported measurements.

The equations have different voltage and current definitions. They are not
interchangeable, and neither returns the measured settling/recovery time.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
DEFINITIONS={
    'sum_maxload':{
        'source_doi':'10.3390/mi15081019','source_equation':'14',
        'formula':'Cout * (undershoot_up + overshoot_down) * IQ / Iload_max**2',
        'voltage_definition':'sum of primary load-up undershoot and unload overshoot; fixed 0.9 V target',
        'load_denominator':'maximum load current squared; not load-step amplitude squared',
        'unit':'s','lower_is_better_within_matched_scope':True},
    'single_spike_step':{
        'source_doi':'10.1587/elex.19.20220051','source_equation':'Table 1 footnote',
        'formula':'Cout * single_peak_deviation * IQ / abs(load_high-load_low)**2',
        'voltage_definition':'one spike per event; cycle summary uses max(up undershoot, down overshoot), not their sum',
        'load_denominator':'actual load-step amplitude squared; not maximum load squared',
        'unit':'s','lower_is_better_within_matched_scope':True},
    'edge_process_normalized':{
        'source_doi':'10.3390/mi13101668','source_equation':'10',
        'formula':'Tedge * DeltaV * (IQ + Iload_min) / (DeltaIload * Lmin**2)',
        'value':None,'status':'unavailable',
        'reason':'qualified technology minimum channel length is not established; nominal node and drawn pass length are not substituted'},
    'measurement_conventions':{
        'iq':'maximum of the two matching endpoint static core-IQ values; both endpoints and their average are also retained',
        'iq_power_scope':'amplifier, driver, bias, divider included; ideal reference power outside scope',
        'capacitance':'declared external ideal zero-ESR Cout; no extracted effective output-parasitic capacitance claim',
        'voltage_baseline':'existing fixed-target 0.9 V deviations, not a newly substituted pre-event DC level',
        'edge':'actual event ramp duration retained; neither capacitance-based equation explicitly normalizes ramp duration',
        'recovery':'separately measured last band entry, 0.891-0.909 V; ramp-end and ramp-start times retained',
        'comparability':'requires matched edge time, capacitance scope, baseline, IQ convention, load range, and simulation/measurement status; no literature ranking'},
}

def finite_positive(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
        raise ValueError(name+' must be finite and positive')
    return float(value)

def derive(summary):
    output=[]
    for case in summary['transients']:
        condition=case['condition']
        if condition['mode']!='load_tran':
            continue
        events=case['events']
        if len(events)!=2:
            raise ValueError('Expected two matched load transitions')
        up,down=events
        refs=condition['dc_references']
        low,high=refs['pre']['dc'],refs['high']['dc']
        if refs['post']['case']!=refs['pre']['case']:
            raise ValueError('Low-load endpoint references differ')
        cout=finite_positive(condition['cout_f'],'Cout')
        ilow=finite_positive(low['load_a'],'load_low')
        ihigh=finite_positive(high['load_a'],'load_high')
        delta=finite_positive(ihigh-ilow,'load_step')
        qlow=finite_positive(low['iq_a'],'IQ_low')
        qhigh=finite_positive(high['iq_a'],'IQ_high')
        iq=max(qlow,qhigh)
        undershoot=finite_positive(up['undershoot_from_target_v'],'undershoot')
        overshoot=finite_positive(down['overshoot_from_target_v'],'overshoot')
        edge_up=finite_positive(up['definition']['edge_end_s']-up['definition']['edge_start_s'],'up ramp')
        edge_down=finite_positive(down['definition']['edge_end_s']-down['definition']['edge_start_s'],'down ramp')
        event_rows=[]
        for event,spike,direction in [(up,undershoot,'load_increase'),(down,overshoot,'unload')]:
            recovery=event['recovery']
            if recovery['status']!='computed_estimate':
                raise ValueError('Recovery unavailable; do not substitute a capacitance-based response estimate')
            event_rows.append({'event':event['name'],'direction':direction,'peak_v':spike,
                'edge_s':event['definition']['edge_end_s']-event['definition']['edge_start_s'],
                'fom_single_spike_step_s':cout*spike*iq/delta**2,
                'recovery_from_edge_end_s':recovery['from_edge_end_s'],
                'recovery_from_edge_start_s':recovery['from_edge_start_s'],
                'recovery_observation_end_s':recovery['observation_end_s'],
                'recovery_method':recovery['method']})
        output.append({'case':case['case'],'temperature_c':condition['temperature_c'],
            'process_corner':condition['model_section'],'cout_f':cout,
            'edge_up_s':edge_up,'edge_down_s':edge_down,'load_low_a':ilow,'load_high_a':ihigh,
            'load_delta_a':delta,'load_max_a':ihigh,'iq_low_a':qlow,'iq_high_a':qhigh,
            'iq_endpoint_average_a':(qlow+qhigh)/2,'iq_used_a':iq,
            'iq_used_over_max_load':iq/ihigh,'iq_used_over_load_step':iq/delta,
            'undershoot_up_v':undershoot,'overshoot_down_v':overshoot,
            'primary_peak_to_peak_v':undershoot+overshoot,
            'unload_secondary_undershoot_v':down['post_primary_peak_undershoot_from_target_v'],
            'fom_sum_maxload_s':cout*(undershoot+overshoot)*iq/ihigh**2,
            'fom_single_worst_step_s':cout*max(undershoot,overshoot)*iq/delta**2,
            'step_vs_max_squared_factor':(ihigh/delta)**2,'events':event_rows,
            'total_extracted_capacitance_fom_s':None,
            'area_normalized_fom':None,'reliability_or_performance_pass':None})
    if len(output)!=8:
        raise ValueError('Expected eight load cases; line events are not LDO load-transient FoMs')
    return {'schema_version':1,'revision':6,'process':'130 nm CMOS',
        'definitions':DEFINITIONS,'cases':output,
        'stability_boundaries':summary['native_stability'],
        'scope':'derived from exported simulation samples and matching static references; not fabricated measurements',
        'ranking_against_literature':None}

def write(out,summary):
    result=derive(summary)
    public_files=[PROJECT/'data/static.json',PROJECT/'scripts/figures_of_merit.py']
    for case in result['cases']:
        public_files.extend(PROJECT/'data/transients'/case['case']/name for name in ['waveform.csv','metadata.json','events.json','expected.json'])
    result['public_input_sha256']={p.relative_to(PROJECT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in public_files}
    out.mkdir(parents=True,exist_ok=True)
    (out/'figures_of_merit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    fields=['case','process_corner','temperature_c','cout_f','edge_up_s','edge_down_s',
            'load_low_a','load_high_a','load_delta_a','iq_low_a','iq_high_a','iq_used_a',
            'undershoot_up_v','overshoot_down_v','primary_peak_to_peak_v',
            'fom_sum_maxload_s','fom_single_worst_step_s','unload_secondary_undershoot_v']
    with (out/'figures_of_merit.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fields,extrasaction='ignore'); writer.writeheader(); writer.writerows(result['cases'])
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir',type=Path,required=True,help='Fresh output directory')
    args=parser.parse_args()
    if args.outdir.exists():
        raise SystemExit('Choose a fresh output directory')
    # Remeasure the exported waveforms rather than treating a retained summary as evidence.
    import reproduce
    general_args=reproduce.general.parser().parse_args([])
    cases=[reproduce.transient_case(entry,general_args)[0] for entry in reproduce.load(PROJECT/'data/transients/index.json')]
    result=write(args.outdir,{'transients':cases,'native_stability':reproduce.native_table()})
    print(json.dumps({'load_cases':len(result['cases']),'equation_families':2,'literature_ranking':None}))

if __name__=='__main__':
    main()

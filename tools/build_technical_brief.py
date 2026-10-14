"""Build the two-column technical brief from the published project assets."""
from pathlib import Path
import argparse
import csv
import json
import math

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).resolve().parents[1]
BLUE = colors.HexColor('#174568')
INK = colors.HexColor('#111111')
GRAY = colors.HexColor('#555555')
PAGE_W, PAGE_H = 612, 792
LEFT, RIGHT, BOTTOM, TOP = 38, 574, 42, 748
COL = 257
GUTTER = 22

STYLES = {
    'body': ParagraphStyle('body', fontName='Times-Roman', fontSize=9.5, leading=11.6, textColor=INK, spaceAfter=6),
    'small': ParagraphStyle('small', fontName='Times-Roman', fontSize=8, leading=9.4, textColor=INK),
    'caption': ParagraphStyle('caption', fontName='Times-Roman', fontSize=8.3, leading=10, textColor=INK),
    'heading': ParagraphStyle('heading', fontName='Times-Bold', fontSize=10.6, leading=13, textColor=INK, spaceAfter=6),
    'title': ParagraphStyle('title', fontName='Times-Bold', fontSize=17, leading=19.5, alignment=1, textColor=INK),
    'subtitle': ParagraphStyle('subtitle', fontName='Times-Roman', fontSize=9.5, leading=12, alignment=1, textColor=GRAY),
    'cell': ParagraphStyle('cell', fontName='Times-Roman', fontSize=7.5, leading=9.0, textColor=INK),
    'cell_head': ParagraphStyle('cell_head', fontName='Times-Bold', fontSize=7.4, leading=9.0, textColor=INK),
}


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def safe(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class Page:
    def __init__(self, pdf, number, heading):
        self.pdf = pdf
        self.number = number
        pdf.setStrokeColor(INK)
        pdf.setLineWidth(.55)
        pdf.line(LEFT, 758, RIGHT, 758)
        pdf.setFillColor(GRAY)
        pdf.setFont('Times-Roman', 8)
        pdf.drawString(LEFT, 765, 'CMOS POWER DELIVERY | TECHNICAL REPORT')
        pdf.drawRightString(RIGHT, 765, '130 nm CMOS | 14 October 2026')
        self.heading = heading
        self.y = TOP

    def paragraph(self, text, x=LEFT, y=None, width=COL, style='body'):
        y = self.y if y is None else y
        item = Paragraph(text, STYLES[style])
        _, height = item.wrap(width, PAGE_H)
        if y-height < BOTTOM:
            raise ValueError(f'Page {self.number} overflows: {text[:70]}')
        item.drawOn(self.pdf, x, y-height)
        return y-height-6

    def section(self, text, x=LEFT, y=None, width=COL):
        return self.paragraph(text, x, y, width, 'heading')

    def table(self, headers, rows, widths, x=LEFT, y=None, font=7.5):
        y = self.y if y is None else y
        data = [[Paragraph(safe(v), STYLES['cell_head']) for v in headers]]
        data.extend([[Paragraph(safe(v), STYLES['cell']) for v in row] for row in rows])
        item = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        item.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LINEABOVE',(0,0),(-1,0),.8,INK),
            ('LINEBELOW',(0,0),(-1,0),.55,INK),
            ('LINEBELOW',(0,-1),(-1,-1),.8,INK),
            ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ]))
        _, height = item.wrap(sum(widths), PAGE_H)
        if y-height < BOTTOM:
            raise ValueError(f'Page {self.number} table overflows ({height:.1f} pt)')
        item.drawOn(self.pdf,x,y-height)
        return y-height-8

    def image(self, relative, caption, y, max_height, width=RIGHT-LEFT):
        path = ROOT / relative
        im = ImageReader(str(path))
        iw, ih = im.getSize()
        height = min(max_height, width * ih / iw)
        drawn_width = height * iw / ih
        if y-height < BOTTOM:
            raise ValueError('Figure overflows')
        self.pdf.drawImage(im,LEFT+(width-drawn_width)/2,y-height,drawn_width,height,mask='auto')
        return self.paragraph(caption,LEFT,y-height-7,width,'caption')

    def finish(self):
        self.pdf.setFillColor(GRAY)
        self.pdf.setFont('Times-Roman',8)
        self.pdf.drawString(LEFT,25,'Schematic-level simulation and analysis')
        self.pdf.drawRightString(RIGHT,25,str(self.number))
        self.pdf.showPage()


def architecture_page(pdf):
    p=Page(pdf,2,'Architecture')
    y=p.section('II. CIRCUIT ARCHITECTURES',width=RIGHT-LEFT)
    y=p.image('projects/ldo-130nm/results/figures/architecture.png',
        '<b>Fig. 1.</b> LDO regulation path, bias, feedback and compensation. Solid power connections and explicit feedback polarity identify the implemented loop. The reference and external output capacitor are testbench elements.',y,270)
    y-=12
    y=p.image('projects/two-phase-buck/figures/block_diagram.png',
        '<b>Fig. 2.</b> Two-phase Buck, remote load and transient-assist architecture. The energy path, analog detector path and behavioral control boundary are distinguished. Source and sink assist act at VLOAD.',y,280)
    p.finish()


def first_page(pdf):
    p=Page(pdf,1,'Overview')
    y=p.paragraph('Transistor-Level LDO and PDN-Aware Two-Phase Buck<br/>in 130 nm CMOS',LEFT,746,RIGHT-LEFT,'title')
    y=p.paragraph('Circuit design, transient-assist tradeoffs, and reproducible numerical verification',LEFT,y,RIGHT-LEFT,'subtitle')
    y-=7
    left=y
    left=p.paragraph('<b>Abstract - </b>Two complementary power-delivery studies are presented. A nine-MOS analog LDO regulates 0.9 V from 1.2 V and is evaluated over 164 static/DC conditions and ten transient runs. A mixed-level two-phase Buck combines transistor power bridges, drivers and window detectors with behavioral PI/PWM control. Forty-seven main cases and eight gate-resistance cases characterize remote-load droop, unload overshoot and solver sensitivity. Complete device sizing and block functions connect circuit decisions to measured simulation outcomes. All results are pre-layout; the reference, passive-network assumptions and controller-power boundary are stated with the metrics.',y=left)
    left=p.section('I. DESIGN OBJECTIVE AND VERIFICATION',y=left)
    left=p.paragraph('Power delivery is assessed at the point where the load receives energy. Regulation accuracy, response latency, capacitance, parasitic impedance and control effort are evaluated together. The two circuits are separate studies; this report does not imply that they have already been integrated into a hierarchical supply system.',y=left)
    left=p.paragraph('The analysis distinguishes transistor simulation, saved numerical samples, derived measurements and normalized metrics. A case finishing successfully establishes data availability, while stability margin, waveform recovery and device headroom require their own evidence.',y=left)
    left=p.section('A. LDO regulation path',y=left)
    left=p.paragraph('M2-M3 sense VREF and the divided output. M4 supplies the input-stage tail current; M5 and the 100-kohm resistor establish bias. M6-M7 form the mirror load. The M8-M9 common-source driver controls the gate of PMOS pass device M1. The feedback divider is 200 kohm / 200 kohm. The dominant series compensation branch uses 36 kohm and 18 pF.',y=left)
    left=p.paragraph('Negative feedback was checked from saved connectivity and DC operating points. Increased feedback voltage reduces EAOUT, raises the pass gate through the driver and reduces pass conduction. The STB probe between FB and FBIN is included in the detailed circuit description.',y=left)
    right=y
    x=LEFT+COL+GUTTER
    right=p.section('B. Buck energy and control paths',x,right)
    right=p.paragraph('The two power bridges are driven 180 degrees apart. Each phase supplies a 2.2-uH external inductor. VCONV is connected to the remote VLOAD through declared resistance and inductance. Output and load capacitors include the stated ESR/ESL test parasitics.',x,right)
    right=p.paragraph('The transistor implementation contains 12 power-bridge MOS, 24 gate-driver MOS, 20 voltage-window-comparator MOS and three source/sink-assist MOS instances. The controller samples voltage and ideal current-sense signals, generates the PI/PWM commands and supervises the finite assist sequence. Its internal power is not modeled.',x,right)
    right=p.paragraph('The selected assist strategy changes the PI current state by 40 mA while the analog helper sources or sinks current at VLOAD. The arbitration interval is 2 us; its end does not erase the resulting integrator state. Gate resistance in revision r9 modifies assist edge rates while preserving device geometry.',x,right)
    right=p.section('TABLE I. PRINCIPAL TEST CONDITIONS',x,right)
    right=p.table(['Quantity','LDO','Two-phase Buck'],[
        ['Process / MOS instances','130 nm / 9','130 nm / 59'],
        ['VIN / target VOUT','1.2 / 0.9 V','1.8 / 0.9 V'],
        ['Nominal load step','0.1 to 5 mA','10 to 100 mA'],
        ['Test capacitance','External 1 nF','1 uF + remote 10 nF'],
        ['Switching frequency','Continuous-time','5 MHz nominal'],
        ['Reference / control','Ideal / transistor','Behavioral PI/PWM'],
    ],[89,79,89],x,right)
    right=p.paragraph('Figures 1-2 identify each functional path. Section III defines the normalized metrics and their denominators. Appendix A discloses unit width, length, parallel multiplicity, finger count and total drawn width.',x,right,style='small')
    p.finish()


def ldo_metrics():
    summary = load('projects/ldo-130nm/results/summary.json')
    published = load('projects/ldo-130nm/results/figures_of_merit.json')
    selected = []
    for name, label in [('r6_load_C1000_T100', 'TT, 27 C, 100 ns'),
                        ('r6_load_C1000_T10', 'TT, 27 C, 10 ns'),
                        ('r6_corner_tran_ss_125', 'SS, 125 C, 100 ns')]:
        case = next(c for c in summary['transients'] if c['case'] == name)
        condition = case['condition']
        up, down = case['events']
        dc = condition['dc_references']
        iq = max(dc['pre']['dc']['iq_a'], dc['high']['dc']['iq_a'])
        ilow = dc['pre']['dc']['load_a']
        imax = dc['high']['dc']['load_a']
        delta_i = imax - ilow
        undershoot = up['undershoot_from_target_v']
        overshoot = down['overshoot_from_target_v']
        cout = condition['cout_f']
        row=dict(name=name, label=label, iq=iq, undershoot=undershoot,
                             overshoot=overshoot, recovery_up=up['recovery']['value'],
                             recovery_down=down['recovery']['value'],
                             fom_sum=cout*(undershoot+overshoot)*iq/imax**2,
                             fom_step_up=cout*undershoot*iq/delta_i**2,
                             fom_step_down=cout*overshoot*iq/delta_i**2,
                             proxy_up=cout*undershoot/delta_i,
                             secondary=down['post_primary_peak_undershoot_from_target_v'])
        retained=next(c for c in published['cases'] if c['case']==name)
        if not math.isclose(row['fom_sum'],retained['fom_sum_maxload_s'],rel_tol=1e-12,abs_tol=1e-21):
            raise ValueError('Report FoM differs from the published calculation')
        selected.append(row)
    return summary, selected


def buck_pair(name, event):
    data = load('projects/two-phase-buck/data/r8_measurements.json')
    pair = next(p for p in data['pairs'] if p['name'] == name)
    result = next(e for e in pair['events'] if e['event'] == event)
    conditions = []
    for case_name in [pair['baseline'], pair['variant']]:
        conditions.append(next(c['config']['parameters'] for c in data['cases']
                               if c['name'] == case_name))
    if conditions[0]['FSW'] != conditions[1]['FSW'] or conditions[0]['VOUT_REQ'] != conditions[1]['VOUT_REQ']:
        raise ValueError('Unmatched normalization conditions')
    return result, conditions[0]


def metrics_page(pdf):
    _, cases = ldo_metrics()
    p = Page(pdf,3,'Figures of merit')
    y = p.section('III. FIGURES OF MERIT AND MEASUREMENT DEFINITIONS',width=RIGHT-LEFT)
    left = p.section('A. Capacitance-weighted LDO FoM',y=y)
    left = p.paragraph('The primary scalar follows the sum-excursion convention in [1, Eq. 14]. Lower is better only when the operating conditions and metric boundaries are comparable.',y=left)
    left = p.paragraph('<i>F</i><sub>C,sum,max</sub> = C<sub>ext</sub> (dV<sub>under</sub> + dV<sub>over</sub>) I<sub>Q</sub> / I<sub>max</sub><super>2</super>  [s]',y=left)
    left = p.paragraph('Here Cext = 1 nF is an external ideal zero-ESR test capacitor; Imax = 5 mA; the load step is 0.1 to 5 mA. Voltage excursions are measured against the fixed 0.9-V target. IQ is the larger of the matched light/heavy DC endpoints at the same process, temperature, input voltage and revision. It includes the modeled amplifier, bias, driver and divider; implemented-reference power is absent.',y=left)
    left = p.section('TABLE II. PRIMARY LDO FoM',y=left)
    left = p.table(['Condition','IQ (uA)','Sum (mV)','FoM (ps)'],[
        [c['label'],f"{c['iq']*1e6:.3f}",f"{(c['undershoot']+c['overshoot'])*1e3:.3f}",f"{c['fom_sum']*1e12:.2f}"] for c in cases
    ],[96,49,56,56],y=left)
    left = p.section('B. Separate per-edge convention',y=left)
    left = p.paragraph('The step-based single-spike definition [2, Table I] is reported separately:',y=left)
    left = p.paragraph('<i>F</i><sub>C,edge,step</sub> = C<sub>ext</sub> dV<sub>edge</sub> I<sub>Q</sub> / (dI<sub>load</sub>)<super>2</super>  [s]',y=left)
    c = cases[0]
    left = p.paragraph(f"At TT, 27 C and 100 ns, dI = 4.9 mA gives {c['fom_step_up']*1e12:.2f} ps for load-up and {c['fom_step_down']*1e12:.2f} ps for unload. These numbers use one directional peak and a different denominator from Table II.",y=left)
    left = p.paragraph(f"Cext dVunder / dI = {c['proxy_up']*1e9:.3f} ns is a charge-deficit time proxy. Actual load-up recovery is {c['recovery_up']*1e6:.3f} us. The proxy is not a settling-time or bandwidth measurement.",y=left)
    x = LEFT+COL+GUTTER
    right = p.section('C. Buck normalized transient diagnostics',x,y)
    right = p.paragraph('Two transparent descriptors are used because physical controller power and active layout area are unavailable:',x,right)
    right = p.paragraph('Normalized excursion = 100 dVpeak / Vtarget  [%]<br/>Recovery cycles = fsw t<sub>recovery</sub>  [cycles]',x,right)
    right = p.paragraph('fsw is the per-phase switching frequency, 5 MHz for the selected cases. OFF/ON comparisons require the same PDN, passives, load edge, phase offset and solver settings, except for the explicitly changed assist flags. They describe this design and do not establish a universal Buck ranking.',x,right)
    rows=[]
    for pair,event,label,metric in [('v3_nom100','load_up','Nominal up','droop'),('v3_pdn_hard_p0','load_down','Hard-PDN down','overshoot')]:
        e,config=buck_pair(pair,event)
        key='droop_from_target_v' if metric=='droop' else 'overshoot_from_target_v'
        rows.append([label,f"{100*e[key+'_baseline']/config['VOUT_REQ']:.3f}",f"{100*e[key+'_variant']/config['VOUT_REQ']:.3f}"])
    right=p.table(['Condition','OFF peak (%)','ON peak (%)'],rows,[95,81,81],x,right)
    right=p.paragraph('Nominal load-up recovery changes from 37.736 to 68.703 cycles. A smaller peak therefore coexists with slower recovery. The hard-PDN unload case also exposes an increased overshoot.',x,right)
    right=p.section('D. Recovery and energy boundaries',x,right)
    right=p.paragraph('Recovery uses the 0.891-0.909 V band and is qualified only through the finite observation window. LDO recovery is timed from the ramp end. Buck raw-grid and cycle-mean recovery are timed from the event start and remain separate measurements.',x,right)
    right=p.paragraph('Helper work is the signed integral of VLOAD times helper current over the declared event window. Source and sink directions are retained separately. Modeled supply-port event energy includes converter, driver and helper interactions; its OFF/ON difference is not helper-only energy or full physical efficiency.',x,right)
    right=p.section('REFERENCES FOR METRIC CONVENTIONS',x,right)
    right=p.paragraph('[1] Y. Zhang et al., output-capacitor-less LDO with sub-threshold slew-rate enhancement, <i>Micromachines</i>, vol. 15, art. 1019, 2024, Eq. 14. <link href="https://doi.org/10.3390/mi15081019" color="#174568">doi:10.3390/mi15081019</link>.<br/>[2] Y. Yao et al., <i>IEICE Electronics Express</i>, vol. 19, art. 20220051, 2022, Table I. <link href="https://doi.org/10.1587/elex.19.20220051" color="#174568">doi:10.1587/elex.19.20220051</link>.',x,right,style='small')
    p.finish()


def ldo_results_page(pdf):
    summary,cases=ldo_metrics()
    p=Page(pdf,4,'LDO results')
    y=p.section('IV. LDO PERFORMANCE AND STABILITY BOUNDARY',width=RIGHT-LEFT)
    y=p.image('projects/ldo-130nm/results/figures/transients.png',
        '<b>Fig. 3.</b> Load-step response, pass-gate response and input-step response from exported simulation samples. The ideal external output capacitance is 1 nF. Curves include the nominal and slow/hot conditions.',y,330)
    y-=7
    y=p.table(['Condition','Up under (mV)','Down over (mV)','Up recovery (us)','Down recovery (us)','Secondary under (mV)'],[
        [c['label'],f"{c['undershoot']*1e3:.3f}",f"{c['overshoot']*1e3:.3f}",f"{c['recovery_up']*1e6:.3f}",f"{c['recovery_down']*1e6:.3f}",f"{c['secondary']*1e3:.3f}"] for c in cases
    ],[112,79,81,87,92,85],y=y)
    left=p.section('A. Stability versus test capacitance',y=y)
    left=p.paragraph('At TT, 27 C and 1 nF, native loop results at 0.1 / 1 / 5 mA give phase margins of 72.44 / 76.17 / 74.76 degrees and gain margins of 38.46 / 23.19 / 18.47 dB. At 100 pF the 5-mA margin falls to 6.62 degrees / 1.27 dB. All three 10-pF cases are identified as unstable by the native analysis.',y=left)
    left=p.paragraph('The 1-nF compensation result does not establish capacitor-less operation. Vin = 1.1-V corners also reveal limited tail/driver headroom; saturation is assessed per operating point.',y=left)
    x=LEFT+COL+GUTTER
    right=p.section('B. DC accuracy and numerical checks',x,y)
    right=p.paragraph('The TT load-regulation slope is -0.01185 mV/mA over 0.1-5 mA. Line-regulation slopes are 0.3753 / 0.4766 mV/V at light/heavy load over Vin = 1.1-1.2 V. The 5-mA dropout estimate is about 131 mV under the stated 1% definition, bracketed by a 10-mV input sweep.',x,right)
    right=p.paragraph('Independent maxstep comparisons change the selected primary peaks by at most 11.864 uV. PSRR, integrated output noise, PVT, full event definitions and all smaller-capacitance failures remain available in the repository. Noise excludes implemented-reference noise.',x,right)
    p.finish()


def buck_results_page(pdf):
    p=Page(pdf,5,'Buck results')
    y=p.section('V. BUCK TRANSIENT-ASSIST TRADEOFFS',width=RIGHT-LEFT)
    y=p.image('projects/two-phase-buck/figures/tradeoffs.png',
        '<b>Fig. 4.</b> Matched OFF/ON transient outcomes, hard-PDN unload behavior and solver sensitivity. The waveform panel uses selected display samples; scalar measurements and event work retain their original full-grid measurement provenance.',y,340)
    y-=8
    left=p.section('A. Assist benefit and adverse conditions',y=y)
    left=p.paragraph('At nominal 100-ns load-up, coordinated assist reduces droop from 143.370 to 107.386 mV but increases recovery from 7.547 to 13.741 us. Nominal unload overshoot improves from 84.175 to 52.562 mV. These two directions have different energy and control-state demands.',y=left)
    left=p.paragraph('For RPDN = 0.3 ohm, LPDN = 2 nH and CLOAD = 2 nF with a 10-ns edge, r8 unload overshoot rises from 86.889 to 110.298 mV. Revision r9 gate resistance reduces the ON peak to 94.554 mV; its matched OFF result is 87.129 mV. The adverse condition remains visible.',y=left)
    left=p.section('B. Analog and behavioral partition',y=left)
    left=p.paragraph('The transistor detectors, bridge, gate drivers and helper devices establish circuit-level interactions. PI/PWM, timing, supervision, programmable reference and ideal current sensing are behavioral. Port energy is meaningful within that modeled boundary; full physical efficiency and controller-IQ FoMs are unavailable.',y=left)
    x=LEFT+COL+GUTTER
    right=p.section('C. Coverage and solver sensitivity',x,y)
    right=p.paragraph('The main set has 47 completed cases, 24 declared comparisons and 94 events. All 141 steady means fall within the target band, but 127 finite-window periodicity checks are not accepted. The r9 set adds eight cases and four matched comparisons. Completion and average regulation do not establish switching-loop signoff.',x,right)
    right=p.paragraph('Main-set sensitivity checks show up to 1.245-mV primary-peak change and 73.770-mV pointwise VLOAD difference. For r9, the hard-PDN ON unload peak changes from 94.554 to 97.637 mV in the finer solve. Recovery and ringing remain solver-sensitive.',x,right)
    right=p.section('D. Reproducibility and scope',x,right)
    right=p.paragraph('The public scripts regenerate numerical comparisons and figures from the published exports. Hashes bind inputs and curated assets. Complete sizing, terminal ordering, assist supervision and passive values are provided in each project directory.',x,right)
    right=p.paragraph('All reported results are schematic-level simulations. Layout extraction, mismatch/yield, absolute-maximum qualification, hardware measurements and a closed switching-loop stability analysis remain future verification work.',x,right)
    p.finish()


def sizing_page(pdf):
    p=Page(pdf,6,'Sizing')
    y=p.section('APPENDIX A. COMPLETE MOS SIZING',width=RIGHT-LEFT)
    y=p.paragraph('W and L are in micrometers. Wtot = Wunit x m x nf; all reported nf values are 1. These are drawn transistor dimensions, not layout area. Drain/gate/source/bulk connections and block assignments are provided in the repository design tables.',LEFT,y,RIGHT-LEFT,'small')
    ldo=[[d['id'],'P' if d['type']=='PMOS' else 'N',d['w_unit_um'],d['l_um'],d['m'],d['nf'],d['w_total_um']]
         for d in load('projects/ldo-130nm/data/circuit.json')['devices']]
    if len(ldo)!=9:
        raise ValueError('Unexpected LDO transistor count')
    with (ROOT/'projects/two-phase-buck/data/mos_dimensions.csv').open(encoding='utf-8',newline='') as f:
        hardware=list(csv.DictReader(f))
    buck=[]
    for row in hardware:
        polarity='P' if 'PMOS' in row['type'] else 'N'
        buck.append([row['instance'],polarity,float(row['Wunit_um']),
                     float(row['L_um']),float(row['m']),float(row['nf']),
                     float(row['Wtotal_um'])])
    if len(buck)!=59:
        raise ValueError('Unexpected Buck transistor count')
    for _,_,w,_,m,nf,total in ldo+buck:
        if nf!=1 or not math.isclose(w*m*nf,total,rel_tol=1e-12):
            raise ValueError('Unexpected finger or total-width convention')
    def numeric(rows):
        return [[v if isinstance(v,str) else f'{v:.5g}' for v in row] for row in rows]
    headers=['Device','P/N','Wunit','L','m','nf','Wtot']
    widths=[67,25,37,29,21,18,49]
    left=p.section('LDO: all nine MOS instances',y=y)
    left=p.table(headers,numeric(ldo),widths,y=left)
    left=p.section('Buck: instances 1-25 of 59',y=left)
    left=p.table(headers,numeric(buck[:25]),widths,y=left)
    x=LEFT+COL+GUTTER
    right=p.section('Buck: instances 26-59 of 59',x,y)
    right=p.table(headers,numeric(buck[25:]),widths,x,right)
    p.paragraph('Revision r9 retains these 59 MOS geometries and adds 1-kohm / 2-kohm assist gate resistors. Some driver drain node names change in r9; its separate connectivity inventory records those changes.',x,right,style='small')
    p.finish()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/technical-brief.pdf')
    args=parser.parse_args()
    output=args.output.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(output),pagesize=(PAGE_W,PAGE_H),pageCompression=1,invariant=1)
    pdf.setTitle('130 nm CMOS Power Delivery: Circuit Design and Numerical Verification')
    pdf.setAuthor('Guan Cheng Lin')
    pdf.setSubject('Simulation-based technical report: LDO and two-phase Buck')
    first_page(pdf)
    architecture_page(pdf)
    metrics_page(pdf)
    ldo_results_page(pdf)
    buck_results_page(pdf)
    sizing_page(pdf)
    pdf.save()
    print(output)


if __name__=='__main__':
    main()

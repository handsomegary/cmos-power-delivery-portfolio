#!/usr/bin/env python3
"""Draw the disclosed LDO circuit using black, white, and one blue accent."""
import argparse
import hashlib
import json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
BLUE='#005A9C'
BLACK='#101010'

class Drawing:
    def __init__(self,width,height):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        self.plt=plt
        self.fig,self.ax=plt.subplots(figsize=(width/100,height/100))
        self.fig.subplots_adjust(left=.012,right=.988,bottom=.012,top=.988)
        self.ax.set(xlim=(0,width),ylim=(height,0),aspect='equal')
        self.ax.axis('off')
    def line(self,points,color=BLACK,lw=1.5,ls='-'):
        self.ax.plot([p[0] for p in points],[p[1] for p in points],color=color,lw=lw,
                     linestyle=ls,solid_capstyle='butt',solid_joinstyle='miter')
    def text(self,x,y,value,size=12,ha='left',color=BLACK,weight='normal',va='center'):
        self.ax.text(x,y,value,fontsize=size,ha=ha,va=va,color=color,
                     fontfamily='DejaVu Sans',weight=weight,linespacing=1.3)
    def dot(self,x,y):
        from matplotlib.patches import Circle
        self.ax.add_patch(Circle((x,y),3,fc=BLACK,ec=BLACK))
    def arrow(self,points,color=BLACK,lw=1.5):
        self.line(points[:-1],color,lw)
        self.ax.annotate('',xy=points[-1],xytext=points[-2],
                         arrowprops={'arrowstyle':'-|>','color':color,'lw':lw,'shrinkA':0,'shrinkB':0})
    def box(self,x,y,w,h,title,detail=None):
        from matplotlib.patches import Rectangle
        self.ax.add_patch(Rectangle((x,y),w,h,fc='white',ec=BLACK,lw=1.5))
        self.text(x+w/2,y+24,title,13,ha='center',weight='bold')
        if detail:
            self.text(x+w/2,y+h/2+12,detail,11,ha='center')
    def ground(self,x,y):
        self.line([(x,y-12),(x,y)])
        for dy,w in [(0,24),(7,16),(14,8)]:
            self.line([(x-w/2,y+dy),(x+w/2,y+dy)])
    def resistor(self,x,y,horizontal=False,label=None):
        from matplotlib.patches import Rectangle
        if horizontal:
            self.line([(x-42,y),(x-25,y)]); self.line([(x+25,y),(x+42,y)])
            self.ax.add_patch(Rectangle((x-25,y-9),50,18,fc='white',ec=BLACK,lw=1.5))
            if label: self.text(x,y-25,label,11,ha='center')
        else:
            self.line([(x,y-42),(x,y-25)]); self.line([(x,y+25),(x,y+42)])
            self.ax.add_patch(Rectangle((x-9,y-25),18,50,fc='white',ec=BLACK,lw=1.5))
            if label: self.text(x+20,y,label,11)
    def capacitor(self,x,y,horizontal=False,label=None):
        if horizontal:
            self.line([(x-35,y),(x-5,y)]); self.line([(x+5,y),(x+35,y)])
            for xx in [x-5,x+5]: self.line([(xx,y-18),(xx,y+18)])
            if label: self.text(x,y-30,label,11,ha='center')
        else:
            self.line([(x,y-35),(x,y-5)]); self.line([(x,y+5),(x,y+35)])
            for yy in [y-5,y+5]: self.line([(x-18,yy),(x+18,yy)])
            if label: self.text(x+25,y,label,11)
    def mos(self,x,y,device,labels=True):
        # Four-terminal symbol. Source is upper for PMOS, lower for NMOS.
        from matplotlib.patches import Circle
        self.line([(x,y-50),(x,y-28),(x-12,y-28)])
        self.line([(x,y+50),(x,y+28),(x-12,y+28)])
        self.line([(x-12,y-31),(x-12,y+31)],lw=2)
        self.line([(x-25,y-27),(x-25,y+27)],lw=1.5)
        self.line([(x-55,y),(x-25,y)])
        if device['type']=='PMOS':
            self.ax.add_patch(Circle((x-31,y),5,fc='white',ec=BLACK,lw=1.3))
        self.line([(x-12,y),(x+35,y)])
        # Body terminal is explicit and labeled; no implicit source-body short.
        if device['type']=='PMOS':
            self.arrow([(x+3,y),(x+18,y)],lw=1.0)
        else:
            self.arrow([(x+18,y),(x+3,y)],lw=1.0)
        self.text(x+39,y,'B='+device['body'],9)
        if labels:
            self.text(x+13,y-37,device['id'],13,weight='bold')
            self.text(x+13,y+66,
                f"{device['w_unit_um']:g}/{device['l_um']:g} um; m={device['m']}, nf={device['nf']}",10)
    def save(self,base):
        base.parent.mkdir(parents=True,exist_ok=True)
        self.fig.savefig(base.with_suffix('.svg'),metadata={'Date':None})
        self.fig.savefig(base.with_suffix('.png'),dpi=170,metadata={'Software':'Matplotlib'})
        self.plt.close(self.fig)

def architecture(out,devices):
    from matplotlib.patches import Polygon
    d=Drawing(1250,720)
    d.text(35,35,'A 130 nm CMOS LDO with a two-stage error amplifier',19,weight='bold')
    d.text(35,66,'VIN=1.2 V | VOUT=0.9 V | ideal VREF=0.45 V | external ideal COUT=1 nF',12)
    d.ax.add_patch(Polygon([(250,175),(250,305),(415,240)],fc='white',ec=BLACK,lw=1.7))
    d.text(300,232,'EA',15,ha='center',weight='bold'); d.text(305,258,'M2-M4, M6-M7',9,ha='center')
    d.text(262,202,'+',15); d.text(262,280,'-',17)
    d.text(75,205,'VREF',12,color=BLUE); d.arrow([(150,205),(250,205)],BLUE)
    d.line([(415,240),(505,240)],BLUE); d.text(448,221,'EAOUT',10,ha='center',color=BLUE)
    d.box(505,180,185,120,'Gate driver','M8 pull-up / M9 sink')
    d.line([(690,240),(785,240)],BLUE); d.text(735,219,'GATE',10,ha='center',color=BLUE)
    d.mos(840,240,devices['M1'],labels=False); d.text(894,200,'PMOS pass M1',12,weight='bold')
    d.line([(840,90),(840,190)],lw=2); d.text(840,89,'VIN',13,ha='center',va='bottom')
    d.line([(840,290),(840,395),(1155,395)],lw=2); d.dot(840,395)
    d.text(1155,375,'VOUT',13,ha='right',color=BLUE)
    d.line([(900,395),(900,418)]); d.dot(900,395)
    d.resistor(900,460,label='RTOP 200 kohm')
    d.line([(900,502),(900,514)]); d.dot(900,508)
    d.resistor(900,556,label='RBOT 200 kohm'); d.ground(900,610)
    d.line([(900,598),(900,598)])
    d.line([(900,508),(170,508),(170,280),(250,280)],color=BLUE)
    d.text(200,489,'FB -> zero-impedance loop probe -> FBIN',10,color=BLUE)
    d.line([(1050,395),(1050,445)]); d.dot(1050,395)
    d.capacitor(1050,480,label='COUT\n1 nF'); d.ground(1050,538)
    d.line([(1050,515),(1050,526)])
    d.line([(1155,395),(1155,448)]); d.dot(1155,395)
    from matplotlib.patches import Circle
    d.ax.add_patch(Circle((1155,480),30,fc='white',ec=BLACK,lw=1.5))
    d.arrow([(1155,463),(1155,497)],lw=1.2); d.line([(1155,510),(1155,526)]); d.ground(1155,538)
    d.text(1155,581,'ILOAD\n0.1-5 mA',11,ha='center')
    d.line([(450,240),(450,342),(500,342)],color=BLUE)
    d.resistor(542,342,horizontal=True,label='36 kohm')
    d.line([(584,342),(600,342)],color=BLUE)
    d.capacitor(635,342,horizontal=True,label='18 pF')
    d.line([(670,342),(735,342),(735,240)],color=BLUE); d.dot(735,240); d.dot(450,240)
    d.box(365,395,285,72,'Bias generation','M5 + RBIAS; BIAS -> M4, M8')
    d.text(35,626,'Signal path: FB rises -> EAOUT falls -> GATE rises -> pass current falls.',12)
    d.text(35,655,'Compensation shown: active EAOUT-GATE series branch. Full circuit includes 0.1 pF and 1 kohm +1 fF paths.',10)
    d.text(35,683,'9 MOS instances / 44 parallel replicas, nf=1. Reference, load, and all passives are ideal test conditions.',10)
    d.save(out/'architecture')

def schematic(out,devices):
    d=Drawing(1800,1030)
    d.text(25,30,'Complete nine-instance LDO core',20,weight='bold')
    d.text(25,64,'Dimensions below each symbol: Wunit/L in um; parallel multiplicity m; fingers nf. Body ties are explicit.',12)
    for x,title in [(40,'BIAS'),(370,'DIFFERENTIAL AMPLIFIER'),(940,'GATE DRIVER'),(1320,'PASS / FEEDBACK / LOAD')]:
        d.text(x,112,title,13,color=BLUE,weight='bold')
    # Bias generator.
    d.mos(180,260,devices['M5'])
    d.line([(180,210),(180,165)]); d.text(180,151,'VIN',12,ha='center')
    d.line([(180,310),(180,390)])
    d.line([(125,260),(90,260),(90,350),(180,350)]); d.dot(180,350)
    d.text(180,376,'BIAS',11,ha='left',color=BLUE)
    d.resistor(180,455,label='RBIAS\n100 kohm'); d.line([(180,390),(180,413)])
    d.line([(180,497),(180,580)]); d.ground(180,592)
    # PMOS pair and active NMOS mirror.
    d.mos(500,210,devices['M4']); d.line([(500,160),(500,150)]); d.text(500,138,'VIN',12,ha='center')
    d.line([(445,210),(370,210)]); d.text(363,210,'BIAS',11,ha='right',color=BLUE)
    d.line([(500,260),(500,290),(410,290),(410,315)])
    d.line([(500,290),(650,290),(650,315)]); d.dot(500,290); d.text(525,310,'TAIL',11,color=BLUE)
    d.mos(410,365,devices['M2']); d.mos(650,365,devices['M3'])
    d.line([(355,365),(310,365)]); d.text(300,365,'VREF',11,ha='right',color=BLUE)
    d.line([(595,365),(570,365)]); d.text(562,365,'FBIN',11,ha='right',color=BLUE)
    d.line([(410,415),(410,510)]); d.text(420,448,'MIRROR',11,color=BLUE)
    d.line([(650,415),(650,510)]); d.text(667,448,'EAOUT',11,color=BLUE)
    d.mos(410,560,devices['M6']); d.mos(650,560,devices['M7'])
    d.line([(410,470),(315,470),(315,560),(355,560)]); d.dot(410,470)
    d.line([(410,488),(580,488),(580,560),(595,560)]); d.dot(410,488)
    d.line([(410,610),(410,650),(650,650),(650,610)])
    d.ground(530,662); d.line([(530,650),(530,650)]); d.dot(530,650)
    # Complementary driver. Repeated named nets connect between panels.
    d.mos(1050,250,devices['M8']); d.mos(1050,535,devices['M9'])
    d.line([(1050,200),(1050,155)]); d.text(1050,140,'VIN',12,ha='center')
    d.line([(995,250),(950,250)]); d.text(940,250,'BIAS',11,ha='right',color=BLUE)
    d.line([(995,535),(950,535)]); d.text(940,535,'EAOUT',11,ha='right',color=BLUE)
    d.line([(1050,300),(1050,485)]); d.dot(1050,392); d.text(1070,373,'GATE',11,color=BLUE)
    d.line([(1050,585),(1050,650)]); d.ground(1050,662)
    # Pass device and output connections.
    d.mos(1370,260,devices['M1']); d.line([(1370,210),(1370,155)])
    d.text(1370,140,'VIN',12,ha='center')
    d.line([(1315,260),(1235,260),(1235,392),(1050,392)])
    d.line([(1370,310),(1370,405),(1730,405)],lw=1.9); d.text(1730,384,'VOUT',12,ha='right',color=BLUE)
    d.line([(1435,405),(1435,525)]); d.dot(1435,405)
    d.capacitor(1435,560,label='COUT\n1 nF'); d.line([(1435,595),(1435,650)]); d.ground(1435,662)
    from matplotlib.patches import Circle
    d.line([(1550,405),(1550,530)]); d.dot(1550,405)
    d.ax.add_patch(Circle((1550,560),30,fc='white',ec=BLACK,lw=1.5))
    d.arrow([(1550,542),(1550,578)],lw=1.2); d.line([(1550,590),(1550,650)]); d.ground(1550,662)
    d.text(1550,706,'ILOAD',11,ha='center')
    d.line([(1690,405),(1690,428)]); d.dot(1690,405)
    d.resistor(1690,470,label='RTOP\n200 kohm')
    d.line([(1690,512),(1690,548)]); d.dot(1690,531); d.text(1668,531,'FB',11,ha='right',color=BLUE)
    d.resistor(1690,590,label='RBOT\n200 kohm')
    d.line([(1690,632),(1690,650)]); d.ground(1690,662)
    d.text(1350,751,'FB -- [zero-impedance STB probe] -- FBIN',11,color=BLUE)
    # Compensation, rendered as separate named-net branches to avoid false crossings.
    d.text(40,735,'COMPENSATION / TEST CONDITIONS',13,color=BLUE,weight='bold')
    d.text(40,797,'EAOUT',11,color=BLUE); d.line([(110,797),(188,797)])
    d.resistor(230,797,horizontal=True,label='RBUF 36 kohm')
    d.line([(272,797),(365,797)]); d.text(315,820,'CBUFMID',9,ha='center')
    d.capacitor(400,797,horizontal=True,label='CBUF 18 pF')
    d.line([(435,797),(500,797)]); d.text(510,797,'GATE',11,color=BLUE)
    d.text(40,895,'GATE',11,color=BLUE); d.line([(110,895),(188,895)])
    d.resistor(230,895,horizontal=True,label='RZ 1 kohm')
    d.line([(272,895),(365,895)]); d.text(315,918,'CMMID',9,ha='center')
    d.capacitor(400,895,horizontal=True,label='CMILL 1 fF')
    d.line([(435,895),(500,895)]); d.text(510,895,'VOUT',11,color=BLUE)
    d.text(705,780,'GATE',11,ha='center',color=BLUE); d.line([(705,795),(705,815)])
    d.capacitor(705,850,label='CCOMP 0.1 pF'); d.line([(705,885),(705,902)]); d.ground(705,914)
    d.text(935,813,'VREF=0.45 V, ideal; VIN=1.2 V nominal.',12)
    d.text(935,849,'COUT is external, ideal, zero ESR; ILOAD is an ideal current sink.',12)
    d.text(935,885,'Repeated net labels are electrical connections, including BIAS and EAOUT.',11)
    d.text(935,921,'All nine instances and all nine passives are disclosed; no layout is implied.',11)
    d.text(40,990,'Connectivity and dimensions are loaded from data/circuit.json. Drawn topology matches the published revision.',11)
    d.save(out/'schematic')

def draw_all(out):
    circuit=json.loads((PROJECT/'data/circuit.json').read_text(encoding='utf-8'))
    devices={d['id']:d for d in circuit['devices']}
    if len(devices)!=9 or sum(d['m']*d['nf'] for d in devices.values())!=44:
        raise ValueError('Expected nine instances and 44 parallel replicas')
    if any(d['nf']!=1 or abs(d['w_total_um']-d['w_unit_um']*d['nf']*d['m'])>1e-10 for d in devices.values()):
        raise ValueError('Inconsistent width semantics')
    pins={
        'M1':('VOUT','GATE','VIN','VIN'),'M2':('MIRROR','VREF','TAIL','VIN'),
        'M3':('EAOUT','FBIN','TAIL','VIN'),'M4':('TAIL','BIAS','VIN','VIN'),
        'M5':('BIAS','BIAS','VIN','VIN'),'M6':('MIRROR','MIRROR','GND','GND'),
        'M7':('EAOUT','MIRROR','GND','GND'),'M8':('GATE','BIAS','VIN','VIN'),
        'M9':('GATE','EAOUT','GND','GND')}
    if any(tuple(devices[name][k] for k in ['drain','gate','source','body'])!=nodes for name,nodes in pins.items()):
        raise ValueError('Circuit topology changed; update the drawing explicitly')
    expected_passives={
        'RTOP':(['VOUT','FB'],200e3),'RBOT':(['FB','GND'],200e3),'RBIAS':(['BIAS','GND'],100e3),
        'RBUF':(['EAOUT','CBUFMID'],36e3),'CBUF':(['CBUFMID','GATE'],18e-12),
        'RZ':(['GATE','CMMID'],1000),'CMILL':(['CMMID','VOUT'],1e-15),
        'CCOMP':(['GATE','GND'],.1e-12),'COUT':(['VOUT','GND'],1e-9)}
    if len(circuit['passives'])!=len(expected_passives) or any(
        (p['nodes'],p['value'])!=expected_passives.get(p['id']) for p in circuit['passives']):
        raise ValueError('Passive values or connections changed; update the drawing explicitly')
    out.mkdir(parents=True,exist_ok=True)
    architecture(out,devices); schematic(out,devices)
    source=PROJECT/'data/circuit.json'
    (out/'circuit_drawing_provenance.json').write_text(json.dumps({
        'circuit_data_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'renderer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source':'data/circuit.json','scope':'design drawing; no circuit simulation or layout extraction'},indent=2)+'\n',encoding='utf-8')
    return ['architecture.svg','architecture.png','schematic.svg','schematic.png','circuit_drawing_provenance.json']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir',type=Path,required=True,help='Fresh figure directory')
    args=parser.parse_args()
    if args.outdir.exists(): raise SystemExit('Choose a fresh output directory')
    print(json.dumps({'files':draw_all(args.outdir)}))

if __name__=='__main__': main()

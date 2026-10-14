"""Electrical architecture drawing for the retained buck implementation."""
import math


def draw_block_diagram(outdir):
    """7.4-inch print-width overview; every label is at least eight points."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    fig,ax=plt.subplots(figsize=(7.4,3.8),layout='constrained')
    ax.set(xlim=(0,7.4),ylim=(0,5.15));ax.axis('off')
    black='#111111';blue='#24629a'
    def text(x,y,s,size=8.5,color=black):
        ax.text(x,y,s,ha='center',va='center',fontsize=size,color=color)
    def box(x,y,w,h,s,behavioral=False):
        ax.add_patch(Rectangle((x,y),w,h,facecolor='white',edgecolor=black,
                              linewidth=1.1,linestyle='--' if behavioral else '-'))
        text(x+w/2,y+h/2,s)
    def route(points,signal=False,both=False):
        color=blue if signal else black
        ax.plot([p[0] for p in points[:-1]],[p[1] for p in points[:-1]],
                color=color,linewidth=1.1,linestyle='--' if signal else '-')
        ax.annotate('',xy=points[-1],xytext=points[-2],
                    arrowprops={'arrowstyle':'<->' if both else '->','color':color,
                                'linewidth':1.1,'linestyle':'--' if signal else '-',
                                'mutation_scale':8})
    text(3.7,4.94,'Two-phase buck: functional overview',11)
    text(1.42,4.53,'VIN = 1.8 V')
    text(6.04,4.53,'VOUT = 0.9 V; 10-100 mA')
    box(.47,3.58,1.9,.82,'Phase 1\nMOS drivers + bridge')
    box(.47,2.38,1.9,.82,'Phase 2\nMOS drivers + bridge')
    box(2.91,2.58,1.31,1.62,'L1 / L2\nexternal\n2.2 uH / phase')
    box(4.89,2.93,2.08,1.27,'VCONV - PDN - VLOAD\nR / L network\nexternal Cout / Cload')
    route([(2.37,3.99),(2.91,3.99)])
    route([(2.37,2.79),(2.91,2.79)])
    ax.plot([4.22,4.56,4.56],[3.99,3.99,3.56],color=black,linewidth=1.1)
    ax.plot([4.22,4.56,4.56],[2.79,2.79,3.56],color=black,linewidth=1.1)
    ax.add_patch(Circle((4.56,3.56),.035,color=black))
    route([(4.56,3.56),(4.89,3.56)])
    box(.47,.70,2.09,1.10,'PI / PWM supervisor\nbehavioral; 180-degree PWM\ninternal power unmodeled',True)
    box(4.89,1.91,2.08,.62,'Window detectors\ncore MOS; FB = VLOAD / 2')
    box(4.89,.70,2.08,.62,'Source / sink assist\nMOS drivers + assist devices')
    route([(1.46,1.80),(1.46,2.13),(.17,2.13),(.17,3.99),(.47,3.99)],True)
    route([(.17,2.79),(.47,2.79)],True)
    text(2.15,2.08,'gate commands',8,blue)
    route([(5.40,2.93),(5.40,2.53)],True)
    ax.add_patch(Circle((5.40,2.70),.025,color=blue))
    route([(5.40,2.70),(4.32,2.70),(4.32,1.59),(2.56,1.59)],True)
    text(3.60,1.78,'-VLOAD feedback',8.5,blue)
    route([(4.89,2.20),(4.65,2.20),(4.65,1.25),(2.56,1.25)],True)
    text(3.50,1.05,'droop / over flags',8,blue)
    route([(2.56,.86),(4.89,.86)],True)
    text(3.71,.55,'bounded pulses + PI-state handoff',8,blue)
    route([(6.97,1.01),(7.23,1.01),(7.23,3.56),(6.97,3.56)],False,True)
    text(6.25,1.53,'charge delivery / removal',8)
    route([(1.52,.34),(1.52,.70)],True)
    text(1.52,.17,'+VREQ',8.5,blue)
    text(5.29,.20,'Solid: MOS / energy path   Dashed blue: control',8)
    for ext in ['png','svg']:
        kwargs={'dpi':220} if ext=='png' else {'metadata':{'Date':None}}
        fig.savefig(outdir/('block_diagram.'+ext),**kwargs)
    plt.close(fig)


def draw_architecture(outdir):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle
    fig,ax=plt.subplots(figsize=(15.8,9.2),layout='constrained')
    ax.set(xlim=(0,17.3),ylim=(0,10));ax.axis('off')
    black='#111111';blue='#24629a'
    def wire(points,color=black,style='-',width=1.15):
        ax.plot([p[0] for p in points],[p[1] for p in points],color=color,linestyle=style,linewidth=width)
    def label(x,y,text,size=8.5,ha='center',color=black):
        ax.text(x,y,text,fontsize=size,ha=ha,va='center',color=color)
    def junction(x,y):ax.add_patch(Circle((x,y),.045,color=black))
    def ground(x,y):
        wire([(x,y+.18),(x,y)])
        for dy,w in [(0,.3),(-.08,.2),(-.16,.1)]:wire([(x-w/2,y+dy),(x+w/2,y+dy)])
    def resistor(x1,x2,y):
        width=x2-x1;xs=[x1,x1+width*.1];ys=[y,y]
        for i in range(1,8):xs.append(x1+width*(.1+.1*i));ys.append(y+(.095 if i%2 else -.095))
        xs += [x2-width*.1,x2];ys += [y,y];wire(list(zip(xs,ys)))
    def inductor(x1,x2,y):
        xs=[x1+(x2-x1)*i/100 for i in range(101)]
        wire(list(zip(xs,[y+.15*abs(math.sin(4*math.pi*i/100)) for i in range(101)])))
    def capacitor(x,y):
        wire([(x,y+.38),(x,y+.075)]);wire([(x,y-.075),(x,y-.38)])
        wire([(x-.25,y+.075),(x+.25,y+.075)]);wire([(x-.25,y-.075),(x+.25,y-.075)])
    def mos(x,y,p,gate):
        for a,b in [(-.26,-.13),(-.065,.065),(.13,.26)]:wire([(x,y+a),(x,y+b)],width=1.5)
        wire([(x-.23,y-.26),(x-.23,y+.26)])
        wire([(x-.65,y),(x-.23,y)],blue)
        wire([(x,y+.26),(x+.2,y+.26),(x+.2,y+.6)])
        wire([(x,y-.26),(x+.2,y-.26),(x+.2,y-.6)])
        if p:ax.add_patch(Circle((x-.23,y),.055,edgecolor=blue,facecolor='white',linewidth=1))
        label(x-.47,y+.24,gate,8,color=blue)
    def sensor(x,y,vertical=False):
        ax.add_patch(Circle((x,y),.16,edgecolor=black,facecolor='white',linewidth=1))
        label(x,y,'I',8)
        if vertical:wire([(x,y+.3),(x,y+.16)]);wire([(x,y-.16),(x,y-.3)])
        else:wire([(x-.3,y),(x-.16,y)]);wire([(x+.16,y),(x+.3,y)])
    def driver(x,y,name,command,gate_x):
        ax.add_patch(Rectangle((x,y-.23),1.25,.46,facecolor='white',edgecolor=black,linewidth=1))
        ax.add_patch(Polygon([(x+.86,y-.12),(x+.86,y+.12),(x+1.08,y)],facecolor='white',edgecolor=black,linewidth=.8))
        label(x+.43,y,name,8.5);wire([(x+1.25,y),(gate_x,y)],blue)
        wire([(x-.25,y),(x,y)],blue,'--');label(x-.3,y,command,7.5,ha='right',color=blue)
    label(8.7,9.72,'130 nm CMOS two-phase buck: electrical architecture',14)
    label(8.7,9.35,'Bank symbols show parallel MOS groups; individual dimensions and D/G/S/B appear in design.md.',9)
    for phase,y in [(1,7.35),(2,3.95)]:
        x=3.2
        mos(x,y+.65,True,'GH'+str(phase));mos(x,y-.65,False,'GL'+str(phase))
        wire([(x+.2,y+.05),(x+.2,y-.05)]);junction(x+.2,y)
        wire([(x+.2,y+1.25),(x+.2,y+1.45)]);label(x+.2,y+1.62,'VIN = 1.8 V',8.5)
        wire([(x+.2,y-1.25),(x+.2,y-1.38)]);ground(x+.2,y-1.38)
        driver(.72,y+.65,'DH'+str(phase),'CMDH'+str(phase),x-.65)
        driver(.72,y-.65,'DL'+str(phase),'CMDL'+str(phase),x-.65)
        label(4.05,y+.73,'PHS'+str(phase)+' bank\n4 x 1000 um',8)
        label(4.05,y-.73,'NLS'+str(phase)+' bank\n2 x 1000 um',8)
        wire([(x+.2,y),(5.0,y)]);label(4.38,y+.23,'SW'+str(phase),8)
        inductor(5.0,6.25,y);wire([(6.25,y),(6.6,y)])
        resistor(6.6,7.48,y);wire([(7.48,y),(7.78,y)])
        sensor(8.08,y);wire([(8.38,y),(8.8,y)])
        label(5.64,y+.38,'L'+str(phase)+'  2.2 uH',8.5)
        label(7.05,y+.36,'DCR 50 mohm',8)
        label(8.08,y-.34,'1 V/A',7.5,color=blue)
    wire([(8.8,3.95),(8.8,7.35)]);junction(8.8,7.35);junction(8.8,3.95)
    label(8.8,7.7,'VCONV',9)
    wire([(8.8,7.35),(9.43,7.35),(9.43,6.9)])
    capacitor(9.43,6.52);wire([(9.43,6.14),(9.43,5.57)]);ground(9.43,5.57)
    label(9.43,5.17,'Cout 1 uF\nESR 20 mohm; ESL 0.2 nH',7.7)
    wire([(9.43,7.35),(10.05,7.35)]);junction(9.43,7.35)
    resistor(10.05,10.97,7.35);wire([(10.97,7.35),(11.22,7.35)])
    inductor(11.22,12.1,7.35);wire([(12.1,7.35),(16.2,7.35)])
    label(10.52,7.72,'RPDN 0.1 ohm',8.5);label(11.68,7.74,'LPDN 0.5 nH',8.5)
    label(12.7,7.73,'VLOAD',9)
    wire([(12.7,7.35),(12.7,6.25)]);junction(12.7,7.35)
    capacitor(12.7,5.87);wire([(12.7,5.49),(12.7,5.25)]);ground(12.7,5.25)
    label(12.7,4.72,'Cload 10 nF\nESR 20 mohm; ESL 0.05 nH',7.7)
    wire([(14.42,7.35),(14.42,6.48)]);junction(14.42,7.35)
    ax.add_patch(Circle((14.42,6.11),.37,edgecolor=black,facecolor='white',linewidth=1.1))
    ax.annotate('',xy=(14.42,5.91),xytext=(14.42,6.32),arrowprops={'arrowstyle':'->','lw':1.1,'color':black})
    wire([(14.42,5.74),(14.42,5.25)]);ground(14.42,5.25)
    label(14.42,4.8,'ILOAD\n10 / 100 mA',8.5)
    mos(13.55,8.62,True,'GBUP');wire([(13.75,9.22),(13.75,9.3)])
    label(14.45,8.93,'VIN',8);label(14.5,8.58,'PASSUP bank\n2 x 600 um',8)
    wire([(13.75,8.02),(13.75,7.95)]);sensor(13.75,7.65,True);junction(13.75,7.35)
    driver(10.45,8.62,'DAU','CMDUP',12.9)
    mos(16,5.55,False,'GBDN');wire([(16.2,6.15),(16.2,6.3)])
    sensor(16.2,6.6,True);wire([(16.2,6.9),(16.2,7.35)]);junction(16.2,7.35)
    wire([(16.2,4.95),(16.2,4.75)]);ground(16.2,4.75)
    label(16.2,4.32,'PASSDN\n600 um',8)
    driver(13.76,3.65,'DAD','CMDDN',15.1)
    wire([(15.1,3.65),(15.35,3.65),(15.35,5.55)],blue)
    label(14.1,3.1,'r9 only: Rgate,up = 1 kohm; Rgate,dn = 2 kohm',8)
    wire([(.45,2.3),(16.8,2.3)],'#777777','--',.65)
    label(8.5,2.54,'Solid black: energy-path connections     Blue: gate / measurement signals',8.5)
    ax.add_patch(Rectangle((.75,.55),7.1,1.62,facecolor='white',edgecolor=black,linewidth=1.2,linestyle='--'))
    label(4.3,1.87,'Behavioral controller: PI, PWM and assist arbitration',11)
    label(4.3,1.27,'5 MHz; 180-degree command phases; ideal 1 V/A current feedback\nMode 2: +/-40 mA PI-state handoff; internal controller power unmodeled',9)
    ax.add_patch(Rectangle((9.2,.55),3.4,1.62,facecolor='white',edgecolor=black,linewidth=1.1))
    for cy in [1.16,1.65]:
        ax.add_patch(Polygon([(10.15,cy-.19),(10.15,cy+.19),(9.75,cy)],facecolor='white',edgecolor=black,linewidth=.8))
    label(11.33,1.56,'CU / CD\nCore-MOS window detectors',9)
    label(10.9,.86,'20 MOS; VDDC = 1.2 V',8.5)
    wire([(9.2,1.4),(7.85,1.4)],blue,'--');label(8.54,1.67,'DROOP_RAW\nOVER_RAW',7.5,color=blue)
    wire([(12.6,1.4),(13.14,1.4),(13.14,2.3)],blue,'--')
    label(14.7,1.83,'FB = VLOAD / 2\nREFUP/DN = (VREQ -/+ WINDOW) / 2',8.5,color=blue)
    label(4.3,.19,'Commands connect to labeled driver inputs; all electrical returns are node 0.',8)
    for ext in ['png','svg']:
        kwargs={'dpi':180} if ext=='png' else {'metadata':{'Date':None}}
        fig.savefig(outdir/('architecture.'+ext),**kwargs)
    plt.close(fig)

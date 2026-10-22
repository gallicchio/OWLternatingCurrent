import pcbnew, math
b = pcbnew.LoadBoard('project/hardware/OWLternatingCurrent.kicad_pcb')
def mm(p): return (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y))
caps={'+1V1':[], '+3V3':[]}
for fp in b.GetFootprints():
    if fp.GetReference().startswith('C'):
        val=fp.GetValue()
        for p in fp.Pads():
            nm=p.GetNetname()
            if nm in caps:
                caps[nm].append((fp.GetReference(),val,p.GetNumber(),*mm(p.GetPosition())))
print("all caps on +1V1:", sorted(set((c[0],c[1]) for c in caps['+1V1'])))
print()
for fp in b.GetFootprints():
    if fp.GetReference()=='U4':
        for p in fp.Pads():
            nm=p.GetNetname()
            if nm in ('+1V1','+3V3'):
                x,y=mm(p.GetPosition())
                cs=sorted(((math.hypot(x-c[3],y-c[4]),c) for c in caps[nm]), key=lambda t:t[0])[:2]
                s="; ".join("%.2fmm %s(%s).%s" % (d,c[0],c[1],c[2]) for d,c in cs)
                print("U4 pin %-3s %-5s (%6.2f,%6.2f): %s" % (p.GetNumber(),nm,x,y,s))
# count of 100n per supply
import collections
cnt=collections.Counter()
for fp in b.GetFootprints():
    if fp.GetReference().startswith('C') and fp.GetValue()=='100n':
        nets=sorted(set(p.GetNetname() for p in fp.Pads()))
        cnt[tuple(nets)]+=1
print()
print("100n caps by nets:", dict(cnt))

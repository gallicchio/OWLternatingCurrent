import pcbnew, math
b = pcbnew.LoadBoard('project/hardware/OWLternatingCurrent.kicad_pcb')
def mm(p): return (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y))
for netname in ('Net-(U4-VREG_LX)','+1V1','Net-(U4-VREG_AVDD)'):
    net=b.FindNet(netname)
    if not net: print(netname,"MISSING"); continue
    nc=net.GetNetCode()
    L=0.0; w=set(); layers=set(); nv=0
    for t in b.GetTracks():
        if t.GetNetCode()==nc:
            if t.Type()==pcbnew.PCB_VIA_T: nv+=1
            else:
                s,e=mm(t.GetStart()),mm(t.GetEnd())
                L+=math.hypot(s[0]-e[0],s[1]-e[1]); w.add(pcbnew.ToMM(t.GetWidth())); layers.add(t.GetLayerName())
    print(netname,"len %.1f mm widths %s layers %s vias %d"%(L,sorted(w),sorted(layers),nv))
# L2 position
for fp in b.GetFootprints():
    if fp.GetReference() in ('L2','R6'):
        print(fp.GetReference(), fp.GetValue(), mm(fp.GetPosition()))
        for p in fp.Pads(): print('   pad',p.GetNumber(),p.GetNetname(),tuple(round(v,2) for v in mm(p.GetPosition())))

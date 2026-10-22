import pcbnew
b = pcbnew.LoadBoard('project/hardware/OWLternatingCurrent.kicad_pcb')
for netname in ('Net-(U1-FB)','Net-(U1-SW)','+5V','VSYS'):
    nc = b.FindNet(netname).GetNetCode()
    print("=== %s" % netname)
    for t in b.GetTracks():
        if t.GetNetCode()==nc and t.Type()!=pcbnew.PCB_VIA_T:
            s,e=t.GetStart(),t.GetEnd()
            print("  seg (%7.2f,%7.2f)-(%7.2f,%7.2f) w=%.2f %s" % (pcbnew.ToMM(s.x),pcbnew.ToMM(s.y),pcbnew.ToMM(e.x),pcbnew.ToMM(e.y),pcbnew.ToMM(t.GetWidth()),t.GetLayerName()))
        elif t.GetNetCode()==nc:
            p=t.GetPosition()
            print("  via (%7.2f,%7.2f)" % (pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode()==nc:
                pos=p.GetPosition()
                print("  pad %s.%s (%7.2f,%7.2f) %s" % (fp.GetReference(),p.GetNumber(),pcbnew.ToMM(pos.x),pcbnew.ToMM(pos.y), 'F' if not fp.IsFlipped() else 'B'))
# inductor outline
for fp in b.GetFootprints():
    if fp.GetReference()=='L1':
        pos=fp.GetPosition()
        print("L1 at", pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y))
        print("  courtyard:", [(pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)) for p in []])

import pcbnew
b = pcbnew.LoadBoard('project/hardware/OWLternatingCurrent.kicad_pcb')
for fp in b.GetFootprints():
    if fp.GetReference() in ('U1','C3','C4','C5','L1','C2','R3','R4','R5','R6','R2'):
        pos=fp.GetPosition()
        print(fp.GetReference(), fp.GetFPID().GetLibItemName(), "at (%.2f,%.2f)" % (pcbnew.ToMM(pos.x),pcbnew.ToMM(pos.y)), 'flipped' if fp.IsFlipped() else 'top')
        for p in fp.Pads():
            po=p.GetPosition()
            print('   pad',p.GetNumber(),p.GetNetname(),"(%.2f,%.2f)"%(pcbnew.ToMM(po.x),pcbnew.ToMM(po.y)))
# GND vias near the buck (226-245, 70-90)
print("GND vias near buck:")
for t in b.GetTracks():
    if t.Type()==pcbnew.PCB_VIA_T and t.GetNetname()=='GND':
        p=t.GetPosition(); x,y=pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
        if 222<x<248 and 68<y<92: print("   (%.2f,%.2f)"%(x,y))

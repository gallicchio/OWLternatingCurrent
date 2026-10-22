import math, json
import pcbnew
b = pcbnew.LoadBoard('project/hardware/OWLternatingCurrent.kicad_pcb')
nc = b.FindNet('+12V').GetNetCode()
pads = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    for p in fp.Pads():
        if p.GetNetCode() == nc:
            pos = p.GetPosition(); sz = p.GetSize()
            pads.append((ref, p.GetNumber(), pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y),
                         pcbnew.ToMM(max(sz.x, sz.y))/2, p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH))
trks=[]
for t in b.GetTracks():
    if t.GetNetCode()==nc:
        if t.Type()==pcbnew.PCB_VIA_T:
            pos=t.GetPosition(); trks.append(('via', pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), pcbnew.ToMM(t.GetDrillValue())/2 + 0.1))
        else:
            s=t.GetStart(); e=t.GetEnd()
            trks.append(('seg', pcbnew.ToMM(s.x), pcbnew.ToMM(s.y), pcbnew.ToMM(e.x), pcbnew.ToMM(e.y), pcbnew.ToMM(t.GetWidth()), t.GetLayerName()))
json.dump({'pads':pads,'trks':trks}, open('net12.json','w'))
print("ok", len(pads), len(trks))

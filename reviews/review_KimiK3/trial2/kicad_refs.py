import pcbnew, collections
b = pcbnew.LoadBoard('project/hardware/OWLternatingCurrent.kicad_pcb')
refs=collections.Counter()
vals={}
for fp in b.GetFootprints():
    refs[fp.GetReference()]+=1
    vals.setdefault(fp.GetReference(), set()).add(fp.GetValue())
for r,c in sorted(refs.items()):
    if c>1: print("DUPLICATE:", r, c, vals[r])
print("total footprints:", sum(refs.values()))
print("U8:", vals.get('U8'), "U9:", vals.get('U9'))

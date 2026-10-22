import json, math, collections, itertools, re
from heapq import heappush, heappop
d=json.load(open('net12.json'))
pads=d['pads']; trks=d['trks']
segs=[t for t in trks if t[0]=='seg']
vias=[t for t in trks if t[0]=='via']
n=len(segs)
# zone polygons for +12V
pcb=open('project/hardware/OWLternatingCurrent.kicad_pcb').read()
def blocks(text, tag):
    out=[]; i=text.find(tag)
    while i!=-1:
        depth=0; j=i
        while j<len(text):
            c=text[j]
            if c=='(':depth+=1
            elif c==')':
                depth-=1
                if depth==0:break
            j+=1
        out.append(text[i:j+1]); i=text.find(tag,j)
    return out
zs=[]
for b in blocks(pcb,'\t(zone'):
    m=re.search(r'\(net "([^"]+)"\)\s*\(layer "([^"]+)"\)', b)
    if not m or m.group(1)!='+12V': continue
    for fm in re.finditer(r'\(filled_polygon\s*\(layer "([^"]+)"\)\s*\(pts((?:\s*\(xy [\d.e+-]+ [\d.e+-]+\))+)\s*\)', b):
        zs.append((m.group(2), [tuple(map(float,p)) for p in re.findall(r'\(xy ([\d.e+-]+) ([\d.e+-]+)\)', fm.group(2))]))
def pip(pts,x,y):
    inside=False;j=len(pts)-1
    for i in range(len(pts)):
        xi,yi=pts[i];xj,yj=pts[j]
        if ((yi>y)!=(yj>y)) and (x<(xj-xi)*(y-yi)/(yj-yi)+xi): inside=not inside
        j=i
    return inside
def inzone(x,y,ly):
    return any(ly==zly and pip(p,x,y) for zly,p in zs)
def ptd(px,py,s):
    _,x1,y1,x2,y2,wd,ly=s
    dx,dy=x2-x1,y2-y1; L2=dx*dx+dy*dy
    if L2==0: return math.hypot(px-x1,py-y1)
    t=max(0,min(1,((px-x1)*dx+(py-y1)*dy)/L2))
    return math.hypot(px-(x1+t*dx),py-(y1+t*dy))

Z=n+len(pads)
adj=collections.defaultdict(list)
segcost=[]
for s in segs:
    _,x1,y1,x2,y2,wd,ly=s
    L=math.hypot(x2-x1,y2-y1)
    segcost.append(L if wd<0.9 else 0.0)
clus=collections.defaultdict(list)
for i,s in enumerate(segs):
    _,x1,y1,x2,y2,wd,ly=s
    clus[(round(x1/0.06),round(y1/0.06),ly)].append(i)
    clus[(round(x2/0.06),round(y2/0.06),ly)].append(i)
for k,v in clus.items():
    for a,b in itertools.combinations(v,2): adj[a].append(b); adj[b].append(a)
bylayer=collections.defaultdict(list)
for i,s in enumerate(segs): bylayer[s[6]].append(i)
for ly,idxs in bylayer.items():
    for ii in range(len(idxs)):
        for jj in range(ii+1,len(idxs)):
            i,j=idxs[ii],idxs[jj]
            w=(segs[i][5]+segs[j][5])/2*0.6
            if ptd(segs[i][1],segs[i][2],segs[j])<=w or ptd(segs[i][3],segs[i][4],segs[j])<=w or ptd(segs[j][1],segs[j][2],segs[i])<=w or ptd(segs[j][3],segs[j][4],segs[i])<=w:
                adj[i].append(j); adj[j].append(i)
for _,vx,vy,vr in vias:
    hit=[i for i in range(n) if ptd(vx,vy,segs[i])<=vr+0.02]
    for a,b in itertools.combinations(hit,2): adj[a].append(b); adj[b].append(a)
# pad sizes unknown here; use 0.45 reach
for pi,(ref,pn,gx,gy,pr,th) in enumerate(pads):
    nd=n+pi
    for i in range(n):
        if ptd(gx,gy,segs[i]) <= segs[i][5]/2 + pr:
            adj[nd].append(i); adj[i].append(nd)
    for vi,(_,vx,vy,vr) in enumerate(vias):
        if math.hypot(gx-vx,gy-vy) <= vr + pr:
            for i in range(n):
                if ptd(vx,vy,segs[i])<=vr+0.02:
                    adj[nd].append(i); adj[i].append(nd)
    if any(inzone(gx,gy,zly) for zly,_ in zs):
        adj[nd].append(Z); adj[Z].append(nd)
for i,s in enumerate(segs):
    _,x1,y1,x2,y2,wd,ly=s
    pts=[(x1,y1),(x2,y2),((x1+x2)/2,(y1+y2)/2),((3*x1+x2)/4,(3*y1+y2)/4),((x1+3*x2)/4,(y1+3*y2)/4)]
    if any(inzone(px,py,ly) for px,py in pts):
        adj[i].append(Z); adj[Z].append(i)
dist={Z:0.0}; pq=[(0.0,Z)]
while pq:
    dd,u=heappop(pq)
    if dist.get(u,float('inf'))<dd: continue
    for v in adj[u]:
        c=segcost[v] if v<n else 0.0
        nd=dd+c
        if nd<dist.get(v,float('inf')): dist[v]=nd; heappush(pq,(nd,v))
print("pads on +12V: mm of sub-0.9mm copper on cheapest path to the +12V pour")
for pi,(ref,pn,gx,gy,pr,th) in enumerate(pads):
    dd=dist.get(n+pi)
    print(f"  {ref:5s} {pn:>3s} ({gx:8.3f},{gy:8.3f}): {'pour-direct' if dd==0.0 else ('%.1f mm thin' % dd if dd is not None else 'NO PATH')}")

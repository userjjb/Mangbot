import glob,re,collections
W=set("#%*"); 
files=sorted(glob.glob('/projectnb/jbrcs/mangband/runs/pilot/dive04/levels/*.txt'))
def isF(c): return c not in W and c not in " :"
def runs(grid,H,Wd,wide):
    """wide=1: 1-wide corridor runs; wide=2: 2-wide. returns list of lengths (>=5) horizontal and vertical"""
    out=[]
    for orient in (0,1):
        g=grid if orient==0 else [''.join(grid[y][x] if x<len(grid[y]) else ' ' for y in range(H)) for x in range(Wd)]
        h=len(g); 
        for y in range(1,h-wide-1):
            row=[ ( (g[y+k][x] if x<len(g[y+k]) else ' ') for k in range(wide)) for x in range(Wd)]
            L=0
            for x in range(Wd+1):
                ok=False
                if x<Wd:
                    cells=[ (g[y+k][x] if x<len(g[y+k]) else ' ') for k in range(wide)]
                    up=g[y-1][x] if x<len(g[y-1]) else ' '
                    dn=g[y+wide][x] if x<len(g[y+wide]) else ' '
                    ok= all(isF(c) for c in cells) and up in W and dn in W
                if ok: L+=1
                else:
                    if L>=5: out.append(L)
                    L=0
    return out
n1=n2=0; hist1=collections.Counter(); allc=[]
lat=collections.Counter(); structs=collections.Counter(); sl=[]
for f in files:
    lines=open(f).read().split('\n')
    hdr=lines[0]; grid=[l for l in lines[1:]]
    H=len(grid); Wd=max(len(l) for l in grid)
    r1=runs(grid,H,Wd,1); r2=runs(grid,H,Wd,2)
    n1+= bool(r1); n2+=bool(r2)
    for L in r1: hist1[L]+=1
    m=re.search(r'structures: (.*)$',hdr)
    if m and m.group(1)!='none':
        for s in m.group(1).split(', '):
            mm=re.match(r'(.*) (\d+),(\d+)$',s)
            if mm: structs[mm.group(1)]+=1; sl.append((mm.group(1),int(mm.group(2)),int(mm.group(3))))
print("levels",len(files),"with 1-wide run>=5:",n1,"with 2-wide run>=5:",n2)
print("1-wide run length hist (>=5):",sorted(hist1.items()))
print("structures flagged:",structs)
print("lattice X mod 33 of flagged:",collections.Counter(x%33 for _,y,x in sl), "Y mod 11:",collections.Counter(y%11 for _,y,x in sl))
print("X values:",sorted(collections.Counter(x for _,y,x in sl).items()))

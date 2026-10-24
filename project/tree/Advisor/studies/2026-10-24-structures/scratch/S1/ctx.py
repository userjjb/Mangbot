import glob
exec(open('dumps.py').read().split("n1=n2=0")[0])
shown=0
def runs_pos(grid,H,Wd):
    out=[]
    for y in range(1,H-2):
        L=0
        for x in range(Wd+1):
            ok=False
            if x<Wd:
                c=grid[y][x] if x<len(grid[y]) else ' '
                up=grid[y-1][x] if x<len(grid[y-1]) else ' '
                dn=grid[y+1][x] if x<len(grid[y+1]) else ' '
                ok=isF(c) and up in W and dn in W
            if ok: L+=1
            else:
                if L>=5: out.append((y,x-L,L))
                L=0
    return out
for f in files:
    lines=open(f).read().split('\n'); grid=lines[1:]
    H=len(grid); Wd=max(len(l) for l in grid)
    rp=[r for r in runs_pos(grid,H,Wd) if r[2] in (9,10,11,13,14)]
    if rp and shown<4:
        y,x,L=rp[0]; shown+=1
        print(f.split('/')[-1],y,x,L)
        for yy in range(max(0,y-4),min(H,y+5)): print(''.join(grid[yy][xx] if xx<len(grid[yy]) else ' ' for xx in range(max(0,x-8),x+L+8)))

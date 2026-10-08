import re,csv,sys,collections
src="/projectnb/jbrcs/mangband/github/lib/edit/vault.txt"
V=[];cur=None
for line in open(src,encoding="latin-1"):
    line=line.rstrip("\n")
    if line.startswith("N:"):
        _,n,name=line.split(":",2); cur=dict(n=int(n),name=name,D=[]);V.append(cur)
    elif line.startswith("X:"):
        t,r,h,w=map(int,line[2:].split(":"));cur.update(typ=t,rat=r,h=h,w=w)
    elif line.startswith("D:"):
        cur["D"].append(line[2:])
rows=[]
for v in V:
    g=[l.ljust(v["w"]) for l in v["D"]]
    bad = len(g)!=v["h"] or any(len(l)!=v["w"] for l in v["D"])
    c=collections.Counter("".join(g))
    # border cells: non-space cells that have a space (or edge) 4-neighbour
    H=len(g);W=v["w"]
    def sp(y,x): return y<0 or y>=H or x<0 or x>=W or g[y][x]==' '
    bd=collections.Counter()
    for y in range(H):
        for x in range(W):
            if g[y][x]!=' ' and any(sp(y+dy,x+dx) for dy,dx in((1,0),(-1,0),(0,1),(0,-1))):
                bd[g[y][x]]+=1
    nb=sum(bd.values())
    perm_out = f"{bd['X']}/{nb}"
    hsym=all(l==l[::-1] for l in g); vsym=g==g[::-1]
    ntr=c['*']+c['^']; mons=c['&']+c['@']+c['9']+c['8']+c[',']
    treas=c['*']+c['9']+c['8']+c[',']
    sig=[]
    if hsym: sig.append("LR-sym")
    if vsym: sig.append("UD-sym")
    sig.append("X=%d"%c['X']); 
    sig.append("%%=%d"%c['%'])
    sig.append("mon[&=%d @=%d 9=%d 8=%d comma=%d]"%(c['&'],c['@'],c['9'],c['8'],c[',']))
    if bad: sig.append("DIMS-MISMATCH")
    # trailing: outer outline chars
    sig.append("border:"+"".join(f"{k}{n}" for k,n in sorted(bd.items())))
    rows.append([v["name"],"lesser" if v["typ"]==7 else ("greater" if v["typ"] in(8,9) else "type%d"%v["typ"]),v["h"],v["w"],v["rat"],perm_out,c['+'],ntr,mons,treas,";".join(sig)])
    v["c"]=c;v["bd"]=bd
w=csv.writer(open("/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-mission15/scratch/V2_vaults.csv","w"))
w.writerow("name,type,rows,cols,rating,perm_outer,n_secret_doors,n_traps,n_monsters,n_treasure,signature".split(","))
w.writerows(rows)
print(len(V),collections.Counter(r[1] for r in rows))
for r in rows: print(r[:10], r[10])

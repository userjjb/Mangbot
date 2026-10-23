import sys; sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
import objgen as o
from objgen import *
# weights: by kind prob at L=20,40 (normal)
for L in (5,10,20,40,60):
    for cursed in (False,True):
        tot=0;fail=0;n=0;nok=0
        dist=pick_dist(L)
        s=sum(dist.values())
        for kid,p in dist.items():
            k=kinds[kid]
            if k["tval"] not in GEAR or k["tval"]==38: continue
            if k["tval"] in AMMO and k["sval"]==4: continue
            el,w=eligible_egos(k,L,cursed)
            S=sum(w)
            pf=(1-S/136)**999
            tot+=p/s
            fail+=p/s*pf
        print(L,"cursed" if cursed else "good","gear share",round(tot,3),"E[P(no ego | eligible found)] weighted",round(fail/tot,4))
# worst kinds
L=20
rows=[]
for k in kinds.values():
    if k.get("tval") in GEAR and k["tval"]!=38:
        el,w=eligible_egos(k,L,False)
        if el: rows.append(((1-sum(w)/136)**999,k["name"],round(sum(w),2),len(el)))
        else: rows.append((None,k["name"],0,0))
rows.sort(key=lambda r:-(r[0] if r[0] is not None else -1))
print(rows[:12])
print("no eligible:",[r[1] for r in rows if r[0] is None][:20])

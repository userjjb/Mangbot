import sys,csv; sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
import objgen as o
STACK={5:24,16:24,17:24,18:24}
rows={(int(r["level"]),r["mode"]):r for r in csv.DictReader(open("/projectnb/jbrcs/mangband/Advisor/data/rulebook/drop_object_by_level.csv"))}
for L in (5,10,20,30,40):
    for mode,good in (("normal",False),("good",True)):
        d=o.pick_dist(L+10 if good else L,good); t=sum(d.values())
        kc=sum(p/t*o.kinds[k]["cost"]*STACK.get(o.kinds[k]["tval"],1) for k,p in d.items())
        r=rows[(L,mode)]
        print(L,mode,"CSV e_value",r["e_value"],"kind-cost-only E",round(kc),"gold pile",r["e_gold_pile"])

import csv,re
exec(open("ego.py").read().split("print(len(egos)")[0])
rows={int(r["idx"]):r for r in csv.DictReader(open("../K1/K1_egos.csv"))}
bad=0
for e in egos:
    r=rows.get(e["idx"])
    if not r: print("missing",e["idx"]);bad+=1;continue
    t=(int(r["max_h"]),int(r["max_d"]),int(r["max_a"]),int(r["max_pval"]),int(r["level"]),int(r["rarity"]),int(r["cost"]))
    c=e["C"]+(e["W"][0],e["W"][1],e["W"][3])
    fl=set(f for f in r["flags"].split("|") if f)
    if t!=c or fl!=e["F"]: print("diff",e["idx"],e["name"],t,c,fl^e["F"]);bad+=1
    sl=set()
    for s in r["tval_slots"].split(";"):
        m=re.match(r"(\w+)\[(\d+)-(\d+)\]",s.strip())
        if m: sl.add((m.group(1),int(m.group(2)),int(m.group(3))))
    # tval names count
    if len(sl)!=len(e["T"]): print("slot count",e["idx"],e["name"],r["tval_slots"],e["T"])
print("checked",len(egos),"bad",bad)

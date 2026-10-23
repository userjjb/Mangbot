import re
egos=[];cur=None
for line in open("/projectnb/jbrcs/mangband/github/lib/edit/ego_item.txt",encoding="latin-1"):
    line=line.rstrip("\n")
    if line.startswith("N:"):
        p=line.split(":",2);cur=dict(idx=int(p[1]),name=p[2],T=[],F=set(),C=(0,0,0,0),W=(0,0,0,0));egos.append(cur)
    elif cur is None: continue
    elif line.startswith("C:"): cur["C"]=tuple(int(x) for x in line[2:].split(":"))
    elif line.startswith("W:"): cur["W"]=tuple(int(x) for x in line[2:].split(":"))
    elif line.startswith("T:"): cur["T"].append(tuple(int(x) for x in line[2:].split(":")))
    elif line.startswith("F:"): cur["F"]|={f.strip() for f in line[2:].split("|") if f.strip()}
print(len(egos), "egos; max idx", max(e["idx"] for e in egos))
CUR={"LIGHT_CURSE","HEAVY_CURSE","PERMA_CURSE"}
print("curse egos:")
for e in egos:
    if e["F"]&CUR: print(e["idx"],e["name"],"C",e["C"],"W",e["W"],"T",e["T"])
print("cost0 non-curse:",[(e["idx"],e["name"]) for e in egos if e["W"][3]==0 and not e["F"]&CUR])
print("curse with cost>0:",[(e["idx"],e["name"],e["W"][3]) for e in egos if e["F"]&CUR and e["W"][3]>0])
print("negative C non-curse:",[(e["idx"],e["name"],e["C"]) for e in egos if min(e["C"])<0 and not e["F"]&CUR])
print("dup tval:",[(e["idx"],e["name"],e["T"]) for e in egos if len({t[0] for t in e["T"]})<len(e["T"])])
print("rarity0:",[(e["idx"],e["name"]) for e in egos if e["W"][1]==0])

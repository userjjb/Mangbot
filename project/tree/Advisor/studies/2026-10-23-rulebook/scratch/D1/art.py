import collections
arts=[];cur=None
for line in open("/projectnb/jbrcs/mangband/github/lib/edit/artifact.txt",encoding="latin-1"):
    line=line.rstrip("\n")
    if line.startswith("N:"):
        p=line.split(":",2);cur=dict(idx=int(p[1]),name=p[2]);arts.append(cur)
    elif cur is None: continue
    elif line.startswith("I:"): p=line.split(":");cur.update(tval=int(p[1]),sval=int(p[2]),pval=int(p[3]))
    elif line.startswith("W:"): p=line.split(":");cur.update(level=int(p[1]),rarity=int(p[2]),wt=int(p[3]),cost=int(p[4]))
print(len(arts))
print("specials:")
for a in arts:
    if a["idx"]<16: print(a["idx"],a["name"],a.get("tval"),a.get("sval"),a.get("level"),a.get("rarity"),a.get("cost"))
tv=collections.Counter(a.get("tval") for a in arts if a["idx"]>=16)
print("normal tvals",dict(tv))
print([ (a["idx"],a["name"],a["tval"]) for a in arts if a["idx"]>=16 and a["tval"] in (16,17,18,39,40,45)])
print("cost0:",[(a["idx"],a["name"]) for a in arts if a.get("cost")==0])

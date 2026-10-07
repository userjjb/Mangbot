import csv,re
SC="/projectnb/jbrcs/mangband/Advisor/studies/2026-09-29-shops/scratch/S1_stock.csv"
OBJ="/projectnb/jbrcs/mangband/github/lib/edit/object.txt"
OWN={"Armoury":[145,0]}
A={"General Store":[153,153,152,157],"Armoury":[135,156,157,162],"Weaponsmith":[145,160,160,162],"Temple":[154,155,157,159],"Alchemy shop":[161,155,161,156],"Magic-User store":[160,158,155,170],"Black market":[170,185,180,200]}
ents={};cur=None
for l in open(OBJ):
    l=l.rstrip("\n")
    m=re.match(r"N:(\d+):(.*)",l)
    if m: cur=int(m.group(1));ents[cur]={"name":m.group(2)};continue
    if cur is None or len(l)<2: continue
    ents[cur].setdefault(l[0],l[2:])
rows=[];seen=set()
for r in csv.DictReader(open(SC)):
    if r["k_idx"]=="" : continue
    k=int(r["k_idx"]);e=ents[k]
    key=(r["store"],k)
    if key in seen: continue
    seen.add(key)
    w=e["W"].split(":");cost=int(w[3]);wt=int(w[2])
    p=e.get("P","0:0d0:0:0:0").split(":")
    kind={"TV_SWORD":"weapon","TV_POLEARM":"weapon","TV_HAFTED":"weapon","TV_BOW":"launcher","TV_SHOT":"ammo","TV_ARROW":"ammo","TV_BOLT":"ammo","TV_RING":"ring","TV_AMULET":"amulet","TV_WAND":"wand","TV_STAFF":"staff","TV_POTION":"potion","TV_SCROLL":"scroll"}.get(r["tval"],"armour" if p[0]!="0" or r["tval"] in("TV_BOOTS","TV_HELM","TV_GLOVES","TV_SHIELD","TV_SOFT_ARMOR","TV_HARD_ARMOR","TV_CLOAK") else "other")
    if r["store"]=="General Store" and kind not in("ammo","armour"): continue
    if kind in("weapon","launcher","ammo"): dice=p[1]
    else: dice=""
    ac=p[0]+("" if p[2]=="0" else f" (to_h {p[2]})") if kind=="armour" else ""
    a=A[r["store"]]
    mult=3 if r["store"]=="Black market" else 1
    bmin=(cost*mult*min(a)+50)//100; bmax=(cost*mult*max(a)+50)//100
    note="mult x%s"%{"Sling":2,"Short Bow":2,"Long Bow":3,"Light Crossbow":3}.get(e["name"].replace("& ","").replace("~",""),"") if kind=="launcher" else ""
    rows.append([r["store"],kind,r["tval"],r["sval"],dice,wt,ac,cost,bmin,bmax,e["name"].replace("&","").replace("~","").strip()+(" "+note if note else "")+(f" lvl{w[0]}")])
with open("/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-progression/scratch/G3_gear.csv","w",newline="") as f:
    w=csv.writer(f);w.writerow("store,kind,tval,sval,dice,weight,ac,cost,buy_min,buy_max,notes".split(","));w.writerows(rows)
for r in rows:
    if r[0] in("Weaponsmith","Temple","Armoury") and r[1] in("weapon","launcher","armour","ammo"): print(",".join(map(str,r)))

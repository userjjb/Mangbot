import json, collections
from datetime import datetime

PATH = '/projectnb/jbrcs/mangband/runs/pilot/dive03/decisions.jsonl'
recs = []
with open(PATH) as f:
    for line in f:
        line=line.strip()
        if not line: continue
        d = json.loads(line)
        recs.append(d)

def dt(t):
    return datetime.fromtimestamp(t)

# Mission boundaries (real epoch, derived from monster/event anchors + activity clusters)
bounds = [
    ("M1", datetime(2026,9,25,20,55,0), datetime(2026,9,26,16,14,0)),
    ("M2", datetime(2026,9,26,16,14,0), datetime(2026,9,26,17,0,0)),
    ("M3", datetime(2026,9,27,11,7,0), datetime(2026,9,27,12,5,0)),
    ("M4", datetime(2026,9,27,12,5,0), datetime(2026,9,27,12,44,0)),
    ("M5", datetime(2026,9,27,12,44,0), datetime(2026,9,27,13,35,0)),
    ("M6", datetime(2026,9,27,13,35,0), datetime(2026,9,27,14,10,0)),
    ("M7", datetime(2026,9,27,22,10,0), datetime(2026,9,27,23,0,0)),
]
def mission_of(t):
    d = dt(t)
    for name, s, e in bounds:
        if s <= d < e:
            return name
    return "GAP"

for r in recs:
    if 't' in r and r['t'] is not None:
        r['mission'] = mission_of(r['t'])
        r['dt'] = dt(r['t'])
    else:
        r['mission'] = None

# Q1: attention breakdown by what x mission, with hp fraction
att = [r for r in recs if r['kind']=='attention']
print("TOTAL ATTENTION", len(att))
by_what_mission = collections.defaultdict(lambda: collections.Counter())
hpfrac_min = collections.defaultdict(lambda: 1.0)
for r in att:
    w = r.get('what')
    m = r.get('mission')
    by_what_mission[w][m]+=1
    hp = r.get('hp')
    if hp and hp[1]:
        frac = hp[0]/hp[1]
        key=(w,m)
        if frac < hpfrac_min[key]:
            hpfrac_min[key]=frac

print("\n=== Q1: what x mission counts (min hp frac) ===")
whats = sorted(by_what_mission.keys(), key=lambda w: -sum(by_what_mission[w].values()))
missions_order = ["M1","M2","M3","M4","M5","M6","M7","GAP"]
header = "what".ljust(16)+"".join(m.rjust(9) for m in missions_order)+"   total  min_hp%"
print(header)
for w in whats:
    row = by_what_mission[w]
    total = sum(row.values())
    minfrac = min([hpfrac_min[(w,m)] for m in missions_order if row.get(m)], default=None)
    line = str(w).ljust(16)+"".join(str(row.get(m,0)).rjust(9) for m in missions_order)
    line += f"   {total:5d}  " + (f"{minfrac*100:.0f}%" if minfrac is not None else "-")
    print(line)

import json, collections
from datetime import datetime

PATH = '/projectnb/jbrcs/mangband/runs/pilot/dive03/decisions.jsonl'
recs = []
with open(PATH) as f:
    for line in f:
        line=line.strip()
        if not line: continue
        recs.append(json.loads(line))

for r in recs:
    r['dt'] = datetime.fromtimestamp(r['t']) if r.get('t') else None

att = [r for r in recs if r['kind']=='attention']
by = collections.defaultdict(lambda: collections.Counter())
minhp = collections.defaultdict(lambda: 1.0)
for r in att:
    day = r['dt'].date().isoformat() if r['dt'] else 'NA'
    w = r.get('what')
    by[w][day]+=1
    hp=r.get('hp')
    if hp and hp[1]:
        f=hp[0]/hp[1]
        if f<minhp[(w,day)]: minhp[(w,day)]=f

days = ['2026-09-25','2026-09-26','2026-09-27']
print("what".ljust(18)+"".join(d.rjust(12) for d in days)+"  total")
for w in sorted(by, key=lambda w:-sum(by[w].values())):
    row=by[w]
    tot=sum(row.values())
    print(w.ljust(18)+"".join((f"{row.get(d,0)}({minhp[(w,d)]*100:.0f}%)".rjust(12) if row.get(d) else "0".rjust(12)) for d in days)+f"  {tot}")

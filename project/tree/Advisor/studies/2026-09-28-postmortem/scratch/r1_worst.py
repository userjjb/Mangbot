import json
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

att = [r for r in recs if r['kind']=='attention' and r.get('what') not in ('started','parked','idle_recall','interesting','pack_full')]
scored=[]
for r in att:
    hp=r.get('hp')
    if hp and hp[1] and hp[1]>1:
        frac=hp[0]/hp[1]
    else:
        frac=1.0 if r.get('what')!='dead' else 0.0
    scored.append((frac,r))
scored.sort(key=lambda x:x[0])
# also force-include dead events at top
worst = scored[:20]
for frac,r in worst:
    t=r['t']
    print(f"{r['dt']} depth={r.get('depth')} hp={r.get('hp')} frac={frac:.2f} what={r.get('what')} detail={r.get('detail')}")
    # act within +-60s
    acts=[a for a in recs if a['kind']=='act' and abs(a['t']-t)<=60]
    for a in acts[:6]:
        print(f"    ACT {a['dt'].strftime('%H:%M:%S')} cmd={a.get('cmd')} why={a.get('why')}")
    print()

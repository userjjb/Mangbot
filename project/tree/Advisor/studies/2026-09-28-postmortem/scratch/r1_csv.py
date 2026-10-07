import json, csv
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

recs_sorted = sorted(recs, key=lambda r: r['t'] if r.get('t') else 0)
acts = [r for r in recs_sorted if r['kind']=='act']
atts = [r for r in recs_sorted if r['kind']=='attention']

def nearby_acts(t, window=45):
    out=[]
    for a in acts:
        if abs(a['t']-t) <= window:
            out.append(f"{a.get('cmd')}[{a.get('why')}]")
    return "; ".join(out[:5])

def outcome_after(idx_t, window=90):
    # look at attention/goal records after t within window for outcome hints
    hints=[]
    for r in recs_sorted:
        if r['t'] is None: continue
        if idx_t < r['t'] <= idx_t+window:
            if r['kind']=='attention' and r.get('what') in ('dead','goal_done','goal_failed','danger_avoided','emergency_loop'):
                hints.append(str(r.get('what'))+':'+str(r.get('detail'))[:60])
            if r['kind']=='goal' and r.get('goal') and ('recall' in r['goal'] or 'dive 0' in r['goal']):
                hints.append('goal:'+r['goal'][:40])
    return " | ".join(hints[:3])

rows=[]
for r in atts:
    t=r['t']
    hp = r.get('hp') or [None,None]
    rows.append({
        'local_time': r['dt'].strftime('%Y-%m-%d %H:%M:%S') if r['dt'] else '',
        'epoch': t,
        'depth': r.get('depth'),
        'hp': hp[0],
        'hp_max': hp[1],
        'what': r.get('what'),
        'detail': (r.get('detail') or '')[:200],
        'pilot_response': nearby_acts(t),
        'outcome': outcome_after(t),
    })

out='/projectnb/jbrcs/mangband/Advisor/studies/2026-09-28-postmortem/scratch/R1_incidents.csv'
with open(out,'w',newline='') as f:
    w=csv.DictWriter(f, fieldnames=['local_time','epoch','depth','hp','hp_max','what','detail','pilot_response','outcome'])
    w.writeheader()
    for row in rows:
        w.writerow(row)
print('wrote', len(rows), 'rows to', out)

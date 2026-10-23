import json,sys,time
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
W={'m20':('2026-10-16 23:41','2026-10-17 00:18'),'m21':('2026-10-17 00:47','2026-10-17 01:36'),'m22':('2026-10-17 01:45','2026-10-17 02:17'),'m23':('2026-10-22 22:15','2026-10-22 22:31')}
def ep(s): return time.mktime(time.strptime(s,'%Y-%m-%d %H:%M'))
for m,(a,b) in W.items():
    a=ep(a);b=ep(b)
    with open(D+'decisions.jsonl') as f, open(m+'_dec.jsonl','w') as o:
        for l in f:
            if not l.startswith('{"t": 179'): continue
            t=float(l[6:l.index(',')])
            if a<=t<=b: o.write(l)
    with open(D+'events.jsonl') as f, open(m+'_ev.jsonl','w') as o:
        for l in f:
            if '"epoch"' not in l[:80] and '"t": 179' not in l[:60]: 
                # find epoch
                pass
            try:
                i=l.index('"epoch": ');t=float(l[i+9:].split(',')[0].split('}')[0])
            except ValueError: continue
            if a<=t<=b and '"ev": "pos"' not in l and '"ev": "ack"' not in l: o.write(l)

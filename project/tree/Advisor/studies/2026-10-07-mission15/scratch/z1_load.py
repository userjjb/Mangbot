import json,pickle
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
ev=[json.loads(l) for l in open(D+'events.jsonl')][111739:130996]
dec=[json.loads(l) for l in open(D+'decisions.jsonl')]
# offset: match 'move' decisions (pos at time) against pos events
pos=[(e['t'],(e['y'],e['x'])) for e in ev if e['ev']=='pos']
mv=[(d['t'],tuple(d['pos'])) for d in dec if d['kind']=='move' and 1791429000<d['t']<1791433000]
import bisect
def score(off):
    s=0
    ts=[p[0]+off for p in pos]
    for t,p in mv[::3]:
        i=bisect.bisect_right(ts,t)-1
        if i>=0 and pos[i][1]==p: s+=1
    return s
if __name__=='__main__':
    base=1791425381
    best=max(((score(base+o/10),o/10) for o in range(-100,600,2)))
    print(best, len(mv[::3]))

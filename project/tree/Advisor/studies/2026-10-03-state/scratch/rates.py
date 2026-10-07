import json,struct,collections
for s in (1,2,3):
    names=collections.defaultdict(list)
    vals=collections.defaultdict(list)
    T=0
    for l in open(f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'):
        d=json.loads(l)
        T=d['t']
        if d['dir']=='R' and d['name'].startswith('IND:'):
            names[d['name']].append(d['t']); vals[d['name']].append(d['hex'])
    print('SESSION',s,'dur',T)
    for n in ('IND:hp','IND:state','IND:depth','IND:level','IND:exp','IND:gold','IND:speed','IND:track','IND:hunger','IND:armor','IND:stat0','IND:skills','IND:plusses'):
        ts=names[n]
        if not ts: continue
        rep=sum(1 for i in range(1,len(vals[n])) if vals[n][i]==vals[n][i-1])
        gaps=[b-a for a,b in zip(ts,ts[1:])]
        gaps.sort()
        print(f' {n}: n={len(ts)} identical-to-previous={rep} median gap={gaps[len(gaps)//2] if gaps else None:.2f}s  per-minute={len(ts)/(T/60):.2f}')

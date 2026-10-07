import json,datetime,re,sys,bisect
def load(p): return [json.loads(l) for l in open(p)]
def segs(E):
    s=[];prev=-1;st=0
    for i,e in enumerate(E):
        if e['t']<prev-1: s.append((st,i));st=i
        prev=e['t']
    s.append((st,len(E)));return s
F=lambda t:datetime.datetime.fromtimestamp(t).strftime('%m-%d %H:%M:%S')
out=[]
for run in ('dive03','dive04'):
    base='/projectnb/jbrcs/mangband/runs/pilot/%s/'%run
    D=load(base+'decisions.jsonl');E=load(base+'events.jsonl')
    starts=[i for i,d in enumerate(D) if d['kind']=='attention' and d['what']=='started']
    S=segs(E)
    print(run,len(starts),len(S),file=sys.stderr)
    for k,(a,b) in enumerate(S):
        ev=E[a:b]
        d0=starts[k] if k<len(starts) else None
        d1=starts[k+1] if k+1<len(starts) else len(D)
        dd=D[d0:d1]
        acts=[d for d in dd if d['kind']=='act']
        acks=[e for e in ev if e['ev']=='ack']
        # offset by matching
        offs=[]
        ak=[(e['t'],e['cmd']) for e in acks]
        approx=dd[0]['t']-1.5 if dd else 0
        for d in acts:
            c=d['cmd']
            best=None
            for t,cm in ak:
                if cm==c and abs(t+approx-d['t'])<6:
                    if best is None or abs(t+approx-d['t'])<abs(best+approx-d['t']): best=t
            if best is not None: offs.append(d['t']-best)
        if not offs: print('no offs',run,k,file=sys.stderr);continue
        offs.sort();off=offs[len(offs)//2]
        print(run,k,'off',off,'n',len(offs),'spread',offs[0]-off,offs[-1]-off,file=sys.stderr)
        msgs=[(e['t']+off,e['text']) for e in ev if e['ev']=='message']
        for d in acts:
            if re.search(r'item=\d+',d['cmd']) and not d['cmd'].startswith('custom p') and not d['cmd'].startswith('custom s'):
                m=[(t,x) for t,x in msgs if d['t']-0.2<=t<=d['t']+3.0]
                out.append((run,k,d,m))
import pickle;pickle.dump(out,open('q2.pkl','wb'))
print(len(out))

import sys,pickle,json
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1')
from common import *
wins=pickle.load(open('wins.pkl','rb'))
W=[(w['trig']-1800,w['end']+40) for w in wins.values()]
def inw(t): return any(a<=t<=b for a,b in W)
res=[];base=None
with open(RUN+'events.jsonl') as f:
    for l in f:
        if not (l.startswith('{"ev": "message"') or l.startswith('{"ev": "flags"') or l.startswith('{"ev": "pilot_start"')): continue
        d=json.loads(l)
        if d['ev']=='pilot_start': base=d['epoch']-d['t'];continue
        if 'epoch' in d: t=d['epoch']
        else:
            if base is None: continue
            t=base+d['t']
        if inw(t):
            d['epoch']=t;res.append(d)
print(len(res))
pickle.dump(res,open('evmsg.pkl','wb'))

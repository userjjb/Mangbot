import json,pickle
from common import *
eps=pickle.load(open('eps.pkl','rb'))
wins=sorted((e['t0']-20,e['t1']+15) for e in eps)
# quick filter
def inw(t):
    for a,b in wins:
        if a<=t<=b:return True
    return False
out=[];base=None;dev=0;n=0;maxdev=0;cnt_old=0
with open(RUN+'events.jsonl') as f:
    for l in f:
        if l.startswith('{"ev": "floor"') or l.startswith('{"ev": "flags"') or l.startswith('{"ev": "pos"') or l.startswith('{"ev": "ack"'):
            if not (l.startswith('{"ev": "ack"')): continue
        d=json.loads(l)
        if d['ev']=='pilot_start':
            base=d['epoch']-d['t'];continue
        if 'epoch' in d:
            b2=d['epoch']-d['t']
            if base is not None: maxdev=max(maxdev,abs(b2-base))
            t=d['epoch']
        else:
            if base is None:continue
            t=base+d['t'];cnt_old+=1
        if inw(t):
            d['epoch']=t;out.append(d)
print(len(out),maxdev,cnt_old)
pickle.dump(out,open('evs.pkl','wb'))

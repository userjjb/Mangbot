import json,pickle
from common import *
E=load_eps()
for i,e in E.items(): print(i,e['row']['start'],e['row']['duration_s'],e['row']['mission'],e['trig'],e['row']['actions_in_order'][:100])
W=[(e['trig']-150,e['end']+30) for e in E.values()]
def inw(t): return any(a<=t<=b for a,b in W)
# decisions
dec=[json.loads(l) for l in open(RUN+'decisions.jsonl') if True]
dec=[d for d in dec if inw(d['t'])]
print('dec',len(dec))
ev=[];base=None;n=0
import collections
c=collections.Counter()
with open(RUN+'events.jsonl') as f:
    for l in f:
        if l.startswith('{"ev": "floor"') or l.startswith('{"ev": "flags"') or l.startswith('{"ev": "map"'):continue
        d=json.loads(l)
        if d['ev']=='pilot_start': base=d['epoch']-d['t'];continue
        if 'epoch' in d:t=d['epoch']
        else:
            if base is None:continue
            t=base+d['t']
        if inw(t):
            d['epoch']=t;ev.append(d);c[d['ev']]+=1
print(len(ev),c)
st=[]
for l in open(RUN+'state.jsonl'):
    if l[:12]=='{"ev": "inve': st.append(json.loads(l))
pickle.dump((dec,ev,st),open('idx.pkl','wb'))
print(len(st))

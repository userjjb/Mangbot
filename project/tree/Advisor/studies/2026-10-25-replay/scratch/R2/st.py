import json,pickle
from common import *
E=load_eps()
W=[(e['trig']-900,e['end']+60) for e in E.values()]
def inw(t): return any(a<=t<=b for a,b in W)
out=[]
for l in open(RUN+'state.jsonl'):
    if l[:14]=='{"ev": "status':
        d=json.loads(l)
        if inw(d['epoch']):
            i=d['ind']; out.append((d['epoch'],d['y'],d['x'],i.get('level'),i.get('armor'),i.get('speed'),i.get('afraid'),i.get('blind'),i.get('confused'),i.get('poisoned'),i.get('state'),i.get('hp')))
pickle.dump(out,open('status.pkl','wb'));print(len(out),out[0])

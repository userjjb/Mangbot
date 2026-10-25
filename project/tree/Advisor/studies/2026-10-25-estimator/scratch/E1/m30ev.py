import json,pickle
from common import *
a,b=eps_('2026-10-25 06:41:30'),eps_('2026-10-25 06:46:40')
out=[]
with open(RUN+'events.jsonl') as f:
    for l in f:
        if l.startswith('{"ev": "floor"') or l.startswith('{"ev": "flags"'):continue
        d=json.loads(l)
        t=d.get('epoch')
        if t and a<=t<=b:out.append(d)
pickle.dump(out,open('m30ev.pkl','wb'));print(len(out))
import collections;print(collections.Counter(d['ev'] for d in out))

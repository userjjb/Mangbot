import json,pickle,re
from common import *
eps=pickle.load(open('eps.pkl','rb'))
inv=[]
for l in open(RUN+'state.jsonl'):
    if l[:12]!='{"ev": "inve':continue
    d=json.loads(l)
    if d['epoch']>=eps[0]['t0']: inv.append(d)
print(len(inv))
KEY=re.compile(r'Phase|Cure|Speed|Heroism|Berserk|Teleport|Recall|Deep Descent|Banish|Resist|Healing|Life|Escape|Slow|Sleep|Free|Flasks?')
def snap(t):
    r=None
    for d in inv:
        if d['epoch']<=t:r=d
        else:break
    if r is None:return None
    return t-r['epoch'],[(it['name']) for it in r['items'] if KEY.search(it['name'])]
if __name__=='__main__':
    for i,e in enumerate(eps):
        if e['mission']>='m24':
            s=snap(e['t0'])
            print(i,e['mission'],hms(e['t0']),s)

import sys
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/data/structures')
import corridors as c
from common import *
maps=[]
for l in open('/projectnb/jbrcs/mangband/runs/pilot/dive04/state.jsonl'):
    if l.startswith('{"ev": "map"'):
        d=json.loads(l); maps.append((d['epoch'],d['rows']))
print(len(maps),maps[0][0],maps[-1][0])
res=pickle.load(open('res.pkl','rb'))
out={}
for f,r in res.items():
    ms=[(e,rw) for e,rw in maps if r['t0']-1<=e<=r['t1']+1]
    series=[]
    for e,rw in ms:
        rows=[rw.get(str(i),'').ljust(198) for i in range(66)]
        rs=[x for x in c.runs(rows,5) if x['width']==1]
        known=sum(ch!=' ' for row in rows for ch in row)
        series.append((e-r['t0'],known,max([x['length'] for x in rs],default=0),[ (x['dir'],x['y'],x['x'],x['length']) for x in rs if x['length']>=8]))
    out[f]=series
pickle.dump(out,open('series.pkl','wb'))

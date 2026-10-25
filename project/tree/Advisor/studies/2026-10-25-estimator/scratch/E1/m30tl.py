import pickle,re,collections,json
from common import *
ev=pickle.load(open('m30ev.pkl','rb'))
recs=[d for d in pickle.load(open('recs.pkl','rb')) if eps_('2026-10-25 06:41:30')<=d['t']<=eps_('2026-10-25 06:46:40')]
rows=[]
for d in recs:
    k=d['kind']
    if k=='mons':rows.append((d['t'],'M',(d['pos'],d['hp'][0],d['monsters'])))
    elif k=='act':rows.append((d['t'],'A',f"{d['cmd']} | {d['why'][:70]}  [hp{d['hp'][0]}]"))
    elif k=='escape':rows.append((d['t'],'E',f"{d['escape']}: {d['trigger'][:60]} adj={d.get('adjacent')}"))
    elif k=='nav_cmd':rows.append((d['t'],'N',f"{d['cmd']} {d['args']}"))
    elif k=='attention':rows.append((d['t'],'T',f"{d['what']}: {d['detail'][:100]}"))
    elif k=='time_factor':rows.append((d['t'],'F',d['factor']))
    elif k=='goal':rows.append((d['t'],'G',str(d['goal'])[:50]))
    elif k=='move':rows.append((d['t'],'V',(d['pos'],d['hp'][0])))
for v in ev:
    t=v['epoch']
    if v['ev']=='message':rows.append((t,'m',v['text']))
    elif v['ev']=='ack':rows.append((t,'K',v['cmd']))
    elif v['ev']=='pos':rows.append((t,'P',(v['y'],v['x'])))
    elif v['ev']=='level':rows.append((t,'L',v['depth']))
rows.sort(key=lambda r:r[0])
pickle.dump(rows,open('m30rows.pkl','wb'))

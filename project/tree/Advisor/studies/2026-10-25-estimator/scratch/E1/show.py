import json,pickle,sys,re
from common import *
eps=pickle.load(open('eps.pkl','rb'))
recs=pickle.load(open('recs.pkl','rb'))
evs=pickle.load(open('evs.pkl','rb'))
hp=pickle.load(open('hp.pkl','rb'))
def show(i,pre=15,post=8,msgs=True,hpstep=True,moves=False):
    e=eps[i]
    print('=== EP',i,e['mission'],hmsd(e['t0']),'->',hms(e['t1']),e['end'],'depth',e['depth'],'levels',[(hms(a),b,c) for a,b,c in e['levels']])
    rows=[]
    for d in recs:
        if e['t0']-pre<=d['t']<=e['t1']+post:
            k=d['kind']
            if k=='act' and not (moves) and d['cmd'].startswith(('walk','run','move','custom ,')) and False: pass
            if k=='act':rows.append((d['t'],'ACT',f"{d['cmd']} | {d['why'][:90]} hp={d['hp']}"))
            elif k=='escape':rows.append((d['t'],'ESC',f"{d['escape']} {d['trigger'][:80]} adj={d.get('adjacent')} goal={d.get('goal')} hp={d['hp']}"))
            elif k=='mons':rows.append((d['t'],'MONS',' '.join(f"{m[2]}@{m[0]}" for m in d['monsters'])[:200]+f" hp={d['hp']}"))
            elif k in('nav_cmd','attention','goal','note','time_factor','nav_say','plan_start','plan_end'):
                x={kk:v for kk,v in d.items() if kk not in('t','kind','pos')}
                rows.append((d['t'],k.upper(),json.dumps(x)[:200]))
    for v in evs:
        if e['t0']-pre<=v['epoch']<=e['t1']+post:
            if v['ev']=='message' and msgs:rows.append((v['epoch'],'MSG',f"[{v['type']}] {v['text']}"))
            elif v['ev']=='level':rows.append((v['epoch'],'LEVEL',str(v['depth'])))
    if hpstep:
        last=None
        for t,h,m,dp,src in hp:
            if e['t0']-pre<=t<=e['t1']+post and h!=last:
                rows.append((t,'HP',f'{h}/{m}'));last=h
    rows.sort(key=lambda r:r[0])
    for t,k,s in rows:print(f"{hms(t)}.{int(t*10)%10} {k:6} {s}")
if __name__=='__main__':
    show(int(sys.argv[1]),*(int(x) for x in sys.argv[2:3]))

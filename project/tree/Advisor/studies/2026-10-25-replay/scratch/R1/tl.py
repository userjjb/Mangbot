import sys,pickle,re,collections
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1')
from common import *
E='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1/'
recs=pickle.load(open(E+'recs.pkl','rb')); wins=pickle.load(open('wins.pkl','rb')); evw=pickle.load(open('evw.pkl','rb'))
def show(i,a,b,skipmelee=True):
    w=wins[i];rows=[]
    T0=w['trig']
    for d in recs:
        if T0-a<=d['t']<=w['end']+b:
            k=d['kind']
            if k=='act':rows.append((d['t'],'ACT',f"{d['cmd']} | {d['why'][:100]} hp={d['hp']} pos={d['pos']}"))
            elif k=='escape':rows.append((d['t'],'ESC',f"{d['escape']} {d['trigger'][:80]} adj={d.get('adjacent')} hp={d['hp']}"))
            elif k=='mons':rows.append((d['t'],'MONS',' '.join(f"{m[2]}@{m[0]},{m[1]}" for m in d['monsters'])[:250]+f" hp={d['hp']} pos={d['pos']}"))
            elif k in('nav_cmd','attention','goal','time_factor'):
                x={kk:v for kk,v in d.items() if kk not in('t','kind','pos','crop','recent')}
                rows.append((d['t'],k.upper(),str(x)[:200]))
    for v in evw:
        if T0-a<=v['epoch']<=w['end']+b:
            if v['ev']=='message':
                if skipmelee and re.match(r'You (hit|miss|smite|bash|slash|pierce|bite)',v['text']):continue
                rows.append((v['epoch'],'MSG',f"[{v['type']}] {v['text']}"))
            elif v['ev']=='level':rows.append((v['epoch'],'LEVEL',str(v['depth'])))
    rows.sort(key=lambda r:r[0])
    print('trig',hms(T0),'end',hms(w['end']))
    for t,k,s in rows:print(f"{hms(t)}.{int(t*10)%10} {k:6} {s}")
if __name__=='__main__':
    show(int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]))

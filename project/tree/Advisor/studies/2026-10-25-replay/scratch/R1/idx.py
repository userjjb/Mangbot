import sys,pickle,json,datetime
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1')
from common import *
E='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1/'
out=pickle.load(open(E+'out.pkl','rb')); eps=pickle.load(open(E+'eps.pkl','rb'))
MY=[0,1,3,4,6,7,8,9,10,11,12,14]
wins={}
for i in MY:
    o=out[i]; s=datetime.datetime.strptime('2026-'+o['start'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=tz).timestamp()
    best=min(eps,key=lambda e:abs(e['t0']-s))
    # E1 start = first trigger in an eps; check
    print(i,o['start'],hms(s),hms(best['t0']),hms(best['t1']),o['duration_s'])
    wins[i]=dict(trig=s,end=s+o['duration_s'],e_t0=best['t0'],e_t1=best['t1'])
pickle.dump(wins,open('wins.pkl','wb'))
# stream events
W=[(w['trig']-150,w['end']+40) for w in wins.values()]
def inw(t): return any(a<=t<=b for a,b in W)
res=[];base=None
with open(RUN+'events.jsonl') as f:
    for l in f:
        d=json.loads(l)
        if d['ev']=='pilot_start': base=d['epoch']-d['t'];continue
        if 'epoch' in d: t=d['epoch']
        else:
            if base is None: continue
            t=base+d['t']
        if inw(t):
            d['epoch']=t;res.append(d)
print(len(res))
pickle.dump(res,open('evw.pkl','wb'))

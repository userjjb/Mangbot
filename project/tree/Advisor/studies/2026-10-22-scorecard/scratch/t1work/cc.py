import sys; sys.path.insert(0,'.')
from t1c import *
import pickle
allm=pickle.load(open('msgs.pkl','rb'))
EPS={'m17':[('14:12:58','14:13:12')],'m18':[('18:54:56','18:55:00'),('19:08:53','19:08:57')],'m19':[('22:24:49','22:24:56')],
'm22':[('01:48:27','01:48:34'),('01:50:48','01:50:49'),('01:54:30','01:54:48'),('02:00:16','02:00:47'),('02:06:03','02:06:04'),('02:11:53','02:12:23')],'m23':[('22:26:55','22:26:55')]}
import datetime
def tod(L,hm):
    a,b=win(L)
    base=time.strftime('%Y-%m-%d',time.localtime(a))
    t=ep(base+' '+hm[:5])+int(hm[6:])
    if t<a-60: t+=86400
    return t
for L,eps in EPS.items():
    R=recs(L)
    for s,e in eps:
        t0,t1=tod(L,s),tod(L,e)
        print('=====',L,s,e)
        names=collections.Counter()
        for d in R:
            if d['kind']=='mons' and t0-25<=d['t']<=t1+3:
                for m in d['monsters']: names[m[2]]+=1
        print(' monsters(25s before):',dict(names))
        for d in R:
            if t0-12<=d['t']<=t1+25:
                if d['kind']=='act' and d['cmd'] not in('rest',) : print('  ',hhmmss(d['t']),'ACT',d['hp'],d['cmd'][:20],d['why'][:70])
                elif d['kind']=='attention': print('  ',hhmmss(d['t']),'ATT',d['hp'],d['what'],d['detail'][:100])
                elif d['kind']=='goal': print('  ',hhmmss(d['t']),'GOAL',d.get('goal'))
                elif d['kind']=='nav_cmd' and d['cmd'] not in('status',): print('  ',hhmmss(d['t']),'NAV',d['cmd'],str(d.get('args'))[:60])
        for e_,t,ty in allm[L]:
            if t0-12<=e_<=t1+25 and re.search(r'yanked|slain|destroyed the|air about|blink|teleport|flees',t): print('  ',hhmmss(e_),'MSG',t[:70])

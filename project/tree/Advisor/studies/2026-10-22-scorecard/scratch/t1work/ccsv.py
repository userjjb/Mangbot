import sys; sys.path.insert(0,'.')
from t1c import *
EP=[
('m17','14:12:53','14:13:25'),('m18','18:54:47','18:55:03'),('m18','19:08:47','19:09:13'),('m19','22:24:38','22:24:59'),
('m22','01:48:21','01:48:41'),('m22','01:50:46','01:50:50'),('m22','01:54:29','01:54:50'),('m22','02:00:12','02:00:39'),
('m22','02:05:52','02:06:05'),('m22','02:11:49','02:12:26'),('m23','22:26:43','22:26:59')]
def tod(L,hm):
    a,b=win(L); base=time.strftime('%Y-%m-%d',time.localtime(a))
    t=ep(base+' '+hm[:5])+int(hm[6:])
    if t<a-60: t+=86400
    return t
for L,s,e in EP:
    R=recs(L); t0,t1=tod(L,s),tod(L,e)
    hp=[(d['hp'][0],d['hp'][1],d['t']) for d in R if t0<=d['t']<=t1 and isinstance(d.get('hp'),list) and d['hp'][1]>=20]
    mn=min(hp,key=lambda h:h[0]/h[1])
    C=collections.Counter()
    for d in R:
        if d['kind']=='act' and t0<=d['t']<=t1:
            w=d['why']
            if 'phase door' in w.lower(): C['Phase']+=1
            m=re.search(r'Cure (Light|Serious|Critical) Wounds',w)
            if m and 'quaff' in w: C['C'+m.group(1)[0]+'W']+=1
            if 'Cure_Critical' in w: C['CCW']+=1
            if 'word of recall' in w.lower() or 'Word_of_Recall' in w: C['WoR']+=1
            if 'Teleportation' in w: C['Teleport']+=1
            if re.match(r'stairs',w): C['stairs']+=1
    print(L,s,hhmmss(mn[2]),mn[:2],round(100*mn[0]/mn[1]),dict(C))

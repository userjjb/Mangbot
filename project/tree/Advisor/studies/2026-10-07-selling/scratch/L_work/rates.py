import json,datetime,collections
R='/projectnb/jbrcs/mangband/runs/pilot/'
def ep(s): return datetime.datetime.strptime('2026-'+s,'%Y-%m-%d %H:%M').timestamp()
M=[('Dive03','pre-test 09-26 04:26-05:02','09-26 04:20','09-26 05:05'),
('Dive03','M1','09-26 15:14','16:05'),('Dive03','M2','09-26 16:14','16:55'),('Dive03','M3','09-27 11:07','12:00'),
('Dive03','M4','09-27 12:05','12:44'),('Dive03','M5','09-27 12:44','13:07'),('Dive03','M6','09-27 13:35','13:59'),('Dive03','M7','09-27 22:15','22:30'),
('Dive04','M8','09-28 01:35','02:08'),('Dive04','M9','09-29 21:35','22:03'),('Dive04','M10','09-29 22:05','22:30'),('Dive04','M11','09-29 22:32','23:08'),
('Dive04','M12','10-03 12:18','12:51'),('Dive04','M13 (to 09:19)','10-07 08:48','09:20')]
def fix(d,a,b):
    day=a.split(' ')[0] if ' ' in a else None
    return a,b
dec={}
for d in ['dive03','dive04']:
    dec[d]=[json.loads(l) for l in open(R+d+'/decisions.jsonl')]
for nick,name,a,b in M:
    day=a.split(' ')[0]
    A=ep(a); B=ep(day+' '+b) if ' ' not in b else ep(b)
    rows=[r for r in dec[nick.lower()] if A<=r['t']<=B]
    secs=collections.Counter(); prev=None; maxd=0
    for r in rows:
        dp=r.get('depth')
        if prev and dp is not None and isinstance(dp,int) and 0<dp<40 and 0<r['t']-prev['t']<=20:
            secs[(dp)]+=r['t']-prev['t']
        prev=r
    tot=sum(secs.values())
    def band(lv): return '0-250' if lv<=5 else '300-450' if lv<=9 else '500-750' if lv<=15 else '800+'
    bs=collections.Counter()
    for lv,s in secs.items(): bs[band(lv)]+=s
    print(nick,name,'wall',round((B-A)/60),'min; dungeon',round(tot/60,1),'min; by band',{k:round(v/60,1) for k,v in sorted(bs.items())})

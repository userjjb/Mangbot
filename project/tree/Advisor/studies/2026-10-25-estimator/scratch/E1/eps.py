import json,re,pickle,collections
from common import *
M=missions()
recs=pickle.load(open('recs.pkl','rb'))
def mis(t):
    for l,a,b in M:
        if a<=t<=b+60:return l
# hp series: (t,hp,max,depth)
hp=[]
for d in recs:
    h=d.get('hp')
    if isinstance(h,list) and len(h)>1 and h[1]>=20 and h[0]>0:
        hp.append((d['t'],h[0],h[1],d.get('depth'),'d'))
hp.sort(key=lambda x:x[0])
pickle.dump(hp,open('hp.pkl','wb'))
print(len(hp))
dsr=[(d['t'],d['depth']) for d in recs if d.get('depth') is not None]
def depth_at(t):
    r=None
    for tt,dd in dsr:
        if tt>t:break
        r=dd
    return r
CURE=re.compile(r'quaff.*(Cure|Potions? of Cure)',re.I)
trig=[]  # (t,kind,desc)
for d in recs:
    t=d['t']
    if d['kind']=='escape' and (d.get('depth') or 0)>0:
        e=d['escape']
        if e in('phase','teleport','wor_escape') or (e=='stairs' and str(d.get('goal')).startswith(('flee','recover'))):
            trig.append((t,'escape:'+e,d['trigger']))
    if d['kind']=='act' and d['cmd'].startswith('custom q') and CURE.search(d['why']) and (d.get('depth') or 0)>0 and 'resend' not in d['why'] and 'town kit' not in d['why']:
        trig.append((t,'cure',d['why']))
# hp triggers
for t,h,m,dep,src in hp:
    if (depth_at(t) or 0)>0 and h<0.6*m: trig.append((t,'hp<60',f'{h}/{m}'))
trig.sort()
# episodes
hp=[x for x in hp]
eps=[];i=0
byt=trig
while i<len(byt):
    t0=byt[i][0];m0=mis(t0)
    dep0=depth_at(t0)
    last=t0;reason='3min';tend=t0+180
    levels=[]
    # iterate through time after t0
    hpa=[x for x in hp if t0<=x[0]<=t0+180]
    dpa=[x for x in dsr if t0<x[0]<=t0+180]
    curdep=dep0
    # event times: build merged sweep at hp samples
    trs=[x for x in byt if t0<=x[0]<=t0+180]
    ti=0
    end=None
    for t,h,m,dp,src in hpa:
        while ti<len(trs) and trs[ti][0]<=t:
            last=max(last,trs[ti][0]);ti+=1
        # level change
        nd=depth_at(t)
        if nd is not None and nd!=curdep:
            levels.append((t,curdep,nd));curdep=nd
            if h>=0.6*m:
                end=(t,'level left');break
        if h>0.8*m and t>=last+5 and t>t0:
            end=(t,'hp>80%');break
    if end is None: end=(t0+180,'3min')
    tend,reason=end
    trs=[x for x in byt if t0<=x[0]<=tend]
    eps.append(dict(t0=t0,t1=tend,end=reason,mission=m0,depth=dep0,levels=levels,trig=trs))
    while i<len(byt) and byt[i][0]<=tend:i+=1
pickle.dump(eps,open('eps.pkl','wb'))
c=collections.Counter(e['mission'] for e in eps);print(sorted(c.items()),len(eps))
for e in eps:
    print(e['mission'],hmsd(e['t0']),hms(e['t1']),e['end'],e['depth'],len(e['levels']),dict(collections.Counter(x[1] for x in e['trig'])))

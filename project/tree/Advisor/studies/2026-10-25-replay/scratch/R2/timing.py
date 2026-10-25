import pickle,re,json,statistics as S,bisect,collections
from common import *
dec,ev,st=pickle.load(open('idx.pkl','rb'))
E=load_eps()
TF=[(d['t'],d['factor']) for d in dec if d['kind']=='time_factor']
TF.sort()
tft=[x[0] for x in TF]
def fac(t):
    i=bisect.bisect_right(tft,t)-1
    return TF[i][1] if i>=0 else 1.0
O={i:json.load(open(f'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-replay/replays/ep{i}.json')) for i in IDX}
def stat(xs):
    if not xs:return None
    xs=sorted(xs);q=lambda p:xs[min(len(xs)-1,int(p*len(xs)))]
    return dict(n=len(xs),median=round(S.median(xs),2),p10=round(q(.1),2),p90=round(q(.9),2),min=round(xs[0],2),max=round(xs[-1],2))
res=collections.defaultdict(lambda:collections.defaultdict(list))
# windows: per episode t0-60..t_end
for i,e in E.items():
    t0=O[i]['t0'];te=O[i]['t_end'];a=t0-100;b=te
    msgs=[m for m in ev if m['ev']=='message' and a<=m['epoch']<=b and re.match(r'You (hit|miss|smite|bash|slash|pierce|bite) ',m['text'])]
    # clusters
    cl=[]
    for m in msgs:
        if cl and m['epoch']-cl[-1]<0.03:continue
        cl.append(m['epoch'])
    for x,y in zip(cl,cl[1:]):
        if y-x<2.5 and fac(x)==fac(y):res['melee_round'][fac(x)].append(y-x)
    pos=[(p['epoch'],(p['y'],p['x'])) for p in ev if p['ev']=='pos' and a<=p['epoch']<=b]
    for (x,px),(y,py) in zip(pos,pos[1:]):
        if max(abs(px[0]-py[0]),abs(px[1]-py[1]))==1 and y-x<2.5 and fac(x)==fac(y):res['walk_step'][fac(x)].append(y-x)
    # acts effect spacing & delay
    acts=[x for x in O[i]['actions'] if x['t_effect'] and x['what'] not in('walk','run','melee','rest')]
    for x in acts:res['cmd_delay_issue_to_effect'][fac(x['t'])].append(x['t_effect']-x['t'])
    te_=sorted(x['t_effect'] for x in acts)
    for x,y in zip(te_,te_[1:]):
        if fac(x)==fac(y):res['consecutive_item_effects'][fac(x)].append(y-x)
    for x,y in zip(acts,acts[1:]):pass
out={}
for k,v in res.items():
    out[k]={}
    for f,xs in sorted(v.items()):
        out[k][str(f)]=stat(xs)
json.dump(out,open('timing.json','w'),indent=1)
for k,v in out.items():
    print(k)
    for f,s in v.items():print('  ',f,s)
print('----')
h=collections.Counter(round(x*20)/20 for x in res['walk_step'][1.0]);print('walk1.0',sorted(h.items())[:40])
h=collections.Counter(round(x*20)/20 for x in res['melee_round'][1.0]);print('melee1.0',sorted(h.items())[:25])
print('0.2 walk',sorted(round(x,2) for x in res['walk_step'][0.2]))
print('0.2 melee',sorted(round(x,2) for x in res['melee_round'][0.2]))
print('0.2 itemeff',sorted(round(x,2) for x in res['consecutive_item_effects'][0.2]))
w=[x for x in res['walk_step'][1.0] if 0.5<=x<=0.85];print('walk 0.5-0.85',stat(w))

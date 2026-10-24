import csv,random,statistics as st,collections
random.seed(7)
exec(open('pits.py').read().split("N=4000")[0].split("hooks={")[0])  # load R,T
hooks={'none':lambda r:True}
def mk(hook,level):
    out=[]
    for r in T:
        if r['level']>level: break
        if r['level']<=0: continue
        if 'FORCE_DEPTH' in r['fl'] and r['level']>level: continue
        out.append((r,100//r['rarity']))
    return out
cache={}
def get_mon(level0):
    level=level0
    if random.randrange(50)==0: level+=min(level//4+2,5)
    if random.randrange(50)==0: level+=min(level//4+2,5)
    if level not in cache:
        c=mk(None,level); cache[level]=(c,[p for _,p in c])
    c,ps=cache[level]
    pick=lambda: random.choices(range(len(c)),weights=ps)[0]
    i=pick();p=random.randrange(100)
    if p<60:
        j=i;i=pick()
        if c[i][0]['level']<c[j][0]['level']: i=j
    if p<10:
        j=i;i=pick()
        if c[i][0]['level']<c[j][0]['level']: i=j
    return c[i][0]
out=[]
for D in (10,13,17,20):
  for name,off in (('ordinary(level)',0),('type3/4 inner (,+2)',2),(', (+3)',3),('& (+5)',5),('9 (+9)',9),('@ (+11)',11),('8 (+40)',40),('summon trap',None)):
    L = D+off if off is not None else (D+D)//2+5
    N=6000
    ms=[get_mon(L) for _ in range(N)]
    d=[m['level']-D for m in ms]
    row=dict(depth=D,source=name,cap=L,mean_ood=round(st.mean(d),1),median_ood=st.median(d),p_ood_gt0=round(sum(x>0 for x in d)/N,2),p_ood_ge5=round(sum(x>=5 for x in d)/N,2),p_ood_ge10=round(sum(x>=10 for x in d)/N,2),p_unique=round(sum('UNIQUE' in m['fl'] for m in ms)/N,3),p_friends=round(sum('FRIENDS' in m['fl'] for m in ms)/N,2),p_escort=round(sum(('ESCORT' in m['fl'] or 'ESCORTS' in m['fl']) for m in ms)/N,2),p_awake_native=round(sum(int(m['alertness'])==255 or False for m in ms)/N,2))
    out.append(row)
    print(row)
w=csv.DictWriter(open('ood_by_source.csv','w',newline=''),fieldnames=list(out[0]));w.writeheader();w.writerows(out)

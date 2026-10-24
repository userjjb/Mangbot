import csv,random,collections
random.seed(12345)
R=[]
for r in csv.DictReader(open('/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv')):
    r['level']=int(r['level']);r['rarity']=int(r['rarity']);r['fl']=set(r['flags'].split('|'));R.append(r)
T=[r for r in R if r['rarity']>0]
T.sort(key=lambda r:r['level'])
hooks={
 'jelly':lambda r:'UNIQUE' not in r['fl'] and r['symbol'] in 'ijm,',
 'animal':lambda r:'UNIQUE' not in r['fl'] and 'ANIMAL' in r['fl'],
 'undead':lambda r:'UNIQUE' not in r['fl'] and 'UNDEAD' in r['fl'],
 'orc':lambda r:'UNIQUE' not in r['fl'] and r['symbol']=='o',
 'troll':lambda r:'UNIQUE' not in r['fl'] and r['symbol']=='T',
 'giant':lambda r:'UNIQUE' not in r['fl'] and r['symbol']=='P',
 'demon':lambda r:'UNIQUE' not in r['fl'] and r['symbol']=='U',
}
def mk(hook,level):
    out=[]
    for r in T:
        if r['level']>level: break
        if r['level']<=0: continue
        if not hook(r): continue
        if 'FORCE_DEPTH' in r['fl'] and r['level']>level: continue
        out.append((r,100//r['rarity']))
    return out
cache={}
def get_mon(hook,level0):
    level=level0
    if random.randrange(50)==0: level+=min(level//4+2,5)
    if random.randrange(50)==0: level+=min(level//4+2,5)
    key=(hook,level)
    if key not in cache:
        c=mk(hooks[hook],level); cache[key]=(c,[p for _,p in c],sum(p for _,p in c))
    c,ps,tot=cache[key]
    if tot<=0: return None
    def pick(): return random.choices(range(len(c)),weights=ps)[0]
    i=pick();p=random.randrange(100)
    if p<60:
        j=i;i=pick()
        if c[i][0]['level']<c[j][0]['level']: i=j
    if p<10:
        j=i;i=pick()
        if c[i][0]['level']<c[j][0]['level']: i=j
    return c[i][0]
def pit(hook,depth):
    w=[get_mon(hook,depth+10) for _ in range(16)]
    if None in w: return None
    w.sort(key=lambda r:r['level'])  # bubble sort stable ascending
    w=[w[i*2] for i in range(8)]
    cells=[44,12,12,12,6,6,2,1]
    cnt=collections.Counter()
    for k,n in enumerate(cells): cnt[w[k]['idx']]+=n
    return cnt
def nest(hook,depth):
    w=[get_mon(hook,depth+10) for _ in range(64)]
    if None in w: return None
    cnt=collections.Counter()
    for _ in range(95): cnt[random.choice(w)['idx']]+=1
    return cnt
N=4000
rows=[]
byidx={r['idx']:r for r in R}
summ=[]
for hook in hooks:
    kind='nest' if hook in('jelly','animal','undead') else 'pit'
    for d in (10,13,17,20):
        tot=collections.Counter();app=collections.Counter();ok=0;lv=[]
        for _ in range(N):
            c=(pit if kind=='pit' else nest)(hook,d)
            if c is None: continue
            ok+=1
            for k,v in c.items(): tot[k]+=v;app[k]+=1
        al=mk(hooks[hook],d+10)
        for r,p in al:
            rows.append(dict(hook=hook,kind=kind,depth=d,cap=d+10,race=r['name'],idx=r['idx'],level=r['level'],char=r['symbol'],rarity=r['rarity'],speed=r['speed'],
              share=round(tot[r['idx']]/(95*max(ok,1)),4),p_present=round(app[r['idx']]/max(ok,1),3)))
w=csv.DictWriter(open('pit_nest_races.csv','w',newline=''),fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# print summaries for reachable
for hook,ds in (('orc',(10,13,17,20)),('troll',(20,)),('jelly',(10,13,17,20))):
    for d in ds:
        S=sorted([r for r in rows if r['hook']==hook and r['depth']==d],key=lambda r:-r['share'])
        print(hook,d,'allowed',len(S),'; top:',', '.join(f"{r['race']}(L{r['level']}) {r['share']:.2f}" for r in S[:8]))

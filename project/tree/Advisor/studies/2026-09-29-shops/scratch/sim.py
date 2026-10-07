import csv,random,collections,sys
rows=list(csv.DictReader(open('S1_stock.csv')))
stores=collections.OrderedDict()
for r in rows:
    if r['store']=='Black market':continue
    cost=int(r['W_line'].split(':')[4]); 
    stores.setdefault(r['store'],[]).append((r['item_name'],r['tval'],cost,int(r['entries'])))
ENCH={'TV_SWORD','TV_POLEARM','TV_HAFTED','TV_BOW','TV_SHOT','TV_ARROW','TV_BOLT','TV_DIGGING','TV_CLOAK','TV_HELM','TV_SOFT_ARMOR','TV_HARD_ARMOR','TV_SHIELD','TV_GLOVES','TV_BOOTS'}
def mr(n,m): return sum(random.randrange(m) for _ in range(n))
def size(tv,cost,ego):
    s=1
    if tv in('TV_FOOD','TV_FLASK','TV_LITE'):
        if cost<=5:s+=mr(3,5)
        if cost<=20:s+=mr(3,5)
    elif tv in('TV_POTION','TV_SCROLL'):
        if cost<=60:s+=mr(3,5)
        if cost<=240:s+=mr(1,5)
    elif tv in('TV_MAGIC_BOOK','TV_PRAYER_BOOK'):
        if cost<=50:s+=mr(2,3)
        if cost<=500:s+=mr(1,3)
    elif tv in ENCH and tv not in('TV_SHOT','TV_ARROW','TV_BOLT'):
        if not ego:
            if cost<=10:s+=mr(3,5)
            if cost<=100:s+=mr(3,5)
    elif tv in('TV_SHOT','TV_ARROW','TV_BOLT'):
        if cost<=5:s+=mr(5,5)
        if cost<=50:s+=mr(5,5)
        if cost<=500:s+=mr(5,5)
    return s
def run(name,items,N=30000,burn=2000):
    table=[i for i,it in enumerate(items) for _ in range(it[3])]
    stock=[] # [kindidx, variant_id(0 plain), number]
    pres=collections.Counter(); slots=[]; nvar=[0]
    def create():
        for t in range(4):
            i=random.choice(table); nm,tv,cost,_=items[i]; var=0; ego=False
            if tv in ENCH:
                L=random.randint(1,7); f1=L+10
                if random.randrange(100)<f1: var=1 if random.random()>0.0 else 0; ego=random.randrange(100)<f1//2
                elif random.randrange(100)<f1: continue  # cursed rejected
            disc=0
            if cost>=5:
                if random.randrange(50)==0:disc=25
                elif random.randrange(300)==0:disc=50
                elif random.randrange(600)==0:disc=75
                elif random.randrange(1000)==0:disc=90
            n=size(tv,cost,ego); n=n-n*disc//100
            key=(i,('g',random.random()) if (var and (ego or tv!='TV_CLOAK' or True)) else 0,disc)
            for s in stock:
                if s[0]==key: s[1]=min(99,s[1]+n); return
            stock.append([key,n]); return
    def delete():
        w=random.randrange(len(stock)); n=stock[w][1]
        if random.randrange(100)<50:n=(n+1)//2
        if random.randrange(100)<50:n=1
        stock[w][1]-=n
        if stock[w][1]<=0: stock.pop(w)
    def maint():
        j=len(stock)-random.randint(1,9); j=min(j,36); j=max(j,12)
        while len(stock)>j: delete()
        j=len(stock)+random.randint(1,9); j=min(j,36); j=max(j,12); j=min(j,47)
        while len(stock)<j: create()
    for m in range(burn+N):
        maint()
        if m>=burn:
            slots.append(len(stock))
            ks=set(s[0][0] for s in stock)
            for k in ks:pres[k]+=1
            for s in stock:
                pass
    print('##',name,'mean slots %.1f'%(sum(slots)/len(slots)))
    for i,it in enumerate(items):
        print('  %-32s entries=%d P(in stock)=%.3f'%(it[0],it[3],pres[i]/N))
random.seed(1)
for n,it in stores.items(): run(n,it)

import sys,random,collections
sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
import objgen as o
random.seed(5)
def table(entries):
    return sorted(entries,key=lambda e:e[0])   # (loc,prob,kidx) sorted by level (stable)
def sim(L,good,n):
    ent=table(o.GOOD_ENTRIES if good else o.ENTRIES)
    out=collections.Counter()
    for _ in range(n):
        level=L
        if level>0 and random.randrange(20)==0:
            level=1+level*128//(random.randrange(128)+1)
        t=[e for e in ent if e[0]<=level]
        tot=sum(e[1] for e in t)
        def pickone():
            v=random.randrange(tot)
            for e in t:
                if v<e[1]: return e
                v-=e[1]
        i=pickone(); p=random.randrange(100)
        if p<60:
            j=i; i=pickone()
            if i[0]<j[0]: i=j
        if p<10:
            j=i; i=pickone()
            if i[0]<j[0]: i=j
        out[i[2]]+=1
    return out
for L,good in ((20,False),(35,True)):
    n=60000
    s=sim(L,good,n)
    d=o.pick_dist(L,good); tot=sum(d.values())
    tv=0.5*sum(abs(s.get(k,0)/n-d.get(k,0)/tot) for k in set(s)|set(d))
    print(L,good,"TV distance sim vs model",round(tv,4),"(sampling noise floor ~",round((len(d)/n)**.5/2,3),")","sum model",round(tot,4))

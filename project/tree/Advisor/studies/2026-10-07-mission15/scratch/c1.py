S=40
def row(p,i=S):
    j=max(2,i-p); s=j/100
    so=(1-s)*(0.125 if i>5 else 1)  # per attempt set-off: fail and not (randint1(i)>5)
    # fail-continue prob = (1-s)*(i-5)/i
    so=(1-s)*(5/i)
    return j, s/(s+so), so/(s+so)
for p in [1,2,3,4,5,8,10,12,15,20,25]:
    j,ok,bad=row(p); print(p,j,round(ok,3),round(bad,3))
# gold
costs=[3,4,5,6,7,8,9,10,12,14,16,18,20,24,28,32,40,80]
def gold_ev(L):
    # i=((randint1(L+2)+2)//2)-1 ; 1/20 extra randint1(L+1)
    tot=0
    for a in range(1,L+3):
        i0=(a+2)//2-1
        for e in range(0,L+2):
            if e==0: w=19/20/(L+2)
            else: w=1/20/(L+2)/(L+1)
            i=min(i0+e,17); b=costs[i]
            tot+=w*(b+8*(b+1)/2+4.5)
    return tot
for p in [1,3,5,10,15]:
    L=p+10; print('pval',p,'L',L,round(gold_ev(L),1))

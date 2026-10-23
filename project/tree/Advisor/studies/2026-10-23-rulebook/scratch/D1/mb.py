import re,random,sys
sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
src=open("/projectnb/jbrcs/mangband/github/src/common/z-rand.c").read()
body=src.split("randnor_table[RANDNOR_NUM] =")[1].split("};")[0]
T=[int(x) for x in re.findall(r"\d+",body)]
assert len(T)==256,len(T)
import bisect
def randnor(mean,stand):
    if stand<1: return mean
    tmp=random.randrange(32768)
    low=bisect.bisect_left(T,tmp)   # first idx with T[idx]>=tmp
    off=stand*low//64
    return mean-off if random.randrange(100)<50 else mean+off
def mb_exact(mx,lev):
    lev=min(lev,127)
    bonus=mx*lev//128
    if random.randrange(128)<(mx*lev)%128: bonus+=1
    stand=mx//4
    if random.randrange(4)<mx%4: stand+=1
    v=randnor(bonus,stand)
    return max(0,min(mx,v))
import objgen
N=200000
random.seed(1)
print("mx L  E_exact  E_model")
for mx in (5,7,10):
    for L in (5,10,20,30,40,60,100):
        a=sum(mb_exact(mx,L) for _ in range(N))/N
        b=sum(objgen.m_bonus(mx,L) for _ in range(N))/N
        print(mx,L,round(a,3),round(b,3),round(b-a,3))

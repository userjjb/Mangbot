import sys,random,re,bisect
patched = sys.argv[1]=="exact"
sys.argv=[sys.argv[0],"2500"]
sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
import objgen, build_jewellery as J
if patched:
    src=open("/projectnb/jbrcs/mangband/github/src/common/z-rand.c").read()
    T=[int(x) for x in re.findall(r"\d+",src.split("randnor_table[RANDNOR_NUM] =")[1].split("};")[0])]
    def randnor(mean,stand):
        if stand<1: return mean
        tmp=random.randrange(32768); low=bisect.bisect_left(T,tmp); off=stand*low//64
        return mean-off if random.randrange(100)<50 else mean+off
    def mb(mx,lev):
        lev=min(lev,127); bonus=mx*lev//128
        if random.randrange(128)<(mx*lev)%128: bonus+=1
        stand=mx//4
        if random.randrange(4)<mx%4: stand+=1
        return max(0,min(mx,randnor(bonus,stand)))
    objgen.m_bonus=mb; J.m_bonus=mb
import build_drops as B
for L in (5,10,20,30,40):
    for mode in ("normal","good","great"):
        o=B.object_expect(L,L,mode)
        print(patched,L,mode,round(o["e_value"]),round(o["e_value_cap"]))

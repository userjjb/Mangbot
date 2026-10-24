"""Room-selection simulator (extends m24/scratch/R1/sim.py): mean count of each room type per level.
Mirrors generate.c cave_gen 3187-3247 + room_build 3048-3124. 6x18 blocks, dungeon_align on."""
import random, sys
R,C=6,18
rm={1:(0,0,-1,1,1),2:(0,0,-1,1,1),3:(0,0,-1,1,3),4:(0,0,-1,1,3),5:(0,0,-1,1,5),6:(0,0,-1,1,5),7:(0,1,-1,1,5),8:(-1,2,-2,3,10)}
def gen(D, align=True):
    occ=[[0]*C for _ in range(R)]; crowded=False; cnt={t:0 for t in range(1,9)}
    destroyed = D>10 and random.randrange(15)==0
    def build(y0,x0,t):
        nonlocal crowded
        dy1,dy2,dx1,dx2,lv=rm[t]
        if D<lv: return False
        if crowded and t in(5,6): return False
        y1,y2,x1,x2=y0+dy1,y0+dy2,x0+dx1,x0+dx2
        if y1<0 or y2>=R or x1<0 or x2>=C: return False
        for y in range(y1,y2+1):
            for x in range(x1,x2+1):
                if occ[y][x]: return False
        for y in range(y1,y2+1):
            for x in range(x1,x2+1): occ[y][x]=1
        if t in(5,6): crowded=True
        cnt[t]+=1
        return True
    for i in range(50):
        y=random.randrange(R); x=random.randrange(C)
        if align:
            if x%3==0:x+=1
            if x%3==2:x-=1
        if destroyed:
            build(y,x,1); continue
        if random.randrange(200)<D:
            k=random.randrange(100)
            if random.randrange(200)<D:
                if k<10 and build(y,x,8): continue
                if k<25 and build(y,x,7): continue
                if k<40 and build(y,x,6): continue
                if k<50 and build(y,x,5): continue
            if k<25 and build(y,x,4): continue
            if k<50 and build(y,x,3): continue
            if k<100 and build(y,x,2): continue
        build(y,x,1)
    return cnt,destroyed
if __name__=="__main__":
    random.seed(12345)
    N=int(sys.argv[1]) if len(sys.argv)>1 else 40000
    align = (sys.argv[2]!="noalign") if len(sys.argv)>2 else True
    print("align",align,"N",N)
    print("Depth ft | mean count per level: t1 t2 t3 t4 t5 t6 t7 t8 | P(>=1): t3 t4 t5 t6 t5or6 t7 t8 t7or8 | destroyed | mean rooms")
    for D in (10,13,17,20):
        tot={t:0 for t in range(1,9)}; any_={t:0 for t in range(1,9)}; a56=a78=0; des=0; rooms=0
        for _ in range(N):
            c,d=gen(D,align)
            des+=d
            for t in c: tot[t]+=c[t]; any_[t]+= c[t]>0
            a56+= (c[5]+c[6])>0; a78+=(c[7]+c[8])>0; rooms+=sum(c.values())
        m=lambda t: "%.3f"%(tot[t]/N)
        p=lambda v: "%.3f"%(v/N)
        print(D,D*50,"|"," ".join(m(t) for t in range(1,9)),"|",p(any_[3]),p(any_[4]),p(any_[5]),p(any_[6]),p(a56),p(any_[7]),p(any_[8]),p(a78),"|",p(des),"|","%.1f"%(rooms/N))

import random
R,C=6,18
rm={1:(0,0,-1,1,1),2:(0,0,-1,1,1),3:(0,0,-1,1,3),4:(0,0,-1,1,3),5:(0,0,-1,1,5),6:(0,0,-1,1,5),7:(0,1,-1,1,5),8:(-1,2,-2,3,10)}
def gen(D):
    occ=[[0]*C for _ in range(R)]; crowded=False; res=set()
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
        if t in(5,6): crowded=True; res.add(t)
        if t in (7,8): res.add(t)
        return True
    for i in range(50):
        y=random.randrange(R); x=random.randrange(C)
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
    return res
N=20000
for D in (6,8,10,12,14,16,18,20,30):
    p=n=v=0
    for _ in range(N):
        r=gen(D); p+=6 in r; n+=5 in r; v+=bool(r&{7,8})
    print(D*50,"ft", "pit %.3f nest %.3f vault %.3f"%(p/N,n/N,v/N))

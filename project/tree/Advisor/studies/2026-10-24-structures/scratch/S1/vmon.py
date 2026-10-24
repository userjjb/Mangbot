"""Mean number of monsters vault_monsters() puts down per room sub-variant (generate.c:1076-1100:
9 scatter tries per requested monster, NO break after a success -> every empty floor grid hit gets a monster).
Counts distinct floor grids hit; ignores groups/escorts (friends add more) and place_monster failures."""
import random
random.seed(7)
def fresh(Y,X):  # type-4 double room as a dict of walls (True=wall); coordinates absolute
    wall=set()
    for dy in range(-5,6):
        for dx in range(-12,13):
            if abs(dy)==5 or abs(dx)==12: wall.add((Y+dy,X+dx))
            elif (abs(dy)==3 and abs(dx)<=10) or (abs(dx)==10 and abs(dy)<=3): wall.add((Y+dy,X+dx))
    return wall
def vm(wall,occ,y,x,num):
    for _ in range(num):
        for _ in range(9):
            ny=random.randint(y-1,y+1); nx=random.randint(x-1,x+1)
            if (ny,nx) in wall or (ny,nx) in occ: continue
            occ.add((ny,nx))
def sub(k,Y,X):
    w=fresh(Y,X); occ=set(); R=random.randint; 
    if k==1: vm(w,occ,Y,X,1)
    elif k==2:
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                if (dy,dx)!=(0,0): w.add((Y+dy,X+dx))
        vm(w,occ,Y,X,R(1,3)+2)
    elif k==3:
        for dy in (-1,0,1):
            for dx in (-1,0,1): w.add((Y+dy,X+dx))
        if random.randrange(2)==0:
            t=R(1,2)
            for dy in (-1,0,1):
                for dx in list(range(-5-t,-2-t))+list(range(3+t,6+t)): w.add((Y+dy,X+dx))
        if random.randrange(3)==0:
            for dx in range(-5,6): w.add((Y-1,X+dx)); w.add((Y+1,X+dx))
            w.add((Y,X-5)); w.add((Y,X+5))
            vm(w,occ,Y,X-2,R(1,2)); vm(w,occ,Y,X+2,R(1,2))
    elif k==4:
        for y in range(Y-2,Y+3):
            for x in range(X-9,X+10):
                if (x+y)&1: w.add((y,x))
        vm(w,occ,Y,X-5,R(1,3)); vm(w,occ,Y,X+5,R(1,3))
    elif k==5:
        for y in range(Y-2,Y+3): w.add((y,X))
        for x in range(X-9,X+10): w.add((Y,x))
        vm(w,occ,Y+1,X-4,R(1,4)); vm(w,occ,Y+1,X+4,R(1,4)); vm(w,occ,Y-1,X-4,R(1,4)); vm(w,occ,Y-1,X+4,R(1,4))
    return len(occ)
N=20000
# center parity matters for the checkerboard: Y=11by+5, X in 16+33k
for k,name in ((1,"4.1 inner room+1 monster"),(2,"4.2 inner-inner (locked door)"),(3,"4.3 pillars"),(4,"4.4 checkerboard"),(5,"4.5 four small rooms")):
    if k==4:
        res={}
        for (Y,X) in ((5,16),(16,16),(5,49),(16,49)):
            v=[sub(k,Y,X) for _ in range(N)]; res[(Y,X)]=sum(v)/N
        print(name,{kk:round(vv,2) for kk,vv in res.items()})
    else:
        v=[sub(k,16,49) for _ in range(N)]; print(name,"mean %.2f min %d max %d"%(sum(v)/N,min(v),max(v)))
# type 3 inner vault: 1 cell
print("3.2 cross-room inner vault: 1 monster (only the centre grid is floor)")

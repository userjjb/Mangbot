def succ(skill,lev,conf=False):
    c=skill//2 if conf else skill
    c-= min(lev,50)
    if c<3:
        p_up=1/(3-c+1)   # randint0(3-c+1)==0
        return p_up*(1/3)   # then chance=3: randint1(3)<3 fails; success only 3
    return 1-2/c
for lev in (0,1,3,5,10,15,20,25,30,35,40,45,50):
    print(lev,[round(1-succ(s,lev),3) for s in (22,23)],[round(1-succ(s,lev,True),3) for s in (22,23)])

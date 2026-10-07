import re
rows=[l.split(':')[1:] for l in open('/projectnb/jbrcs/mangband/github/lib/edit/cost_adj.txt') if l.startswith('A:')]
g=[[int(x) for x in r] for r in rows]
own=[];st=None
for l in open('/projectnb/jbrcs/mangband/github/lib/edit/shop_own.txt'):
    if l.startswith('N:'):
        p=l.strip().split(':');st=int(p[1]);nm=p[3]
    elif l.startswith('I:'):
        p=l.strip().split(':');own.append((st,nm,int(p[1]),int(p[2]),int(p[3]),int(p[4]) if len(p)>4 else int(p[3])))
races="Hum HfE Elf Hob Gno Dwa HfO HfT Dun HiE Kob".split()
CHR=125;PR=6
def buy(c,gr,f): 
    fac=f+CHR; adj=max(100,100+gr+fac-300); return (c*adj+50)//100
def sell(c,gr,f):
    fac=f+CHR; adj=min(100,100+300-(gr+fac)); return (c*adj+50)//100
items=[("Phase",15),("CLW",15),("CSW",40),("CCW",100),("EnchToDam",125),("WoR",150),("Torch",2),("Lantern",35),("Flask",3),("MainGauche",25),("Rapier",42)]
import sys
print("store owner race purse greed maxgreed factor(race+CHR) buyadj sellpct")
for s,nm,r,pu,gr,mg in own:
    if s>6: continue
    f=g[r][PR]
    print(s,nm,races[r],pu*5,gr,mg,f+CHR,max(100,100+gr+f+CHR-300),min(100,400-(gr+f+CHR)))

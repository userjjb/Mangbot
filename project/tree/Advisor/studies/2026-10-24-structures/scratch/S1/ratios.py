import random
from sim2 import gen
random.seed(99)
N=60000
print("Depth | P(lit)=(26-D)/25 | mean type4 | mean pit+nest | share pit/nest among all double rooms | among DARK double rooms | mean type1 pillar-room (1/20) | ragged (19/20*1/50)")
for D in (10,13,17,20):
    t4=pn=t1=0
    for _ in range(N):
        c,_d=gen(D); t4+=c[4]; pn+=c[5]+c[6]; t1+=c[1]
    lit=(26-D)/25
    t4/=N; pn/=N; t1/=N
    print(D,"%.2f"%lit,"%.3f"%t4,"%.3f"%pn,"%.3f"%(pn/(pn+t4)),"%.3f"%(pn/(pn+t4*(1-lit))),"%.2f"%(t1*0.05),"%.2f"%(t1*0.95/50))

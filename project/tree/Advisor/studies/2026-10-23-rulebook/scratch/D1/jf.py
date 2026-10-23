import sys; sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
import build_jewellery as J, objgen as o
allpv={"STR","INT","WIS","DEX","CON","CHR","STEALTH","SEARCH","INFRA","TUNNEL","BLOWS","SPEED"}
for k in J.kinds:
    key=(k["tval"],k["name"])
    if key in J.RULES:
        fl=sorted(k["F"]&allpv)
        miss=sorted(set(fl)-set(J.FLAGCOST)-{"SPEED"})
        print(key,fl,"MISSING in FLAGCOST:" if miss else "",miss if miss else "")

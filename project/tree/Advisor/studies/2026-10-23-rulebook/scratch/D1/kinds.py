import sys; sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
import objgen as o, build_jewellery as J
from objgen import kinds, GEAR, CURSES
print("gear kinds cost0 or curse flag or neg plusses:")
for k in kinds.values():
    if k.get("tval") in GEAR and (k["cost"]==0 or k["F"]&CURSES or k["to_h"]<0 or k["to_d"]<0 or k["to_a"]<0):
        print(" ",k["k_idx"],k["name"],k["tval"],"cost",k["cost"],k["F"]&CURSES,k["to_h"],k["to_d"],k["to_a"],"A",k["A"])
print("gear kinds with nonzero kind pval & flags:")
for k in kinds.values():
    if k.get("tval") in GEAR and k["pval"] and k["tval"] not in (19,): print(" ",k["name"],k["pval"],sorted(k["F"]&set(o.PVAL_COST)))
print("jewellery w/o rule:")
JK=J.kinds
for k in JK:
    key=(k["tval"],k["name"])
    if key in J.RULES: continue
    kk=[x for x in kinds.values() if x.get("tval")==k["tval"] and x.get("sval")==k["sval"]][0]
    print(" ",k["tval"],k["name"],"cost",k["cost"],"pval",kk["pval"],"to",kk["to_h"],kk["to_d"],kk["to_a"],sorted(k["F"]&(set(o.PVAL_COST)|CURSES)),"A",kk["A"])

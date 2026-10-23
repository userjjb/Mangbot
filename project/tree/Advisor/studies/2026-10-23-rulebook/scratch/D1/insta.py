import sys; sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
import objgen as o
for k in o.kinds.values():
    if "INSTA_ART" in k["F"]: print(k["k_idx"],k["name"],k["tval"],k["sval"],"A",k["A"],"cost",k["cost"])

import sys; sys.path.insert(0,"/projectnb/jbrcs/mangband/Advisor/data/rulebook")
import build_drops as B
M=B.mons
print(len(M))
def has(f): return [m for m in M if f in m["F"]]
print("GREAT w/o GOOD:",[(m["idx"],m["name"]) for m in has("DROP_GREAT") if "DROP_GOOD" not in m["F"]])
print("GREAT:",[(m["idx"],m["name"],m["level"]) for m in has("DROP_GREAT")])
print("CHOSEN:",[(m["idx"],m["name"]) for m in has("DROP_CHOSEN")])
print("TAKE_ITEM:",len(has("TAKE_ITEM")),[(m["name"],m["level"]) for m in has("TAKE_ITEM")][:40])
print("ONLY_ITEM&ONLY_GOLD:",[m["name"] for m in M if "ONLY_ITEM" in m["F"] and "ONLY_GOLD" in m["F"]])
print("GOOD no count:",[(m["name"]) for m in has("DROP_GOOD") if B.count_dist(m["F"])=={0:1.0}])
print("GOOD count:",len(has("DROP_GOOD")))
print("ONLY_GOLD w/o drop count:",[(m["name"]) for m in has("ONLY_GOLD") if B.count_dist(m["F"])=={0:1.0}])
print("KILL_BODY/ others w/ 'DROP_' flags unknown:", {f for m in M for f in m["F"] if f.startswith("DROP")})
print("coin:",[(m["idx"],m["name"],B.coin_type(m)) for m in M if m.get("sym")=="$"])

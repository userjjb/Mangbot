import sys; sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-03-state/scratch')
from g4_lib import *
# usage: g4_q.py dive day a b [msgpat] [--dec]
d,day,a,b=sys.argv[1:5]
pat=sys.argv[5] if len(sys.argv)>5 and not sys.argv[5].startswith("--") else None
A=parse(f"2026-{day} {a}"); B=parse(f"2026-{day} {b}")
if "--dec" in sys.argv:
    last=None
    for r in decs(d):
        if A<=r["t"]<=B and (r["kind"] in("attention","goal","note") or r.get("depth")!=last) and r["kind"]!="move":
            last=r.get("depth"); 
            print(stamp(r["t"]),(r["depth"]*50 if r.get("depth") is not None else None),r["hp"],r["kind"],(r.get("goal") or r.get("what") or r.get("text") or r.get("cmd") or "")[:90],(r.get("detail") or "")[:110])
else:
    msgs(abs_t(d),A,B,pat)

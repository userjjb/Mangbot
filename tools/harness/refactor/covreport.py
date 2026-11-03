"""Branch coverage of reflexes/escape per equiv.py state: python3 covreport.py PILOT_DIR COV.json"""
import json
import os
import sys
d = os.path.abspath(sys.argv[1])
sys.path.insert(0, d)
os.chdir(d)
import pilot as P  # noqa: E402
cov = json.load(open(sys.argv[2]))
funcs = ("reflexes", "escape")
exe = {}
for f in funcs:
    co = getattr(P.Pilot, f).__code__
    exe[f] = {ln - co.co_firstlineno for _, _, ln in co.co_lines() if ln is not None} - {0}
combat = [n for n in cov if n.startswith("combat_")]
base = [n for n in cov if not n.startswith("combat_")]
for f in funcs:
    u_base = set().union(*(set(cov[n].get(f, [])) for n in base))
    u_all = set().union(*(set(cov[n].get(f, [])) for n in cov))
    print(f"{f}: {len(exe[f])} executable lines; the 33 old states reach {len(u_base & exe[f])}, "
          f"all {len(cov)} states {len(u_all & exe[f])} (+{len((u_all - u_base) & exe[f])} by the new states)")
print()
sig = {}
for n in combat:
    s = tuple(tuple(sorted(cov[n].get(f, []))) for f in funcs)
    sig.setdefault(s, []).append(n)
    others = set()
    for m in cov:
        if m != n:
            for f in funcs:
                others |= {(f, x) for x in cov[m].get(f, [])}
    own = {(f, x) for f in funcs for x in cov[n].get(f, [])}
    print(f"{n:34s} reflexes {len(cov[n].get('reflexes', [])):3d}  escape {len(cov[n].get('escape', [])):3d}  "
          f"lines no other state reaches: {len(own - others)}")
dups = [v for v in sig.values() if len(v) > 1]
print("\nstates with identical line sets:", dups or "none")

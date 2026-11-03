"""Which step orders the equivalence states can see (E3): swap each adjacent pair of REFLEX_STEPS / ESCAPE_STEPS in a
scratch tree's combat.py, run equiv.py on the states that reach the earlier step of the pair (from a coverage file of
the unswapped tree), and count the states whose record changes. A pair no state tells apart is an order the harness
would miss (or one that can't matter: the steps exclude each other, or one never acts).

    python3 stepswap.py MUT_TREE COV.json BASE.json [PAIR_INDEX...]

MUT_TREE: a scratch copy of the new tree (its tools/pilot/combat.py is rewritten for each swap and restored at the end).
COV.json: EQUIV_COVER of the new tree with EQUIV_COVER_FUNCS naming the step methods. BASE.json: equiv.py's output
for the new tree. Runs one equiv.py at a time (PYTHONHASHSEED=0)."""
import json
import os
import re
import subprocess
import sys

tree, cov_f, base_f = sys.argv[1:4]
only = {int(x) for x in sys.argv[4:]}
here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(tree, "tools", "pilot", "combat.py")
orig = open(src).read()
cov, base = json.load(open(cov_f)), json.load(open(base_f))


def steps(name):
    m = re.search(rf"    {name} = \((.*?)\n    \)", orig, re.S)
    return re.findall(r'"(\w+)",', m.group(1))


pairs = [(lst, a, b) for lst in ("REFLEX_STEPS", "ESCAPE_STEPS") for a, b in zip(steps(lst), steps(lst)[1:])]
out = os.path.join(os.path.dirname(os.path.abspath(cov_f)), "stepswap")
os.makedirs(out, exist_ok=True)
try:
    for i, (lst, a, b) in enumerate(pairs):
        if only and i not in only:
            continue
        states = sorted(n for n in cov if cov[n].get(a))
        qa, qb = f'"{a}",', f'"{b}",'
        mut = orig.replace(qa, "\0").replace(qb, qa).replace("\0", qb)
        with open(src, "w") as f:
            f.write(mut)
        pyc = os.path.join(tree, "tools", "pilot", "__pycache__")
        for p in os.listdir(pyc) if os.path.isdir(pyc) else ():
            if p.startswith("combat."):
                os.remove(os.path.join(pyc, p))
        res = os.path.join(out, f"{i:02d}.json")
        subprocess.run([sys.executable, os.path.join(here, "equiv.py"), os.path.join(tree, "tools", "pilot"), res]
                       + states, env=dict(os.environ, PYTHONHASHSEED="0"), stdout=subprocess.DEVNULL, check=True)
        got = json.load(open(res))
        diff = [n for n in states if got[n] != base[n]]
        errs = [n for n in states if any(t["error"] for t in got[n]["ticks"])]
        print(f"{i:2d} {a} <-> {b}: {len(states)} states reach {a}; {len(diff)} differ"
              + (f" ({len(errs)} with errors)" if errs else "") + (f": {' '.join(diff[:4])}" if diff else ""),
              flush=True)
finally:
    with open(src, "w") as f:
        f.write(orig)

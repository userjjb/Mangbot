"""The lines of reflexes/escape no equiv.py state reaches: python3 uncovered.py PILOT_DIR COV.json [FUNC...]
(COV.json from EQUIV_COVER; prints each unreached executable line with its file line number and source)."""
import inspect
import json
import os
import sys
d = os.path.abspath(sys.argv[1])
sys.path.insert(0, d)
os.chdir(d)
import pilot as P  # noqa: E402
cov = json.load(open(sys.argv[2]))
funcs = sys.argv[3:] or ["reflexes", "escape"]
for f in funcs:
    fn = getattr(P.Pilot, f)
    co = fn.__code__
    src, first = inspect.getsourcelines(fn)
    exe = sorted({ln - co.co_firstlineno for _, _, ln in co.co_lines() if ln is not None} - {0})
    hit = set().union(*(set(cov[n].get(f, [])) for n in cov))
    miss = [r for r in exe if r not in hit]
    print(f"== {f}: {len(exe)} executable, {len(set(exe) & hit)} reached ({100 * len(set(exe) & hit) / len(exe):.0f}%), "
          f"{len(miss)} not")
    for r in miss:
        print(f"{first + r:5d}  {src[r].rstrip()}")

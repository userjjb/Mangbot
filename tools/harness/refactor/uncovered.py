"""The lines of the named functions no equiv.py state reaches: python3 uncovered.py PILOT_DIR COV.json [FUNC...]
(COV.json from EQUIV_COVER; prints each unreached executable line with its file line number and source). FUNC: a
Pilot method by its bare name (reflexes, escape: the default) or a class's method by its qualname (TownKit.tick,
HouseBank.item_step; the class from any of the Pilot's modules), recorded under that name (EQUIV_COVER_FUNCS)."""
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


def resolve(f):
    if "." not in f:
        return getattr(P.Pilot, f)
    cls, meth = f.split(".", 1)
    for m in list(sys.modules.values()):
        if os.path.dirname(os.path.abspath(getattr(m, "__file__", None) or "/")) == d and isinstance(
                getattr(m, cls, None), type) and getattr(m, cls).__module__ == m.__name__:
            return getattr(getattr(m, cls), meth)
    raise SystemExit(f"{f}: no such class in the Pilot's modules")


for f in funcs:
    fn = resolve(f)
    co = fn.__code__
    src, first = inspect.getsourcelines(fn)
    exe = sorted({ln - co.co_firstlineno for _, _, ln in co.co_lines() if ln is not None} - {0})
    hit = set().union(*(set(cov[n].get(f, [])) for n in cov))
    miss = [r for r in exe if r not in hit]
    print(f"== {f}: {len(exe)} executable, {len(set(exe) & hit)} reached ({100 * len(set(exe) & hit) / len(exe):.0f}%), "
          f"{len(miss)} not")
    for r in miss:
        print(f"{first + r:5d}  {src[r].rstrip()}")

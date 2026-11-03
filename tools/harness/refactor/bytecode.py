"""Dump a digest of the moved names as found in one tree: python3 bytecode.py PILOT_DIR CLASS OUT.json
(old tree: CLASS=Pilot; new tree: CLASS=TownMixin)."""
import json
import os
import sys
import types

d, clsname, out = sys.argv[1:4]
sys.path.insert(0, d)
os.chdir(d)
import pilot as P  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split import MOVE  # noqa: E402

cls = getattr(P, clsname)


def code_digest(co):
    consts = [code_digest(c) if isinstance(c, types.CodeType) else repr(c) for c in co.co_consts]
    return {"code": co.co_code.hex(), "consts": consts, "names": list(co.co_names), "varnames": list(co.co_varnames),
            "freevars": list(co.co_freevars), "cellvars": list(co.co_cellvars), "argcount": co.co_argcount,
            "kwonly": co.co_kwonlyargcount, "flags": co.co_flags, "linetable": co.co_linetable.hex(),
            "exctable": co.co_exceptiontable.hex(), "name": co.co_name, "qualname": co.co_qualname}


def all_names(co):
    out = set(co.co_names)
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            out |= all_names(c)
    return out


def ident(v):
    if isinstance(v, types.ModuleType):
        return f"module {v.__name__}"
    if callable(v) and hasattr(v, "__qualname__"):
        return f"{getattr(v, '__module__', '?')}.{v.__qualname__}"
    return f"{type(v).__name__} {v!r}"[:200]


res = {}
for n in MOVE:
    raw = cls.__dict__[n]                     # (KeyError: not defined on this class itself)
    kind = type(raw).__name__
    f = raw
    if isinstance(f, staticmethod):
        f = f.__func__
    wrapped = []
    while hasattr(f, "__wrapped__"):
        wrapped.append(type(f).__name__)
        f = f.__wrapped__
    if isinstance(f, types.FunctionType):
        res[n] = {"kind": kind, "wrappers": wrapped, "defaults": repr(f.__defaults__),
                  "kwdefaults": repr(f.__kwdefaults__), "code": code_digest(f.__code__),
                  "globals_used": {g: ident(f.__globals__[g]) for g in sorted(all_names(f.__code__) & set(f.__globals__))}}
    else:
        res[n] = {"kind": kind, "value": repr(raw)}
json.dump(res, open(out, "w"), indent=1, sort_keys=True)
print(f"{len(res)} names from {clsname}")

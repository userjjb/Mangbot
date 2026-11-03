"""Dump a digest of the moved names as found in one tree: python3 bytecode.py PILOT_DIR CLASS MODULE OUT.json
(old tree: CLASS=Pilot MODULE=pilot; new tree: CLASS=CombatMixin MODULE=combat). split.MOVE is read from CLASS's own
__dict__ (functions, properties: fget/fset/fdel, staticmethods, constants), split.MOVE_TOP from MODULE's globals.
Compare two dumps with bcdiff.py."""
import json
import os
import sys
import types

d, clsname, modname, out = sys.argv[1:5]
d = os.path.abspath(d)
sys.path.insert(0, d)
os.chdir(d)
import pilot as P  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split import MOVE, MOVE_TOP  # noqa: E402

cls = getattr(P, clsname)
mod = sys.modules[modname]


def code_digest(co):
    consts = [code_digest(c) if isinstance(c, types.CodeType) else repr(c) for c in co.co_consts]
    return {"code": co.co_code.hex(), "consts": consts, "names": list(co.co_names), "varnames": list(co.co_varnames),
            "freevars": list(co.co_freevars), "cellvars": list(co.co_cellvars), "argcount": co.co_argcount,
            "kwonly": co.co_kwonlyargcount, "flags": co.co_flags, "linetable": co.co_linetable.hex(),
            "exctable": co.co_exceptiontable.hex(), "name": co.co_name, "qualname": co.co_qualname,
            "firstlineno": co.co_firstlineno, "file": co.co_filename}


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
    return f"{type(v).__name__} {v!r}".replace(d, "<PILOT_DIR>")[:200]      # (HERE: the tree's own path)


def func_digest(f):
    wrapped = []
    while hasattr(f, "__wrapped__"):
        wrapped.append(type(f).__name__)
        f = f.__wrapped__
    return {"wrappers": wrapped, "defaults": repr(f.__defaults__), "kwdefaults": repr(f.__kwdefaults__),
            "closure": repr([c.cell_contents for c in f.__closure__]) if f.__closure__ else None,
            "code": code_digest(f.__code__),
            "globals_used": {g: ident(f.__globals__[g]) for g in sorted(all_names(f.__code__) & set(f.__globals__))}}


def digest(raw):
    kind = type(raw).__name__
    if isinstance(raw, property):
        return {"kind": kind, "doc": raw.__doc__,
                **{a: (func_digest(getattr(raw, a)) if getattr(raw, a) else None) for a in ("fget", "fset", "fdel")}}
    f = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
    if isinstance(f, types.FunctionType):
        return {"kind": kind, **func_digest(f)}
    return {"kind": kind, "value": repr(raw)}


res = {}
for n in MOVE:
    res[n] = digest(cls.__dict__[n])               # (KeyError: not defined on this class itself)
for n in MOVE_TOP:
    res["<top>." + n] = digest(mod.__dict__[n])
json.dump(res, open(out, "w"), indent=1, sort_keys=True)
print(f"{len(res)} names from {clsname} / {modname}")

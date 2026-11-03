"""The name check: python3 names.py PILOT_DIR [OLD_PILOT_DIR]. Pilot's MRO; no name defined in two of the classes
(Pilot and its mixins); no method of a mixin uses super() or __class__; every attribute of the old Pilot resolves on
the new one to the same kind of object (and to a function whose code is the old one's, by bytecode)."""
import os
import subprocess
import sys
import types

d = os.path.abspath(sys.argv[1])
sys.path.insert(0, d)
os.chdir(d)
import pilot as P  # noqa: E402

mro = P.Pilot.__mro__
print("MRO:", " -> ".join(c.__name__ for c in mro))
own = [c for c in mro if c is not object]
seen, clash = {}, []
for c in own:
    for n in c.__dict__:
        if n in ("__module__", "__qualname__", "__doc__", "__dict__", "__weakref__", "__firstlineno__",
                 "__static_attributes__"):
            continue
        if n in seen:
            clash.append((n, seen[n], c.__name__))
        seen[n] = c.__name__
print("names defined in two classes:", clash or "none")
bad = []
for c in own[1:]:
    for n, v in c.__dict__.items():
        fs = [v.fget, v.fset, v.fdel] if isinstance(v, property) else [getattr(v, "__func__", v)]
        for f in fs:
            if isinstance(f, types.FunctionType):
                co = f.__code__
                def names(co):
                    out = set(co.co_names) | set(co.co_freevars)
                    for k in co.co_consts:
                        if isinstance(k, types.CodeType):
                            out |= names(k)
                    return out
                if {"super", "__class__"} & names(co):
                    bad.append(f"{c.__name__}.{n}")
print("mixin methods using super()/__class__:", bad or "none")
by = {}
for n in seen:
    by.setdefault(seen[n], 0)
    by[seen[n]] += 1
print("names per class:", by)
if len(sys.argv) > 2:
    # every name of the old Pilot (its own __dict__ and its bases') still resolves on the new Pilot
    old = subprocess.run([sys.executable, "-c", f"""
import sys, os; sys.path.insert(0, {sys.argv[2]!r}); os.chdir({sys.argv[2]!r}); import pilot as P
print(' '.join(sorted(n for c in P.Pilot.__mro__ for n in c.__dict__)))
print(' '.join(sorted(n for n in vars(P) if not n.startswith('__'))))
"""], capture_output=True, text=True, check=True).stdout.split("\n")
    old_attrs, old_mod = set(old[0].split()), set(old[1].split())
    miss = sorted(n for n in old_attrs if not hasattr(P.Pilot, n) and n not in ("__static_attributes__",))
    miss_mod = sorted(n for n in old_mod if not hasattr(P, n))
    print("old Pilot names missing on the new Pilot:", miss or "none")
    print("old pilot module names missing in the new module:", miss_mod or "none")
    print("new pilot module names:", sorted(set(n for n in vars(P) if not n.startswith('__')) - old_mod))
for n in ("escape", "group_tick", "speed_start_tick", "berserk_tick", "fear_cure", "reflexes", "hard_fight",
          "teleport_item", "has_ability", "danger_why", "escaping_to_stairs"):
    v = getattr(P.Pilot, n)
    print(f"  Pilot.{n}: {getattr(v, '__qualname__', type(v).__name__)} from {next(c.__name__ for c in mro if n in c.__dict__)}")
sys.exit(1 if clash or bad else 0)

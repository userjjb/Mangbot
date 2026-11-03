"""Every function of the Pilot's modules, old tree vs new tree, by bytecode (line numbers, file names and qualnames
ignored): python3 bcall.py OLD_PILOT_DIR NEW_PILOT_DIR. Prints the functions whose code changed, the added and the
removed ones (module.Class.name; properties as .fget/.fset). Run with PYTHONHASHSEED=0 (a frozenset constant's repr
follows the hash seed). E3: only reflexes and escape change; their steps are added.
"""
import json
import subprocess
import sys

DUMP = r"""
import glob, hashlib, json, os, sys, types
d = sys.argv[1]
sys.path.insert(0, d)
os.chdir(d)
import pilot  # noqa: E402  (imports the rest)


def digest(co):
    parts = [co.co_code.hex(), repr(co.co_names), repr(co.co_varnames), repr(co.co_freevars), repr(co.co_cellvars)]
    for k in co.co_consts:
        parts.append(digest(k) if isinstance(k, types.CodeType) else repr(k))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


out = {}
mods = [os.path.basename(f)[:-3] for f in sorted(glob.glob(os.path.join(d, "*.py")))]
for mn in mods:
    m = sys.modules.get(mn)
    if m is None:
        continue
    for n, v in vars(m).items():
        if isinstance(v, types.FunctionType) and v.__module__ == mn:
            out[f"{mn}.{n}"] = digest(v.__code__)
        elif isinstance(v, type) and v.__module__ == mn:
            for an, av in vars(v).items():
                fs = {"fget": av.fget, "fset": av.fset, "fdel": av.fdel} if isinstance(av, property) else \
                    {"": getattr(av, "__func__", av)}
                for suf, f in fs.items():
                    if isinstance(f, types.FunctionType):
                        out[f"{mn}.{n}.{an}" + (f".{suf}" if suf else "")] = digest(f.__code__)
print(json.dumps(out))
"""


def dump(d):
    r = subprocess.run([sys.executable, "-c", DUMP, d], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)
    return json.loads(r.stdout.strip().splitlines()[-1])


a, b = dump(sys.argv[1]), dump(sys.argv[2])
changed = sorted(k for k in a if k in b and a[k] != b[k])
print(f"{len(a)} functions old, {len(b)} new")
print("changed:", " ".join(changed) or "none")
print("added:", " ".join(sorted(set(b) - set(a))) or "none")
print("removed:", " ".join(sorted(set(a) - set(b))) or "none")
sys.exit(0)

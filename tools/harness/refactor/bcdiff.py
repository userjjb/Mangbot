"""Compare two bytecode.py dumps (old tree, new tree): python3 bcdiff.py OLD.json NEW.json [OLDMOD NEWMOD OLDCLS NEWCLS]
Allowed differences: co_qualname (Pilot.x -> CombatMixin.x), co_firstlineno and co_filename, and in globals_used the
module of the moved top-level functions (pilot.heal_of -> combat.heal_of). Anything else is printed; exit 1 if any."""
import json
import sys

a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
om, nm, oc, nc = (sys.argv[3:7] + ["pilot", "combat", "Pilot", "CombatMixin"][len(sys.argv[3:7]):])
IGNORE = {"qualname", "firstlineno", "file"}
diffs = []


def walk(x, y, path):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if k in IGNORE:
                continue
            if k not in x or k not in y:
                diffs.append(f"{path}.{k}: only in {'new' if k in y else 'old'}")
                continue
            walk(x[k], y[k], f"{path}.{k}")
    elif isinstance(x, list) and isinstance(y, list):
        if len(x) != len(y):
            diffs.append(f"{path}: length {len(x)} -> {len(y)}")
        for i, (p, q) in enumerate(zip(x, y)):
            walk(p, q, f"{path}[{i}]")
    elif x != y:
        if isinstance(x, str) and isinstance(y, str) and ".globals_used." in path and \
                x.replace(f"{om}.", f"{nm}.", 1) == y:
            return
        diffs.append(f"{path}: {str(x)[:100]!r} -> {str(y)[:100]!r}")


if set(a) != set(b):
    print("names differ:", sorted(set(a) ^ set(b)))
for n in sorted(set(a) & set(b)):
    walk(a[n], b[n], n)
quals = sum(1 for n in a if isinstance(a[n], dict) and a[n].get("code"))
print(f"{len(a)} names compared; {len(diffs)} differences beyond qualname/line/file")
for d in diffs[:60]:
    print("  ", d)
sys.exit(1 if diffs or set(a) != set(b) else 0)

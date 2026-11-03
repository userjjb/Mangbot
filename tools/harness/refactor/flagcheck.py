"""E5's declared-flags check: python3 flagcheck.py OLD_PILOT_DIR NEW_PILOT_DIR
For each class of town_goals.py and plan.py: every lazy read of an attribute of self in the OLD code --
getattr(self, "f", D), self.__dict__.get("f", D), self.__dict__.setdefault("f", D) -- with its default, against the
value the NEW __init__ assigns it. A flag passes when every read site's default equals the declared value (so the
first read gives what it gave before). Prints flags whose sites disagree (to be kept lazy), declared flags with no
lazy read, and lazy reads left undeclared. Then every other place in the Pilot's code (tools/pilot, tools/harness,
tools/observe) that names a declared flag through hasattr(), vars(), __dict__ or a getattr on something other than
self, and every vars(goal) dump (cmd_goalstate), which sees a declared flag from the first tick on. Exit 1 if a
declared value differs from a read's default."""
import ast
import glob
import os
import re
import sys

old_dir, new_dir = sys.argv[1:3]
FILES = ("town_goals.py", "plan.py")


def value(node):
    try:
        return ast.literal_eval(node)
    except ValueError:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.args:
            return {"set": set(), "list": [], "dict": {}}.get(node.func.id, ast.unparse(node))
        return ast.unparse(node)


def lazy_reads(tree):
    """{(class, flag): [(method, line, default)]}"""
    out = {}
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for f in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(f):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id == "getattr" and len(node.args) == 3 and \
                        isinstance(node.args[0], ast.Name) and node.args[0].id == "self" and \
                        isinstance(node.args[1], ast.Constant):
                    name, d = node.args[1].value, node.args[2]
                elif isinstance(fn, ast.Attribute) and fn.attr in ("get", "setdefault") and \
                        ast.unparse(fn.value) == "self.__dict__" and isinstance(node.args[0], ast.Constant):
                    name, d = node.args[0].value, node.args[1] if len(node.args) > 1 else ast.Constant(None)
                else:
                    continue
                out.setdefault((cls.name, name), []).append((f.name, node.lineno, value(d)))
    return out


def declared(tree):
    """{(class, attr): value} assigned in __init__"""
    out = {}
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        init = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
        for st in (init.body if init else []):
            if isinstance(st, ast.Assign):
                for t in st.targets:
                    for e in (t.elts if isinstance(t, ast.Tuple) else [t]):
                        if isinstance(e, ast.Attribute) and ast.unparse(e.value) == "self":
                            out[(cls.name, e.attr)] = value(st.value) if not isinstance(t, ast.Tuple) else "?"
    return out


bad, flags = 0, set()
for f in FILES:
    old_t = ast.parse(open(os.path.join(old_dir, f)).read())
    new_t = ast.parse(open(os.path.join(new_dir, f)).read())
    reads, old_decl, new_decl = lazy_reads(old_t), declared(old_t), declared(new_t)
    added = {k: v for k, v in new_decl.items() if k not in old_decl}
    print(f"== {f}: {len(added)} attributes declared in __init__ by E5")
    for (cls, name), v in sorted(added.items()):
        sites = reads.get((cls, name), [])
        defaults = [d for _, _, d in sites]
        ok = all(type(d) is type(v) and d == v for d in defaults)
        bad += not ok
        flags.add(name)
        print(f"   {'ok ' if ok else 'BAD'} {cls}.{name} = {v!r}: " +
              (", ".join(f"{m}:{ln} default {d!r}" for m, ln, d in sites) if sites else "no lazy read (set before read)"))
    for (cls, name), sites in sorted(reads.items()):
        if (cls, name) not in added and (cls, name) not in old_decl:
            ds = {repr(d) for _, _, d in sites}
            print(f"   left lazy: {cls}.{name}: " + ", ".join(f"{m}:{ln} default {d!r}" for m, ln, d in sites) +
                  ("  (DEFAULTS DIFFER)" if len(ds) > 1 else ""))

print("== other code naming a declared flag through hasattr / vars / __dict__ / getattr on something else:")
tools = os.path.dirname(os.path.abspath(new_dir.rstrip("/")))
hits = 0
for path in sorted(glob.glob(os.path.join(tools, "pilot", "*.py")) + glob.glob(os.path.join(tools, "harness", "*.py")) +
                   glob.glob(os.path.join(tools, "observe", "*.py"))):
    for i, ln in enumerate(open(path), 1):
        for name in flags:
            if re.search(rf'(hasattr|getattr)\((?!self,)[^)]*"{name}"|__dict__[^\n]*"{name}"|vars\([^)]*\)[^\n]*"{name}"', ln):
                print(f"   {os.path.relpath(path, tools)}:{i}: {ln.strip()[:110]}")
                hits += 1
        if re.search(r"vars\((g|self\.goal|goal)\)", ln):
            print(f"   {os.path.relpath(path, tools)}:{i}: (a dump of a goal's attributes) {ln.strip()[:100]}")
print(f"   {hits} by name")
sys.exit(1 if bad else 0)

"""E5's mechanical-move check: python3 stepdiff5.py OLD_PILOT_DIR NEW_PILOT_DIR
For Shop, HouseBank and TownKit (town_goals.py) and TripPlan (plan.py): the old tick()'s code lines against the new
tick's and its step methods' code lines, concatenated in the order they run (Shop: tick, the STATES methods, then
TRADE_STEPS; HouseBank: TICK_STEPS with _bank_door's STEPS in place; TownKit: KIT_STEPS with _kit_buying's
BUYING_STEPS in place; TripPlan: TRIP_STEPS), compared with the indentation stripped (a dispatched state's body sits
one level shallower), and without each step's def, docstring, `x = ctx.x` prologue and closing `return NEXT`. The
declared flags' lazy reads in the old lines are rewritten first (getattr(self, "f", d) / self.__dict__.get or
setdefault("f", d) -> self.f, for the flags each new __init__ declares). Prints a unified diff of what remains: the
lines that are not a verbatim move (the dispatch and step loops, the ctx stores, the `if self.state == ...` tests a
dispatch replaces). Then the comments: every old comment line must be in the new code. Exit 1 if a comment is lost."""
import ast
import difflib
import re
import sys

old_dir, new_dir = sys.argv[1:3]


def load(d, f):
    src = open(f"{d}/{f}").read()
    return src, src.split("\n"), ast.parse(src)


def classes(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def members(cls):
    out = {}
    for f in cls.body:
        if isinstance(f, ast.FunctionDef):
            out[f.name] = f
        elif isinstance(f, ast.Assign) and isinstance(getattr(f.targets[0], "id", None), str):
            v = f.value
            if isinstance(v, ast.Tuple):
                out[f.targets[0].id] = [e.value for e in v.elts]
            elif isinstance(v, ast.Dict):
                out[f.targets[0].id] = [e.value for e in v.values]
    return out


def body(lines, f):
    first = f.body[0]
    start = first.end_lineno if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
        and isinstance(first.value.value, str) else f.lineno
    return lines[start:f.end_lineno]


def e5_flags(lines, init):
    """the flags declared under the `refactor-candidates E5 declares them` comment of __init__"""
    seg = lines[init.lineno - 1:init.end_lineno]
    k = next((i for i, ln in enumerate(seg) if "E5 declares them" in ln), None)
    return [m.group(1) for ln in seg[k + 1:] for m in [re.match(r"\s+self\.(\w+) = ", ln)] if m] if k is not None else []


def lazy_to_attr(ln, flags):
    for f in flags:
        ln = re.sub(rf'getattr\(self, "{f}", [^()]*(\(\))?\)', f"self.{f}", ln)
        ln = re.sub(rf'self\.__dict__\.(get|setdefault)\("{f}", [^()]*(\(\))?\)', f"self.{f}", ln)
    return ln


def code(ls):
    return [ln.strip() for ln in ls if ln.strip() and not ln.strip().startswith("#")]


def comments(ls):
    return [ln.strip().lstrip("#").strip() for ln in ls if ln.strip().startswith("#")]


ORDER = {
    "Shop": lambda M: ["tick"] + M["STATES"] + M["TRADE_STEPS"],
    "HouseBank": lambda M: ["tick"] + M["TICK_STEPS"] + M["STEPS"],
    "TownKit": lambda M: ["tick"] + M["KIT_STEPS"] + M["BUYING_STEPS"],
    "TripPlan": lambda M: ["tick"] + M["TRIP_STEPS"],
}
bad = 0
for f, names in (("town_goals.py", ("Shop", "HouseBank", "TownKit")), ("plan.py", ("TripPlan",))):
    _, ol, ot = load(old_dir, f)
    _, nl, nt = load(new_dir, f)
    OC, NC = classes(ot), classes(nt)
    for cn in names:
        O, N = members(OC[cn]), members(NC[cn])
        flags = e5_flags(nl, N["__init__"])
        old_body = [lazy_to_attr(ln, flags) for ln in body(ol, O["tick"])]
        new_body, docs = [], []
        for name in ORDER[cn](N):
            ls = body(nl, N[name])
            while ls and re.match(r"^\s+[\w, ]+ = ctx\.\w+(, ctx\.\w+)*$", ls[0]):
                ls = ls[1:]
            if ls and ls[-1].strip() == "return NEXT":
                ls = ls[:-1]
            new_body += ls
            docs.append(ast.get_docstring(N[name], clean=False) or "")
        a, b = code(old_body), code(new_body)
        d = list(difflib.unified_diff(a, b, f"old {cn}.tick", f"new {cn} steps", n=0, lineterm=""))
        print(f"== {cn}: {len(a)} code lines old, {len(b)} in the new tick and its steps "
              f"({len(ORDER[cn](N)) - 1} methods); flags declared: {' '.join(flags)}; not verbatim:")
        print("\n".join(d) if d else "(none)")
        have = set(comments(new_body)) | {x.strip() for t in docs for x in t.split("\n")}
        lost = [c for c in comments(old_body) if c not in have]
        print(f"   old comment lines not in the new code: {lost or 'none'}")
        bad += bool(lost)
sys.exit(1 if bad else 0)

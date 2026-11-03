"""E3's mechanical-move check: python3 stepdiff.py OLD_COMBAT.py NEW_COMBAT.py
For reflexes and escape: the old method's code lines against the new step methods' code lines, concatenated in
REFLEX_STEPS / ESCAPE_STEPS order -- without each step's def, docstring, `x = ctx.x` prologue and closing
`return NEXT`, and without the loop in the entry point. Prints a unified diff of what remains: the lines that are not
a verbatim move (the ctx stores, the old preamble and final return). Then the comments: every old comment line must
be in the new code, as a comment or in a step's docstring."""
import ast
import difflib
import re
import sys

old_src, new_src = open(sys.argv[1]).read(), open(sys.argv[2]).read()
old_lines, new_lines = old_src.split("\n"), new_src.split("\n")


def methods(src):
    out = {}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and node.name == "CombatMixin":
            for f in node.body:
                if isinstance(f, ast.FunctionDef):
                    out[f.name] = f
                elif isinstance(f, ast.Assign) and isinstance(f.value, ast.Tuple) and \
                        getattr(f.targets[0], "id", "").endswith("_STEPS"):
                    out[f.targets[0].id] = [e.value for e in f.value.elts]
    return out


def body(lines, f, skip_doc=True):
    """the source lines of f's body (after the docstring)."""
    first = f.body[0]
    if skip_doc and isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and \
            isinstance(first.value.value, str):
        start = first.end_lineno
    else:
        start = f.lineno
    return lines[start:f.end_lineno]


def doc(f):
    return ast.get_docstring(f, clean=False) or ""


def code(ls):
    return [ln for ln in ls if ln.strip() and not ln.strip().startswith("#")]


def comments(ls):
    return [ln.strip().lstrip("#").strip() for ln in ls if ln.strip().startswith("#")]


O, N = methods(old_src), methods(new_src)
bad = 0
for entry, lst in (("reflexes", "REFLEX_STEPS"), ("escape", "ESCAPE_STEPS")):
    old_body = body(old_lines, O[entry], skip_doc=(entry == "escape"))
    new_body, docs = [], []
    for name in N[lst]:
        ls = body(new_lines, N[name])
        while ls and re.match(r"^\s+[\w, ]+ = ctx\.\w+(, ctx\.\w+)*$", ls[0]):
            ls = ls[1:]
        if ls and ls[-1].strip() == "return NEXT":
            ls = ls[:-1]
        new_body += ls
        docs.append(doc(N[name]))
    a, b = code(old_body), code(new_body)
    d = list(difflib.unified_diff(a, b, f"old {entry}", f"new {lst} steps", n=0, lineterm=""))
    print(f"== {entry}: {len(a)} code lines old, {len(b)} in the steps; not verbatim:")
    print("\n".join(d) if d else "(none)")
    have = set(comments(new_body)) | {w for t in docs for w in [x.strip() for x in t.split("\n")]}
    have |= {re.sub(r"^\d+\w?'?\. ", "", h) for h in have}
    lost = [c for c in comments(old_body) if c not in have and re.sub(r"^\d+\w?'?\. ", "", c) not in have]
    print(f"   old comment lines not in the new code (as comments or docstrings): {lost or 'none'}")
    bad += bool(lost)
sys.exit(1 if bad else 0)

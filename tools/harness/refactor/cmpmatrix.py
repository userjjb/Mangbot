"""Compare two cmdmatrix.py dumps (old tree, new tree): python3 cmpmatrix.py OLD.json NEW.json [MAX]
Prints the cases (context | role | command args) whose record differs, field by field (at most MAX, default 40),
and a count per command; exit 1 if any differ or the case sets differ."""
import collections
import json
import sys

a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
most = int(sys.argv[3]) if len(sys.argv) > 3 else 40
only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
diff = []
for k in sorted(set(a) & set(b)):
    if a[k] != b[k]:
        fields = sorted(f for f in set(a[k]) | set(b[k]) if a[k].get(f) != b[k].get(f))
        diff.append((k, fields))
by_cmd = collections.Counter(k.split(" | ")[2].split(" ")[0] for k, _ in diff)
print(f"{len(set(a) & set(b))} cases in both; only in old {len(only_a)}, only in new {len(only_b)}; "
      f"{len(diff)} differ")
for k in only_a[:10]:
    print("  only old:", k)
for k in only_b[:10]:
    print("  only new:", k)
if diff:
    print("differing cases per command:", dict(by_cmd))
for k, fields in diff[:most]:
    print(f"== {k}")
    for f in fields:
        x, y = a[k].get(f), b[k].get(f)
        if isinstance(x, dict) and isinstance(y, dict):
            for kk in sorted(set(x) | set(y)):
                if x.get(kk) != y.get(kk):
                    print(f"   {f}.{kk}: {str(x.get(kk))[:200]!r}\n   {' ' * len(f + kk)}  -> {str(y.get(kk))[:200]!r}")
        else:
            print(f"   {f}: {str(x)[:300]!r}\n   {' ' * len(f)} -> {str(y)[:300]!r}")
sys.exit(1 if diff or only_a or only_b else 0)

"""Per state of an equiv.py dump: the actions (act records' why) and notices. python3 summ.py EQ.json [COV.json]"""
import json
import sys
from collections import Counter
r = json.load(open(sys.argv[1]))
cov = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
for name, rec in r.items():
    acts, notes = Counter(), Counter()
    for d in rec["decisions"]:
        j = json.loads(d)
        if j.get("kind") == "act":
            acts[(j.get("why") or "")[:70]] += 1
        elif j.get("kind") == "attention":
            notes[j.get("what")] += 1
    c = cov.get(name, {})
    print(f"== {name}: lines reflexes {len(c.get('reflexes', []))} escape {len(c.get('escape', []))}")
    for k, v in acts.most_common(8):
        print(f"   act x{v}: {k}")
    print("   notices:", dict(notes))

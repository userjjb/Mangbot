#!/usr/bin/env python3
"""Flavoured item kinds (potions, scrolls, staffs, wands, rods, rings, amulets) from object.txt,
with what a shop pays for one unknown vs known, for a CHR-4 Half-Orc (the shops memo's owner %).

Unknown (unaware) value = object_value_base() per tval (object2.c:1075-1112): potion/scroll 20,
staff 70, wand 50, rod 90, ring/amulet 45. Aware/known value = the kind's cost (W: line); wands
and staffs also get +cost/20 per charge when the charges are known (object2.c:1253-1257) - not
included here. Sell price = (value x S + 50)//100, S = owner sell % (shops memo §1.5).
Writes kinds.csv next to this script."""
import csv, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/projectnb/jbrcs/mangband/github/lib/edit/object.txt"
TV = {75: "potion", 70: "scroll", 55: "staff", 65: "wand", 66: "rod", 45: "ring", 40: "amulet"}
UNAWARE = {"potion": 20, "scroll": 20, "staff": 70, "wand": 50, "rod": 90, "ring": 45, "amulet": 45}
# owner sell % ranges of the stores that buy each tval (Alchemist 39-45, Temple 41-46, Magic 30-45)
SELL = {"potion": (39, 46), "scroll": (39, 46), "staff": (30, 45), "wand": (30, 45),
        "rod": (30, 45), "ring": (30, 45), "amulet": (30, 45)}
ID_SCROLL_BUY = (78, 81)       # Identify, cost 50, Alchemist buy 155-161%

def sell(v, s): return (v * s + 50) // 100

rows, cur = [], None
for line in open(SRC, encoding="latin-1"):
    line = line.rstrip("\n")
    if line.startswith("N:"):
        _, k, name = line.split(":", 2)
        cur = dict(k_idx=int(k), name=name.replace("&", "").replace("~", "").strip(), flags="", alloc="")
        rows.append(cur)
    elif cur is None:
        continue
    elif line.startswith("I:"):
        tv, sv, pv = line[2:].split(":")
        cur.update(tval=int(tv), sval=int(sv), pval=pv)
    elif line.startswith("W:"):
        lv, _, wt, cost = line[2:].split(":")
        cur.update(level=int(lv), cost=int(cost))
    elif line.startswith("A:"):
        cur["alloc"] = line[2:]
    elif line.startswith("F:"):
        cur["flags"] = (cur["flags"] + " | " if cur["flags"] else "") + line[2:].strip()

out = []
for r in rows:
    kind = TV.get(r.get("tval"))
    if not kind or r["name"].startswith("<"):
        continue
    depths = [int(a.split("/")[0]) for a in r["alloc"].split(":") if a]
    lo, hi = SELL[kind]
    u = UNAWARE[kind]
    gain_lo, gain_hi = sell(r["cost"], lo) - sell(u, lo), sell(r["cost"], hi) - sell(u, hi)
    out.append(dict(kind=kind, k_idx=r["k_idx"], sval=r["sval"], name=r["name"], level=r["level"],
                    alloc=r["alloc"], min_depth_ft=(min(depths) * 50 if depths else ""),
                    cost=r["cost"], flags=r["flags"],
                    sell_unknown=f"{sell(u, lo)}-{sell(u, hi)}",
                    sell_known=f"{sell(r['cost'], lo)}-{sell(r['cost'], hi)}",
                    id_gain=f"{gain_lo}-{gain_hi}",
                    id_scroll_pays=("yes" if gain_lo > ID_SCROLL_BUY[1] else
                                    "no" if gain_hi < ID_SCROLL_BUY[0] else "maybe")))
out.sort(key=lambda d: (d["kind"], d["level"]))
with open(os.path.join(HERE, "kinds.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]))
    w.writeheader(); w.writerows(out)
print(len(out), "kinds;", {k: sum(1 for o in out if o["kind"] == k) for k in TV.values()})

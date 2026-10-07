#!/usr/bin/env python3
"""Exact kind probabilities from get_obj_num() (object2.c:646-770) at each object level, for the
flavoured tvals, and the expected sale value of one unknown item unknown vs aware.

get_obj_num(L): with prob 1/20 (L>0) L := 1 + L*128 // randint1(128) (MAX_DEPTH 128); table entries
are object.txt A: pairs (locale, 100//rarity) with locale <= L; pick one by weight; then with
prob 50% keep the better of 2 picks, 10% the best of 3 ("better" = higher locale; on a tie the later
pick wins, so within the top locale the pick is weight-proportional). The object level of a floor
item is the dungeon level; monster drops use other levels (not modelled).

usage: dist.py [LEVEL ...]   (default 2 5 10 15 20 25 30). Writes dist.csv (level,tval,kind,p_in_tval).
"""
import collections, csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/projectnb/jbrcs/mangband/github/lib/edit/object.txt"
FLAV = {75: "potion", 70: "scroll", 55: "staff", 65: "wand", 66: "rod", 45: "ring", 40: "amulet"}

entries, kinds, cur = [], {}, None          # entries: (locale, prob, k_idx)
for line in open(SRC, encoding="latin-1"):
    if line.startswith("N:"):
        _, k, name = line.rstrip("\n").split(":", 2)
        cur = int(k); kinds[cur] = {"name": name.replace("&", "").replace("~", "").strip()}
    elif cur is not None and line.startswith("I:"):
        kinds[cur]["tval"] = int(line.split(":")[1])
    elif cur is not None and line.startswith("A:"):
        for pair in line[2:].strip().split(":"):
            loc, rar = map(int, pair.split("/"))
            if rar:
                entries.append((loc, 100 // rar, cur))

def pick_dist(L):
    """P(k_idx) from one get_obj_num call at a fixed (already boosted) level L."""
    t = [e for e in entries if e[0] <= L]
    tot = sum(p for _, p, _ in t)
    if not tot:
        return {}
    byloc = collections.defaultdict(float)
    for loc, p, _ in t:
        byloc[loc] += p / tot
    F, acc = {}, 0.0                       # F[loc] = P(one pick has locale <= loc)
    for loc in sorted(byloc):
        acc += byloc[loc]; F[loc] = acc
    locs = sorted(byloc)
    prev = {l: (F[locs[i - 1]] if i else 0.0) for i, l in enumerate(locs)}
    out = collections.defaultdict(float)
    for loc, p, k in t:
        q = p / tot
        share = q / byloc[loc]
        top = sum(w * (F[loc] ** n - prev[loc] ** n) for n, w in ((1, .4), (2, .5), (3, .1)))
        out[k] += share * top
    return out

def level_dist(L):
    """With the 1-in-20 boost."""
    res = collections.defaultdict(float)
    for k, p in pick_dist(L).items():
        res[k] += p * (19 / 20 if L > 0 else 1)
    if L > 0:
        for r in range(1, 129):
            for k, p in pick_dist(1 + L * 128 // r).items():
                res[k] += p / 20 / 128
    return res

if __name__ == "__main__":
    levels = [int(a) for a in sys.argv[1:]] or [2, 5, 10, 15, 20, 25, 30]
    rows = []
    for L in levels:
        d = level_dist(L)
        for tv, tn in FLAV.items():
            ks = {k: p for k, p in d.items() if kinds[k].get("tval") == tv}
            s = sum(ks.values())
            for k, p in sorted(ks.items(), key=lambda x: -x[1]):
                rows.append(dict(level=L, tval=tn, k_idx=k, kind=kinds[k]["name"],
                                 p_in_tval=round(p / s, 5), p_any_object=round(p, 6)))
    with open(os.path.join(HERE, "dist.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(len(rows), "rows ->", os.path.join(HERE, "dist.csv"))

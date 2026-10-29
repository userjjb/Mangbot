#!/usr/bin/env python3
"""Check the server's wake rule against the Pilot's looks (decisions.jsonl kind "looks", from m48).

Rule (melee2.c:2498-2540, 3484-3501; cmd1.c:2936; dungeon.c:1322; monster2.c:1981): while we act, our noise is capped at 2^30
(stealth ~1: each action adds 29, each block removes 2), so every turn a sleeping monster gets (within its activation range)
removes 100/distance sleep points (1 at 50+ squares). Initial sleep = 2*alertness + randint1(10*alertness).
Pairs: a monster seen asleep at (y,x), and the next look that reports a monster of that name at the same square (asleep or not).
For each pair: blocks elapsed (0.625 s a block; 0.2x in the HP bubble), its turns (speed), our distance; predicted P(still asleep)
from the initial-sleep distribution (an upper bound: some sleep was already lost before the first look).
usage: calib_wake.py"""
import collections, csv, json, os, re, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options_sim as S  # noqa: E402

DEC = "/projectnb/jbrcs/mangband/runs/pilot/dive04/decisions.jsonl"
ALERT = {r["name"]: int(r["alertness"]) for r in csv.DictReader(open(S.MON))}
recs = [json.loads(l) for l in open(DEC) if '"kind": "looks"' in l]
recs.sort(key=lambda r: r["t"])
NAME = re.compile(r"^(?:The |An? )?(.+?) \((.*?)\)")


def parse(r):
    out = {}
    for y, x, txt in r["sample"]:
        m = NAME.match(txt)
        if m and m.group(1) in S.RACES:
            out[(m.group(1), y, x)] = "asleep" in m.group(2)
    return out


def p_still_asleep(name, removed):
    v = ALERT.get(name, 0)
    if v <= 0:
        return 0.0
    lo, n = 2 * v, 10 * v                      # csleep = 2v + U{1..10v}
    return min(1.0, max(0.0, (lo + n - removed) / n)) if removed > lo else 1.0


pairs = []
for i, a in enumerate(recs):
    A = parse(a)
    for (name, y, x), asleep in A.items():
        if not asleep:
            continue
        for b in recs[i + 1:i + 6]:
            if b["t"] - a["t"] > 60:
                break
            B = parse(b)
            if (name, y, x) in B:
                dt = b["t"] - a["t"]
                hp = a["hp"]
                factor = 0.2 if hp and hp[1] and hp[0] <= 0.5 * hp[1] else 1.0
                blocks = dt * factor / 0.625
                sx = S.ENERGY.get(int(S.RACES[name]["speed"]), 1000) / 1000
                d = max(1, S.adist(y - a["pos"][0], x - a["pos"][1]))
                per = 100 // d if d < 50 else 1
                removed = blocks * sx * per
                pairs.append((name, d, blocks, removed, B[(name, y, x)], p_still_asleep(name, removed)))
                break
print(len(recs), "looks;", len(pairs), "asleep -> re-seen pairs")
by = collections.defaultdict(lambda: [0, 0, 0.0])
for name, d, blocks, removed, still, pred in pairs:
    band = "<=5" if d <= 5 else "6-10" if d <= 10 else "11-20" if d <= 20 else ">20"
    g = by[band]; g[0] += 1; g[1] += still; g[2] += pred
for band in ("<=5", "6-10", "11-20", ">20"):
    if band in by:
        n, s, p = by[band]
        print(f"  distance {band:6s} n={n:4d}  still asleep observed {s / n:.2f}  predicted <= {p / n:.2f}")
print("median blocks between looks", round(statistics.median(p[2] for p in pairs), 1) if pairs else None)

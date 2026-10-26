#!/usr/bin/env python3
"""Depth-native fight scenarios for options_sim / the gear evaluator: what a fresh level at depth D throws at us.

One scenario = an encounter as options_sim.rollout takes it: team [(race name, distance)], arrivals [(block, name, dist)].
  race       get_mon_num at D (monster2.c; the same pick as depth_value.py: table entries with level <= D, weight 100/rarity,
             60% best of 2 and 10% best of 3 by level, two 1-in-50 NASTY_MON boosts of min(D/4+2, 5) levels; town
             races excluded); uniques in `skip` (e.g. the ones Dive04 has killed) are re-drawn
  group      FRIENDS: randint1(13) +/- randint1(min(|D - level|, 12)) (more in depth, fewer out of depth), 1..32
             (place_monster_group); everything else alone. ESCORT/ESCORTS are not modelled (noted per scenario)
  placement  the first member adjacent, the rest of the group 1-4 squares away; with P_SECOND a second, independent
             encounter (another draw) arrives 3-12 blocks later at 4-8 squares (a fight drawing a wanderer in)
  awake      left to options_sim (p_awake on the player dict; the gear evaluator uses 1.0 for "they came at us")
Auto_scum is not modelled: Dive04's levels at 500 ft+ are rerolled until rating > 20 or special (memo 2026-10-24-structures),
so real levels hold more out-of-depth monsters than these draws; use a higher `boost` (extra levels) to approximate that.

usage: scenarios.py DEPTH_FT [--n 10] [--seed 1] [--boost 0]   (prints the scenarios)
       import scenarios; scenarios.make(depth_ft, n, seed, skip=set(), boost=0) -> [dict(team=..., arrivals=..., notes=...)]"""
import argparse, csv, functools, os, random, sys

sys.path.insert(0, "/projectnb/jbrcs/mangband/Advisor/data/rulebook")
from objgen import _pick  # noqa: E402

MON = "/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"
RACES = {r["idx"]: r for r in csv.DictReader(open(MON))}
ENTRIES = [(int(r["level"]), 100 // max(1, int(r["rarity"])), r["idx"]) for r in RACES.values()
           if int(r["level"]) > 0 and int(r.get("rarity") or 0) > 0]
GROUP_MAX = 32
P_SECOND = 0.3


@functools.lru_cache(maxsize=None)
def mon_dist(L):
    out = {}
    for b1, p1 in ((0, 49 / 50), (1, 1 / 50)):
        for b2, p2 in ((0, 49 / 50), (1, 1 / 50)):
            lv = L
            if b1: lv += min(lv // 4 + 2, 5)
            if b2: lv += min(lv // 4 + 2, 5)
            for k, p in _pick(lv, ENTRIES).items():
                out[k] = out.get(k, 0.0) + p * p1 * p2
    ks = sorted(out)
    return tuple(ks), tuple(out[k] for k in ks)


def draw(rng, D, skip):
    ks, ws = mon_dist(D)
    while True:
        r = RACES[rng.choices(ks, ws)[0]]
        if r["name"] not in skip:
            return r


def group_size(rng, r, D):
    if "FRIENDS" not in r["flags"].split("|"):
        return 1
    lv, n = int(r["level"]), rng.randint(1, 13)
    if lv > D:
        n -= rng.randint(1, min(lv - D, 12))
    elif lv < D:
        n += rng.randint(1, min(D - lv, 12))
    return max(1, min(GROUP_MAX, n))


def make(depth_ft, n=10, seed=1, skip=frozenset(), boost=0):
    D = depth_ft // 50 + boost
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        r = draw(rng, D, skip)
        k = group_size(rng, r, D)
        team = [(r["name"], 1)] + [(r["name"], rng.randint(1, 4)) for _ in range(k - 1)]
        notes = [f"{r['name']} L{r['level']} x{k}"]
        if {"ESCORT", "ESCORTS"} & set(r["flags"].split("|")):
            notes.append("escort not modelled")
        arrivals = []
        if rng.random() < P_SECOND:
            r2 = draw(rng, D, skip)
            k2 = group_size(rng, r2, D)
            t = rng.randint(3, 12)
            arrivals = [(t, r2["name"], rng.randint(4, 8)) for _ in range(k2)]
            notes.append(f"+ at block {t}: {r2['name']} L{r2['level']} x{k2}")
        out.append(dict(team=team, arrivals=arrivals, notes="; ".join(notes)))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("depth_ft", type=int)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--boost", type=int, default=0)
    o = ap.parse_args()
    for s in make(o.depth_ft, o.n, o.seed, boost=o.boost):
        print(s["notes"])

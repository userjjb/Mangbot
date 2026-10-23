#!/usr/bin/env python3
"""Rulebook table T9: what a dungeon level offers a character, by depth: XP per kill, HP lost per kill, the share of monsters a
hunt check refuses, and the chance a level holds something the character must avoid.

Model:
  monster mix   get_mon_num (monster2.c): table entries (level, 100/rarity) with level <= L, level-0 (town) races excluded at
                L > 0; 60% best of 2 and 10% best of 3 picks by level (same as get_obj_num; objgen._pick); two 1-in-50 boosts
                (NASTY_MON) each of min(L/4+2, 5) levels
  groups        FRIENDS races come in groups of randint1(13) + randint1(Depth - level) (capped 12; fewer if out of depth),
                at most GROUP_MAX (place_monster_group); counted per monster, so a group adds that many kills
  XP per kill   mexp x level / clvl (monster1.c:1055)
  HP per kill   fight_sim duel mean at the character's profile (fight_dive04.csv by default); levels > 40 not tabulated
  refused       AVOID/LEAVE rating, or duel p90 > 60% of HP (the Pilot's hunt check)
Not modelled: monsters generated over time, uniques already killed, pits/nests/vaults, escorts, the Pilot's running speed.

usage: depth_value.py [CLVL]   (default 22; HP and kill cost from fight_dive04.csv). Writes depth_value.csv."""
import csv, collections, os, sys
from objgen import _pick

HERE = os.path.dirname(os.path.abspath(__file__))
MON = "/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"
CLVL = int(sys.argv[1]) if len(sys.argv) > 1 else 22
GROUP_MAX = 32
PER_LEVEL = 18          # monsters placed at generation, roughly (MIN_M_ALLOC_LEVEL 14 + randint1(8))

races = {r["idx"]: r for r in csv.DictReader(open(MON))}
fight = {r["idx"]: r for r in csv.DictReader(open(os.path.join(HERE, "fight_dive04.csv")))}
entries = [(int(r["level"]), 100 // max(1, int(r["rarity"])), r["idx"]) for r in races.values()
           if int(r["level"]) > 0 and int(r.get("rarity") or 0) > 0]


def mon_dist(L):
    out = collections.defaultdict(float)
    for b1, p1 in ((0, 49 / 50), (1, 1 / 50)):
        for b2, p2 in ((0, 49 / 50), (1, 1 / 50)):
            lv = L
            if b1: lv += min(lv // 4 + 2, 5)
            if b2: lv += min(lv // 4 + 2, 5)
            for k, p in _pick(lv, entries).items():
                out[k] += p * p1 * p2
    return out


def group(r, D):
    if "FRIENDS" not in r["flags"]:
        return 1.0
    lv = int(r["level"]); tot = 0.0
    for t in range(1, 14):
        if lv > D:
            ex = [-e for e in range(1, min(lv - D, 12) + 1)]
        elif lv < D:
            ex = list(range(1, min(D - lv, 12) + 1))
        else:
            ex = [0]
        tot += sum(min(GROUP_MAX, max(1, t + e)) for e in ex) / len(ex) / 13
    return tot


rows = []
for D in range(1, 31):
    d = mon_dist(D)
    w = {k: p * group(races[k], D) for k, p in d.items()}
    W = sum(w.values())
    xp = hp = refused = avoid = known = 0.0
    severe = 0.0
    for k, q in w.items():
        r = races[k]; f = fight.get(k); q /= W
        xp += q * int(r["exp"]) * int(r["level"]) / CLVL
        if f:
            known += q
            hp += q * float(f["loss_mean"])
            ref = f["response"] in ("AVOID", "LEAVE") or int(f["p90_pct_hp"]) > 60
            refused += q * ref
            avoid += q * (f["response"] in ("AVOID", "LEAVE"))
    p_sev = sum(p for k, p in d.items() if k in fight and (fight[k]["response"] == "LEAVE" or int(fight[k]["p90_pct_hp"]) > 100))
    fought = [(k, q) for k, q in w.items() if k in fight and fight[k]["response"] not in ("AVOID", "LEAVE")
              and int(fight[k]["p90_pct_hp"]) <= 60]
    fq = sum(q for _, q in fought)
    xp_f = sum(q * int(races[k]["exp"]) * int(races[k]["level"]) / CLVL for k, q in fought) / fq if fq else 0
    hp_f = sum(q * float(fight[k]["loss_mean"]) for k, q in fought) / fq if fq else 0
    rows.append(dict(depth=D, depth_ft=50 * D, xp_per_kill=round(xp, 1), hp_lost_per_kill=round(hp / known, 1) if known else "",
                     share_refused=round(refused / known, 3) if known else "", share_avoid_leave=round(avoid / known, 3) if known else "",
                     xp_per_allowed_kill=round(xp_f, 1), hp_per_allowed_kill=round(hp_f, 1),
                     xp_per_hp_allowed=round(xp_f / hp_f, 2) if hp_f else "",
                     p_level_has_severe=round(1 - (1 - p_sev) ** PER_LEVEL, 3)))
with open(os.path.join(HERE, "depth_value.csv"), "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
for r in rows:
    print(r)

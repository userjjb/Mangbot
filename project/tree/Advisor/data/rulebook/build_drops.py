#!/usr/bin/env python3
"""Rulebook table T8: what a kill drops (and what a floor object is worth), from monster_death and place_object.

Mechanics (xtra2.c:1980-2090 monster_death, object2.c place_object/place_gold/apply_magic; model in objgen.py):
  drops per kill   DROP_60 (60%) + DROP_90 (90%) + DROP_1D2 + DROP_2D2 + DROP_3D2 + DROP_4D2 (dice); each drop needs a clean
                   floor square within 2 (else lost, see data/drops/drop_sim.py; not modelled here)
  gold or item     each drop is gold with 50%, unless ONLY_ITEM (never gold) or ONLY_GOLD (always gold)
  object level     L = (dungeon level + monster level) // 2 (floor items: L = dungeon level)
  item             DROP_GOOD: 1/10 special-artifact gate, kind from get_obj_num(L+10) among "good" kinds (weapons/armour
                   without a penalty, ammo, high books, Ring of Speed), power >= 1; DROP_GREAT: power 2 and 4 artifact
                   rolls. Otherwise 1/1000 special gate, kind from get_obj_num(L), power from apply_magic.
                   Ammo and spikes come in stacks of 6d7 (mean 24).
  gold pile        type i = (randint1(L+2)+2)//2 - 1, + randint1(L+1) with 1/20, max 17 (creeping coins: their metal);
                   amount = base + 8*randint1(base) + randint1(8), base = the gold kind's cost (object.txt 480-497)
Values are object_value_real = what a shop's price is based on ONCE THE ITEM IS IDENTIFIED (a shop pays value x pay% and at
most the owner's purse, 25,000-150,000). An unidentified item is priced on object_value_base (store.c:192, object2.c:1362):
its kind's cost, 0 if it felt cursed/broken; unaware flavours a fixed 20-90 -> e_value_unid assumes aware kinds.
m_bonus here uses a rounded Gaussian, not the server's table randnor: values run 0-4% high (dispatch D1). Artifact values are their artifact.txt cost and are kept OUT of e_value (rare and huge); see p_artifact.
Assumes no artifact has been found yet on the server (found ones are never made again).

Writes
  drop_object_by_level.csv  one generated object at object level L (0-127), for mode normal / good / great, with
                            dungeon depth = L for the artifact rolls: e_value, e_value_cap (each item capped at 25,000),
                            e_value_unid (what it sells for unidentified),
                            p_worthless, p_excellent (a non-cursed ego), p_irreplaceable (ego with a resist/FA/SI/...),
                            p_artifact (incl. specials), e_artifact_cost, e_gold_pile, and the share of e_value by class
  drops.csv                 per monster race at its native depth (dungeon level = monster level): drop flags, e_drops,
                            e_gold, e_items, e_item_value, e_item_value_cap, e_item_value_unid, p_excellent_any, p_artifact_any, e_total_cap
  drops_by_depth.csv        the same per monster (with any drop) at dungeon levels 1,5,10,...,100

usage: build_drops.py [N]   (Monte Carlo samples per gear/jewellery cell, default 400)"""
import bisect, collections, csv, os, random, sys
from objgen import (kinds, GEAR, AMMO, pick_dist, power_probs, gear_value, art_chance, special_chance, m_bonus)
import build_jewellery as J

HERE = os.path.dirname(os.path.abspath(__file__))
EDIT = "/projectnb/jbrcs/mangband/github/lib/edit"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
CAP = 25000
LGRID = [0, 5, 10, 15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 100, 127]
STACK = {5: 24.0, 16: 24.0, 17: 24.0, 18: 24.0}          # TV_SPIKE and ammo: damroll(6,7)
JEWEL = {40, 45}
CLASS = lambda tv: ("weapon" if tv in (19, 20, 21, 22, 23) else "ammo" if tv in AMMO else "armour" if tv in GEAR
                    else "jewellery" if tv in JEWEL else "device" if tv in (55, 65, 66) else
                    "potion_scroll" if tv in (70, 75) else "other")
random.seed(20261025)

# --- flavoured non-jewellery values (wand/staff charges) from kinds_by_level.csv; everything else: kind cost
FLAVVAL = {}
for r in csv.DictReader(open(os.path.join(HERE, "kinds_by_level.csv"))):
    if int(r["tval_num"]) not in JEWEL:
        FLAVVAL[int(r["k_idx"])] = float(r["value"])


# --- per-kind cells: (E value, E capped, P worthless, P excellent, P irreplaceable) at (k, L, power)
def stats(samples):
    n = len(samples)
    return (sum(s[0] for s in samples) / n, sum(min(s[0], CAP) for s in samples) / n,
            sum(s[0] <= 0 for s in samples) / n, sum(s[1] for s in samples) / n, sum(s[2] for s in samples) / n)


JK = {(k["tval"], k["sval"]): k for k in J.kinds}


def jewel_sample(k, L, power):
    jk = JK.get((k["tval"], k["sval"]))
    key = (k["tval"], jk["name"]) if jk else None
    if key not in J.RULES:
        v = 0 if (k["cost"] == 0 or "LIGHT_CURSE" in k["F"]) else k["cost"]
        return v, False, False
    cursable, gen = J.RULES[key]
    if key == (45, "Speed"): gen = J.ring_speed
    p, a, h, d = gen(L)
    if cursable and power < 0:
        return 0, False, False
    v = k["cost"] + 100 * (a + h + d)
    v += p * (sum(c for f, c in J.FLAGCOST.items() if f in jk["F"]) + ((50000 if k["tval"] == 45 else 25000)
                                                                       if "SPEED" in jk["F"] else 0))
    return v, False, False


CELL = {}


def cell(k, L, power):
    """Stats for kind k at grid level L and power."""
    key = (k["k_idx"], L, power)
    if key not in CELL:
        tv = k["tval"]
        if tv in GEAR:
            n = N if power > 0 else max(50, N // 4)
            ss = []
            for _ in range(n):
                v, _, _, _, e, irr = gear_value(k, power, L)
                ss.append((v, bool(e) and v > 0, irr))
            CELL[key] = stats(ss)
        elif tv in JEWEL:
            CELL[key] = stats([jewel_sample(k, L, power) for _ in range(N)])
        else:
            v = FLAVVAL.get(k["k_idx"], k["cost"])
            CELL[key] = (v, min(v, CAP), float(v <= 0), 0.0, 0.0)
    return CELL[key]


def cell_at(k, L, power):
    """Linear interpolation between grid levels (gear and jewellery depend on L through m_bonus)."""
    if k["tval"] not in GEAR and k["tval"] not in JEWEL:
        return cell(k, 0, 0)
    L = min(L, 127)
    i = bisect.bisect_right(LGRID, L) - 1
    if LGRID[i] == L or i == len(LGRID) - 1:
        return cell(k, LGRID[i], power)
    a, b = LGRID[i], LGRID[i + 1]; t = (L - a) / (b - a)
    ca, cb = cell(k, a, power), cell(k, b, power)
    return tuple(x + t * (y - x) for x, y in zip(ca, cb))


# --- one object at object level L, dungeon depth D, mode
OBJ = {}
FIELDS = ["e_value", "e_value_cap", "e_value_unid", "p_worthless", "p_excellent", "p_irreplaceable", "p_artifact", "e_artifact_cost"]


def object_expect(L, D, mode):
    key = (L, D, mode)
    if key in OBJ:
        return OBJ[key]
    good, great = mode in ("good", "great"), mode == "great"
    ps, es = special_chance(D, L, good)
    dist = pick_dist(L + 10 if good else L, good)
    tot = sum(dist.values())
    acc = collections.defaultdict(float)
    for kid, p in dist.items():
        k = kinds[kid]; p /= tot; tv = k["tval"]
        pw = power_probs(L, good, great)
        if tv in JEWEL and not good and not great:           # power 0 jewellery turns -1 half the time
            pw = dict(pw); z = pw.pop(0, 0); pw[0] = z / 2; pw[-1] = pw.get(-1, 0) + z / 2
        stack = STACK.get(tv, 1.0)
        for power, q in pw.items():
            w = p * q
            pa, ea = art_chance(k, D, 4 if great else 1) if power >= 2 else (0.0, 0.0)
            v, vc, pz, pe, pi = cell_at(k, L, power)
            wn = w * (1 - pa)
            acc["e_value"] += wn * v * stack
            acc["e_value_cap"] += wn * min(v * stack, CAP) if stack > 1 else wn * vc
            acc["p_worthless"] += wn * pz; acc["p_excellent"] += wn * pe; acc["p_irreplaceable"] += wn * pi
            acc["p_artifact"] += w * pa; acc["e_artifact_cost"] += w * pa * ea
            acc["v_" + CLASS(tv)] += wn * v * stack
            # sold unidentified: object_value -> object_value_base = kind cost (aware kinds; store.c:192, object2.c:1362-1395);
            # gear that feels cursed/broken (heavy pseudo-ID) is 0; jewellery is never felt, so it keeps the kind cost
            acc["e_value_unid"] += w * (0 if (tv in GEAR and power < 0) else k["cost"]) * (stack if pa == 0 else 1)
    out = {f: (1 - ps) * acc[f] for f in acc}
    out["p_artifact"] = out.get("p_artifact", 0) + ps
    out["e_artifact_cost"] = out.get("e_artifact_cost", 0) + ps * es
    OBJ[key] = out
    return out


# --- gold
GOLD = [kinds[480 + i]["cost"] for i in range(18)]


def gold_pile(L, coin=0):
    """E[gold in one pile] (place_gold, object2.c:3860-3912)."""
    if coin:
        return 5 * GOLD[min(coin, 17)] + 8.5
    eb = 0.0
    for r in range(1, L + 3):                                # randint1(L+2)
        i0 = (r + 2) // 2 - 1
        boosted = sum(GOLD[min(i0 + s, 17)] for s in range(1, L + 2)) / (L + 1)
        eb += (19 / 20 * GOLD[min(i0, 17)] + boosted / 20) / (L + 2)
    return 5 * eb + 8.5                                      # base + 8*randint1(base) + randint1(8)


# --- monsters
mons, cur = [], None
for line in open(f"{EDIT}/monster.txt", encoding="latin-1"):
    line = line.rstrip("\n")
    if line.startswith("N:"):
        p = line.split(":", 2); cur = {"idx": int(p[1]), "name": p[2].strip(), "F": set()}; mons.append(cur)
    elif cur is None:
        continue
    elif line.startswith("G:"):
        cur["sym"] = line.split(":")[1]
    elif line.startswith("W:"):
        cur["level"] = int(line.split(":")[1])
    elif line.startswith("F:"):
        cur["F"] |= {f.strip() for f in line[2:].split("|") if f.strip()}
DICE = {"DROP_1D2": (1, 2), "DROP_2D2": (2, 2), "DROP_3D2": (3, 2), "DROP_4D2": (4, 2)}


def count_dist(F):
    d = {0: 1.0}
    def add(dd):
        nonlocal d
        nd = collections.defaultdict(float)
        for a, p in d.items():
            for b, q in dd.items():
                nd[a + b] += p * q
        d = nd
    if "DROP_60" in F: add({0: .4, 1: .6})
    if "DROP_90" in F: add({0: .1, 1: .9})
    for f, (n, s) in DICE.items():
        if f in F:
            for _ in range(n): add({v: 1 / s for v in range(1, s + 1)})
    return d


def coin_type(m):
    if m.get("sym") != "$":
        return 0
    for word, c in (("copper", 2), ("silver", 5), ("gold", 10), ("mithril", 16), ("adamantite", 17)):
        if f" {word} " in m["name"] or f"{word.capitalize()} " in m["name"]:
            return c
    return 0


def monster_row(m, D):
    F = m["F"]; cd = count_dist(F)
    n = sum(a * p for a, p in cd.items())
    pg = 0.0 if "ONLY_ITEM" in F else 1.0 if "ONLY_GOLD" in F else 0.5
    L = (D + m["level"]) // 2
    mode = "great" if "DROP_GREAT" in F else "good" if "DROP_GOOD" in F else "normal"
    o = object_expect(L, D, mode)
    ni = n * (1 - pg)
    eg = n * pg * gold_pile(L, coin_type(m))
    p_no = lambda q: sum(p * (1 - (1 - pg) * q) ** a for a, p in cd.items())
    flags = "|".join(sorted(f for f in F if f.startswith("DROP_") or f in ("ONLY_ITEM", "ONLY_GOLD")))
    return dict(idx=m["idx"], name=m["name"], level=m["level"], depth=D, unique=int("UNIQUE" in F), drop_flags=flags,
                object_level=L, mode=mode, e_drops=round(n, 2), e_gold=round(eg), e_items=round(ni, 2),
                e_item_value=round(ni * o.get("e_value", 0)), e_item_value_cap=round(ni * o.get("e_value_cap", 0)),
                e_item_value_unid=round(ni * o.get("e_value_unid", 0)),
                p_excellent_any=round(1 - p_no(o.get("p_excellent", 0)), 4),
                p_artifact_any=round(1 - p_no(o.get("p_artifact", 0)), 5),
                e_total_cap=round(eg + ni * o.get("e_value_cap", 0)))


def write(name, rows):
    with open(os.path.join(HERE, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(len(rows), "rows ->", name)


if __name__ == "__main__":
    rows = []
    for L in range(0, 128):
        for mode in ("normal", "good", "great"):
            o = object_expect(L, L, mode)
            r = dict(level=L, mode=mode, e_gold_pile=round(gold_pile(L), 1))
            r.update({f: round(o.get(f, 0), 5 if f.startswith("p_") else 1) for f in FIELDS})
            ev = o.get("e_value", 0) or 1
            for c in ("weapon", "ammo", "armour", "jewellery", "device", "potion_scroll", "other"):
                r["share_" + c] = round(o.get("v_" + c, 0) / ev, 3)
            rows.append(r)
    write("drop_object_by_level.csv", rows)
    native = [monster_row(m, m["level"]) for m in mons if "level" in m]
    write("drops.csv", native)
    byd = [monster_row(m, D) for m in mons if "level" in m and count_dist(m["F"]) != {0: 1.0}
           for D in [1] + list(range(5, 101, 5))]
    write("drops_by_depth.csv", byd)

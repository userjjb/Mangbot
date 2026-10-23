#!/usr/bin/env python3
"""Shared object-generation model (MAngband server object2.c), used by build_feelings.py and build_drops.py.

  kinds        every object.txt kind: k_idx, name, tval, sval, pval, level, cost, to_h/to_d/to_a, dd/ds, flags, alloc
  egos, arts   ego_item.txt (via the K1 CSV) and artifact.txt
  pick_dist    exact get_obj_num() kind probabilities at an object level, optionally under kind_is_good (object2.c:646-770,
               3466-3528): 1-in-20 level boost to 1+L*128//randint1(128); best of 1/2/3 picks with 40/50/10%
  power_probs  apply_magic power roll (object2.c:3187-3235): f1=min(L+10,75), f2=min(f1//2,20); good forces >=1, great 2
  gear_value   one weapon/ammo/bow/digger/armour item at a given power (a_m_aux_1/2 + ego + object_value_real):
               to-hit/dam/AC from randint1(5)+m_bonus(5,L) (+m_bonus(10,L) at |power| 2), extra damage dice at power 2
               (hafted/polearm/sword/ammo), ego by weight 1/rarity among eligible egos (curse egos at power -2),
               value = kind cost + ego cost + 100 x (to_h+to_d+to_a) (ammo: 5 x (to_h+to_d)) INCLUDING the kind's own plusses
               + extra dice x ds x 100 (ammo 5) + pval x flag credits; 0 if cursed/broken ego, negative pval, or negative
               plusses (object2.c:1136-1345)
  art_chance   make_artifact (normal artifacts, a_info 16+; per roll the first artifact of the base kind that passes
               out-of-depth 1/((level-Depth)*2) and rarity 1/rarity) and make_artifact_special (indices 1-15, place_object:
               1/1000 per object, 1/10 for DROP_GOOD; extra 1/((klevel-L)*5) when the base kind is above the object level)
Assumes no artifact exists yet (cur_num = 0). Randarts are off (mangband.cfg)."""
import collections, csv, functools, random, re

EDIT = "/projectnb/jbrcs/mangband/github/lib/edit"
EGOS = "/projectnb/jbrcs/mangband/Advisor/studies/2026-10-23-rulebook/scratch/K1/K1_egos.csv"
TV = {"shot": 16, "arrow": 17, "bolt": 18, "bow": 19, "digging": 20, "hafted": 21, "polearm": 22, "sword": 23,
      "boots": 30, "gloves": 31, "helm": 32, "crown": 33, "shield": 34, "cloak": 35, "softarmor": 36, "hardarmor": 37,
      "dragarmor": 38}
WEAPON = {16, 17, 18, 19, 20, 21, 22, 23}
AMMO = {16, 17, 18}
DICE_UP = {16, 17, 18, 21, 22, 23}          # extra damage dice at power 2 (not bows, not diggers)
ARMOUR = {30, 31, 32, 33, 34, 35, 36, 37, 38}
GEAR = WEAPON | ARMOUR
SV_AMMO_MAGIC = 4
PVAL_COST = {"STR": 200, "INT": 200, "WIS": 200, "DEX": 200, "CON": 200, "CHR": 200, "STEALTH": 100, "SEARCH": 100,
             "INFRA": 50, "TUNNEL": 50, "BLOWS": 2000, "SPEED": 100000}
IRREPL = {"FREE_ACT", "SEE_INVIS", "RES_POIS", "RES_BLIND", "RES_CONF", "HOLD_LIFE", "SPEED", "TELEPATHY", "REGEN",
          "RES_ACID", "RES_ELEC", "RES_FIRE", "RES_COLD", "RES_NETHER", "RES_SOUND", "RES_SHARDS", "RES_NEXUS",
          "RES_CHAOS", "RES_DISEN", "RES_LITE", "RES_DARK"}
CURSES = {"LIGHT_CURSE", "HEAVY_CURSE", "PERMA_CURSE"}

# --- kinds (all of object.txt)
kinds, cur = {}, None
for line in open(f"{EDIT}/object.txt", encoding="latin-1"):
    line = line.rstrip("\n")
    if line.startswith("N:"):
        _, k, name = line.split(":", 2)
        cur = {"k_idx": int(k), "name": name.replace("&", "").replace("~", "").strip(), "A": [], "F": set(),
               "pval": 0, "to_h": 0, "to_d": 0, "to_a": 0, "dd": 0, "ds": 0, "level": 0, "cost": 0}
        kinds[cur["k_idx"]] = cur
    elif cur is None:
        continue
    elif line.startswith("I:"):
        p = line.split(":"); cur.update(tval=int(p[1]), sval=int(p[2]), pval=int(p[3]))
    elif line.startswith("W:"):
        p = line.split(":"); cur.update(level=int(p[1]), cost=int(p[4]))
    elif line.startswith("P:"):
        p = line.split(":"); dd, ds = p[2].split("d")
        cur.update(ac=int(p[1]), dd=int(dd), ds=int(ds), to_h=int(p[3]), to_d=int(p[4]), to_a=int(p[5]))
    elif line.startswith("A:"):
        for pair in line[2:].strip().split(":"):
            loc, rar = map(int, pair.split("/"))
            if rar:
                cur["A"].append((loc, 100 // rar))
    elif line.startswith("F:"):
        cur["F"] |= {f.strip() for f in line[2:].split("|") if f.strip()}
by_tsv = {(k["tval"], k["sval"]): k for k in kinds.values() if "tval" in k}

# --- egos
egos = []
for r in csv.DictReader(open(EGOS)):
    slots = []
    for s in r["tval_slots"].split(";"):
        m = re.match(r"(\w+)\[(\d+)-(\d+)\]", s.strip())
        if m and m.group(1) in TV:
            slots.append((TV[m.group(1)], int(m.group(2)), int(m.group(3))))
    if not slots:
        continue
    fl = set(f for f in r["flags"].split("|") if f)
    egos.append(dict(name=r["name"], slots=slots, level=int(r["level"]), rarity=max(1, int(r["rarity"])),
                     h=int(r["max_h"]), d=int(r["max_d"]), a=int(r["max_a"]), pval=int(r["max_pval"]),
                     cost=int(r["cost"]), flags=fl, curse=bool(fl & CURSES)))

# --- artifacts
arts, cur = [], None
for line in open(f"{EDIT}/artifact.txt", encoding="latin-1"):
    if line.startswith("N:"):
        p = line.rstrip("\n").split(":", 2); cur = {"idx": int(p[1]), "name": p[2].strip()}; arts.append(cur)
    elif cur is not None and line.startswith("I:"):
        p = line.split(":"); cur.update(tval=int(p[1]), sval=int(p[2]))
    elif cur is not None and line.startswith("W:"):
        p = line.split(":"); cur.update(level=int(p[1]), rarity=max(1, int(p[2])), cost=int(p[4]))
specials = sorted([a for a in arts if 1 <= a["idx"] < 16], key=lambda a: a["idx"])
normal_arts = collections.defaultdict(list)
for a in sorted(arts, key=lambda a: a["idx"]):
    if a["idx"] >= 16 and "tval" in a:
        normal_arts[(a["tval"], a["sval"])].append(a)


# --- kind allocation
def kind_is_good(k):
    tv = k.get("tval")
    if tv in ARMOUR:
        return k["to_a"] >= 0
    if tv in (19, 20, 21, 22, 23):
        return k["to_h"] >= 0 and k["to_d"] >= 0
    if tv in AMMO:
        return k["sval"] != SV_AMMO_MAGIC
    if tv in (90, 91):
        return k["sval"] >= 4                  # SV_BOOK_MIN_GOOD
    if tv == 45:
        return k["name"] == "Speed"            # SV_RING_SPEED
    return False


ENTRIES = [(loc, p, k["k_idx"]) for k in kinds.values() for loc, p in k["A"]]
GOOD_ENTRIES = [e for e in ENTRIES if kind_is_good(kinds[e[2]])]


def _pick(L, entries):
    t = [e for e in entries if e[0] <= L]
    tot = sum(p for _, p, _ in t)
    if not tot:
        return {}
    byloc = collections.defaultdict(float)
    for loc, p, _ in t:
        byloc[loc] += p / tot
    F, acc = {}, 0.0
    for loc in sorted(byloc):
        acc += byloc[loc]; F[loc] = acc
    locs = sorted(byloc)
    prev = {l: (F[locs[i - 1]] if i else 0.0) for i, l in enumerate(locs)}
    out = collections.defaultdict(float)
    for loc, p, k in t:
        top = sum(w * (F[loc] ** n - prev[loc] ** n) for n, w in ((1, .4), (2, .5), (3, .1)))
        out[k] += p / tot / byloc[loc] * top
    return out


@functools.lru_cache(maxsize=None)
def pick_dist(L, good=False):
    """P(k_idx) from get_obj_num(L) with the 1-in-20 boost; good = kind_is_good hook. Empty dict = failure."""
    L = min(L, 127)
    ent = GOOD_ENTRIES if good else ENTRIES
    res = collections.defaultdict(float)
    for k, p in _pick(L, ent).items():
        res[k] += p * (19 / 20 if L > 0 else 1)
    if L > 0:
        for r in range(1, 129):
            for k, p in _pick(1 + L * 128 // r, ent).items():
                res[k] += p / 20 / 128
    return res


def power_probs(L, good=False, great=False):
    L = min(L, 127)
    f1 = min(L + 10, 75) / 100; f2 = min(min(L + 10, 75) // 2, 20) / 100
    if great:
        return {2: 1.0}
    if good:
        return {2: f2, 1: 1 - f2}
    return {2: f1 * f2, 1: f1 * (1 - f2), 0: (1 - f1) ** 2, -1: (1 - f1) * f1 * (1 - f2), -2: (1 - f1) * f1 * f2}


# --- one weapon/armour item
def m_bonus(mx, lev):
    lev = min(lev, 127)
    bonus = mx * lev // 128 + (1 if random.randrange(128) < (mx * lev) % 128 else 0)
    stand = mx // 4 + (1 if random.randrange(4) < mx % 4 else 0)
    v = bonus if stand < 1 else int(round(random.gauss(bonus, stand)))
    return max(0, min(mx, v))


def r1(n):
    return random.randint(1, n) if n > 0 else (-random.randint(1, -n) if n < 0 else 0)


_ego_cache = {}


def eligible_egos(k, lev, cursed):
    key = (k["k_idx"], min(lev, 127), cursed)
    if key not in _ego_cache:
        el = [e for e in egos if e["curse"] == cursed and e["level"] <= lev and
              any(t == k["tval"] and lo <= k["sval"] <= hi for t, lo, hi in e["slots"])]
        _ego_cache[key] = (el, [1 / e["rarity"] for e in el])
    return _ego_cache[key]


def gear_value(k, power, lev):
    """One item of gear kind k at the given power: (value, to_h, to_d, to_a, ego name or '', irreplaceable?)."""
    tv = k["tval"]; th, td, ta, dd, pval = k["to_h"], k["to_d"], k["to_a"], k["dd"], k["pval"]
    if tv in AMMO and k["sval"] == SV_AMMO_MAGIC:
        return k["cost"], th, td, ta, "", False
    if tv in WEAPON:
        if power:
            h1, d1 = random.randint(1, 5) + m_bonus(5, lev), random.randint(1, 5) + m_bonus(5, lev)
            h2, d2 = m_bonus(10, lev), m_bonus(10, lev)
            s = 1 if power > 0 else -1
            th += s * h1; td += s * d1
            if abs(power) > 1: th += s * h2; td += s * d2
            if tv == 20 and power < -1: pval = -(5 + random.randint(1, 5))
            elif tv == 20 and power < 0: pval = -pval
            if tv in DICE_UP and power > 1:
                while dd * k["ds"] > 0 and random.randrange(10 * dd * k["ds"]) == 0:
                    dd += 1
                dd = min(dd, 9)
    else:
        a1, a2 = random.randint(1, 5) + m_bonus(5, lev), m_bonus(10, lev)
        if power:
            s = 1 if power > 0 else -1
            ta += s * a1
            if abs(power) > 1: ta += s * a2
    ego, broken = None, k["cost"] == 0
    if abs(power) > 1 and tv != 38:
        el, w = eligible_egos(k, lev, power < 0)
        if el:
            ego = random.choices(el, w)[0]
            if ego["curse"] or ego["cost"] == 0:
                broken = True
                th -= r1(ego["h"]) if ego["h"] else 0; td -= r1(ego["d"]) if ego["d"] else 0
                ta -= r1(ego["a"]) if ego["a"] else 0; pval -= r1(ego["pval"]) if ego["pval"] else 0
            else:
                th += r1(ego["h"]); td += r1(ego["d"]); ta += r1(ego["a"]); pval += r1(ego["pval"])
    name = ego["name"] if ego else ""
    irr = bool(ego and not broken and ego["flags"] & IRREPL)
    flags = k["F"] | (ego["flags"] if ego else set())
    if broken or pval < 0:
        return 0, th, td, ta, name, False
    val = k["cost"] + (ego["cost"] if ego else 0)
    val += pval * sum(c for f, c in PVAL_COST.items() if f in flags)
    if tv in AMMO:
        if th + td < 0: return 0, th, td, ta, name, False
        val += 5 * (th + td) + ((dd - k["dd"]) * k["ds"] * 5 if dd > k["dd"] else 0)
    elif tv in WEAPON:
        if th + td < 0: return 0, th, td, ta, name, False
        val += 100 * (th + td + ta) + ((dd - k["dd"]) * k["ds"] * 100 if dd > k["dd"] else 0)
    else:
        if ta < 0: return 0, th, td, ta, name, False
        val += 100 * (th + td + ta)
    return val, th, td, ta, name, irr


# --- artifacts
def _ood(level, depth, mult):
    return 1.0 if level <= depth else 1.0 / ((level - depth) * mult)


def art_chance(k, depth, rolls=1):
    """make_artifact for kind k: (P(artifact), E[cost | artifact])."""
    if depth <= 0 or rolls <= 0:
        return 0.0, 0.0
    miss, hit, ev = 1.0, 0.0, 0.0
    for a in normal_arts.get((k["tval"], k["sval"]), []):
        p = _ood(a["level"], depth, 2) / a["rarity"]
        ev += miss * p * a["cost"]; hit += miss * p; miss *= 1 - p
    if hit == 0:
        return 0.0, 0.0
    p_roll, e_cost = hit, ev / hit
    return 1 - (1 - p_roll) ** rolls, e_cost


def special_chance(depth, L, good):
    """make_artifact_special inside place_object: (P(special), E[cost | special])."""
    if depth <= 0:
        return 0.0, 0.0
    miss, hit, ev = 1.0, 0.0, 0.0
    for a in specials:
        kl = by_tsv[(a["tval"], a["sval"])]["level"]
        p = _ood(a["level"], depth, 2) / a["rarity"] * _ood(kl, L, 5)
        ev += miss * p * a["cost"]; hit += miss * p; miss *= 1 - p
    gate = 1 / 10 if good else 1 / 1000
    return gate * hit, (ev / hit if hit else 0.0)

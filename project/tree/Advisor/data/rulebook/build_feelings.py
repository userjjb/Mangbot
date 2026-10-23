#!/usr/bin/env python3
"""Rulebook table T2: what a pseudo-ID feeling means, per base kind and object level (warrior = heavy sensing).

Writes feelings.csv: for every weapon / ammo / bow / digger / armour kind in object.txt, at object levels
5,10,15,20,25,30,40,50 and for the feelings "good" and "excellent" (Monte Carlo of apply_magic):
  exp_value        E[true value | feeling]  (object_value_real: kind cost + ego cost + 100 per to-hit/to-dam/to-AC plus
                   (5 for ammo, per item) + ego pval x flag cost; object2.c:1136-1300)
  p10,p50,p90      value percentiles
  exp_to_h/to_d/to_a   expected plusses (incl. the kind's own)
  p_irreplaceable  P(the ego gives Free Action, See Invisible, a basic or high resist, Hold Life, ESP, Regen or Speed)
  top_egos         the most likely egos with probabilities
and per kind (any level): average = kind cost (power 0); cursed/worthless/broken/terrible = 0 (shops refuse);
special = artifact: expected artifact cost for this base kind (weight 1/rarity).
Mechanics (study 2026-10-23-rulebook, dispatch K1; object2.c): power +1 -> "good": plusses randint1(5)+m_bonus(5,L)
(to-hit and to-dam for weapons, to-AC for armour); power +2 -> also m_bonus(10,L) each, then an ego chosen with weight
1/rarity among egos for the tval/sval with level <= L and no curse -> "excellent" (+randint1(max) on each ego field).
Dragon armour gets no ego (feels "good"). Object level: floor = dungeon level; drops = (dungeon + monster level)/2.

usage: build_feelings.py [N_SAMPLES]   (default 3000)"""
import collections, csv, os, random, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
EDIT = "/projectnb/jbrcs/mangband/github/lib/edit"
EGOS = "/projectnb/jbrcs/mangband/Advisor/studies/2026-10-23-rulebook/scratch/K1/K1_egos.csv"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
LEVELS = [5, 10, 15, 20, 25, 30, 40, 50]
TV = {"shot": 16, "arrow": 17, "bolt": 18, "bow": 19, "digging": 20, "hafted": 21, "polearm": 22, "sword": 23,
      "boots": 30, "gloves": 31, "helm": 32, "crown": 33, "shield": 34, "cloak": 35, "softarmor": 36, "hardarmor": 37,
      "dragarmor": 38}
WEAPON = {16, 17, 18, 19, 20, 21, 22, 23}
AMMO = {16, 17, 18}
ARMOUR = {30, 31, 32, 33, 34, 35, 36, 37, 38}
PVAL_COST = {"STR": 200, "INT": 200, "WIS": 200, "DEX": 200, "CON": 200, "CHR": 200, "STEALTH": 100, "SEARCH": 100,
             "INFRA": 50, "TUNNEL": 50, "BLOWS": 2000, "SPEED": 100000}
IRREPL = {"FREE_ACT", "SEE_INVIS", "RES_POIS", "RES_BLIND", "RES_CONF", "HOLD_LIFE", "SPEED", "TELEPATHY", "REGEN",
          "RES_ACID", "RES_ELEC", "RES_FIRE", "RES_COLD", "RES_NETHER", "RES_SOUND", "RES_SHARDS", "RES_NEXUS",
          "RES_CHAOS", "RES_DISEN", "RES_LITE", "RES_DARK"}
CURSES = {"LIGHT_CURSE", "HEAVY_CURSE", "PERMA_CURSE"}

# --- base kinds
kinds, cur = [], None
for line in open(f"{EDIT}/object.txt", encoding="latin-1"):
    line = line.rstrip("\n")
    if line.startswith("N:"):
        cur = {"name": line.split(":", 2)[2].replace("&", "").replace("~", "").strip(), "A": []}
        kinds.append(cur)
    elif cur is None:
        continue
    elif line.startswith("I:"):
        _, tv, sv, pv = line.split(":")[:4]; cur.update(tval=int(tv), sval=int(sv))
    elif line.startswith("W:"):
        p = line.split(":"); cur.update(level=int(p[1]), cost=int(p[4]))
    elif line.startswith("P:"):
        p = line.split(":"); cur.update(ac=int(p[1]), dice=p[2], to_h=int(p[3]), to_d=int(p[4]), to_a=int(p[5]))
    elif line.startswith("A:"):
        cur["A"] += line[2:].split(":")
kinds = [k for k in kinds if k.get("tval") in WEAPON | ARMOUR and k.get("A") and "to_h" in k and k.get("cost", 0) > 0]

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
                     cost=int(r["cost"]), flags=fl, cursed=bool(fl & CURSES) or int(r["cost"]) == 0))

# --- artifacts (special)
arts, cur = [], None
for line in open(f"{EDIT}/artifact.txt", encoding="latin-1"):
    if line.startswith("N:"):
        cur = {"name": line.split(":", 2)[2].strip()}; arts.append(cur)
    elif cur is not None and line.startswith("I:"):
        p = line.split(":"); cur.update(tval=int(p[1]), sval=int(p[2]))
    elif cur is not None and line.startswith("W:"):
        p = line.split(":"); cur.update(level=int(p[1]), rarity=max(1, int(p[2])), cost=int(p[4]))


def randnor(mean, stand):
    return mean if stand < 1 else int(round(random.gauss(mean, stand)))


def m_bonus(mx, lev):
    lev = min(lev, 127)
    bonus = mx * lev // 128 + (1 if random.randrange(128) < (mx * lev) % 128 else 0)
    stand = mx // 4 + (1 if random.randrange(4) < mx % 4 else 0)
    return max(0, min(mx, randnor(bonus, stand)))


def r1(n):
    return random.randint(1, n) if n > 0 else (-random.randint(1, -n) if n < 0 else 0)


def sample(k, power, lev):
    """One item of kind k at power +1/+2: (value, to_h, to_d, to_a, ego name or '', irreplaceable?)."""
    tv = k["tval"]; th, td, ta = k["to_h"], k["to_d"], k["to_a"]
    if tv in WEAPON:
        th += random.randint(1, 5) + m_bonus(5, lev); td += random.randint(1, 5) + m_bonus(5, lev)
        if power > 1: th += m_bonus(10, lev); td += m_bonus(10, lev)
    else:
        ta += random.randint(1, 5) + m_bonus(5, lev)
        if power > 1: ta += m_bonus(10, lev)
    ego, val, pval_extra, irr = None, k["cost"], 0, False
    if power > 1 and tv != 38:
        el = [e for e in egos if not e["cursed"] and e["level"] <= lev and
              any(t == tv and lo <= k["sval"] <= hi for t, lo, hi in e["slots"])]
        if el:
            w = [1 / e["rarity"] for e in el]
            ego = random.choices(el, w)[0]
            th += r1(ego["h"]); td += r1(ego["d"]); ta += r1(ego["a"])
            pv = r1(ego["pval"]) if ego["pval"] else 0
            val += ego["cost"]
            pval_extra = sum(pv * c for f, c in PVAL_COST.items() if f in ego["flags"] and pv > 0)
            irr = bool(ego["flags"] & IRREPL)
    per = 5 if tv in AMMO else 100
    val += per * (th - k["to_h"] + td - k["to_d"] + ta - k["to_a"]) + pval_extra
    val += per * (k["to_h"] + k["to_d"] + k["to_a"]) if False else 0   # kind plusses are in the kind cost already
    return val, th, td, ta, ego["name"] if ego else "", irr


random.seed(20261023)
rows = []
for k in kinds:
    sp = [a for a in arts if a.get("tval") == k["tval"] and a.get("sval") == k["sval"] and a.get("cost")]
    special = round(sum(a["cost"] / a["rarity"] for a in sp) / sum(1 / a["rarity"] for a in sp)) if sp else ""
    for L in LEVELS:
        for feeling, power in (("good", 1), ("excellent", 2)):
            if feeling == "excellent" and k["tval"] == 38:
                continue
            vs, hs, ds, as_, irr, eg = [], [], [], [], 0, collections.Counter()
            for _ in range(N):
                v, h, d, a, e, ir = sample(k, power, L)
                if feeling == "excellent" and not e:
                    continue                      # no ego found: would feel "good", not "excellent"
                vs.append(v); hs.append(h); ds.append(d); as_.append(a); irr += ir; eg[e] += 1
            if not vs:
                continue
            vs.sort(); n = len(vs)
            rows.append(dict(kind=k["name"], tval=k["tval"], sval=k["sval"], kind_cost=k["cost"], level=L,
                             feeling=feeling, exp_value=round(sum(vs) / n), p10=vs[n // 10], p50=vs[n // 2],
                             p90=vs[9 * n // 10], exp_to_h=round(sum(hs) / n, 1), exp_to_d=round(sum(ds) / n, 1),
                             exp_to_a=round(sum(as_) / n, 1), p_irreplaceable=round(irr / n, 3),
                             top_egos="; ".join(f"{e} {c / n:.2f}" for e, c in eg.most_common(4) if e),
                             special_artifact_value=special))
out = os.path.join(HERE, "feelings.csv")
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "rows,", len(kinds), "kinds ->", out)

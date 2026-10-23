#!/usr/bin/env python3
"""Rulebook table T2b: rings and amulets with their plusses, by kind and object level (rings/amulets are never pseudo-ID'd).

Writes jewellery.csv: kind, tval, sval, level, p_cursed, exp_value, p10/p50/p90 value, exp_pval, exp_to_a, exp_to_h, exp_to_d.
Monte Carlo of apply_magic + a_m_aux_3 (object2.c:2675-3088, 3187-3350; dispatch K1 table 7):
  power: f1=min(L+10,75), f2=min(f1//2,20); magik(f1) -> +1 (magik(f2) -> +2); else magik(f1) -> -1 (magik(f2) -> -2);
         jewellery at power 0 becomes -1 with 50%.  Kinds marked c get cursed (pval/plusses negated) when power < 0.
  value (object_value_real): cursed or any negative plus -> 0; else kind cost + 100*(to_h+to_d+to_a) + pval x flag cost
         (STR..CHR 200, STEALTH/SEARCH 100, INFRA/TUNNEL 50, SPEED 50000 ring / 25000 amulet).
Kinds without a rule (resists, sustains, Free Action, See Invisible, Slow Digestion...) have fixed value = kind cost;
always-cursed kinds (Teleportation, Weakness, Stupidity, Woe, DOOM, Aggravate) have value 0.
usage: build_jewellery.py [N]   (default 4000)"""
import csv, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
EDIT = "/projectnb/jbrcs/mangband/github/lib/edit"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
LEVELS = list(range(0, 61, 5))
FLAGCOST = {"STR": 200, "INT": 200, "WIS": 200, "DEX": 200, "CON": 200, "CHR": 200, "STEALTH": 100, "SEARCH": 100,
            "INFRA": 50, "TUNNEL": 50}


def m_bonus(mx, lev):
    lev = min(lev, 127)
    bonus = mx * lev // 128 + (1 if random.randrange(128) < (mx * lev) % 128 else 0)
    stand = mx // 4 + (1 if random.randrange(4) < mx % 4 else 0)
    v = bonus if stand < 1 else int(round(random.gauss(bonus, stand)))
    return max(0, min(mx, v))


r1 = lambda n: random.randint(1, n)
# (tval, name) -> (cursable, generator returning (pval, to_a, to_h, to_d))
RULES = {
    (45, "Strength"): (True, lambda L: (1 + m_bonus(5, L), 0, 0, 0)),
    (45, "Dexterity"): (True, lambda L: (1 + m_bonus(5, L), 0, 0, 0)),
    (45, "Constitution"): (True, lambda L: (1 + m_bonus(5, L), 0, 0, 0)),
    (45, "Intelligence"): (True, lambda L: (1 + m_bonus(5, L), 0, 0, 0)),
    (45, "Searching"): (True, lambda L: (1 + m_bonus(5, L), 0, 0, 0)),
    (45, "Speed"): (True, None),
    (45, "Flames"): (False, lambda L: (0, 5 + r1(5) + m_bonus(10, L), 0, 0)),
    (45, "Acid"): (False, lambda L: (0, 5 + r1(5) + m_bonus(10, L), 0, 0)),
    (45, "Ice"): (False, lambda L: (0, 5 + r1(5) + m_bonus(10, L), 0, 0)),
    (45, "Lightning"): (False, lambda L: (0, 5 + r1(5) + m_bonus(10, L), 0, 0)),
    (45, "Protection"): (True, lambda L: (0, 5 + r1(5) + m_bonus(10, L), 0, 0)),
    (45, "Damage"): (True, lambda L: (0, 0, 0, 5 + r1(5) + m_bonus(7, L))),
    (45, "Accuracy"): (True, lambda L: (0, 0, 5 + r1(5) + m_bonus(7, L), 0)),
    (45, "Slaying"): (True, lambda L: (0, 0, r1(5) + m_bonus(5, L), r1(5) + m_bonus(5, L))),
    (40, "Wisdom"): (True, lambda L: (1 + m_bonus(5, L), 0, 0, 0)),
    (40, "Charisma"): (True, lambda L: (1 + m_bonus(5, L), 0, 0, 0)),
    (40, "Searching"): (True, lambda L: (r1(5) + m_bonus(5, L), 0, 0, 0)),
    (40, "Infravision"): (True, lambda L: (r1(5) + m_bonus(5, L), 0, 0, 0)),
    (40, "ESP"): (False, lambda L: (r1(5) + m_bonus(5, L), 0, 0, 0)),
    (40, "Terken"): (False, lambda L: (r1(5) + m_bonus(5, L), 0, 0, 0)),
    (40, "the Magi"): (False, lambda L: (1 + m_bonus(2, L), r1(5) + m_bonus(5, L), 0, 0)),
    (40, "Speed"): (True, lambda L: (r1(r1(3)), 0, 0, 0)),
    (40, "the Moon"): (False, lambda L: (r1(5) + m_bonus(5, L), 0, r1(5), r1(5))),
    (40, "Devotion"): (False, lambda L: (1 + m_bonus(3, L), 0, 0, 0)),
    (40, "Weaponmastery"): (False, lambda L: (1 + m_bonus(2, L), 0, 1 + m_bonus(4, L), 1 + m_bonus(4, L))),
    (40, "Trickery"): (False, lambda L: (1 + m_bonus(3, L), 0, 0, 0)),
}


def ring_speed(L):
    p = r1(5) + m_bonus(5, L)
    while random.randrange(100) < 50:
        p += 1
    return (p, 0, 0, 0)


kinds, cur = [], None
for line in open(f"{EDIT}/object.txt", encoding="latin-1"):
    line = line.rstrip("\n")
    if line.startswith("N:"):
        cur = {"name": line.split(":", 2)[2].replace("&", "").replace("~", "").strip(), "F": set()}
        kinds.append(cur)
    elif cur and line.startswith("I:"):
        p = line.split(":"); cur.update(tval=int(p[1]), sval=int(p[2]))
    elif cur and line.startswith("W:"):
        cur["cost"] = int(line.split(":")[4])
    elif cur and line.startswith("F:"):
        cur["F"] |= {f.strip() for f in line[2:].split("|") if f.strip()}
kinds = [k for k in kinds if k.get("tval") in (40, 45) and "INSTA_ART" not in k["F"]]

random.seed(20261024)
rows = []
for k in kinds:
    key = (k["tval"], k["name"])
    if key not in RULES:
        v = 0 if (k["cost"] == 0 or "LIGHT_CURSE" in k["F"]) else k["cost"]
        for L in LEVELS:
            rows.append(dict(kind=k["name"], tval=k["tval"], sval=k["sval"], level=L, p_cursed=int(v == 0),
                             exp_value=v, p10=v, p50=v, p90=v, exp_pval=0, exp_to_a=0, exp_to_h=0, exp_to_d=0))
        continue
    cursable, gen = RULES[key]
    if key == (45, "Speed"): gen = ring_speed
    for L in LEVELS:
        f1 = min(L + 10, 75); f2 = min(f1 // 2, 20)
        vals, pv, ta, th, td, cursed = [], 0, 0, 0, 0, 0
        for _ in range(N):
            if random.randrange(100) < f1:
                power = 2 if random.randrange(100) < f2 else 1
            elif random.randrange(100) < f1:
                power = -2 if random.randrange(100) < f2 else -1
            else:
                power = 0
            if power == 0 and random.randrange(100) < 50:
                power = -1
            p, a, h, d = gen(L)
            if cursable and power < 0:
                cursed += 1; vals.append(0); continue
            v = k["cost"] + 100 * (a + h + d)
            spd = 50000 if k["tval"] == 45 else 25000
            v += p * (sum(c for f, c in FLAGCOST.items() if f in k["F"]) + (spd if "SPEED" in k["F"] else 0))
            vals.append(v); pv += p; ta += a; th += h; td += d
        vals.sort(); n = len(vals); ok = max(1, n - cursed)
        rows.append(dict(kind=k["name"], tval=k["tval"], sval=k["sval"], level=L, p_cursed=round(cursed / n, 3),
                         exp_value=round(sum(vals) / n), p10=vals[n // 10], p50=vals[n // 2], p90=vals[9 * n // 10],
                         exp_pval=round(pv / ok, 1), exp_to_a=round(ta / ok, 1), exp_to_h=round(th / ok, 1),
                         exp_to_d=round(td / ok, 1)))
with open(os.path.join(HERE, "jewellery.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "rows")

#!/usr/bin/env python3
"""Rulebook table T2: what a pseudo-ID feeling means, per base kind and object level (warrior = heavy sensing).

Writes feelings.csv: for every weapon / ammo / bow / digger / armour kind in object.txt, at object levels
5,10,15,20,25,30,40,50 and for the feelings "good" and "excellent" (Monte Carlo of apply_magic):
  exp_value        E[true value | feeling]  (object_value_real: kind cost + ego cost + 100 per to-hit/to-dam/to-AC plus INCLUDING the
                   kind's own (5 for ammo, per item) + extra damage dice + pval x flag cost; object2.c:1136-1345;
                   model in objgen.py. Release 3 fix: r1/r2 left out the kind's own plusses, e.g. Kolla, dragon armour)
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
import collections, csv, os, random, sys
from objgen import kinds as ALLKINDS, arts, gear_value, GEAR
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
LEVELS = [5, 10, 15, 20, 25, 30, 40, 50]
kinds = [k for k in ALLKINDS.values() if k.get("tval") in GEAR and k["A"] and k["cost"] > 0]


def sample(k, power, lev):
    return gear_value(k, power, lev)


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

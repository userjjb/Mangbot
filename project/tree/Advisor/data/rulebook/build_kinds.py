#!/usr/bin/env python3
"""Rulebook table T1: flavoured kinds by object level, for valuing an UNKNOWN item.

Writes kinds_by_level.csv: one row per (object level L, flavoured kind) with
  p_in_tval   P(an item of this tval generated at object level L is this kind)   (get_obj_num, object2.c:646-770,
              incl. the 1-in-20 level boost and best-of-2/3; floor items: L = dungeon level; monster drops:
              L = (dungeon level + monster level) / 2, xtra2.c monster_death)
  value       true value of one identified item (object_value_real): kind cost (object.txt W:), + 5% of it per
              charge for wands/staffs at the MEAN initial charges (object2.c charge_wand/charge_staff, 1252-1259);
              rings/amulets: kind cost only (plusses/pval from apply_magic not yet included: see T2)
  worthless   1 if cost 0 (shops refuse it once known: store_will_buy)
  hazard      what using/wearing it unknown does to our warrior (identify study, P/D dispatches): "" if harmless
How the Pilot uses it: E[value | tval, L, still-unaware kinds] = sum(p*value)/sum(p) over the kinds the character is
not aware of (awareness = server kind_aware; the flavour table runs/flavours.json maps flavour -> kind).
Sale price = value x S (owner sell %), see T6.

usage: build_kinds.py [MAXLEVEL]   (default 60)"""
import csv, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "identify"))
from dist import level_dist, kinds as KINDS, FLAV          # noqa: E402

SRC = "/projectnb/jbrcs/mangband/github/src/server"
STUDY = "/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch"

# mean initial charges by (tval, SV_ name) from charge_wand / charge_staff
charges = {}
for line in open(f"{SRC}/object2.c", encoding="latin-1"):
    m = re.search(r"case SV_(WAND|STAFF)_(\w+):\s*o_ptr->pval = randint1\((\d+)\)\s*\+\s*(\d+)", line)
    if m:
        charges[(m.group(1).lower(), m.group(2))] = (int(m.group(3)) + 1) / 2 + int(m.group(4))
svname = {}
for line in open(f"{SRC}/mdefines.h", encoding="latin-1"):
    m = re.match(r"#define SV_(WAND|STAFF)_(\w+)\s+(\d+)", line)
    if m:
        svname[(m.group(1).lower(), int(m.group(3)))] = m.group(2)
krow = {int(r["k_idx"]): r for r in csv.DictReader(open(os.path.join(HERE, "..", "identify", "kinds.csv")))}

# hazard classes from the identify study (potions: P, others: D)
haz = {}
for r in csv.DictReader(open(f"{STUDY}/P_potions.csv")):
    if r["class"].split()[0] not in ("GOOD", "HARMLESS"):
        haz[("potion", r["potion"])] = r["class"]
for r in csv.DictReader(open(f"{STUDY}/D_devices.csv")):
    c = r["class"]
    if not (c.startswith("GOOD") or c.startswith("HARMLESS")):
        haz[(r["tval"], r["kind"])] = c

maxlev = int(sys.argv[1]) if len(sys.argv) > 1 else 60
rows = []
for L in range(0, maxlev + 1):
    d = level_dist(L)
    for tv, tn in FLAV.items():
        ks = {k: p for k, p in d.items() if KINDS[k].get("tval") == tv}
        tot = sum(ks.values())
        for k, p in sorted(ks.items(), key=lambda x: -x[1]):
            r = krow.get(k)
            if not r or p / tot < 1e-5:
                continue
            cost = int(r["cost"])
            ch = charges.get((tn, svname.get((tn, int(r["sval"])), "")), 0) if tn in ("wand", "staff") else 0
            rows.append(dict(level=L, tval=tn, tval_num=tv, k_idx=k, kind=r["name"], p_in_tval=round(p / tot, 6),
                             value=round(cost + (cost // 20) * ch), mean_charges=round(ch, 1) if ch else "",
                             worthless=int(cost == 0), hazard=haz.get((tn, r["name"]), "")))
out = os.path.join(HERE, "kinds_by_level.csv")
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "rows ->", out)

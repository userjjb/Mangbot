#!/usr/bin/env python3
"""Expected sale value of one unknown flavoured item by tval and object level (unknown vs aware vs
known), and the cost of one identification by each route. Uses dist.py (kind odds), kinds.csv.

Facts (code-checked, study 2026-10-07-selling):
- sale = (value x S + 50)//100; S = 200 - buy% at CHR 4 (store.c:217-225). Mean owner S used here:
  potions/scrolls 43.75 (Temple: 46,45,43,41), devices/jewellery 39.25 (Magic: 40,42,45,30).
- unknown value per tval (object2.c:1075-1112); aware = kind cost; known wands/staffs + cost/20 per
  charge (object2.c:1252-1259); worthless kinds (cost 0) are refused once known (store.c:541ff).
- a sale quotes the unknown price, then makes the flavour aware and the item known (store.c:2134-2141).
- Staff of Perception: charges randint1(15)+5 (object2.c:2350); price (400+20N) x buy%; a failed use
  costs no charge (cmd6.c:477-497). Recharging scroll (strength 60, use-obj.c:891): backfire 1/i,
  i=(160-10-10c)//15, destroys the staff (SAFE_RECHARGE=false); success +2+randint1(6) (spells2.c:3118-3176).
"""
import csv, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dist import level_dist, kinds as KINDS, FLAV

UNAWARE = {"potion": 20, "scroll": 20, "staff": 70, "wand": 50, "rod": 90, "ring": 45, "amulet": 45}
S = {"potion": 43.75, "scroll": 43.75}
SRC = "/projectnb/jbrcs/mangband/github/src/server/object2.c"

# mean charges by sval name from charge_wand/charge_staff: "randint1(a) + b" -> (a+1)/2 + b
import re
charges = {}
for line in open(SRC, encoding="latin-1"):
    m = re.search(r"case SV_(WAND|STAFF)_(\w+):\s*o_ptr->pval = randint1\((\d+)\)\s*\+\s*(\d+)", line)
    if m:
        charges[(m.group(1).lower(), m.group(2))] = (int(m.group(3)) + 1) / 2 + int(m.group(4))
cost = {}
for r in csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kinds.csv"))):
    cost[int(r["k_idx"])] = int(r["cost"])

# sval -> SV_ name for wands/staffs from mdefines.h
svname = {}
for line in open("/projectnb/jbrcs/mangband/github/src/server/mdefines.h", encoding="latin-1"):
    m = re.match(r"#define SV_(WAND|STAFF)_(\w+)\s+(\d+)", line)
    if m:
        svname[(m.group(1).lower(), int(m.group(3)))] = m.group(2)
sval = {}
for r in csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kinds.csv"))):
    sval[int(r["k_idx"])] = int(r["sval"])

def sell(v, s): return int((v * s + 50) // 100) if v > 0 else 0

print("== Expected shop payment for ONE unknown item (mean owner), by object level ==")
print("level tval     unknown  aware  known  P(worthless)  P(aware>=+80 over unknown)")
for L in (5, 10, 15, 20, 25, 30):
    d = level_dist(L)
    for tv, tn in FLAV.items():
        ks = {k: p for k, p in d.items() if KINDS[k].get("tval") == tv and k in cost}
        tot = sum(ks.values())
        s = S.get(tn, 39.25)
        unk = sell(UNAWARE[tn], s)
        aw = kn = worth0 = big = 0.0
        for k, p in ks.items():
            p /= tot
            c = cost[k]
            a = sell(c, s)
            ch = charges.get((tn, svname.get((tn, sval[k]), "")), 0) if tn in ("wand", "staff") else 0
            kv = sell(c + (c // 20) * ch, s) if c else 0
            aw += p * a; kn += p * kv
            worth0 += p * (c == 0)
            big += p * (a - unk >= 80)
        print(f"{L:5d} {tn:8s} {unk:7d} {aw:6.0f} {kn:6.0f} {worth0:12.0%} {big:12.0%}")

print("\n== Cost of one identification ==")
for buy in (155, 158, 161):
    print(f"Identify scroll at {buy}%: {(50*buy+50)//100}; at 25% off: {(37*buy+50)//100}")
c0 = []
for buy_staff, buy_scroll in ((155, 155), (160, 158), (170, 161)):
    rech = (200 * buy_scroll + 50) // 100
    staff0 = (400 * buy_staff + 50) // 100            # replacing a destroyed (empty) staff: buy one, charges extra
    staff_new = statistics.mean(((400 + 20 * n) * buy_staff + 50) // 100 for n in range(6, 21))
    gain = 0.9 * statistics.mean(range(3, 9))          # recharge at 0 charges: 10% backfire
    # long-run cost per charge: a recharge each cycle; a backfire forces a new staff (with its own charges)
    # cycle: pay rech; 90%: +5.5 charges; 10%: staff gone, buy new (staff_new, mean 13 charges)
    per_cycle_cost = rech + 0.1 * staff_new
    per_cycle_charges = gain + 0.1 * 13
    print(f"Perception: staff {staff_new:.0f} new (13 charges, {staff_new/13:.0f}/charge), "
          f"Recharging {rech}: long run {per_cycle_cost/per_cycle_charges:.0f} gold per charge "
          f"(staff buy {buy_staff}%, scroll {buy_scroll}%), x1.2 turns for fails")

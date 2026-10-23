#!/usr/bin/env python3
"""Query the rulebook (for the Navigator, the Pilot or a human).

  rule.py monster NAME             one monster's row (substring match)
  rule.py unknown TVAL LEVEL       expected value of an unknown flavoured item (e.g. unknown wand 13)
  rule.py feeling KIND FEELING [LEVEL]   what a pseudo-ID feeling means for a base kind (e.g. feeling "Soft Leather Boots" excellent 13)
  rule.py owner NAME [CHR]         a shop owner's buy/pay % (default CHR 3)
  rule.py const WORD               timing/odds constants matching WORD
  rule.py room                     room/vault geometry facts
  rule.py fight MONSTER [--clvl 22 --blows 4 --dpb 9 --tohit 3 --ac 40]
                                   expected player turns to kill it, and the HP it takes from you meanwhile
                                   (dpb = mean damage per hit incl. weapon and STR to-dam; tohit = all to-hit bonuses)"""
import csv, os, sys
H = os.path.dirname(os.path.abspath(__file__))
R = lambda f: list(csv.DictReader(open(os.path.join(H, f))))
a = sys.argv[1:]
if not a: print(__doc__); sys.exit()
c, args = a[0], a[1:]
if c == "monster":
    for r in R("monsters.csv"):
        if args[0].lower() in r["name"].lower(): print({k: v for k, v in r.items() if v not in ("", "0", "0.0")})
elif c == "unknown":
    for r in R("unknown_expect.csv"):
        if r["tval"] == args[0] and r["level"] == args[1]: print(r)
elif c == "feeling":
    lev = args[2] if len(args) > 2 else None
    for r in R("feelings.csv"):
        if r["kind"].lower() == args[0].lower() and r["feeling"] == args[1] and (not lev or r["level"] == lev): print(r)
elif c == "owner":
    ch = args[1] if len(args) > 1 else "3"
    for r in R("shop_owners.csv"):
        if args[0].lower() in r["owner"].lower(): print(r["store"], r["owner"], "buy%", r[f"buy%_chr{ch}"], "pay%", r[f"pay%_chr{ch}"])
elif c == "const":
    for r in R("constants.csv"):
        if args[0].lower() in (r["name"] + r["applies_when"]).lower(): print(r)
elif c == "fight":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("name"); ap.add_argument("--clvl", type=int, default=22)
    ap.add_argument("--blows", type=float, default=4); ap.add_argument("--dpb", type=float, default=9)
    ap.add_argument("--tohit", type=int, default=3); ap.add_argument("--ac", type=int, default=40)
    o = ap.parse_args(args)
    acol = min((20, 40, 60), key=lambda a: abs(a - o.ac))
    for r in R("monsters.csv"):
        if o.name.lower() not in r["name"].lower(): continue
        chance = 82 + 45 * o.clvl // 10 + 3 * o.tohit     # skill_thn (Half-Orc warrior) + 3*to_h (cmd1.c:51-70, xtra1.c)
        mac = int(r["ac"]) * 3 // 4
        ph = 0.05 + 0.90 * max(0.0, 1 - mac / chance)
        per_turn = o.blows * ph * o.dpb
        turns = int(r["hp"]) / per_turn
        taken = turns * (float(r[f"melee_turn_ac{acol}"]) * (1 - float(r["spell_pct"])) + float(r["range_turn"]))
        print(f"{r['name']}: hp {r['hp']}, ac {r['ac']}; your hit {ph:.0%}, {per_turn:.1f}/turn -> {turns:.1f} turns; "
              f"it deals ~{taken:.0f} meanwhile at AC {acol} (worst round {r['melee_max']}, breath {r['breath_max']})")
elif c == "room":
    for r in R("structures.csv"): print(r["structure"], r["parameter"], ":", r["value"])

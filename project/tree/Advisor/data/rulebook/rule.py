#!/usr/bin/env python3
"""Query the rulebook (for the Navigator, the Pilot or a human).

  rule.py monster NAME             one monster's row (substring match)
  rule.py unknown TVAL LEVEL       expected value of an unknown flavoured item (e.g. unknown wand 13)
  rule.py feeling KIND FEELING [LEVEL]   what a pseudo-ID feeling means for a base kind (e.g. feeling "Soft Leather Boots" excellent 13)
  rule.py owner NAME [CHR]         a shop owner's buy/pay % (default CHR 3)
  rule.py const WORD               timing/odds constants matching WORD
  rule.py room                     room/vault geometry facts"""
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
elif c == "room":
    for r in R("structures.csv"): print(r["structure"], r["parameter"], ":", r["value"])

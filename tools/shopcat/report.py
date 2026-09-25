#!/usr/bin/env python3
"""Flatten a shopcat catalog (JSON lines) into a CSV of current shop stock.

For each door, the latest *complete* shop visit wins; doors whose latest
result is something else (e.g. now for sale) are dropped from the stock.
"""
import argparse
import csv
import json
import sys

FIELDS = ["time", "depth", "level", "door_y", "door_x", "store_name", "owner", "slot", "name", "full_name",
          "count", "price_each", "ask_price", "weight_each", "gc", "ga", "attr", "examine_text"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("catalog", nargs="+", help="catalog .jsonl file(s)")
    ap.add_argument("-o", "--out", help="CSV file (default: stdout)")
    args = ap.parse_args()

    latest = {}          # (depth, y, x) -> record
    for path in args.catalog:
        with open(path) as f:
            for line in f:
                rec = json.loads(line)
                if "door_y" not in rec:
                    continue          # e.g. level_done markers
                key = (rec["depth"], rec["door_y"], rec["door_x"])
                # An incomplete shop visit doesn't replace an earlier complete one
                if rec["result"] in ("ejected", "locked", "no_door", "none", "unreachable") and key in latest:
                    continue
                latest[key] = rec

    out = open(args.out, "w", newline="") if args.out else sys.stdout
    w = csv.DictWriter(out, fieldnames=FIELDS, extrasaction="ignore")
    w.writeheader()
    shops = 0
    for key in sorted(latest, key=lambda k: (k[0] if k[0] is not None else 0, k[1], k[2])):
        rec = latest[key]
        if rec["result"] != "shop":
            continue
        shops += 1
        for it in rec["items"]:
            w.writerow({**{k: rec.get(k) for k in FIELDS}, **it})
    print(f"{shops} shops, {sum(1 for r in latest.values() if r['result'] == 'for_sale')} houses for sale, "
          f"{len(latest)} doors", file=sys.stderr)


if __name__ == "__main__":
    main()

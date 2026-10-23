#!/usr/bin/env python3
"""Rulebook table T6: shops. Writes
  shop_owners.csv : every owner with store, race, greed, and the shop's BUY (what we pay, %) and PAY (what it pays us, %)
                    for a Half-Orc at CHR 3..18/50 -- formula from store.c price_item via the Architect's shopmath.py
                    (verified to 1 gold on identified sales, scorecard memo). Black market (store index 6): asks x3, pays /3.
  shop_stock.csv  : the stock tables (init2.c store_table, from the shops study S1): store, kind, entries (weight in the
                    random pick); stores restock every 10*STORE_TURNS game turns (~33 s real at 75 fps, shops memo).
Store numbers: code index (0 General .. 6 Black market, 7 Home); the Pilot's `shop N` is index+1."""
import csv, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/projectnb/jbrcs/mangband/github/tools/observe")
import shopmath as sm                                                     # noqa: E402
STORES = ["General Store", "Armoury", "Weaponsmith", "Temple", "Alchemy shop", "Magic shop", "Black market", "Home"]
CHRS = [3, 4, 5, 8, 10, 12, 14, 16, 18, 28, 38, 48, 68]                  # 18+10*n = 18/(10n)
rows = []
for name, (store, orace, greed) in sorted(sm.OWNERS.items(), key=lambda x: (x[1][0], x[0])):
    r = dict(store_index=store, store=STORES[store] if store < len(STORES) else store, owner=name,
             owner_race=sm.RACES[orace] if orace < len(sm.RACES) else orace, greed=greed)
    try:
        sm.factors(name, 3)
    except IndexError:
        continue                                                        # owners of non-store pseudo-shops (no cost_adj row)
    for c in CHRS:
        buy, sell, _ = sm.factors(name, c)
        lab = str(c) if c <= 18 else f"18/{c-18:02d}"
        r[f"buy%_chr{lab}"] = sell; r[f"pay%_chr{lab}"] = buy      # shopmath: (buy adjust = shop buying, sell = shop selling)
    rows.append(r)
with open(os.path.join(HERE, "shop_owners.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
shutil.copy("/projectnb/jbrcs/mangband/Advisor/studies/2026-09-29-shops/scratch/S1_stock.csv", os.path.join(HERE, "shop_stock.csv"))
print(len(rows), "owners")

#!/usr/bin/env python3
"""CHR-4 Half-Orc buy/sell prices for the items the warrior needs, by store and owner.
Inputs: studies/2026-09-29-shops/scratch/S1_stock.csv (store tables) and S2_values.csv (costs),
owner adjust % from S2's owner table (store.c:183-222, adj_chr_gold[CHR 4]=125, cost_adj.txt).
Price = (cost × A + 50)//100 (buy), (cost × S + 50)//100 (sell); no haggling.
Writes price_table.csv."""
import csv, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.join(HERE, "../../studies/2026-09-29-shops/scratch")
OWN = {  # store: [(owner, A buy %, S sell %)]
    "General Store": [("Bilbo", 153, 47), ("Rincewind", 153, 47), ("Snafu", 152, 48), ("Lyar-el", 157, 43)],
    "Armoury": [("Kon-Dar", 135, 65), ("Darg-Low", 156, 44), ("Decado", 157, 43), ("Mauglin", 162, 38)],
    "Weaponsmith": [("Ithyl-Mak", 145, 55), ("Arndal", 160, 40), ("Tarl", 160, 40), ("Oglign", 162, 38)],
    "Temple": [("Ludwig", 154, 46), ("Gunnar", 155, 45), ("Delilah", 157, 43), ("Keldon", 159, 41)],
    "Alchemy shop": [("Mauser", 161, 39), ("Wizzle", 155, 45), ("Ga-nat", 161, 39), ("Vella", 156, 44)],
    "Magic-User store": [("Ariel", 160, 40), ("Buggerby", 158, 42), ("Inglorian", 155, 45), ("Luthien", 170, 30)],
}
stock = list(csv.DictReader(open(os.path.join(SC, "S1_stock.csv"))))
vals = list(csv.DictReader(open(os.path.join(SC, "S2_values.csv"))))
def norm(s):
    s = re.sub(r"[&~]|\(.*?\)", "", s).lower()
    s = s.replace("potion of ", "").replace("scroll of ", "").replace("staff of ", "")
    return re.sub(r"\s+", " ", s).strip()
out = []
for v in vals:
    cost = int(re.sub(r"\D", "", v["cost"]) or 0)
    tv, sv = v["tval"], v["sval"]
    stores = sorted({s["store"] for s in stock if s["tval_num"] == tv and s["sval_num"] == sv})
    entries = sum(int(s["entries"]) for s in stock if s["tval_num"] == tv and s["sval_num"] == sv)
    for st in stores or ["(not stocked)"]:
        own = OWN.get(st)
        if own:
            buys = [(cost * a + 50) // 100 for _, a, _ in own]
            sells = [(cost * s + 50) // 100 for _, _, s in own]
            out.append(dict(item=v["item"], cost=cost, store=st, table_entries=entries,
                            buy_min=min(buys), buy_max=max(buys), sell_min=min(sells), sell_max=max(sells)))
        else:
            out.append(dict(item=v["item"], cost=cost, store=st, table_entries=entries,
                            buy_min="", buy_max="", sell_min="", sell_max=""))
with open(os.path.join(HERE, "price_table.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
for r in out:
    print(f'{r["item"][:34]:34} {r["store"][:14]:14} cost {r["cost"]:>5}  buy {r["buy_min"]}-{r["buy_max"]}  sell {r["sell_min"]}-{r["sell_max"]}  (entries {r["table_entries"]})')

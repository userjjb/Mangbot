"""shopmath -- what a shop pays and asks, from the server source (store.c price_item).

A shop prices an item at value x adjust / 100, with G = owner greed (min_inflate, shop_own.txt
I-line) + the racial factor (cost_adj.txt, owner race x player race) + adj_chr_gold[CHR]:
  shop selling: adjust = max(100, G - 200)        shop buying: adjust = min(100, 400 - G)
and the Black Market (store 6, 0-based) asks x3 and pays /3. So the fair pay for an item a
shop has just re-listed at P is P x buy / sell (/9 at the Black Market). The Advisor checked
this against every identified sale: within 1 gold (scorecard memo, 2026-10-23).
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
EDIT = os.path.join(REPO, "lib", "edit")


def _owners():
    """{owner name: (store index, owner race, min_inflate)} from shop_own.txt."""
    out, cur = {}, None
    with open(os.path.join(EDIT, "shop_own.txt")) as f:
        for line in f:
            m = re.match(r"N:(\d+):(\d+):(.+)", line.strip())
            if m:
                cur = (int(m.group(1)), m.group(3).strip())
                continue
            m = re.match(r"I:(\d+):(\d+):(\d+)(?::(\d+))?", line.strip())
            if m and cur:
                out[cur[1]] = (cur[0], int(m.group(1)), int(m.group(3)))
                cur = None
    return out


def _cost_adj():
    rows = []
    with open(os.path.join(EDIT, "cost_adj.txt")) as f:
        for line in f:
            if line.startswith("A:"):
                rows.append([int(v) for v in line.strip()[2:].split(":")])
    return rows


def _adj_chr_gold():
    with open(os.path.join(REPO, "src", "server", "tables.c")) as f:
        src = f.read()
    body = src[src.index("byte adj_chr_gold[]"):]
    body = body[body.index("{") + 1:body.index("};")]
    return [int(v) for v in re.findall(r"^\s*(\d+)", body, re.M)]


def _races():
    out = []
    with open(os.path.join(EDIT, "p_race.txt")) as f:
        for line in f:
            m = re.match(r"N:(\d+):(.+)", line.strip())
            if m:
                out.append(m.group(2).strip())
    return out


OWNERS, COST_ADJ, ADJ_CHR_GOLD, RACES = _owners(), _cost_adj(), _adj_chr_gold(), _races()


def stat_index(v):
    """A stat value as the indicators give it (3..18, then 18 + tens of 18/xx) -> table index."""
    return max(0, v - 3) if v <= 18 else min(37, 15 + (v - 18) // 10)


def factors(owner, chr_value, race="Half-Orc"):
    """(buy adjust, sell adjust, store index) for this owner, or None if unknown."""
    o = OWNERS.get(owner) or next((v for k, v in OWNERS.items() if owner and owner.startswith(k)), None)
    if not o:
        return None
    store, orace, greed = o
    prace = RACES.index(race) if race in RACES else 6
    g = greed + COST_ADJ[orace][prace] + ADJ_CHR_GOLD[stat_index(chr_value)]
    return min(100, 400 - g), max(100, g - 200), store


def fair_pay(relist, owner, chr_value, race="Half-Orc"):
    """What the shop should have paid for an item it re-lists at `relist`."""
    f = factors(owner, chr_value, race)
    if not f or not relist:
        return None
    buy, sell, store = f
    pay = relist * buy / sell
    return round(pay / 9 if store == 6 else pay)

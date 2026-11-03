"""E1 split helper (used for step 4, town.py; edit MOVE and the target names for the next mixin): move the town methods (verbatim chunks: each statement with the blank lines and comments above it)
from class Pilot in pilot.py into class TownMixin in town.py.

    python3 split.py PILOT_DIR            # writes PILOT_DIR/town.py, rewrites PILOT_DIR/pilot.py
"""
import ast
import os
import sys

MOVE = """
note_town_stairs
SUPPLY_STAGES supply_gate
STORE_NUM STORE_LABEL BUYERS KIT_ITEMS KIT_CAP KITS FUEL_TOPUP FLASK_FUEL USEFUL_DEVICES STAT_FULL RECHARGE_MAX_FAIL
ENCHANT_TABLE ENCHANT_MIN_CHANCE
enchant_chance enchant_plan town_extras_note enchant_scrolls_wanted device_level recharge_fail recharge_wanted
note_store kind_key_of price_of lantern_fuel trip_minutes_left provisions_spare kit_count planned_depth town_buyers
CRUTCH_DEVICES is_crutch town_sell_count PACK_SLOTS town_make_room provision_step broke_for_recall town_sell_stores
town_sells identify_candidates town_identify_wanted town_needs restore_potion town_reserve town_shopping buy_store
stock_table
is_stash_item tavern_state stash_places stash_where stash_has stash_take BANK_FLOAT TURNS_PER_DMIN FOOD_MID
supply_minutes supply_text supply_watch edge_dir note_edge_cross house_state retire_stash_json house_save banked
tavern_entrance stash_wanted
""".split()

HEADER = '''"""town -- the Pilot's town side, as a mixin of Pilot (refactor-candidates E1; docs/goals-and-plans.md, the town
visit): the town kit's tables (STORE_NUM, KIT_ITEMS, KITS, BUYERS, SUPPLY_STAGES...) and what TownKit/Shop/HouseBank
ask of the Pilot -- the shopping list and the gold (town_needs, town_shopping, town_reserve, price_of, note_store,
buy_store), what to sell (town_buyers, town_sell_count, town_sells, is_crutch), making room and provisioning
(town_make_room, provision_step, kit_count, lantern_fuel, trip_minutes_left, provisions_spare), Identify, Enchant
Armour and Recharging (identify_candidates, enchant_plan, recharge_wanted), the supply gate (supply_gate) and the
food/light clock (supply_minutes, supply_text, supply_watch, TURNS_PER_DMIN, FOOD_MID), the house and the stash
(house_state, house_save, banked, stash_*, tavern_*, retire_stash_json) and the town's stairs and edge crossings
(note_town_stairs, note_edge_cross). The methods stay Pilot's: they read and write the Pilot's state through self.
"""
import csv
import functools
import json
import os
import re
import sys
import time

import geareval
from common import HERE, TV_POTION, TV_FOOD, TV_FLASK, TV_LITE, bare_name, singular, bad_inscription
from world import gnow, light_turns
from mover import MAX_HGT, MAX_WID
from town_goals import Shop
if os.path.join(HERE, "..", "observe") not in sys.path:     # (shopmath, as pilot.py loads it)
    sys.path.insert(0, os.path.join(HERE, "..", "observe"))
import shopmath                                  # noqa: E402


class TownMixin:
    """Pilot's town methods (`class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin)`: every name stays on
    Pilot)."""
'''


def names_of(stmt):
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [stmt.name]
    if isinstance(stmt, ast.Assign):
        out = []
        for t in stmt.targets:
            out += [n.id for n in ast.walk(t) if isinstance(n, ast.Name)]
        return out
    if isinstance(stmt, ast.AnnAssign):
        return [stmt.target.id]
    return []


def main(d):
    path = os.path.join(d, "pilot.py")
    src = open(path).read()
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    cls = next(s for s in tree.body if isinstance(s, ast.ClassDef) and s.name == "Pilot")
    # chunk i: from the line after the previous statement's end to this statement's end (1-based, inclusive)
    prev_end = cls.body[0].lineno - 1          # (the first statement keeps whatever is above it)
    chunks = []
    for s in cls.body:
        start = prev_end + 1
        chunks.append((start, s.end_lineno, names_of(s)))
        prev_end = s.end_lineno
    want = set(MOVE)
    moved, seen = [], set()
    for a, b, ns in chunks:
        hit = [n for n in ns if n in want]
        if hit:
            if len(hit) != len(ns):
                sys.exit(f"partial statement {ns}")
            moved.append((a, b, ns))
            seen.update(ns)
    missing = want - seen
    if missing:
        sys.exit(f"not found: {sorted(missing)}")
    # duplicate definitions inside Pilot of a moved name (a later one would have won)
    allnames = [n for _, _, ns in chunks for n in ns]
    dups = {n for n in seen if allnames.count(n) > 1}
    if dups:
        sys.exit(f"defined more than once in Pilot: {dups}")
    drop = set()
    body = []
    for a, b, ns in moved:
        drop.update(range(a, b + 1))
        body.append("".join(lines[a - 1:b]))
    town = HEADER + "".join(body)
    if not town.endswith("\n"):
        town += "\n"
    newp = "".join(l for i, l in enumerate(lines, 1) if i not in drop)
    old_hdr = "class Pilot(ReportMixin, GearMixin, ItemsMixin):"
    assert newp.count(old_hdr) == 1
    newp = newp.replace(old_hdr, "class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin):")
    open(os.path.join(d, "town.py"), "w").write(town)
    open(path, "w").write(newp)
    print(f"moved {len(moved)} statements ({len(drop)} lines): {' '.join(n for *_, ns in moved for n in ns)}")
    print(f"pilot.py {len(lines)} -> {len(newp.splitlines())} lines; town.py {len(town.splitlines())} lines")


if __name__ == "__main__":
    main(sys.argv[1])

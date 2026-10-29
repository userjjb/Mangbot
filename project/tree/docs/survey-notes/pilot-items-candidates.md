# pilot-items: refactor candidates

- **Flavour-learning bug (fix first).** `Pilot.learn_flavours_tick`, the "You have no more X" branch, takes
  `tv = next((tv for tv, _ in gone))`, which is any vanished unknown's tval, not X's, and pairs it with X. Evidence:
  `runs/flavours.json` has `"Amber Amulet": {"kind": "Scroll of Identify", "source": "identified or used"}`.
  `learn_flavour` never checks that the kind's type word matches the flavour's. Fix: match tval by X's type word and
  reject mismatches in `learn_flavour`. Then remove the bad entry from flavours.json (Architect, data). Risk S.
- **Item policy spread across `Pilot`.** About 1500 lines in five separate places in pilot.py (values/debt/pack around
  `has_ability`..`watch_weapons`; review around `review_state`; flavours around `load_flavours`..`loot_beside`;
  `auto_destroy`/`wear_step`; `town_sell_count`/`identify_candidates`). Candidate: an `items.py` mixin or module
  (`ItemPolicy`). Risk L (lots of `self.w`, `self.cmd`, `self.notify` coupling).
- **Junk rules in three places.** `is_junk_name` (pickup), `auto_destroy` (adds `JUNK_DEVICES`, limits tvals), and the
  `known_junk` test in the tick's itemlist scan (uses `junk_kinds` by `kind_key`). Their lists and tval limits differ
  (`JUNK_DEVICES` only in auto_destroy; food on the junk order is never auto-destroyed). One `is_junk(it)`. Risk M.
- **Repeated name normalisation.** `re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", n)).lower()` appears 12
  times (value_refusal, is_kept, pack_value, upgrade_step's `bare`, watch_abilities, identify_candidates, review keep,
  town_sell_count, ...). The `{cursed|worthless|broken|terrible}` regex appears 8 times. Two helpers. Risk S.
- **Two `light_left`s.** `Pilot.light_left` and a local `light_left` inside `wear_step`. Risk S.
- **Three tval-to-slot tables.** `Pilot.ARMOUR_SLOTS`, `Pilot.WEAR_TVALS`, `geareval.SLOT_OF_TVAL`. There are also two
  `FLAVOURED` (a dict in itemvalue, a set in Pilot). Risk S.
- **Magic number.** `pickup_room` uses `23 - len(w.items())`, but `PACK_SLOTS = 23` exists. Risk S.
- **`kinds.csv` is legacy.** It is read only as a fallback in `load_flavours` when `rulebook/kinds_by_level.csv` is
  missing. Remove it with the fallback branch, and update `harness/unit.py` (it checks for the "38 kinds of the old
  kinds.csv"). Risk S.
- **`SHOP_CUT` duplicated.** `observe/scorecard.py` has its own `SHOP_CUT = 0.38` and `est()` (kind cost x cut, its
  own junk regex) instead of `itemvalue.value` and the owner-aware `pay_cut`. Its estimates diverge from the Pilot's.
  Risk M.
- **`order pickup=none` doesn't stop `loot_step`.** It still walks to items within `loot_radius`, which the order's
  comment doesn't suggest. Gate `loot_step` on `pickup == "all"`. Risk S (behaviour change).
- **`review wear` details.** It is recorded as `"keep"` in `decided`, and in the dungeon it only marks keep and wears
  nothing, silently. Say so in the reply. Risk S.

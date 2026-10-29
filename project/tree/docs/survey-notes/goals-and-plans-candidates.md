# Refactor candidates: goals and plans (survey, session 10)

- **Light-fuel parsing duplicated ~10 times.** `re.search(r"with (\d+) turns", ...)` appears in TownFarm.tick (its
  own `left()` and own "light on" code), `Pilot.light_left` (and a second nested `light_left` inside another method),
  `supply_gate` (its own `turns()`), `lantern_fuel`, `supply_lines` and others; Recall and TownFarm wear a light by
  hand instead of `wear_light`/`best_light`. One helper (`light_left`) plus `wear_light` would do. Risk S.
- **Item-name normalisation duplicated.** `re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", name))` occurs
  15 times (Shop.tick twice, `town_sell_count`, `identify_candidates`, `kind_key_of`, ...); `kind_key_of` already
  wraps it. Risk S.
- **TownKit.tick (~210 lines) and its ad-hoc state.** Flags created on the fly with `getattr`/`__dict__.setdefault`
  (`withdrawn`, `fetched`, `farmed`, `id_bought`, `recharge_bought`, `enchant_bought`, `stashed`, `deposited`,
  `restock_waits`, `quaffed`, `recharged`, `swapped`, `fuelled`, `ate`, `room_tries`, `room_said`, ...): declare them
  in `__init__` and split the "buying" tail (wear, quaff, provision, restock wait, recharge, enchant, stash, deposit)
  into one method per step. Risk M (the live town visit depends on it; set-pieces should cover it first).
- **Shop.tick (~180 lines), HouseBank.tick (~200), TripPlan.tick (~190).** Each mixes several concerns (Shop: sale
  records, debts, flavour learning, buy remainders; HouseBank: the wilderness crossing + door dance + gold + stash;
  TripPlan: watchdogs + phases). Split per state/phase (`_trade_sell`, `_trade_buy`; `_cross`, `_door`, `_inside`;
  `_phase_down`/`_phase_level`/`_phase_home`). Risk M.
- **Two records of the stash.** stash.json `items` and house.json `items` both list the stash (today both hold "a
  Potion of Restore Charisma"); stash.json also keeps tavern `squares`, `entrance` and free-text `where`/`lost`. With
  the house as the stash, the tavern path (StashDeposit/StashFetch, `squares`) is only a no-house fallback. Make one
  file the source of truth (house.json `items`, with stash.json derived or dropped). Risk M.
- **`goal recall`'s supply gate recomputes `planned_depth()` inline** (request_goal: `want = min(md, deepest) ...`).
  Call `planned_depth()`. Risk S.
- **Goal attributes set from outside.** `role`, `by_navigator`, `by_plan`, `stop`, `estimate`, `overridden`, `abort`,
  `quiet` are attached to goal instances by the Pilot/plan; Dive keeps `scummed`/`kept` on the Pilot via `hasattr`.
  Declare defaults on `Goal` (and the Pilot's `__init__`). Risk S.
- **Stale docstrings/comments (code is right).** TownKit docstring: "an essential item out of stock gets one more look
  after 40 s" (code: up to `RESTOCK_WAITS` = 4 waits of 35 s). HouseBank docstring: "An owned town house" (it handles
  the wilderness house). `KITS` comment: rations "eaten to Full" (provision_step eats to Fed). Risk S.
- **design_pilot.md "Goals" section** lists goals that don't exist as such (`pickup`, `drop ITEM`, `fire`...) and
  `dive ... stop_on`; its header already says it's stale. Replace it with a pointer to docs/goals-and-plans.md. Risk S.

# pilot-combat: refactor candidates

- **`escaping_to_stairs` is never reset (likely bug).** It is set True in `Pilot.escape` (the out-of-melee walk to
  stairs) and set False only in `__init__`; grep shows no other assignment. After the first such walk, three things go
  wrong:
  1. `escape`'s "out of combat: rest/retreat" branch is skipped whenever any mover is active.
  2. The "if self.mover.active and self.escaping_to_stairs" branch ticks *any* active mover, e.g. an Explore path, as an
     escape walk, and takes whatever stairs it arrives on.
  3. The emergency reflex no longer stops the mover when `escape()` has nothing to do.

  Fix: clear the flag when the walk ends or the level changes. Risk M (it changes emergency behaviour; tell the Advisor:
  base_policy).
- **Split `reflexes()` (~370 lines) and `escape()` (~200 lines).** Make each numbered step its own method (`arrival_tick`,
  `danger_flee_tick`, `fear_tick`, `still_tick`, `hunger_tick`, `adjacent_tick`, `rest_tick`) and keep the order in one
  list. The step numbering in comments is already inconsistent ("3a'" is used twice, and 3b sits before 3a''). Risk M
  (the order is behaviour; the Advisor mirrors the escape order by function names: POLICY_VERSION comment).
- **Duplicated item lookups.** `next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)` appears
  7×, sometimes with `w.tagged("r", 1)` first and sometimes not. "Word of Recall" appears 6×, and potion lookups by name
  many times. One `find_item(kind, tval)` helper and one `phase_item()` that always honours `@r1` would remove the
  inconsistency (the fear and fearer phases ignore `@r1`). Risk S.
- **Three `light_left` helpers.** There are `Pilot.light_left` (static; counts a lantern without "turns" as 1), a local
  `light_left` in `wear_step` (counts it as 0), and a local `left()` in `keep_light`. Merge them into the static one.
  Risk S.
- **Inconsistent supply notice kinds.** `low_supply` (hunger recall, light), `supply` (`food_watch`) and `supplies`
  (`supply_watch`) say similar things. `food_watch` overlaps `supply_watch` (food minutes). Merge them into one kind and
  one watch. Risk S (check the viewer and HANDBOOK for the kind names).
- **`emergency_loop` counts every `emergency` notice**, including the non-actions "waiting to use … fighting on" (every
  10 s), "potions too weak: escaping instead" and `kill_caster_step`'s "attacking X first". Count escape actions instead
  (e.g. from `log_escape`/cures). Risk S–M.
- **Dead condition in `choke_tick`:** `ch in "<>" and False` is never true. Remove it. Risk S.
- **`escape()` docstring is stale.** It lists only the stairs, rest, phase, walk and cure steps, and omits one-turn
  teleport, Speed, WoR, futility, kill-caster and crowd teleport. Risk S.
- **Misplaced:** `light`, hunger and pickup/auto-destroy live inside `reflexes()`, though they are not combat. Pickup
  calls item-policy code in the middle of the safety stack, so move it to `policy_tick`. Also, `food_watch` is called
  from `track_gains` (XP/gold tracking, every 15 s), not with the other watches in `tick()`. Risk S.
- **`Recover` docstring** says it takes the stairs again "if threatened (the arrival rule)". That is done by the reflexes'
  arrival rule, not the goal itself. Risk S.

# gear-and-estimator: refactor candidates

- **Shadow snapshot passes the weapon's own to-hit/to-dam, not totals.** `shadow.weapon_profile` parses "(+h,+d)" from
  the weapon name; the Advisor's contract (memo 2026-10-28 §4) says `tohit`/`todam` are totals. geareval's `sim_player`
  passes totals (STR, rings, gloves). The estimator underrates our damage (Dive04's rings/gloves/STR to-dam missing).
  Fix: build the shadow snapshot from `gear_character().derive()` (or the sheet's to-hit/to-dam). Risk S-M (changes
  estimator answers; shadow only).
- **Duplicate snapshot builders.** `Pilot.shadow_decision` and `Pilot.gear_character` both count the consumables
  (identical `n(word, tv)` helper, staff-charges regex, the same inv dict); `shadow_decision` also re-derives resists
  via geareval's tables. One `consumables_inv()` helper. Risk S.
- **Stale text in code.** `loadout_info`'s header says "Slays, brands and criticals aren't simulated" -- they are since
  options_sim 27k (`sim_player` passes slays/brands/weight). geareval's module docstring says the loadout optimizer is
  "not built yet", the simulator models "not elemental resists", and the score is "XP per turn" -- all outdated.
  Risk S (text only).
- **optimize's keep-set vs compare's no_loss disagree.** `optimize` keeps NO_LOSS + REQUIRED + RES_/IM_ flags, but
  `compare(no_loss=True)` with TRADE_RESISTS off rules out losing *any* flag (SUST_*, feather fall, regen, telepathy,
  slow digestion). Loadouts losing a sustain are simulated and then ruled out with the message "an automatic swap
  never does" (misleading in the advisory `loadout`). Share one predicate. Risk S.
- **replay_group.py is dead.** No caller (grep over tools/, hooks, scripts); a one-off tuning script with a hard-coded
  path to `tools/pilot/danger_table.csv` (legacy). Move to a `tools/attic/` or delete. Risk S.
- **Weapon-profile parsing duplicated.** Name regexes for dice and (+h,+d) appear in `shadow.weapon_profile`,
  `Pilot.fight_sim`, `Pilot.fight_estimate`, a top-level helper near `shadow_agree`, and `geareval.Item`. Use
  `geareval.Item` everywhere. Risk M (fight_estimate/hunt checks depend on it).
- **Gear code placement.** pilot.py holds ~400 lines of gear/estimator glue (`gear_line`, `gear_review`, `jewel_gives`,
  `armour_ac`, `gear_character`, `gear_eval`, `loadout_info`, `gear_better`, `shadow_decision`, `shadow_results`,
  `band_shadow`, `hard_fight_shadow`, `fight_*`): a natural `gear.py` mixin and an `estimator.py`/shadow mixin for the
  pilot.py split. Risk M.
- **damage_mix range is fixed at 700-800 ft.** `wrap.sh` runs it with defaults, whatever the depth the character now
  plays; EHP will use a stale mix when diving deeper. Pass the current depth band. Risk S.
- **`encounters()` reads the whole decision log every evaluation** (no `since` passed; Dive04's log is large), and the
  met set can include fights from much earlier in the character's life. Pass a `since`/tail-read like `why_info`.
  Risk S.
- **`gear_review` vs `upgrade_step`/`gear_line` static AC rules** overlap (three AC-only "better than worn" checks:
  gear_line, gear_review shop ideas, upgrade_step step 3) with slightly different guards (ability subset vs flags-grid
  letter). Consider one static comparator. Risk M.

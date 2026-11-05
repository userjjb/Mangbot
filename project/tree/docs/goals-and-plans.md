# Goals and plans

The Pilot (`github/tools/pilot/pilot.py`) plays second to second, but what it is *trying to do* is held in one
**goal** at a time: a small state machine (walk to a place, dive to a depth, shop, bank gold, wait quietly...) that
the Pilot ticks whenever its reflexes and item policy have nothing more urgent to do. Above the goal sits an optional
**plan**: `plan trip` (a `TripPlan`: down, level after level within a depth range, home when a condition holds) and
`plan town` (the `TownKit` goal: the whole town visit by policy). The Navigator sets goals and plans through
`pilotctl`; the Pilot also sets goals itself (escapes, recalls). This file catalogs every goal, both plans, the town
kit's shopping rules, how supplies are measured, the gold bank and the stash, and the state files they keep.

Related: the tick loop and reflex order are in [pilot-core.md](pilot-core.md); the escape/fight goals in detail in
[pilot-combat.md](pilot-combat.md); what is sold, kept, identified and worn in [pilot-items.md](pilot-items.md);
the `pilotctl` syntax of every command in [commands.md](commands.md).

Where the code is (E1 step 2): `Goal` and the dungeon goals in `tools/pilot/goals.py`, the town goals (`Town`,
`TownFarm`, `Shop`, `StashDeposit`/`StashFetch`, `HouseBank`, `TownKit`) in `town_goals.py`, `TripPlan` in `plan.py`;
`pilot.py` imports the ones it uses back (`Goal`, `Flee`, `TownKit`, `TripPlan`...; not `Goto`, `Recover`,
`BandLeave`, `Resurrect`, `RestGoal`, `TownFarm`), so read `pilot.py: Goal` below as `goals.py: Goal`. The `Pilot` methods the town visit uses
(E1 step 4) live in `town.py` as `TownMixin`, still `Pilot`'s names (`Pilot.town_needs` below is one): the kit's tables
(`STORE_NUM`, `STORE_LABEL`, `BUYERS`, `KIT_ITEMS`, `KIT_CAP`, `KITS`, `SUPPLY_STAGES`, `FUEL_LAMP`/`FLASK_FUEL`/`FILL_SLACK`,
`PACK_SLOTS`, `BANK_FLOAT`...), the shopping list and gold (`town_needs`, `town_shopping`, `town_reserve`,
`price_of`, `note_store`, `buy_store`, `stock_table`), selling (`town_buyers`, `town_sell_count`, `town_sells`,
`town_sell_stores`, `is_crutch`), `town_make_room`, `provision_step`, `kit_count`, `lantern_fuel`, `flasks_to_fill`,
`flasks_spare`,
`trip_minutes_left`, `provisions_spare`, `planned_depth`, `restore_item`/`restore_for` (2.50.0: potions and restore mushrooms), Identify/Enchant/Recharging
(`identify_candidates`, `town_identify_wanted`, `enchant_plan`, `weapon_enchant_plan`, `enchant_buys`,
`recharge_wanted`, `town_extras_note`...),
`supply_gate`, `supply_minutes`/`supply_text`/`supply_watch` (`TURNS_PER_DMIN`, `FOOD_MID`), the house and the stash
(`house_state`, `house_save`, `retire_stash_json`, `banked`, `stash_places`/`stash_where`/`stash_has`/`stash_take`/
`stash_wanted`, `is_stash_item`, `tavern_state`/`tavern_entrance`; 2.50.0: `stash_backups`/`stash_backup`/`backup_item`,
`on_store_list`, `stash_reason`/`stored_reason`, `stash_room`, `stash_fetch_list`, `stash_stored`, `stash_rec`, the
acquisitions `acq_state`/`note_acquired`/`acquired_fresh`, `stash_credit_sold`/`stash_credit_worn`), `note_town_stairs`, `note_edge_cross`/`edge_dir`.
The commands that reach them (`plan town`/`plan trip`: `request_plan`/`request_trip`, `request_goal`, `house_info`,
`price_info`) are in commands.py (`CommandsMixin`, E1 step 6; commands.md); `plan_tick` is still in pilot.py.

## What a goal is

- **Class shape.** A subclass of `pilot.py: Goal` with a `name` (what `describe()` returns: shown in reports, logs
  and `plan` output) and `tick(p)`, called with the Pilot. `tick` returns `None` while running, or a pair
  `(status, detail)` to end: `"done"`, `"failed"`, or (only `Dive`, when something interesting turns up)
  `"interesting"`. A goal keeps its own state in attributes; most are re-entrant per tick (no threads, no sleeps:
  they send one command with a `hold` and come back later).
- **Long ticks, one method per step** (refactor-candidates E5). `Shop`, `HouseBank`, `TownKit` and `TripPlan` split
  their `tick` into step methods `(self, p, ctx)`: `ctx` is a per-call namespace with what the steps share (`w`,
  `now`, and values a step computes for later ones, set where the old code computed them); a step returns `NEXT`
  (`town_goals.NEXT`) to go on, or what `tick` returns. A **state machine** whose states each end the tick dispatches
  on its state attribute (`Shop.STATES`, `HouseBank.STEPS`); one whose stages fall through to the next in the same
  tick runs an ordered tuple whose steps test their own stage or phase (`TownKit.KIT_STEPS`/`BUYING_STEPS`,
  `TripPlan.TRIP_STEPS`). The flags these classes used to create on first use (`getattr(self, "x", default)`) are
  declared in `__init__` with those defaults (so `goalstate`, which shows `vars(goal)`, lists them from the start).
  The tables and the method names are given with each class below; `unit.py`'s `town_plan_step_tables` (in `unit_structure.py`) checks that they
  name existing methods.
- **One at a time.** `Pilot.set_goal(g)` replaces the current goal (stopping the mover), stamps who set it (`role`:
  navigator / architect / pilot, read by `goal_origin` for the viewer and debts) and logs a `goal` record.
  `set_goal(None)` is the safe idle.
- **Ticking.** `Pilot.tick` runs reflexes, the park check, the Navigator's `react` rules, the item policy, *then*
  `step_goal()`; if no goal ran the plan gets its turn (under a goal it is ticked every 2 s, for its conditions),
  then `idle()`. While blind or confused, `Explore`,
  `Search` and `Dive` are paused (steps go astray). An exception inside a goal ends it as `failed: error: ...`; a goal
  given an `abort` attribute fails with that text on its next tick.
- **Ending.** `step_goal` clears the goal and notifies `goal_done` / `goal_failed` (an alert that wakes the
  Navigator's `wait`), except: goals marked `quiet` and goals the plan set (`by_plan`) end as news only. Special cases:
  if an emergency interrupted a goal (`Pilot.resume_after`), that goal is put back and a `resumed` news item is
  posted; a `Hunt` that fails because its target "blinked away" becomes a `Reprieve`; a failed `flee`/`leave` calls
  `flee_failed` (a `BandLeave`, or Word of Recall plus Phase Door with monsters close).
- **Who sets goals.**
  - The Navigator (or Architect) with `pilotctl goal NAME ARGS` (`Pilot.request_goal`), `plan town` (`TownKit`) and
    `house buy|deposit|withdraw` (`HouseBank`). Positional orders (`goto` other than `goto <`/`>`, `fetch`,
    `searchroom`, `hunt`, `avoid Y,X`) are refused if they answer a report from a level since left, or, when the
    report is over 5 s old, (`hunt`) the monster isn't in view, or (`goto`/`fetch`) HP fell by more than 25% of
    max HP since the report (`Pilot.stale_order`). A goal given while a trip plan runs
    **pauses the plan** until it ends (`plan resume` ends it early).
  - The trip plan sets its goals itself, marked `by_plan` (`TripPlan.mark`).
  - The Pilot's reflexes: `Flee` (danger, groups, emergency loop, unseen attacker, stat drain, the Navigator's
    `react leave`), `WalkAway` (a summoner seen at range), `BandLeave`, `Recover` (after a stairs escape), `Hunt`
    (a drainer it can beat), `Recall` (dangers, and `idle()`: no goal, no plan and no word from the Navigator for
    `idle_recall_s` = 600 s in the dungeon).

## The goals

"Set by" gives the `pilotctl` syntax where there is one (details in [commands.md](commands.md)).

| Class | Set by | Parameters | Behaviour | Ends |
|---|---|---|---|---|
| `Wait` | `goal wait [SECS]` (default 5); plan and TownKit internally | secs | does nothing | done when the time is up |
| `Goto` | `goal goto TARGET [force]` (the Architect's; the Navigator is told to use `goal leave`/`fetch`), `goal fetch Y,X` (with band/danger refusals) | target: `<`, `>`, `stairs`, `item` (nearest non-junk item glyph), or `Y,X`; `force` | paths there (`Pilot.resolve_target`, mover; may path through unexplored squares and says so). **Holds** (doesn't walk) while a dangerous monster is adjacent or a faster monster hit us in the last 2 s, unless `force`: walking away gives free hits. Arriving on an item, waits up to 1.5 s for the pickup | done on arrival; failed: no such place, no path, stuck |
| `Explore` | `goal explore [until=stairs\|upstairs] [radius=N]`; Dive; the trip plan | until, radius, skip (stairs not to count) | dungeon only; refuses below `max_depth` unless looking for stairs. Walks to the nearest frontier (known floor next to unknown), running along corridors and across dark rooms, looting on the way (`loot_step`); avoids drainer and avoid zones; digs rubble that borders the unknown; with no frontier left searches unsearched corridor dead ends (`Search(strict, 15 tries)`) | done: stairs seen (with `until`), or "nothing left to explore" (lists inner rooms not opened: `goal searchroom`); failed: frontier unreachable, or on the surface |
| `Dive` | `goal dive [FEET] [scum] [force]` (default one level down); the trip plan | target_ft (capped by `max_depth`), scum | stair-scums: on a level with the wanted stairs known and reachable, walks there and takes them (2.54.0, m64: with no known path, one through unexplored squares -- `mover.go(..., unknown=True)`, replanned as they come into view, as the flee does; known traps and avoid zones as before, and the 2.53.0 zone hold when a zone alone blocks them; **2.67.0,
the user after m69: before such a walk it searches the best corridor dead end -- a 2-wide one first (a 2-wide corridor
never just stops: a secret door's giveaway, `Search.wide_dead_ends`), else a walled 1-wide one pointing toward the
stairs; one pointing toward them first, then by its distance plus its distance to the stairs; within 40, at most 2 a
level, `WIDE_TRIES` = 20 searches; news "a 2-wide corridor dead-ends at Y,X: searching for a secret door before walking
through unexplored squares..."; then walks on, by a known way if the search opened one** (`search_wide_end`); **2.68.0 (m69 09:26: 20 searches at each
of two 2-wide dead ends found nothing, the doors were there): a door detector comes first -- from where it stands when
no detection on this level covered its surroundings (the arrival zap may have been far off; `DETECT_CAP` 3 a level),
with news; a dead end a detection covered is not searched (a secret door there would show), and the walk goes on**); standing on the other kind, takes them for a fresh level (not on a level the server keeps: then explores); else uses a Door/Stair Location device once, else explores for stairs (then searches dead ends; 2.54.0: with the wanted stairs known but out of reach, `Explore(toward=...)` tries the frontier nearest them first, within `TOWARD_SLACK` = 3 of the nearest). Puts the light on leaving town; loots what's close; explores pillared rooms (`order pillared`); refuses for FLED_HOLD (120 s, live server only; 300 s on a kept level) stairs back to a level just fled. On a climb never takes a `>` unless `scum`. Gate: going deeper checks `supply_gate` (overridden by `force`) | done: reached the depth; `interesting` on a new level when `p.interesting()` fires (not for plan dives); failed: no stairs after exploring and searching |
| `Search` | `goal search`; `goal searchroom Y,X` (an inner room's 4 door spots, 20 tries) | tries (8), strict, spots, wide | stands at each dead end / corridor end / given spot, nearest first, searching once a player turn; 2.67.0: 2-wide corridor dead ends (`wide_dead_ends`: two floor lines ending side by side against wall, walled both sides 3 squares back) first, `WIDE_TRIES` = 20 searches each (a warrior searches poorly); 2.68.0: at a 2-wide dead end a door detector first (`door_detect`, from where it stands when the dead end is within its range), a rod recharging within `DETECT_WAIT_S` = 30 s waited for; a dead end a detection covered is skipped ("detected" in the summary); searching only with no detector | done "found a way on" when a new door or opening appears (summary lists spots and searches); failed: all spots searched |
| `Hunt` | `goal hunt NAME` (checked by `hunt_refusal`: the HP rules on `fight_sim` at the gear model's to-hit/to-dam totals, 2.45.0, and a disenchanter refused when its expected enchantment loss is more than a kill brings, 2.45.1 -- pilot-combat.md §5; `!NAME` overrides into the fight debt; each taken hunt logs a `hunt` record); reflex | name, lost_s 15 | walk next to it, let auto-retaliate fight (see pilot-combat.md) | done slain; failed lost sight / blinked away |
| `Recover` | reflex after a stairs escape | came_by, prev goal | rest on the stairs, go back up if past `max_depth`, then resume (pilot-combat.md) | done healed |
| `Reprieve` | after a Hunt's target blinked away | who | rest out of its sight, or leave if mortal danger is near (pilot-combat.md) | done healed / 2 min |
| `BandLeave` | `flee_failed` for a band at high HP | names | find stairs with Door/Stair Location or Magic Mapping, else walk out of sight (pilot-combat.md) | done/failed; a second failure recalls |
| `WalkAway` | reflex: a summoner in view | names | walk out of its sight over walked ground (pilot-combat.md) | fails to the flee rules when it closes in |
| `Flee` | `goal leave`; reflexes; the trip plan for a band | why | to the nearest known stairs and take them (pilot-combat.md) | done on the new level |
| `Recall` | `goal recall [force]`; reflexes; the plan | depth_ft (from town: the depth to inscribe; default `max_depth`) | in town first inscribes `@R<feet>` on the scroll (the server reads the recall depth from it; checked by parsing, 3 tries); puts a light on (no light, no reading); cures blindness/confusion with the cheapest potion; doesn't read a second scroll if one is already under way; reads one; while it charges, rests if hurt and nothing is in view (time runs ~10x resting). From town, `goal recall` checks the supply gate for the planned depth (2 Words of Recall) unless `force` | done when the level changed *and* the recall flag cleared; failed: no scroll, can't inscribe, nothing after 120 s (60 s if never pending; quotes the game's reason) |
| `Resurrect` | `goal resurrect` (the only goal a ghost may give; read-only commands still work) | - | a ghost: `<` anywhere, one level a press; in town walks onto the Temple entrance (`4`), which resurrects (costs half the experience) | done resurrected; failed: no Temple on the map |
| `Town` | `goal town`; the plan | - | from the wilderness back to town: walks off each sector by the edge it came in through (`Pilot.wild_trail`); 2.59.0 (the user: "look at our position relative to town on the overworld map"; m66: after a hot-swap, inside the house, it failed "don't know which edge leads back" ~130 times) without a trail, by the sector's world offset from town (`common.world_xy`, the inverse of the server's `world_index`, wilderness.c:44: ring r = |x|+|y|, base 2r(r-1)+1, offset r-y for x >= 0 else 3r+y, level -(base+offset); -1 north, -2 east, -3 south, -4 west): west/east while x isn't 0, then south/north (`edge_home`), recomputed after each crossing; inside the owned house, out by its door first (`leave_house`, house.json); last, `edge_of` the arrival square. The trip plan stops re-issuing it after 3 identical failures (`reissue_ok`: Word of Recall once) | done in town; failed in the dungeon or edge unknown |
| `TownFarm` | `goal townfarm GOLD [MINUTES]` (default 10); TownKit when broke | target gold, minutes | in town: light on, then chase thieves within 8 squares first (item thieves before gold ones, hitting them directly), walk over dropped gold, kill the gold-dropping townspeople (`TARGETS`), else sweep the town in a zig-zag | done at the target, time up, or no gold gained in 2 minutes (townspeople thinned out / night) |
| `Shop` | `goal shop N [list] [buy NAME:N[@MAX]] [buy NAME:+N] [sell NAME\|LETTER:N] [quote NAME]`; TownKit | store number, buys `(name, n, cap)`, sells `(index or name, n)`, list_stock | walks next to the door (unseen squares count, for night), enters, then: sells (from the end of the pack first; names resolved when their turn comes) with the item policy's refusals (unknown items, value policy, "probably special"; `!NAME` forces and the value lost goes into the Navigator's debt), learns a flavour sold unknown, logs a `sale` record with the re-listing price; quotes (offer and decline); buys the **cheapest** matching line, within the cap and the gold, continuing at the next price if the cheap stack runs out. `NAME:N` in `goal shop` means *have* N; `:+N` buys N more. Re-enters (twice) if its own command closed the store. In code: `STATES` -> `_walk`, `_enter`, `_trade`; the trade runs `TRADE_STEPS` (`_trade_record` the last sale's record, `_trade_quote`, `_trade_answer`, `_trade_left` back in or thrown out, `_trade_list`, `_trade_sell`, `_trade_fresh` a remainder's wait, `_trade_buy`, `_trade_leave`), one acting a tick | done with a log of what happened; failed: not in town, store not on the map, can't reach, stuck, thrown out |
| `StashDeposit` | TownKit: no house, or (2.50.0) the overflow of a full house | - | drops each stash item (below), the most valuable first, on an empty square **inside** the tavern room (farthest from the door first; never the entrance square: it holds no object, and drops from it land on the street where townsfolk take them); records square -> the record (2.50.0: `stash_rec`) in house.json `tavern.items` | done when none is carried; failed: no empty square seen inside |
| `StashFetch` | TownKit, for a drained stat's Restore in the tavern (2.50.0: or a stored backup to wear or sell); `house withdraw ITEM` | kind (or full name) | lights up, walks the squares within 4 of the tavern entrance (item glyphs first) until the pickup reflex (`p.fetching`) takes the kind | done when in the pack; failed: none left / no tavern |
| `HouseBank` | `house buy [Y,X]` (Architect only), `house deposit [KEEP]`, `house withdraw [ITEM]`; TownKit | mode buy/deposit/withdraw, keep, house, fetch (2.50.0: stored items to bring out by name) | see "The gold bank" below | done: "N gold in the house, M carried" |
| `TownKit` | `plan town ...`; a trip plan with `then town` | kit, buylist | the whole town visit: see "plan town" below | done with a summary; failed outside town (the house's wilderness tile excepted) |
| `RestGoal` | `goal rest` | - | rests until HP >= `rest_to` (0.95) and SP full | failed if monsters are in view |
| `QuietWait` | `goal quiet [SECS]` (10-600, default 120; refused with a moving monster in view); `ask quiet` | secs, prev (the goal it replaced) | time for the Navigator to think: pauses the plan or the replaced goal, caps the wait at a quarter of the food/light minutes left, walks to a `quiet_spot` (a room on walked ground, away from doors and the unknown), rests if hurt, waits. In town it just waits | ends (alert `quiet_end`, then the paused goal or plan resumes) when a moving monster comes into view, something hits us, the Architect answers the `ask quiet`, or time is up |

## The trip plan (`plan trip`)

`plan trip LO-HI [until "COND or COND ..."] [then recall|town] [level_min=N] [via=stairs|recall] [force]`
(`Pilot.request_trip`). LO/HI are feet, multiples of 50 (LO at least 50); HI may not exceed `max_depth` (raise it with `order` first).
Defaults: `until "cures<3 or phase<3 or minutes>45"`, `then recall`, `level_min=10`. `TripPlan` is not a goal: it
sits above the goals in `Pilot.plan` and is ticked by `Pilot.plan_tick` every tick when no goal runs, and every 2 s
under a goal (to check the conditions). Its own goals are marked `by_plan`; their ends are news only.

**Conditions** (`TripPlan.parse_until`): `VAR OP N` with OP in `< > <= >= =`, joined by `or` or commas.

| var | meaning |
|---|---|
| `cures` / `ccw` / `csw` / `clw` | Cure potions carried (all three / each kind) |
| `phase`, `wor` | Phase Door, Word of Recall scrolls (`wor` is ignored until the trip has gone down; `wor<N` for N ≥ 2 and `wor<=N` for N ≥ 1 are refused, since they hold with the one recall kept for coming home; `wor<1` and `wor<=0` are allowed but redundant: "no Word of Recall left" is built in -- A18, 2.39.0) |
| `food` | rations (`kit_count`) |
| `hp` | HP percent |
| `minutes`, `dmin` | minutes since the plan was given / since it first reached the dungeon (2.61.0, the user: not counting the time the test server was frozen -- the wall clock less `Pilot.frozen_between`, the freeze ledger in `frozen.json`, so a restart or hot-swap keeps it; `unfrozen_min`) |
| `time` | wall clock `HH:MM` (the next such moment after the plan started; across midnight); 2.61.0: shifted by the time frozen since the plan started (`frozen_since_start`), so a freeze moves it on |
| `clvl`, `gold`, `free` (pack slots free of 23), `levels` (levels worked) | |
| events | `band` (only while the band is live: `Pilot.band_live`), `drained`, `emergency`, `emergency_loop`, `danger`, `pack_full`, `unique_slain`, `unseen_attacker`: counted since the plan began from the Pilot's notifications (`TripPlan.on_event`) |

Always added: "no Word of Recall left" and "90 minutes". In town (unless `force`) the **supply gate** for
`min(HI, max(LO, deepest))` is checked first, needing 2 Words of Recall when going down by recall and 1 by the stairs.

**Phases** (`TripPlan.tick`, `phase` attribute; `step` is the human-readable sub-step shown by `plan`):

1. **down.** In town: down by the stairs (`Dive(LO)`) if `via=stairs`, or (no `via`) when the target is at most
   150 ft or the character has never reached 250 ft (`stairs_down`); else `Recall(depth)` to
   `min(HI, max(LO, deepest))`, one level above HI when the range allows (both stairs lead somewhere useful), and
   never deeper than the deepest level reached (a `Dive` then goes the rest of the way). In the
   wilderness: `Town` first. Arriving in the dungeon starts **level**.
2. **level.** Outside LO-HI: a `Dive` into range. On each new level: the **arrival protocol** (after a recall, or a
   "something special" feeling, use Door/Stair Location once; on a special level `Explore(until=stairs)` first),
   then `Explore()`. A level is **done** when its exploration ends, after `level_min` minutes, when it's **quiet**
   (under 10 XP a minute over the last 3 minutes, nothing in view: `TripPlan.quiet`), or when a **bad level**
   notification arrives (`LEAVE_ON`: band -> `Flee`, unless `band` is an `until` condition, which brings the trip
   home instead; pit/nest, breeders, a STR/DEX/CON drainer, a fearer, trap-laden -> the next dive). The next level is `Dive(depth+50)` while above HI, `Dive(depth-50)` at HI (a fresh level). Pinned
   by breeders while leaving: one teleport. Watchdogs: more than 6 failed leaves -> home; a done level not left within
   `LEAVE_MAX` (300 s) -> recall home (if a Word of Recall is carried).
3. **home** (a condition held, an escape recall is under way, or a watchdog). Within 150 ft: climb by the stairs
   (`Dive(0)`, saves a scroll) for up to 3 minutes; else `Recall()`; with no scroll, climb. A plan dive home that
   finds no way up in 3 minutes switches to Word of Recall. A recall already pending (the Pilot's own escape) is waited
   for with `Wait(3)` goals, and the reason is reported. More than 10 failures: plan **failed**.
4. **town** (`then town`): runs `TownKit()`; when it ends, the plan is **done**.

In code (E5), `TripPlan.tick` runs `TRIP_STEPS` in order, the first that ends the tick winning: the watchdogs first
-- `_trip_xp0` (the trip's XP base), `_trip_paused` (a Navigator's goal pauses it), `_trip_recall_pending` (a recall
under way: wait; an escape's recall means home), `_trip_until` (a condition holds: home), `_trip_climb_watch` (3
minutes climbing: Word of Recall), `_trip_level_time` (`level_min`), `_trip_leave_max` (`LEAVE_MAX`), `_trip_quiet`,
`_trip_goal_running` (a goal running: stop here) -- then one method per phase, each testing `self.phase`:
`_phase_down` (which sets **level** on reaching the dungeon, so `_phase_level` runs in the same tick),
`_phase_level`, `_phase_home`, `_phase_town`.

The plan ends **done** at home (`then recall`), after the town kit (`then town`), or if the character turns up in
town by another route (an escape recall: the reply names it and points to `why`). On end it logs `plan_end` and
notifies `plan_done` / `plan_failed`. `plan` shows it (2.51.0: `describe` adds `end_text`, the soonest clock end --
`minutes>N` from the start, `dmin>N` once in the dungeon, `time>HH:MM` -- as "ends ~09:46 (minutes>33)", on the
report's Plan line), `plan stop` (or `stop`) ends it, `plan resume` ends the
Navigator's pausing goal. The Pilot's reflex goals (flee, recover, recall) replace a plan goal without pausing the
plan; while a plan runs (not paused) `idle()` never recalls. `Pilot.trip_minutes_left` (from the recall, the `minutes`/`time`
conditions and the 90-minute cap) tells the item policy when spare rations and flasks can go (`provisions_spare`:
within 3 minutes, or 20 when Full).

## Avoid zones that block the way (2.53.0)

The user (after m63, where a dark inner room's zone covered its ring corridor and the only '<' at max_depth, and the
trip recalled): "When an avoid zone blocks the Pilot's path, but the Navigator has time to evaluate the situation,
allow it to decide if it should path through or not." `Dive` (both its stairs walks) and `Explore` (the frontier) ask
`Pilot.zone_hold(tiles, what)` before giving up on tiles they can't reach. `zone_blocks(tiles)` plans with the avoid
zones ignored (`mover.plan` with `World.avoid_zone` emptied): a path means the zone alone blocks them. With time
(`zone_time`: nothing dangerous in view, not hit for 8 s, HP >= `think_hp`, no Flee/Recall/Recover goal, no recall
pending) the Pilot holds -- the goal returns nothing, the Pilot walks to a `quiet_spot` -- and raises `zone_blocks`
once (fields `to`, `len`; logged `zone_hold`): what is blocked, the structures the path crosses, its length and the
choices: `avoid pass` (`zone_pass`: `avoid_tick` takes the structure's 13 x 27 surroundings out of the zone and keeps
its inner block, Y-3..Y+3 x X-10..X+10, in it), `avoid clear`, `goal recall`/`goal leave`. No answer within
`ZONE_WAIT_S` = 90 s (a Navigator turn is 20-60 s after its wait report: one or two turns), or no time any more: the
goal goes on as before (the stairs marked unreachable; the trip recalls). The trip plan's leave clocks (`LEAVE_MAX`,
the 3-minute climb) leave the hold out (`zone_hold_spent`, at most 90 s a level).

## Queued plans (2.53.0)

A Navigator's `plan trip` or `goal ...` sent while a `TownKit` runs (its `plan town`, or a trip's `then town`) is
queued (`Pilot.queued`, commands.py `do_request`) instead of replacing it -- m63's `plan trip` 6 s into plan town cut
the house visit short. The reply names plan town's stage (`town_stage`); `plan` shows the queued request, `stop` and
`plan stop` drop it; `queue_tick` (in the act layers, after the item work) runs it once no TownKit runs and no trip is
in its town phase, telling the Navigator (`queued`: news if it started, an alert if it was refused). **2.65.0 (m68
00:05):** one queued behind a trip's own `then town` visit starts at that trip's end, before the `plan_done` goes out,
and the `plan_done` says so ("... -- your queued `plan trip ...` started", or refused and why): the Navigator, woken by
the plan_done a tick before the queue ran, read the trip as dropped and sent it again (`start_queued`).

## The town visit (`plan town`)

`plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@MAX],...]` (`Pilot.request_plan`), town only. Each buy spec: STORE
1-7 optional (else the rulebook's `shop_stock.csv` via `buy_store`, a shop listing seen, or the kit table), `NAME`
with `_` for spaces, `:N` = **have** N in all, `@MAX` a price cap each. The reply forecasts what it will buy at the
prices last seen, what it can't afford, and the extras (`town_extras_note`: Enchant Armor, Enchant Weapon To-Dam /
To-Hit and Recharging scrolls).
It starts a `TownKit` goal, which works through **stages**, one sub-goal (`Shop`, `HouseBank`, `StashFetch`,
`TownFarm`, `Wait`) at a time, settling 1 s between steps. Its Shops act as the Pilot (`role = "pilot"`: the sale
rules' role -- `value_refusal`, a forced sale's debt, the override check; a buy-only Shop reads none):

1. **upgrade**: first `HouseBank("withdraw")` if a house holds gold or the Restore a drained stat wants, or (2.50.0)
   stored items `stash_fetch_list` names -- a stored backup the gear policy would wear (its slot empty, or
   `gear_better` over a damaged piece) and one a carried backup now outclasses (fetched so the shops sell it) --
   (**withdraws first**); else `StashFetch` that Restore (and those items) from the tavern; then wear what the gear
   policy prefers (`upgrade_step`).
2. **sell**: one `Shop` per store that buys something the policy sells (`town_sell_stores`, `town_sells`), in store
   order; a store is revisited once if a sale taught an unknown flavour (the rest of the stack then sells).
   (2.48.0, the user) This stage runs before the buying stage's recharge and enchant steps, so `town_sell_count`'s
   exemption is what protects a Scroll of Enchant or Recharging the kit would read (`scroll_use`); a fallback
   (Boldness) is kept while its kit kind (Heroism) is short, and the stopgaps are sold (Satisfy Hunger; CLW in kits B
   and C; torches beside a lit lantern; mushrooms but the restoring ones; on the test server, Magic Mapping scrolls):
   pilot-items.md, "Fallbacks, stopgaps, crutches".
3. **identify** (2.55.0, the user after m64: "identify everything other than weapon/armor with a pseudo-ID already"
   -- clarified: only gear felt {average}/{worthless}/{cursed}/{broken} is sold by its feeling; felt
   {good}/{excellent}/{special} gear is identified too -- every `must_identify` item counts, whatever its value, and is kept, not sold, until identified; with gold for
   fewer scrolls than unknowns, the most valuable by expectation go first and the rest wait for the next visit; the
   upgrade stage first drinks any stat-gain potion carried, `quaff_gain`): read Identify scrolls on the candidates
   (`identify_step`, pilot-items.md); buy more at the Alchemist
   (5) for the unknowns worth it: `town_identify_wanted` counts unknown items whose expected sale value is at least
   twice the scroll's price (ability sources and likely-irreplaceable items always count), limited by gold beyond
   `town_reserve`, capped at 1.5x the price. Staff of Perception charges count as Identify scrolls. If anything was
   identified: **upgrade again** and **sell again**.
4. **buy**: if `broke_for_recall` (fewer than 2 Words of Recall and not the gold for one) and it's day, `TownFarm`
   for 5 minutes, to the gold now plus the price of the missing Words (+20) (at night it saves the gold instead). Then `town_shopping` turns the list into buys,
   `town_make_room` frees pack slots for new kinds (sells the least valuable unprotected item, else destroys it; 6 tries),
   and the stores are ordered by the highest-priority line each holds.
5. **buying**: one `Shop` per store; then wear what was bought; quaff a Restore bought for a drained stat
   (`restore_potion`); `provision_step` (wear the fuller lantern, fill it to full from the flasks bought for it,
   `flasks_to_fill` -- 2.49.0, the user: oil is cheap and fuel past 15000 just caps; was: up to 9000 turns --
   eat rations while Hungry or worse, up to 3, to Fed); **restock waits**: if a critical item (the gate's minimums, a
   Restore for a drained STR/DEX/CON) is still missing and a shop said "no ... in stock" (not of a fallback), `Wait(35)`
   and redo the buy stage, up to `RESTOCK_WAITS` = 4 times; **fallback** (2.48.0, the user's principle A): a kit kind
   still under the kit's target after that (Heroism: none in stock, over its cap, or not the gold) gets its fallback
   for the shortfall less the fallbacks carried (`fallback_buys`: Boldness at the Temple, cap 1.5x its price, within
   the gold beyond `town_reserve` at 110%), once; not when the Temple's listing seen this visit had none; **recharge** each `recharge_wanted` device with a Scroll of Recharging
   (bought once at the Alchemist, cap 1.5x; a carried scroll is read first); **enchant** worn armour per `enchant_plan` with Enchant Armor scrolls,
   and (2.46.0) the wielded melee weapon per `weapon_enchant_plan` with Enchant Weapon To-Dam and To-Hit scrolls --
   the same rule: while the next point is >= 50% (half the chance on an artifact), to about +8; never the bow, nor a
   weapon whose plusses aren't shown. One read a tick, the scroll read onto the piece (`custom r item=S dir=T`, T the
   worn item), armour first, then the weapon's to-dam, then its to-hit. The scrolls are bought once, in one Alchemist
   visit (`enchant_buys`): the expected number each needs (sum of 1/chance to the stopping place) less the scrolls
   of the kind carried (2.48.0: those are read first, and the sell stage kept them), Enchant Armor
   first, then To-Dam, then To-Hit, within the gold beyond `town_reserve` (at 110% of the price) and **one**
   `order enchant_max` (default 25) for all three together, each capped at 1.5x its last price; **stash** to the
   tavern (`StashDeposit`, without a house); and **deposits last**: `HouseBank("deposit")` when gold exceeds
   `BANK_FLOAT` + 500 or stash items are carried and the house has a free square; (2.50.0) the **overflow**: the house
   full, the stash items left go inside the tavern room (`StashDeposit`); **no room anywhere**: they stay in the pack
   (never sold) and a `stash_full` alert (once a visit per item; field `items`) tells the Navigator to `ask` the
   Architect about storage -- another house is their decision, never the policy's.
6. **finish**: (2.53.0) first, with a house owned and more than `BANK_FLOAT` + 500 gold still carried, "BANK: N gold
   still carried -- `house deposit`" (with the house step's failure line, else "the bank step didn't run") and a
   `bank` alert; then a summary (sold for, bought for, identified, gold now and banked, `supply_text`, the supply gate for
   the planned depth: OK or MISSING, what couldn't be afforded, the step log); logs `town_kit`.

On its first tick it counts a town visit for the item-review queue and notifies the supplies it came back with;
(2.63.0) it raises the items held for review as one `review` alert (`review_raise`), and its buying stage ends
(before the stash and the bank) with `_buying_review`: undecided items, after at least 60 s from the alert, get the
policy's default and are sold there (pilot-items.md, the review queue) -- nothing is carried to a later visit.

In code (E5), `TownKit.tick` runs `KIT_STEPS` in order: `_kit_where` (town only), `_kit_count` (the first tick),
`_kit_sub` (a sub-goal running: tick it; its result into the log), `_kit_settle` (1 s, nothing busy), then a step per
stage, each testing `self.stage` -- `_kit_withdraw` and `_kit_fetch` (upgrade: the house's gold, a tavern Restore),
`_kit_upgrade`, `_kit_upgrade_again`, `_kit_sell` (sell and sell again), `_kit_identify`, `_kit_buy`, `_kit_buying`. A
stage that finishes sets the next and the next step runs in the same tick (upgrade -> sell -> identify; upgrade again
-> sell again -> buy). `_kit_buying` runs `BUYING_STEPS` -- `_buying_shop`, `_buying_upgrade`, `_buying_quaff`,
`_buying_provision`, `_buying_restock`, `_buying_fallback` (2.48.0: Boldness for Heroism's shortfall),
`_buying_recharge`, `_buying_enchant` (armour and, 2.46.0, the weapon: one step, one purchase), `_buying_stash`,
`_buying_deposit`, `_buying_overflow` and `_buying_stash_full` (2.50.0) --
and `finish` when none acts. Its once-only flags (`withdrawn`, `fetched`, `id_bought`, `farmed`, `recharge_bought`,
`enchant_bought`, `fallback_bought`, `stashed`, `deposited`, `overflowed`, `fetch_tried`, `full_told`, the `quaffed`/`recharged` sets, `restock_waits`,
`enchanted`, `last_sell`, `short`; and `t0`, the visit's start: a store listing seen since is this visit's stock) are
declared in `__init__`.

### The shopping list (`Pilot.town_needs`, `town_shopping`)

`town_needs(kit, buylist)` lists `[tier, kind, store, n, cap]`, counting what's carried (`kit_count`) and what's
already planned:

| tier | what |
|---|---|
| 1 | Word of Recall up to 2 (the supply gate's; kits B and C then keep a 3rd at tier 4, 2.51.0) |
| 2 | the supply gate's minimums for `planned_depth()` (`min(max_depth, deepest)`): CCW, CSW (unless 3 CCW), total cures (CLW below 500 ft, CSW deeper), Phase Door; and the Flasks of oil that fill the lantern, `flasks_to_fill`: ceil((15000 - fuel) / 7500), none within `FILL_SLACK` = 300 turns of full (FUEL_LAMP, mdefines.h:187; a flask's 7500, object.txt; the refill caps at the top, cmd3.c:1365-1374; 2.49.0, was: to 9000) |
| 3 | Restore STR/DEX/CON for a drained stat (unless one waits in the stash, or -- 2.50.0 -- a carried restore mushroom covers it: `restore_for`) |
| 4 | the kit's stock levels (`KITS`; default by planned depth: A below 500 ft, B below 1000 ft, C deeper) |
| 5 | the Navigator's buy list (`NAME:N` = have N) |
| 6 | Restore Charisma, only with 3000+ gold |

(2.65.0) Rations follow the worn gear's digestion (`rations_for_trip`): at least enough for a trip of unknown length
(`SUPPLY_UNKNOWN_DMIN` 40 + `SUPPLY_MARGIN_DMIN` 5 dungeon minutes, the stomach not counted) at 2 food a player turn, or
1 with slow digestion (the grid's `slow_digest`) -- 4 without it, the kits' 3 with it. In the dungeon make-room keeps
the pack's last ration (valued at the minutes it gives: m68 destroyed all 4 for a Staff of Trap Location 8 minutes
before the trip's end), and a `supplies` "low" notice is news when the trip's own end, plus the margin, comes first.
`KITS`: **A** = 2 Word of Recall, 5 CLW, 5 Phase Door, 3 rations. **B** = 3 WoR (2.51.0, the user: was 2), 4 CCW, 4 CSW, 10 Phase, 3 rations,
3 Heroism, 2 Potion of Speed. **C** = as B with 6 CCW, 12 Phase. **none** = nothing. `KIT_ITEMS` gives each kind's
tval, store and a price guess (Speed comes from the Black Market, 7; potions of healing and Heroism from the Temple, 4;
scrolls and Restores from the Alchemist, 5; food and oil from the General Store, 1). `town_shopping` spends the gold
down the list: a line's price is `price_of` (the last seen, else the `KIT_ITEMS` guess), else its cap; tier 4 lines are capped at 1.5x the price
seen, `KIT_CAP` caps Speed at 600; lines over their cap are reported as short. If Word of Recall (tier 1) can't be
fully afforded, everything else but rations waits ("saving for Word of Recall"). `town_reserve()` is the gold tiers 1-2
need: Identify, the Enchant scrolls (armour and weapon) and a house purchase only spend beyond it. The Enchant
scrolls come last of the buying stage's purchases (after the kit and the list), from what is left.

### Selling and the other town helpers

| Pilot method | what it does |
|---|---|
| `town_sell_count(it)` | how many of an item the town visit sells (0 = keep). First `town_rule` (2.48.0): keeps a fallback while its kit kind is short and a Scroll of Enchant/Recharging the kit would read, and the restoring mushrooms; frees for sale Boldness otherwise, Satisfy Hunger, CLW in kits B/C, other mushrooms, torches beside a lit lantern. Then keeps: worn items, kit kinds, needed food/light (sells other food, the flasks beyond those that fill the lantern -- `flasks_spare`, 2.49.0 -- a second lantern no fuller than another), useful devices (`USEFUL_DEVICES`; not a staff duplicating a carried rod; an empty one only if no recharge is planned), `keep`-protected items, ability sources, cursed/worthless, unknowns the policy won't sell blind (unknown devices do sell when broke for a recall), probably-special or value-refused items, gear the evaluator would wear, items held for the Navigator's review, and anything worth nothing. Details in pilot-items.md |
| `is_crutch(it)` | on the test server (not `--live`): Enlightenment, Detection and Magic Mapping devices, and (2.48.0) Scrolls of Magic Mapping (`CRUTCH_SCROLLS`; not Deep Descent), are sold like loot and the scrolls never read, so exploring by hand stays honest |
| `town_rule(it)`, `visit_kit()`, `kit_target(kind)`, `fallback_kept(it)`, `clw_spare()`, `lantern_lit()`, `scroll_use(it)`, `fallback_buys(spare, since)` | 2.48.0, the user's two principles (A fallback, B dungeon stopgap) and the scrolls the kit would read: ("keep"\|"sell", why) for a pack item in town, which `town_sell_count` and `price` follow -- pilot-items.md, "Fallbacks, stopgaps, crutches" |
| `town_buyers(it)` | the stores that buy its tval (`BUYERS`, from store.c; never the Black Market), the best-paying owner first (`shopmath.factors` with our CHR) |
| `town_sell_stores()` / `town_sells(store)` | the stores to visit / the `(index, count)` sells for one store |
| `town_make_room(kit, buys)` | see stage 4 (`PACK_SLOTS` = 23) |
| `provision_step(kit)` | see stage 5 |
| `broke_for_recall()` | fewer than 2 WoR and gold below one's price |
| `identify_candidates(min)` / `town_identify_wanted()` | unknown items and their priority (expected sale value; infinite for ability sources) / the count worth a scroll |
| `restore_item(skip, stats)`, `restore_for(stat)` | (2.50.0; was `restore_potion`) the cheapest pack item restoring a drained stat: a Restore potion (STR/DEX/CON/CHR) or a known restore mushroom (STR/DEX/CON, not one that could gorge); `_buying_quaff` eats or quaffs it -- pilot-items.md, "Restore items" |
| `enchant_chance(it)`, `enchant_plan()`, `enchant_scrolls_wanted(kind)` | spells2.c's enchant table (`ENCHANT_TABLE`): +1 to-AC succeeds with `1 - table[to_a]/1000`, halved on artifacts; enchant while the chance is >= 50% (to about +8); the expected scrolls = sum of 1/chance (`kind` "Enchant Armor", the default, or an Enchant Weapon kind: the wielded weapon's to-dam / to-hit) |
| `wielded_weapon()`, `weapon_plusses(it)`, `weapon_enchant_plan()` | 2.46.0: the wielded melee weapon (tval 20-23, not the bow); its shown (+h,+d); [(weapon, Enchant Weapon To-Dam / To-Hit, chance)] for each plus whose next point is >= 50% (half on an artifact), to-dam first |
| `enchant_buys(spare)` | 2.46.0: [(kind, n, price)] for the visit: Enchant Armor, then To-Dam, then To-Hit, each its expected count, within `spare` gold (110% a scroll) and one `order enchant_max` for all |
| `device_level(kind)`, `recharge_fail(it)`, `recharge_wanted()` | object.txt level; spells2.c's chance a Recharging scroll destroys a staff/wand; the useful devices at 0-1 charges each with at most 15% risk |
| `town_extras_note()` | the `plan town` reply's note of the Enchant scrolls (`enchant_buys` without the gold limit: "up to 3 Scrolls of Enchant Armor + 5 Scrolls of Enchant Weapon To-Dam (~1520 gold; `order enchant_max=N` caps them all, 0 skips)") and Recharging |
| `note_store()` | on entering a shop: owner and the cheapest price per kind -> `stores.json`; (2.56.0, the user after m65) a line shown with the shop's discount ("{50% off}") counts at its undiscounted price (`normal_price`), so every cap built on `price_of` -- the kit's 1.5x, Identify, Recharging, the Enchant scrolls, the fallback -- rests on the normal price; the Shop still buys the cheapest line within the cap (m65: one CSW at 50% off, 31, made the cap 46 and the normal 63 went unbought) |
| `price_of(kind, store)` | the cheapest price seen for a kind at a store, else the `KIT_ITEMS` guess |
| `buy_store(name)`, `stock_table()` | which store sells a name (`rulebook/shop_stock.csv`, which gives 7 for its few Black Market rows such as Healing; else listings seen, never 7) |
| `lantern_fuel()` | turns in the worn lantern, else the fullest in the pack |
| `flasks_to_fill(fuel)`, `flasks_spare(it)` | 2.49.0: the flasks that fill the lantern (0 within `FILL_SLACK` of 15000, or no lantern); how many of a flask stack it doesn't need (the other stacks first): what the town visit sells, its make-room values at their sale price and destroys |
| `kit_count(kind)` | how many carried (rations only for food; Perception charges count as Identify) |
| `planned_depth()` | `min(max_depth, deepest)` (or whichever is set) |

## The supply gate

`Pilot.supply_gate(target_ft, recall_down)` returns what's missing to go down to a depth (`[]` = OK). Nothing is
required above 250 ft. The stage table `SUPPLY_STAGES` (from the Advisor's progression memo):

| from | all cures (CLW+CSW+CCW) | CSW+CCW (or 3 CCW) | CCW | Phase Door |
|---|---|---|---|---|
| 250 ft | 5 | - | - | 4 |
| 500 ft | 5 | 5 | - | 5 |
| 750 ft | 4 | 4 | 4 | 8 |

Plus Word of Recall: 2 when going down by recall (one to go, one to come home), else 1; and a light: none, or under
1000 turns of fuel without a flask for a lantern, is missing. It **blocks** `plan trip` from town (by recall or stairs,
per `stairs_down`), `goal recall` from town, and `goal dive` deeper than the current depth; each takes `force`. The
town kit's tier 2 buys exactly these minimums, its restock waits wait for them, and its summary reports the gate.

## Supplies in dungeon minutes

Food and light are measured in **dungeon minutes** (`Pilot.supply_minutes`), the clock a trip runs on:
`TURNS_PER_DMIN` = 215 player turns a dungeon minute (the resting and running speed-ups included; field-measured: a
full lantern's 7500 turns in ~35 minutes).

- **Light** = (lantern fuel + flasks x 7500) / 215; without a lantern, a worn light that shows turns (a torch) counts
  them plus spare torches' (A19, 2.40.0); `None` for a permanent light (one that shows no turns); 0 without one.
- **Food** = (the least the stomach holds, `food_now()` -- the stomach tracker's bottom, exact once a hunger crossing
  has pinned it, else the hunger level's bottom (2.49.0; 2.48.1 took the level's bottom, `food_floor`) -- plus the food
  value of rations and other food carried, minus 1000 for Weak) / (2 a turn, 1 with slow digestion, x 215). Food
  isn't digested in town. The tracker: pilot-items.md, "The stomach tracker".
- `supply_text()`: "food >=N dungeon min, light ~M" (food: since 2.48.1 the least it can be; "food ~N" once the stomach
  tracker is exact, 2.49.0; the middle of the level stood still for minutes in m61 and ran out) (on the status line via `supply_lines`, at `plan town`'s start and
  end, on reaching the dungeon). `supply_watch()` (every tick in the dungeon) alerts `supplies` once under 15 and once
  under 5 minutes, reset above 20 (2.53.0: not on a hunger crossing until the stomach tracker has seen the new
  level -- m63's Full -> Fed said "~5 min" from the level's bottom; 2.51.0: not while the pack is being read, a meal is unconfirmed, or within 3 s of
  an eat, fuel or destroy -- m62's "~5 minutes" right after a ration). `QuietWait` is capped at a quarter of the smaller.
- `supply_lines()`: the report's supplies line: cures, escapes, food, light (with flasks and the minutes), a pending
  recall, and other potions/scrolls/devices.

## The gold bank (wilderness house) and the stash

**Why.** Thieves take ~10% of the purse a touch; the dungeon has no use for gold. An owned house keeps what is
dropped in it across server restarts; monsters can't enter it or take floor gold (operations.md, "Houses and the
gold bank"). Dive04's bank is the 4-square house in the wilderness tile north of town (depth -1, door 60,129).

**`town_houses(memory, door)`** finds houses on a surface map: closed wall rectangles with exactly one door glyph
(`0` for houses, `8` for the tavern), returning `area`, `door`, `inside` squares, `step_in` (the interior square
inside the door), `outside` (where to stand to open it) and `box`, smallest first.

**`HouseBank(mode, keep, house)`**, modes `buy`, `deposit`, `withdraw`:

- *Getting there.* A wilderness house records `depth` and `cross` (`{town, wild, depth}`): the town square where we
  walked off the edge and the square we arrived on, captured by `Pilot.note_edge_cross` each tick (`edge_dir` gives
  the direction off an edge). The goal walks to `cross.town`, steps off the edge, walks to the door's `outside`, and at
  the end walks back to `cross.wild` and steps back into town.
- *Buy* (`house buy [Y,X]`, the Architect's decision; refuses while the old house holds gold; on a wilderness tile
  only after walking there from town): opens the door to read "This house costs N gold.", buys (`h`) only if the price
  is within the gold beyond `town_reserve`, records it in house.json (an earlier house moves to `old_houses`), then
  deposits.
- *The pile.* Gold piles never merge and a drop with no free square vanishes, so the bank is **one pile on the
  `step_in` square**: walking in picks the whole bank up (checked: if the purse didn't grow by ~the banked amount,
  the gold's square is read (2.52.0, m63): bare -> the record was stale, `bank_stale` is logged and the purse is
  banked as usual; gold still there -> `,` picks it up first; anything else, or no reading in 4 s -> nothing is
  dropped and the Navigator is told). The idle gold fetch never targets a square inside the house (`house_square`). Inside, door closed, it drops all but `keep` (default `BANK_FLOAT` =
  300) for a deposit, nothing for a withdraw, then opens, steps out and closes the door. `banked` is updated and a
  `bank` log record written.
- *The stash in the house* (`item_step`): one stack a square on the other interior squares (farthest from the door
  first), mapped square -> record in house.json `items`. **Reconcile first** (2.50.0, the live check of 11-04: the
  house held two Restore Charisma, the record one; the Scimitar dropped on the "free" square scattered to another --
  the server's drop_near, object2.c:3963, one object a grid -- and `,` on the recorded square took the potion): inside
  with the door closed, each interior square but the gold's is walked and its floor read (the client's `floor` query,
  `World.floor_pos`/`floor_t`, `Pilot.floor_here`), and the record rebuilt: an item it lacks is adopted
  (`stash_found`: not fresh, valued by itemvalue; logged `stash_found`), a recorded item not on its square struck
  (`stash_take` lost). A drop goes only on a square read bare and is recorded (`stash_commit`: the `stash_store` log
  and credit) once the floor underfoot shows it; if not, the house is read again and it is recorded where it lies.
  `,` is pressed only when the floor underfoot names the wanted item (else the house is read again, twice at most,
  then the record is struck); a different item picked up anyway is dropped back. Inside the house the pickup reflex
  takes nothing but the fetch target (`in_house`). The tavern room gets the same checks on the squares its goals walk
  (StashDeposit drops only on a square read bare, adopting what it finds there, and records the drop where it is seen
  -- else as somewhere in the room, `?N`; StashFetch strikes or adopts on the room squares it visits). A deposit drops the stash items carried, the most valuable
  first (2.50.0; what doesn't fit goes to the tavern room); a withdraw picks up the kind a drained stat wants
  (`stash_wanted`), then (2.50.0) the items named in `fetch`, giving up after 4 tries each, and strikes each off
  `items` as soon as the pack holds one more (`fetch_at`; 2.45.0 -- before, the record kept it, `house` still listed it, and a later withdraw spent its
  4 tries on the empty square and said "no X after all").
- `house` (no argument) shows the house, the banked gold and its timestamp, and (2.50.0) each stored item, what it is and
  where (house or tavern room), its value and credit; `banked()` feeds the status line's
  `(+N banked)`.
- *In code* (E5): `tick` runs `TICK_STEPS` -- `_bank_house` (the house on record, town or its tile, one step a
  second; `ctx.h`, `hd`, `door`, `inside`, `outside`), `_bank_cross` (off the town's edge to the tile; `ctx.cross`),
  `_bank_back` and `_bank_home` (the steps `back` and `home`: into town, done), `_bank_turn` (`ctx.gold`, `ctx.said`,
  a new step's tries, a new level stops the walk) and `_bank_door`, which dispatches `self.step` on `STEPS`: `go`
  `_step_go`, `open` `_step_open` (buy: the price, then `h`), `bought` `_step_bought`, `in1` `_step_in1` (the
  doorway), `in2` `_step_in2` (inside, door closed), `inside` `_step_inside` (the pile, `item_step`, the deposit),
  `dropped` `_step_dropped`, `out0`/`out1` `_step_out0`/`_step_out1`, `closed` `_step_closed`; any other step fails.

**The stash** = stat-restore potions (STR/INT/WIS/DEX/CON/CHR, not Restore Mana) and Wands of Stone to Mud
(`is_stash_item`), and since 2.50.0 (the user: "spare items that are valuable and can't be bought should be stored
when possible") the **best backup for each worn slot** and the **store list** (pilot-items.md, section 6a): kept in town
during a mission, never sold. **Placement** (2.50.0): the house first; when its squares are used, inside the tavern room
(the overflow); else kept in the pack with a `stash_full` alert to `ask` the Architect. **Retrieval**: plan town's
withdraw stage fetches a stored backup to wear (its slot empty -- the piece stolen -- or the gear evaluator's choice
over a disenchanted one) and an outclassed one to sell (`stash_fetch_list`; 2.51.0: any stored item the stash no
longer keeps -- `stash_keeps`: not the best backup, not on the store list, not a Restore or Stone to Mud -- is fetched
to be sold, past the review queue, its credit debited at the sale); `house withdraw ITEM` fetches a named one
from the house or the tavern room. With a house they live there (above); without one, in the tavern
room (`StashDeposit`/`StashFetch`, the entrance from `tavern_entrance`). **house.json is the stash's only record**
(refactor-candidates D10, 2026-11-01): the house's `items`, and without a house `tavern` (`entrance`, `items`
"Y,X" -> name). `stash_places()`, `stash_where(kind)` (house first, the house's items only while a house is owned),
`stash_has(kind)`, `stash_take(at, kind, square, lost)` read and strike off; `town_needs` doesn't buy a Restore the stash
holds; `stash_wanted(at)` names the Restore a drained stat needs when the pack lacks it and the stash (in `at`, or
either) has it. `house` shows the stored items. The old `stash.json` (items, tavern squares, hand-written `where`/`lost`
notes) is retired at load (`retire_stash_json`: entrance and tavern items into house.json, the file renamed
`stash.json.retired-DATE`); Dive04's became `stash.json.retired-2026-11-01`.

**Artifacts and refused drops** (2.53.0, the live check: the Phial was dropped ~600 times, "You can not drop this
here."): the server never drops a true artifact above its depth (object2.c `inven_drop_okay`; town and the house tile
are above every artifact), so `true_artifact` items (geareval's artifact, an INSTA_ART kind such as the Phial, or an
artifact's name) are never stash items, never backups; `town_rule` keeps an unworn artifact wearable in the pack ("an
artifact: the server won't let it be dropped above its depth") unless the review decided `sell`. Every stash drop is
bounded: `drop_failed` counts a drop that didn't happen (HouseBank's pending drop not seen and still carried;
StashDeposit's likewise), and the server's refusal counts as all `DROP_TRIES` = 3 at once; a given-up item is skipped
(`stash_to_drop`) for the rest of the visit (reset at plan town's first tick and by `house deposit`), with news.

**Stored finds are income** (2.50.0, the user: storing a valuable item instead of selling it deflated a mission's
gold). Each new record carries `value` (iv.value x pay_cut x count: what the sell decision would have realised), `t`,
`fresh` and the `mission` credited (fresh only). **Fresh** (`acquired_fresh`), first **by inscription** (the user,
11-04): during a mission each find that could be stored -- a single wearable (weapon, armour, ring, amulet; a light
other than a torch or lantern; not a bow, nothing that stacks) -- is inscribed with the mission's label (`{m62}`;
`inscribe_label`/`inscribe_finds`, the `{` command, which costs no game time -- tables.c energy_cost 0 -- sent one at a
time from policy_tick's safe moments and at the start of plan town's upgrade stage). A feeling already shown is kept in
the server's own format, `{excellent - m62}`; a pseudo-ID after the inscription prepends the same way (dungeon.c
sense_inventory) and Identify keeps it (spells2.c clears only a bare feeling), so the unidentified case is solved. Never
over another inscription (the Navigator's `@`/`!` tags, `@R750`, a unique's name), never with no mission running. An
item inscribed with the running mission's label is fresh, with another mission's (`mission_tag`: m<N>, sp-...) not.
**Else** (no label) its pickup was recorded (`note_acquired`,
from the game's "You have X (c)." in the dungeon -- never a purchase or a town pickup -- and not while fetching from the
stash; `acquired.json`) in the
mission running now, or with none running, since we last left town for the dungeon (`trip_t0`). The pickup is matched
by name, else -- an item identified since, whose name changed -- by the latest unidentified pickup of the same base
kind (a Dagger {excellent} -> the Dagger of Westernesse) -- the fallback for a stackable or a Navigator-inscribed find;
limit: two unidentified finds of one kind can be confused,
and an item owned before 2.50.0 or bought has no record (not fresh: Dive04's Scimitar). Log records:
`stash_store` {item, where, value, fresh, mission} on each deposit; `stash_take` {item, where, credited_value,
credited_mission, lost} on each withdrawal; `stash_credit_sold` {item, credited_value, received, credited_mission} when
a credited item, withdrawn, is sold (the debit: a find counted once); withdrawn and worn, no debit. The Pilot's gold
rate (`rate_tick`: rates.json, `gold_per_dmin`, `xp_per_gold`) counts `gold_stored` - `gold_debited` beside the gold
found and sold; the scorecard does the same (observe.md).

## State files (`runs/pilot/<nick>/`)

| file | written by | contents |
|---|---|---|
| `plan.json` | `TripPlan.save` every plan tick; removed by `clear_plan_file` when the plan ends or stops | the trip's `STATE` (range, then, level_min, start time, phase, levels, went_down, home_why, conditions text, via, XP base, dungeon start) and the current level's state (`lvl`: depth, age, done, arrival, located, special, stairs_first, fails). `TripPlan.load` at Pilot start resumes a plan under 90 minutes old (restart.sh parks mid-trip) |
| `stores.json` | `note_store` | per store number: `owner`, `t`, `prices` (cheapest per kind key) |
| `house.json` | `HouseBank`, `house_save` | `house` (area, door, step_in, outside, box, depth, cross, price, bought), `banked`, `t`, `items` ("Y,X" -> stash record), `old_houses`, `tavern` (`entrance`, `items`: the no-house stash and, 2.50.0, the house's overflow). A record is a plain name (before 2.50.0, still read) or `{name, value, t, fresh, mission}` (`stash_rec`) |
| `acquired.json` | `note_acquired`, `note_trip_start`, `stash_take`, `stash_credit_*` (2.50.0) | `items` (the last 400 pickups: name, kind, known, t, mission), `trip_t0` (when we last left town for the dungeon), `credits` (a fresh stored item withdrawn: bare name -> value, mission; debited if sold, dropped if worn or stored again) |
| `store.json` | `store add|del` (2.50.0) | the store list: lower-case name parts |
| `stash.json.retired-DATE` | `retire_stash_json` (rename) | the old stash record, kept as history (D10, 2026-11-01) |
| `review.json` | TownKit's first tick | `town_visits` (the item-review queue's clock: pilot-items.md) |
| `deepest.json` | the Pilot | `{"ft": N}`: the deepest level reached (`deepest_ft`), used by `planned_depth`, the recall depth and `stairs_down` |
| `decisions.jsonl` | `Pilot.log` | one JSON record a line; this component writes `goal`, `plan_start`, `plan_end`, `plan_resumed`, `town_kit`, `bank`, `sale` |

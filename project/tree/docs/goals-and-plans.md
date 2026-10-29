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

## What a goal is

- **Class shape.** A subclass of `pilot.py: Goal` with a `name` (what `describe()` returns: shown in reports, logs
  and `plan` output) and `tick(p)`, called with the Pilot. `tick` returns `None` while running, or a pair
  `(status, detail)` to end: `"done"`, `"failed"`, or (only `Dive`, when something interesting turns up)
  `"interesting"`. A goal keeps its own state in attributes; most are re-entrant per tick (no threads, no sleeps:
  they send one command with a `hold` and come back later).
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
| `Goto` | `goal goto TARGET [force]`, `goal fetch Y,X` (with band/danger refusals) | target: `<`, `>`, `stairs`, `item` (nearest non-junk item glyph), or `Y,X`; `force` | paths there (`Pilot.resolve_target`, mover; may path through unexplored squares and says so). **Holds** (doesn't walk) while a dangerous monster is adjacent or a faster monster hit us in the last 2 s, unless `force`: walking away gives free hits. Arriving on an item, waits up to 1.5 s for the pickup | done on arrival; failed: no such place, no path, stuck |
| `Explore` | `goal explore [until=stairs\|upstairs] [radius=N]`; Dive; the trip plan | until, radius, skip (stairs not to count) | dungeon only; refuses below `max_depth` unless looking for stairs. Walks to the nearest frontier (known floor next to unknown), running along corridors and across dark rooms, looting on the way (`loot_step`); avoids drainer and avoid zones; digs rubble that borders the unknown; with no frontier left searches unsearched corridor dead ends (`Search(strict, 15 tries)`) | done: stairs seen (with `until`), or "nothing left to explore" (lists inner rooms not opened: `goal searchroom`); failed: frontier unreachable, or on the surface |
| `Dive` | `goal dive [FEET] [scum] [force]` (default one level down); the trip plan | target_ft (capped by `max_depth`), scum | stair-scums: on a level with the wanted stairs known and reachable, walks there and takes them; standing on the other kind, takes them for a fresh level (not on a level the server keeps: then explores); else uses a Door/Stair Location device once, else explores for stairs (then searches dead ends). Puts the light on leaving town; loots what's close; explores pillared rooms (`order pillared`); refuses for FLED_HOLD (120 s, live server only; 300 s on a kept level) stairs back to a level just fled. On a climb never takes a `>` unless `scum`. Gate: going deeper checks `supply_gate` (overridden by `force`) | done: reached the depth; `interesting` on a new level when `p.interesting()` fires (not for plan dives); failed: no stairs after exploring and searching |
| `Search` | `goal search`; `goal searchroom Y,X` (an inner room's 4 door spots, 20 tries) | tries (8), strict, spots | stands at each dead end / corridor end / given spot, nearest first, searching once a player turn | done "found a way on" when a new door or opening appears (summary lists spots and searches); failed: all spots searched |
| `Hunt` | `goal hunt NAME` (checked; `!NAME` overrides into the fight debt); reflex | name, lost_s 15 | walk next to it, let auto-retaliate fight (see pilot-combat.md) | done slain; failed lost sight / blinked away |
| `Recover` | reflex after a stairs escape | came_by, prev goal | rest on the stairs, go back up if past `max_depth`, then resume (pilot-combat.md) | done healed |
| `Reprieve` | after a Hunt's target blinked away | who | rest out of its sight, or leave if mortal danger is near (pilot-combat.md) | done healed / 2 min |
| `BandLeave` | `flee_failed` for a band at high HP | names | find stairs with Door/Stair Location or Magic Mapping, else walk out of sight (pilot-combat.md) | done/failed; a second failure recalls |
| `WalkAway` | reflex: a summoner in view | names | walk out of its sight over walked ground (pilot-combat.md) | fails to the flee rules when it closes in |
| `Flee` | `goal leave`; reflexes; the trip plan for a band | why | to the nearest known stairs and take them (pilot-combat.md) | done on the new level |
| `Recall` | `goal recall [force]`; reflexes; the plan | depth_ft (from town: the depth to inscribe; default `max_depth`) | in town first inscribes `@R<feet>` on the scroll (the server reads the recall depth from it; checked by parsing, 3 tries); puts a light on (no light, no reading); cures blindness/confusion with the cheapest potion; doesn't read a second scroll if one is already under way; reads one; while it charges, rests if hurt and nothing is in view (time runs ~10x resting). From town, `goal recall` checks the supply gate for the planned depth (2 Words of Recall) unless `force` | done when the level changed *and* the recall flag cleared; failed: no scroll, can't inscribe, nothing after 120 s (60 s if never pending; quotes the game's reason) |
| `Resurrect` | `goal resurrect` (the only goal a ghost may give; read-only commands still work) | - | a ghost: `<` anywhere, one level a press; in town walks onto the Temple entrance (`4`), which resurrects (costs half the experience) | done resurrected; failed: no Temple on the map |
| `Town` | `goal town`; the plan | - | from the wilderness back to town: walks off each sector by the edge it came in through (`Pilot.wild_trail`, else `edge_of` the arrival square) | done in town; failed in the dungeon or edge unknown |
| `TownFarm` | `goal townfarm GOLD [MINUTES]` (default 10); TownKit when broke | target gold, minutes | in town: light on, then chase thieves within 8 squares first (item thieves before gold ones, hitting them directly), walk over dropped gold, kill the gold-dropping townspeople (`TARGETS`), else sweep the town in a zig-zag | done at the target, time up, or no gold gained in 2 minutes (townspeople thinned out / night) |
| `Shop` | `goal shop N [list] [buy NAME:N[@MAX]] [buy NAME:+N] [sell NAME\|LETTER:N] [quote NAME]`; TownKit | store number, buys `(name, n, cap)`, sells `(index or name, n)`, list_stock | walks next to the door (unseen squares count, for night), enters, then: sells (from the end of the pack first; names resolved when their turn comes) with the item policy's refusals (unknown items, value policy, "probably special"; `!NAME` forces and the value lost goes into the Navigator's debt), learns a flavour sold unknown, logs a `sale` record with the re-listing price; quotes (offer and decline); buys the **cheapest** matching line, within the cap and the gold, continuing at the next price if the cheap stack runs out. `NAME:N` in `goal shop` means *have* N; `:+N` buys N more. Re-enters (twice) if its own command closed the store | done with a log of what happened; failed: not in town, store not on the map, can't reach, thrown out |
| `StashDeposit` | TownKit (no house only) | - | drops each stash item (below) on an empty square **inside** the tavern room (farthest from the door first; the entrance square holds no object, and drops from it land on the street where townsfolk take them); records the squares in stash.json | done when none is carried; failed: no empty square seen inside |
| `StashFetch` | TownKit, for a drained stat's Restore in the tavern | kind | lights up, walks the squares within 4 of the tavern entrance (item glyphs first) until the pickup reflex (`p.fetching`) takes the kind | done when in the pack; failed: none left / no tavern |
| `HouseBank` | `house buy [Y,X]` (Architect only), `house deposit [KEEP]`, `house withdraw`; TownKit | mode buy/deposit/withdraw, keep, house | see "The gold bank" below | done: "N gold in the house, M carried" |
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
| `minutes`, `dmin` | minutes since the plan was given / since it first reached the dungeon |
| `time` | wall clock `HH:MM` (the next such moment after the plan started; across midnight) |
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

The plan ends **done** at home (`then recall`), after the town kit (`then town`), or if the character turns up in
town by another route (an escape recall: the reply names it and points to `why`). On end it logs `plan_end` and
notifies `plan_done` / `plan_failed`. `plan` shows it, `plan stop` (or `stop`) ends it, `plan resume` ends the
Navigator's pausing goal. The Pilot's reflex goals (flee, recover, recall) replace a plan goal without pausing the
plan; while a plan runs (not paused) `idle()` never recalls. `Pilot.trip_minutes_left` (from the recall, the `minutes`/`time`
conditions and the 90-minute cap) tells the item policy when spare rations and flasks can go (`provisions_spare`:
within 3 minutes, or 20 when Full).

## The town visit (`plan town`)

`plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@MAX],...]` (`Pilot.request_plan`), town only. Each buy spec: STORE
1-7 optional (else the rulebook's `shop_stock.csv` via `buy_store`, a shop listing seen, or the kit table), `NAME`
with `_` for spaces, `:N` = **have** N in all, `@MAX` a price cap each. The reply forecasts what it will buy at the
prices last seen, what it can't afford, and the extras (`town_extras_note`: Enchant Armor and Recharging scrolls).
It starts a `TownKit` goal, which works through **stages**, one sub-goal (`Shop`, `HouseBank`, `StashFetch`,
`TownFarm`, `Wait`) at a time, settling 1 s between steps:

1. **upgrade**: first `HouseBank("withdraw")` if a house holds gold or the Restore a drained stat wants (**withdraws
   first**); else `StashFetch` that Restore from the tavern; then wear what the gear policy prefers (`upgrade_step`).
2. **sell**: one `Shop` per store that buys something the policy sells (`town_sell_stores`, `town_sells`), in store
   order; a store is revisited once if a sale taught an unknown flavour (the rest of the stack then sells).
3. **identify**: read Identify scrolls on the candidates (`identify_step`, pilot-items.md); buy more at the Alchemist
   (5) for the unknowns worth it: `town_identify_wanted` counts unknown items whose expected sale value is at least
   twice the scroll's price (ability sources and likely-irreplaceable items always count), limited by gold beyond
   `town_reserve`, capped at 1.5x the price. Staff of Perception charges count as Identify scrolls. If anything was
   identified: **upgrade again** and **sell again**.
4. **buy**: if `broke_for_recall` (fewer than 2 Words of Recall and not the gold for one) and it's day, `TownFarm`
   for 5 minutes, to the gold now plus the price of the missing Words (+20) (at night it saves the gold instead). Then `town_shopping` turns the list into buys,
   `town_make_room` frees pack slots for new kinds (sells the least valuable unprotected item, else destroys it; 6 tries),
   and the stores are ordered by the highest-priority line each holds.
5. **buying**: one `Shop` per store; then wear what was bought; quaff a Restore bought for a drained stat
   (`restore_potion`); `provision_step` (wear the fuller lantern, fill it from flasks up to `FUEL_TOPUP` 9000 turns,
   eat rations while Hungry or worse, up to 3, to Fed); **restock waits**: if a critical item (the gate's minimums, a
   Restore for a drained STR/DEX/CON) is still missing and a shop said "no ... in stock", `Wait(35)` and redo the buy
   stage, up to `RESTOCK_WAITS` = 4 times; **recharge** each `recharge_wanted` device with a Scroll of Recharging
   (bought once at the Alchemist, cap 1.5x); **enchant** worn armour per `enchant_plan` with Enchant Armor scrolls
   (bought once: the expected number needed, within spare gold and `order enchant_max`, default 25); **stash** to the
   tavern (`StashDeposit`, only without a house); and **deposits last**: `HouseBank("deposit")` when gold exceeds
   `BANK_FLOAT` + 500 or stash items are carried.
6. **finish**: a summary (sold for, bought for, identified, gold now and banked, `supply_text`, the supply gate for
   the planned depth: OK or MISSING, what couldn't be afforded, the step log); logs `town_kit`.

On its first tick it counts a town visit for the item-review queue and notifies the supplies it came back with.

### The shopping list (`Pilot.town_needs`, `town_shopping`)

`town_needs(kit, buylist)` lists `[tier, kind, store, n, cap]`, counting what's carried (`kit_count`) and what's
already planned:

| tier | what |
|---|---|
| 1 | Word of Recall up to 2 |
| 2 | the supply gate's minimums for `planned_depth()` (`min(max_depth, deepest)`): CCW, CSW (unless 3 CCW), total cures (CLW below 500 ft, CSW deeper), Phase Door; and Flasks of oil to bring the lantern to 9000 turns (7500 a flask) |
| 3 | Restore STR/DEX/CON for a drained stat (unless one waits in the stash) |
| 4 | the kit's stock levels (`KITS`; default by planned depth: A below 500 ft, B below 1000 ft, C deeper) |
| 5 | the Navigator's buy list (`NAME:N` = have N) |
| 6 | Restore Charisma, only with 3000+ gold |

`KITS`: **A** = 2 Word of Recall, 5 CLW, 5 Phase Door, 3 rations. **B** = 2 WoR, 4 CCW, 4 CSW, 10 Phase, 3 rations,
3 Heroism, 2 Potion of Speed. **C** = as B with 6 CCW, 12 Phase. **none** = nothing. `KIT_ITEMS` gives each kind's
tval, store and a price guess (Speed comes from the Black Market, 7; potions of healing and Heroism from the Temple, 4;
scrolls and Restores from the Alchemist, 5; food and oil from the General Store, 1). `town_shopping` spends the gold
down the list: a line's price is `price_of` (the last seen, else the `KIT_ITEMS` guess), else its cap; tier 4 lines are capped at 1.5x the price
seen, `KIT_CAP` caps Speed at 600; lines over their cap are reported as short. If Word of Recall (tier 1) can't be
fully afforded, everything else but rations waits ("saving for Word of Recall"). `town_reserve()` is the gold tiers 1-2
need: Identify, Enchant Armor and a house purchase only spend beyond it.

### Selling and the other town helpers

| Pilot method | what it does |
|---|---|
| `town_sell_count(it)` | how many of an item the town visit sells (0 = keep). Keeps: worn items, kit kinds, needed food/light (sells other food, spare flasks once the lantern has 9000+, a second lantern no fuller than another), useful devices (`USEFUL_DEVICES`; not a staff duplicating a carried rod; an empty one only if no recharge is planned), `keep`-protected items, ability sources, cursed/worthless, unknowns the policy won't sell blind (unknown devices do sell when broke for a recall), probably-special or value-refused items, gear the evaluator would wear, items held for the Navigator's review, and anything worth nothing. Details in pilot-items.md |
| `is_crutch(it)` | on the test server (not `--live`): Enlightenment, Detection and Magic Mapping devices are sold like loot, so exploring by hand stays honest |
| `town_buyers(it)` | the stores that buy its tval (`BUYERS`, from store.c; never the Black Market), the best-paying owner first (`shopmath.factors` with our CHR) |
| `town_sell_stores()` / `town_sells(store)` | the stores to visit / the `(index, count)` sells for one store |
| `town_make_room(kit, buys)` | see stage 4 (`PACK_SLOTS` = 23) |
| `provision_step(kit)` | see stage 5 |
| `broke_for_recall()` | fewer than 2 WoR and gold below one's price |
| `identify_candidates(min)` / `town_identify_wanted()` | unknown items and their priority (expected sale value; infinite for ability sources) / the count worth a scroll |
| `restore_potion(skip)` | a Restore in the pack for a drained STR/DEX/CON/CHR |
| `enchant_chance(it)`, `enchant_plan()`, `enchant_scrolls_wanted()` | spells2.c's enchant table (`ENCHANT_TABLE`): +1 to-AC succeeds with `1 - table[to_a]/1000`, halved on artifacts; enchant while the chance is >= 50% (to about +8); the expected scrolls = sum of 1/chance |
| `device_level(kind)`, `recharge_fail(it)`, `recharge_wanted()` | object.txt level; spells2.c's chance a Recharging scroll destroys a staff/wand; the useful devices at 0-1 charges each with at most 15% risk |
| `town_extras_note()` | the `plan town` reply's note of Enchant Armor / Recharging spending |
| `note_store()` | on entering a shop: owner and the cheapest price per kind -> `stores.json` |
| `price_of(kind, store)` | the cheapest price seen for a kind at a store, else the `KIT_ITEMS` guess |
| `buy_store(name)`, `stock_table()` | which store sells a name (`rulebook/shop_stock.csv`, which gives 7 for its few Black Market rows such as Healing; else listings seen, never 7) |
| `lantern_fuel()` | turns in the worn lantern, else the fullest in the pack |
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

- **Light** = (lantern fuel + flasks x 7500) / 215; `None` for a permanent light; 0 without one.
- **Food** = (the middle of the current hunger level, `FOOD_MID`, plus the food value of rations and other food
  carried, minus 1000 for Weak) / (2 a turn, 1 with slow digestion, x 215). Food isn't digested in town.
- `supply_text()`: "food ~N dungeon min, light ~M" (on the status line via `supply_lines`, at `plan town`'s start and
  end, on reaching the dungeon). `supply_watch()` (every tick in the dungeon) alerts `supplies` once under 15 and once
  under 5 minutes, reset above 20. `QuietWait` is capped at a quarter of the smaller.
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
  nothing is dropped and the Navigator is told). Inside, door closed, it drops all but `keep` (default `BANK_FLOAT` =
  300) for a deposit, nothing for a withdraw, then opens, steps out and closes the door. `banked` is updated and a
  `bank` log record written.
- *The stash in the house* (`item_step`): one stack a square on the other interior squares (farthest from the door
  first), mapped square -> name in house.json `items`. A deposit drops the stash items carried; a withdraw picks up the
  kind a drained stat wants (`stash_wanted`), giving up after 4 tries.
- `house` (no argument) shows the house, the banked gold and its timestamp; `banked()` feeds the status line's
  `(+N banked)`.

**The stash** = stat-restore potions (STR/INT/WIS/DEX/CON/CHR, not Restore Mana) and Wands of Stone to Mud
(`is_stash_item`): kept in town during a mission. With a house they live there (above); without one, in the tavern
room (`StashDeposit`/`StashFetch`, the entrance from `tavern_entrance`, remembered in stash.json). `stash_add`,
`stash_remove(kind)`, `stash_has(kind)` keep the list in stash.json; `town_needs` doesn't buy a Restore the stash
holds; `stash_wanted()` names the Restore a drained STR/DEX/CON needs when the pack lacks it and the stash has it.

## State files (`runs/pilot/<nick>/`)

| file | written by | contents |
|---|---|---|
| `plan.json` | `TripPlan.save` every plan tick; removed by `clear_plan_file` when the plan ends or stops | the trip's `STATE` (range, then, level_min, start time, phase, levels, went_down, home_why, conditions text, via, XP base, dungeon start) and the current level's state (`lvl`: depth, age, done, arrival, located, special, stairs_first, fails). `TripPlan.load` at Pilot start resumes a plan under 90 minutes old (restart.sh parks mid-trip) |
| `stores.json` | `note_store` | per store number: `owner`, `t`, `prices` (cheapest per kind key) |
| `house.json` | `HouseBank`, `house_save` | `house` (area, door, step_in, outside, box, depth, cross, price, bought), `banked`, `t`, `items` ("Y,X" -> stash item), `old_houses` |
| `stash.json` | `stash_save` | `items` (stash item names, wherever they are), `entrance` (the tavern's), `squares` (tavern squares used), free-text `where`/`lost` notes (hand-written; the code never writes them) |
| `review.json` | TownKit's first tick | `town_visits` (the item-review queue's clock: pilot-items.md) |
| `deepest.json` | the Pilot | `{"ft": N}`: the deepest level reached (`deepest_ft`), used by `planned_depth`, the recall depth and `stairs_down` |
| `decisions.jsonl` | `Pilot.log` | one JSON record a line; this component writes `goal`, `plan_start`, `plan_end`, `plan_resumed`, `town_kit`, `bank`, `sale` |

# Testing, the rulebook, shopcat and the ops scripts

This file covers what surrounds the Pilot rather than the Pilot itself: the **test harness** that checks its
decisions (offline unit cases and live set-pieces staged with the Dungeon Master), the **rulebook** (the Advisor's
tables of game facts built from the server source, which the Pilot and the Navigator query), **shopcat** (the
original shop-catalogue tool, whose client wrapper everything still uses), and the **ops scripts** that freeze the
test server, snapshot and restore characters, update the Pilot and snapshot the project for git. For the step-by-step
server how-tos see [`operations.md`](../operations.md); this file summarizes and links it.

All paths below are relative to `github/tools/` unless they start with `runs/`, `testserver/` or `Advisor/` (those are
under `/projectnb/jbrcs/mangband/`). Python is `module load python3/3.12.4` (the OS python is 3.6).

Related: Pilot internals in [pilot-core.md](pilot-core.md); the decisions the tests exercise in
[pilot-combat.md](pilot-combat.md), [pilot-items.md](pilot-items.md), [goals-and-plans.md](goals-and-plans.md);
`pilotctl` (including `pilotctl rule`) in [commands.md](commands.md); the tool client's `interactive`/`keys`/`special`
commands in [client-server.md](client-server.md); the viewer's freeze key in [observe.md](observe.md).

## At a glance

| piece | what | who runs it | live / stale |
|---|---|---|---|
| `harness/unit.py` (+ `fixtures.py`, `unit_<family>.py`) | 156 offline unit cases of the Pilot's decision code | the Architect, after every Pilot or rulebook change | live; the regression gate (all must pass) |
| `harness/setpiece.py` (+ `setpiece_run.py`, `setpiece_a/bcd/l/mh.py`) | 39 live scenarios staged on the test server and scored | the Architect, by hand, one at a time | live code; never re-run as a suite since the 10-23..10-28 batch (single IDs re-run 11-02..11-03: A2I/A2K/A2L, A6, A8w, B3, M2) |
| `harness/dm.py` | scripts the DM character Gandalf (summon, paint terrain, forge, pull a player) | `setpiece.py` | live |
| `harness/charsave.sh` | save/restore a character's savefile + Pilot state | `setpiece.py`; the Architect for checkpoints | live |
| `harness/refactor/` | the refactor's equivalence checks (session 11: tick() equivalence, the command matrix, bytecode and step-order checks) | the Architect, for a change meant to leave play unchanged | live (by hand; not a suite) |
| `rulebook/` | 27 CSV tables (26 from the Advisor + `monsters_raw.csv`) + `rule.py`, `fight_sim.py` | the Pilot (loads tables), the Navigator (`pilotctl rule`), the Architect | live; synced 2026-10-24, identical to the Advisor's copy today |
| `client/mang.py` | Python wrapper for the tool-mode client | the Pilot, `dm.py`, `observe/study/scribe.py` | **live, core** Moved from `shopcat/` on 2026-11-02 (E7); `shopcat/mang.py` is a shim that loads it under the same name (for shopcat.py, newchar.py). |
| `shopcat/newchar.py` | create a throwaway character + its private files | the Architect (rarely); `scribe.py` imports two helpers | live, rarely used |
| `shopcat/shopcat.py`, `nav.py`, `wild.py`, `report.py` | the player-shop cataloguer | nobody since 2026-09-25 | **stale** |
| `freeze.sh` | stop/start game time on the test server | the Architect, `hotswap.sh`, set-piece H1 | live |
| `pilot/restart.sh` | park the Pilot, start the new code | the Architect (Dive04 idle in town) | live |
| `pilot/hotswap.sh` | freeze, kill, restart, thaw (mid-mission code swap) | the Architect | live (tested by H1/H1r) |
| `snapshot.sh` | copy the project state into `github/project/` before a commit/push | the Architect | live |

---

## The harness (`harness/`)

The harness turns the Advisor's set-piece memo (`memos/2026-10-24-setpieces.md` and addendum) into tests, in three
kinds: **U** unit cases on constructed states (`unit.py`), **L** live set-pieces on the test server (`setpiece.py`),
**R** replays (not built: the Pilot logs thinned status/pack/map replies to `runs/pilot/NICK/state.jsonl` so a state
could be rebuilt, but there is no replay runner). `harness/README.md` is the long-form record: a reference table of
the set-pieces (what each stages, its pass criteria, its status) and a dated findings log (staging facts, the bugs the
harness found); read it before writing a new set-piece.

**Files** (E8, 2026-11-03: `unit.py` and `setpiece.py` split by family; the commands are unchanged):

| file | holds |
|---|---|
| `unit.py` | the unit runner: imports the family files (`FAMILIES`), runs every `@case` in `ORDER` (the order the cases were written in), `main()` (name filter, `--golden`) |
| `fixtures.py` | `P` (pilot.py), RACES/BYNAME, the `@case` registry `CASES`, `G`, `W`, `pilot()`, `PHASE`, `pilot_ast()`, the helpers two families share (`_Stub`, `_quiet_level`), the golden report text (`GOLDEN_REPORTS`, `render_reports`) |
| `unit_<family>.py` | the cases, one file per family (the table below); a helper only one family uses lives in its file (`_Mover` in loot, `_dive_on_back_stairs` in levels, `_town_memory` in house, `_trip_on_level` in trips, `_dive04_character` in gear) |
| `golden/reports.txt` | the golden report text (`reports_match_golden`) |
| `setpiece.py` | the set-piece runner: `SETPIECES` (ID -> function, the `list` order), `TOWN`, `main()` |
| `setpiece_run.py` | the framework: paths, `ctl`, `pilot_view`, `log_since`, `messages_since`, `hp_now`, `gold_now`, `first_seen`, the map helpers (`floor_near`, `clear_line`, `step_dir`, `find_pocket`, `find_floor_block`), the `Run` class, `give_item`/`con_swap`, FREEZE/HOTSWAP, WOR_KIND, `fresh_depth` |
| `setpiece_a.py`, `setpiece_bcd.py`, `setpiece_l.py`, `setpiece_mh.py` | the scenario functions: group A; B, C and D; L; M and H |

### `unit.py` -- offline unit cases

**What:** 156 functions decorated `@case` (in `unit_<family>.py`), each building a situation by hand and calling the
real Pilot decision code on it, returning `(ok, detail)` (one, `emergency_notices_say_if_action`, is a static check of the Pilot's source: `pilot_ast()` parses pilot.py and the modules split out of it, combat.py
and commands.py among them). No
server, no client, no network.

**How it works:** `fixtures.py` imports `pilot/pilot.py` (as `P`) and `glyphs` (the family files that use
`itemvalue` import it themselves), and loads the monster races merged with the rulebook (`glyphs.load_rulebook`).
`unit.py` imports the family files, whose `@case` functions register in `CASES`, sorts them into `ORDER` (a case not
listed runs after the listed ones; a listed name with no case, or two cases of one name, stop the run) and runs them.
`W` is a fake World: Dive04 as of 2026-10-23 (clvl 22, 265 HP, 300 ft, a Spear
(+5,+7), AC 56, 172 gold) unless a case passes other HP, pack, worn items or monsters. `pilot(w)` makes a `Pilot` with
`Pilot.for_test(w, ...)` (every attribute at its default from `_init_state()`, `log` a no-op, no client, rundir or
decisions.jsonl: E6, 2026-11-02), sets the case's own (orders, deepest, drained stats, unique names), records `notify`
calls in `p.notes`, and resets the game clock in `world` (a case that leaves the clock fast or frozen once made the
Phase rule flaky). Some cases add
small fakes (a `_Mover`, a town memory, a quiet level) or write temporary state files.

**Run:**

```
cd github/tools/harness && python3 unit.py          # all cases; exit status 1 if any fails
python3 unit.py hunt                                # only cases whose name contains "hunt"
python3 unit.py --golden                            # rewrite golden/reports.txt after a report change on purpose
```

Output: one `PASS|FAIL name: detail` line per case and a total. No files written by the suite itself. There is no
`--help` (an argument is taken as a name filter). **Run 2026-11-03 (2.46.0): 156 passed, 0 failed.**
The old handoffs (`history/handoffs-s1-s9.md`) record an intermittent failure (~1 in 20 runs, twice, not reproduced since).

**Case families** (names are descriptive; one file each, `unit_<family>.py`; grep `unit_*.py` for the full list):

| family (file) | examples |
|---|---|
| Hunt check and fight vetoes (`unit_hunts.py`) | `hunt_hill_giant_by_hp`, `hunt_ranger_summoner`, `hunt_qualitative_vetoes`, `hunt_repeat_unique`, `engage_nearby_monster_only_when_appropriate`, `disenchanter_beside_path_not_fought`, `weapon_numbers_by_geareval` |
| Danger, emergency and escapes (`unit_danger.py`) | `a5_unseen_caster_news_above_80`, `estimator_memo_rules`, `emergency_speed_first_berserk_hard_fights`, `speed_at_hard_fight_start_and_kit`, `flee_at_max_depth_teleports`, `flee_maps_before_unexplored`, `flee_replans_after_a_phase`, `why_explains_the_last_escape`, `escape_landing_and_trapdoor_notes`, `emergency_loop_counts_actions_only`, `emergency_notices_say_if_action` |
| Status effects (`unit_status.py`) | `fear_cure_order`, `blind_cured_when_it_matters`, `blind_escape_uses_the_staff_and_sees_refused_reads`, `recall_cures_confusion_first`, `confusion_lock_is_cured`, `confusion_window_teleports`, `unseen_drainer_leaves`, `breeder_swarm_leaves`, `breeder_swarm_pin_teleports_once`, `theft_is_news` |
| Bands and levels (`unit_levels.py`) | `band_leave_finds_stairs`, `bands_by_expected_cost_weak_drainers_news`, `band_condition_only_while_live`, `quiet_level_left`, `quiet_wait_finds_a_spot_and_wakes`, `stairs_beside_mold`, `fled_stairs_refused_two_minutes_only`, `refused_stairs_dont_end_explore`, `structures_on_the_aligned_lattice`, `run_loop_walks` |
| Item values and identification (`unit_items.py`) | `jewellery_unknown_plusses`, `bracketed_ego_valued`, `unique_drop_feeling`, `junk_kinds_from_rulebook`, `c2_unknown_charges`, `c6_ambiguous_names`, `c7_unknown_ring_not_worn`, `c9_identify_good_first`, `ability_proofs`, `asleep_flags_from_look_answers`, `junk_one_rule`, `pay_cut_in_shopmath_and_aware` |
| Looting, pack room, destroying (`unit_loot.py`) | `unique_drop_fetched`, `loot_band_stops_looting`, `loot_owed_and_valuables`, `dive_loots_beside_its_path`, `pack_full_makes_room`, `weight_limit_sheds_cheap_heavy_loot`, `unique_drop_pushes_out_only_cheap`, `floor_junk_destroyed_when_quiet`, `rations_by_need_and_heavy_loot_left`, `navigator_rules_review_and_nopickup`, `pickup_none_no_loot_walks` |
| Gear (evaluator, loadout, review) (`unit_gear.py`) | `gear_model_matches_dive04_sheet`, `gear_evaluator_no_loss_rules`, `gear_score_rests_and_paired_error`, `ehp_counts_ac_hp_and_resists`, `proxy_counts_resists_by_ehp`, `ehp_gate_and_tie_break`, `gear_review_finds_free_slot`, `better_ring_replaces_worn`, `gear_line_keeps_ability_armour`, `ability_weapon_kept`, `ability_armour_kept`, `loadout_moves_free_action`, `fullest_lantern_worn`, `speed_potion_over_junk_weapon`, `gear_items_parsed_from_names`, `rings_of_damage_and_accuracy`, `better_ac_by_geareval` |
| Shops and town (`unit_town.py`) | `shop_pay_by_owner`, `c1_valuable_sale_refused`, `town_kit_tiers`, `town_kit_townfarms_when_broke`, `crutch_devices_sold_on_test`, `town_makes_room_before_buying`, `town_identifies_scrolls_in_hand`, `town_waits_for_restock`, `ask_price_and_buy_commas`, `empty_devices_recharged_or_sold`, `enchant_armour_to_the_stopping_place`, `plan_town_survives_the_house_tile` |
| House bank and stash (`unit_house.py`) | `house_bank_round_trip`, `house_bank_in_the_wilderness`, `house_keeps_the_stash`, `house_walk_stops_at_the_crossing`, `tavern_stash_and_one_lantern`, `tavern_stash_drops_inside`, `stash_in_house_json_only` |
| Trips, supplies, clocks (`unit_trips.py`) | `trip_conditions_parse`, `trip_clock_condition_across_midnight`, `trip_dmin_counts_dungeon_minutes`, `trip_level_state_survives_restart`, `trip_recalls_when_a_level_wont_let_go`, `e1_supply_gate`, `supply_minutes_and_quiet_cap`, `provisions_one_food_no_oil`, `food_warning_and_trip_rate`, `room_eat_never_gorges`, `game_clock_from_fuel`, `supplies_one_kind_with_fields` |
| Orders, reports, rates, shadow (`unit_orders.py`) | `f1_stale_order`, `react_hunt_resumes_the_goal`, `actions_say_who`, `ask_quiet_waits_for_the_answer`, `ask_limits_lifted_by_the_flag_file`, `item_commands_wait_for_the_pack`, `mission_label_survives_restart`, `prep_report_sections`, `rates_gold_found_not_shopping`, `xp_per_gold_rolling`, `shadow_estimator_logs`, `shadow_agrees_by_the_action_taken`, `hard_fight_shadow_once_per_fight` |
| Code structure: the refactor's tables, the golden report (`unit_structure.py`) | `command_table_methods_exist`, `command_table_fields_valid`, `command_table_help_lists_every_command`, `command_table_architect_only_refused` (E2: the command table), `reflex_escape_step_lists` (E3), `town_plan_step_tables` (E5), `reports_match_golden` (E1) |

Gotcha: because `pilot()` (`fixtures.py`) sets attributes by hand, a new attribute read by the decision code but set only in
`Pilot.__init__` makes cases fail with `AttributeError`; add it to `pilot()`.

### `setpiece.py` -- live set-pieces

**What a set-piece is:** a short, repeatable scene on the test server built around one Pilot behaviour ("a Hill
giant adjacent at full HP, ordered to hunt it"), played by Dive04's real, running Pilot and scored from its decision
log. It tests what unit cases can't: timing, the server's actual behaviour, perception in the dark, the mover.

**Run:** `python3 setpiece.py ID [--depth FT] [--keep] [--hpwarn N]`; `python3 setpiece.py list` prints the IDs with
the first docstring line. `--depth` defaults to the least recently used of 300-650 ft (`runs/setpieces/depths.json`);
B4/B4w run in town. `--keep` skips the restore. `--hpwarn N` restarts the Pilot with that option (via `PILOT_ARGS`) for
an A/B. A run takes a few minutes.

**How one is staged and run** (`Run` class, `setpiece_run.py`):

1. `setup`: `charsave.sh save Dive04 TAG` (parks the Pilot, waits out the orphan timeout, copies the savefile and
   Pilot state, restarts the Pilot); `pilotctl mission start sp-TAG navigator=harness` (so the run is labelled as a
   mission); connects as Gandalf (`dm.DM`), clears the DM hooks, takes Gandalf up to town and back down to the chosen
   depth so the level is fresh.
2. The scenario function (`a7(run)` etc., in `setpiece_<group>.py`): `bring_dive04` (DM Invoke: a recall to Gandalf's depth, then a pull to his
   square); `place(race, dist)` walks Gandalf to a floor square `dist` from Dive04 (from Dive04's map, or with
   `gmap=True` from Gandalf's full-level map with a clear line of sight) and summons there; `give_item` forges an item
   and has Dive04 fetch it; terrain is painted with `dm.paint`. The order under test goes in through `ctl(...)`
   (pilotctl, Navigator role by default, so order checks apply) the instant the monster lands.
3. `watch(secs, until)` polls the Pilot's decision log (`runs/pilot/dive04/`); `stats` extracts HP min, attention
   records, acts, Phase/Recall reads, cures; `check(name, ok, detail)` records each criterion.
4. `teardown`: clears hooks, `mission end`, then `charsave.sh restore` (unless `--keep`): Dive04 keeps nothing from a
   set-piece, death included. `finish` writes `runs/setpieces/<ID>-<time>.json` and appends a line to
   `runs/setpieces/results.md` (PASS only if every check passed).

**The set-pieces** (39 in `SETPIECES`; pass criteria and history in `harness/README.md`; status = latest run):

| group (file) | IDs | tests | latest |
|---|---|---|---|
| A: danger, hunts, escapes (`setpiece_a.py`) | A1 (trip plan vs orc groups), A2/A2I/A2K/A2L (an out-of-depth unique adjacent, no stairs: recall in 2 s), A2f (a rated caster 8 off), A3 (a goto held while a tiger is adjacent), A4 (Wormtongue near stairs), A5/A5s (unseen caster: no level change above 80% HP), A6 (blinking summoner, Phase budget), A7 (hunt a Hill giant), A7f (fear answered), A8/A8o/A8w (summoner hunt refused / overridden / walked away from), A9 (recall arrival: Door/Stair Location first) | danger rule, hunt check, WalkAway, escapes | all PASSed at least once; A2I, A2L, A2K, A6, A8w PASS 11-03 (A2's criterion follows the danger call since 11-02; A8w stages an Ogre shaman since 2.45.1); A4 not stageable (Wormtongue killed, a unique exists once) |
| B: hazards (`setpiece_bcd.py`) | B1 (mold beside path), B2 (STR-draining ants), B3 (Brigand thief), B4/B4w (town gold thief, idle/walking), B6 (painted trap on the path) | avoidance, drain response, thieves, traps | all PASS |
| C: items/uniques (`setpiece_bcd.py`) | C3 (hunt Ulfast, fetch his drop), C8 (unidentified Free Action boots vs a Floating eye) | drop fetching, ability inference | C3 PASS; C8 not stageable (the Forge's items come out identified; unit `ability_proofs` covers it) |
| D: movement (`setpiece_bcd.py`) | D3 (walled in behind a secret door), D6 (explore speed >= 3 tiles/s) | explore, search, mover/pathfind | PASS |
| L: rulebook claims checked live (`setpiece_l.py`) | L1 (Hill giant throws boulders), L2/L2g (resting speeds up recall), L3 (Free Action vs HOLD), L3b (rBlind cap) | game facts | L1, L3 PASS; L2/L2g FAIL (the claim is wrong in practice: any awake monster in LOS stops the speed-up); L3b not stageable (forge gives a plain cap) |
| M: mission regressions (`setpiece_mh.py`) | M1 (mold beside stairs loop), M2 (fetch a wand then dive), M3 (invisible DEX drainer), M4 (crowd emergency rules), M5 (confusing breeder swarm) | bugs seen in missions | M1-M4 PASS; M5 not reliably stageable (verified live instead) |
| H: hot swap (`setpiece_mh.py`) | H1 (hotswap.sh mid-trip), H1r (with a recall pending) | `hotswap.sh` | PASS |

**Gotchas** (more in `harness/README.md`, "Staging facts"):
- **A snapshot restore covers the character, not the world** (2026-11-01). `charsave.sh` copies Dive04's savefile and
  the Pilot's state files only; houses, shop stock and the floor live in the server. Never run, under a snapshot, a
  test that moves items between Dive04 and the world -- `plan town` (it withdraws the house's gold first), `house
  deposit/withdraw`, the stash, selling: on 11-01 a `plan town` test picked up the banked 19,327 gold and the stash,
  the restore put back the old savefile, and both were gone from the house (recovered with the DM, then deposited
  again). Test the town visit with a real one, or not at all.
- It takes over Dive04 and the test server: never run it during a mission, and only with the Pilot running.
- A repeat kill of a unique drops nothing and gives no XP; DM summons come with escorts; uniques exist once (a summon
  of one alive elsewhere fails silently); empty levels persist a while (hence the depth rotation).
- The Forge destroys whatever is in Gandalf's pack slot a; forged items are identified.
- Every run takes a snapshot in `runs/setpieces/saves/TAG/` (TAG = `ID-YYYYMMDD-HHMMSS`); after a good restore only the
  newest 5 timestamped snapshots are kept (since session 10, C12; 158 had piled up). Named checkpoints such as
  `dive04-pre-m43` stay. Excluded from `snapshot.sh`
  because savefiles hold passwords.

### `dm.py` -- the Dungeon Master driver

`DM(nick="Gandalf", port=28346)` logs Gandalf in through `client/mang.py` (private files `runs/private/gandalf.*`) and
drives the server's DM menu (`server/xtra2.c do_cmd_dungeon_master`) with the tool client's `interactive 13`, `keys`
and `special` events.

| method | does |
|---|---|
| `connect()`, `quit()` | log in / out |
| `menu(keys)`, `close()` | send keys into the open DM menu, keep the last screen in `self.screen` |
| `hooks()`, `clear_hooks()` | read / clear the menu's hook slots (a hook left set summons on every step) |
| `summon(race, step, after)` | put monster race N on the movement hook, step Gandalf so it lands where he stood, clear the hook, check |
| `paint(feat, steps)` | Build page: paint terrain feature N (1 floor, 48 secret door, 56 granite, 16-31 traps) on each square he walks off |
| `forge(kind, ego, number, pval)`, `drop_first(n)` | make an item in pack slot a, drop it |
| `players()`, `invoke(name)` | list players; pull one to Gandalf's square (same level) or recall it to his depth |
| `status()`, `walk(d, n)`, `descend(n)`, `ascend(n)` | Gandalf's state and movement (a ghost: walks through rock, sees the whole level) |

### `charsave.sh` -- character snapshots

`charsave.sh save|restore NICK TAG [PORT]`. Parks the Pilot (`pilotctl park` as the Architect: the script passes
the token from `runs/private/architect.token`, since `park` is the Architect's from 2.45.0; waits up to 330 s for it to exit),
sleeps 20 s for the server to free and save the orphaned character, refuses to touch the savefile if the server
hasn't saved since the logout, then copies `testserver/save/NICK` and the Pilot's state files (`orders deepest plan
standing navigator_debt keep stores uniques_killed rates recall .json`) to or from `runs/setpieces/saves/TAG/`, and
restarts the Pilot (`PILOT_ARGS` passed through). A restore deletes state files the snapshot lacks. Used by
`setpiece.py` and by hand for checkpoints (e.g. `dive04-pre-m43`, restore only on the user's word).

### `refactor/` -- the equivalence harness (session 11)

The checks behind the refactor's "no play change" versions (2.44.x; refactor-candidates E1-E8), run on an old and a
new tree and compared; no server. Each script's docstring has its command line. Run them from a scratch copy
(`SCRATCH/scripts/*.py`, next to a `SCRATCH/rundir_template/` holding a copy of Dive04's state files: `fake.py`'s
docstring), with `PYTHONHASHSEED=0`.

| script | checks |
|---|---|
| `fake.py` | (library) a deterministic fake clock and fake `MangClient`, so the real Pilot runs without a server |
| `equiv.py` | tick() equivalence: the real Pilot through scripted game states (177 at 2.46.0), recording every command, notice and log record; `EQUIV_COVER` records line coverage (`covreport.py`, `uncovered.py`; `summ.py` summarises a dump) |
| `cmdmatrix.py`, `cmpmatrix.py` | the command matrix: every command x argument variants x 6 roles x 5 contexts (E2), and its comparison |
| `dry.py` | a dry start: `Pilot.__init__` on a fake client, its state dumped |
| `bytecode.py`, `bcdiff.py`, `bcall.py` | moved code is bytecode-identical (one class's names, or every function of the Pilot's modules) |
| `stepdiff.py`, `stepdiff5.py`, `stepswap.py` | the step lists (E3, E5) are the old code moved verbatim; which adjacent step swaps a state can tell apart |
| `flagcheck.py`, `names.py` | lazily created flags declared with the same default (E5); no name defined twice across Pilot and its mixins |
| `split.py` | the E1 split helper (moves Pilot methods into a mixin module) |

---

## The rulebook (`rulebook/`)

**What:** the Advisor's tables of game facts, computed from the server source (`github/src/server/`,
`github/lib/edit/`): monster damage and danger, drop values, item-kind odds, shop owners, timing constants. The
Advisor owns and rebuilds them in `Advisor/data/rulebook/`; `sync.sh` copies them here so the Pilot runs against a
versioned copy. `rulebook/README.md` is the Advisor's (its `build_*.py` and `build_all.sh` live only in the Advisor's
directory).

**`sync.sh`** (run after the Advisor announces a release, then commit): copies `Advisor/data/rulebook/*.csv`,
`README.md`, `fight_sim.py`, `build_monsters.py`, `rule.py`, and `Advisor/data/monsters/monsters.csv` as
`monsters_raw.csv`; writes the date to **`SYNCED`** (now `2026-10-24 01:46`). Checked 2026-10-29: every CSV is
byte-identical to the Advisor's copy.

**`rule.py`** -- query CLI (also `pilotctl rule ...`, no Pilot needed; the Navigator's HANDBOOK lists it):

| command | answers |
|---|---|
| `monster NAME` | a monster's `monsters.csv` row (substring match, non-zero fields) |
| `unknown TVAL LEVEL` | expected value / P(worthless) / P(hazard) of an unknown flavoured item |
| `feeling KIND FEELING [LEVEL]` | what a pseudo-ID feeling means for a base kind |
| `owner NAME [CHR]` | a shop owner's buy/pay % |
| `const WORD` | timing/odds constants matching WORD |
| `room` | room and vault geometry facts |
| `fight MONSTER [--clvl --blows --dpb --tohit --ac]` | expected turns to kill and HP lost (closed form) |
| `drop MONSTER [DEPTH]` | what a kill drops |
| `object LEVEL [MODE]` | one floor object at an object level |

**`fight_sim.py`** -- Monte Carlo of one melee duel (player stands and fights one adjacent monster): the distribution
of HP lost (mean, p50, p90, p95) and turns. Ignores status effects, summons, fear, criticals, regeneration, other
monsters. CLI `fight_sim.py MONSTER [--clvl --blows --dice --todam --tohit --ac --hp --n]`; `table()` writes
`fight_dive04.csv`. **The Pilot uses it live:** `Pilot.fight_sim(race)` imports it, feeds it the race's row from
`monsters_raw.csv` and the live profile (clvl, wielded weapon's dice and plusses, AC, current HP), ~0.1 s for 600
duels; the hunt check and the danger rule ("the simulator's average loss is over 80% of current HP") use it.

**`build_monsters.py`** -- the Advisor's builder of `monsters.csv`; synced only because `fight_sim.py` imports its
damage helpers (`POWER`, `spell_dmg`, `ENERGY`, `dice`). Not run here.

**The tables** (consumer = our code that reads the file; "none" = reference for the Advisor/Navigator via `rule.py` or
by reading):

| table | contents | consumer |
|---|---|---|
| `monsters.csv` | all 616 races: hp, speed per player turn, melee by AC, spells, breath, hand rating, `veto_reason`, `worst_3turns_acNN` | `glyphs.load_rulebook` (ratings, speeds, emergency threshold), `Pilot.fight_estimate`, `rule.py monster` |
| `monsters_raw.csv` | raw `monster.txt` parse (dice, blows, spells, flags) | `Pilot.fight_sim` |
| `danger_table_v1.csv` | the 09-27 hand danger table (merged into monsters.csv) | none (the Pilot's old fallback copy is now `tools/attic/danger_table.csv`) |
| `fight_dive04.csv` | every monster to level 40 dueled 1,000x at Dive04's 10-23 profile | none (the Pilot simulates live) |
| `drops.csv` | per monster: expected gold, items, value, P(ego/artifact) at native depth | `Pilot` (hunt verdict, `monster` reply), `rule.py drop` |
| `drops_by_depth.csv` | the same at dungeon levels 1,5..100 | `rule.py drop NAME DEPTH` |
| `drop_object_by_level.csv` | one floor object by object level and mode: E[value], P(ego/artifact) | `rule.py object` |
| `kinds_by_level.csv` | flavoured kinds by level: P(kind), value, worthless, hazard | `itemvalue`, `Pilot` (junk kinds) |
| `unknown_expect.csv` | E[value] of an unknown flavoured item by tval and level | `rule.py unknown` |
| `jewellery.csv` | rings/amulets by kind and level: P(cursed), value percentiles | `itemvalue` |
| `feelings.csv` | per weapon/armour kind and level: value behind each pseudo-ID feeling | `itemvalue`, `rule.py feeling` |
| `ego_flags.csv` | all 118 egos with flags | `Pilot` (abilities a weapon/armour gives) |
| `abilities.csv` | messages that prove or disprove each ability/resist | `Pilot` (ability proofs), `setpiece.py` |
| `constants.csv` | timing, odds, ranges (time factors, recall, regen, traps, devices...) | `rule.py const` |
| `shop_owners.csv` | every owner's buy%/pay% at CHR 3..18/50 | `rule.py owner` (the Pilot uses `observe/shopmath.py`, same model) |
| `shop_stock.csv` | the stores' stock tables | `Pilot` (what a shop can sell) |
| `store_gear.csv` | town weapons/armour: dice, weight, AC, prices | none |
| `char_stat_tables.csv` | stat adjustment tables | `geareval` |
| `char_blows_table.csv` | the blows table | `geareval` |
| `char_extract_energy.csv`, `char_level_speeds.csv` | energy per game turn by speed; level speeds | none here (the Advisor's estimator) |
| `char_player_exp.csv`, `char_hp_expected.csv`, `char_skills_by_clvl.csv` | exp table, expected HP, skills by clvl | none |
| `structures.csv`, `vaults.csv` | room geometry (inner rooms, nests, pits), vault list | none (the Pilot's `structures.py` encodes the lattice itself) |
| `depth_value.csv` | per depth: XP and HP lost per kill, share of refused/avoided monsters | none (not in the README) |

---

## shopcat (`shopcat/`)

**What it was:** the project's first tool (2026-09-25): a headless cataloguer of **player shops**. `shopcat.py` logs a
character in through the tool-mode client, finds every closed house door on the level, walks to each and opens it,
and writes one JSON record per door (stock, prices, examine text); `--wilderness` tours the 12 wilderness levels round
town (`wild.py`); `nav.py` is its client-side path planner and runner; `report.py` flattens a catalogue to CSV. It ran
the live server's shop tour once (`runs/live-tour*.jsonl/csv`, 416 doors) and a regression (`runs/regress.py`). Its
README documents the options, output format and limits (including the server's 11th-arena crash).

**Still used?** Only two pieces:
- **`mang.py`**: since 2026-11-02 (E7) a shim that loads `client/mang.py` (`MangClient`, `ClientExited`,
  `meta_servers`: the Python wrapper for `mangclient -mtool`) under the same name, for `shopcat.py` and `newchar.py`.
  The Pilot, `harness/dm.py` and `observe/study/scribe.py` import `client/mang.py` directly.
- **`newchar.py`**: `newchar.py --nick NAME [--birth RACE:CLASS:SEX:STATS] [--privdir DIR]` writes
  `runs/private/NAME.pass` and `.mangrc` (mode 600), logs in with `--birth` (creates the character, or **replaces a
  dead one**), wields/wears the starting kit and prints a summary. Default build: Half-Orc Warrior,
  DEX>STR>CON>WIS>CHR>INT. `observe/study/scribe.py` imports `private_files` and `DEFAULT_BIRTH`. Needed again only for a new
  character (e.g. the planned live character Sneezy).

`shopcat.py`, `nav.py`, `wild.py`, `report.py` have no importers outside `shopcat/` and haven't changed or run since 2026-09-25 (the Pilot
has its own mover).

---

## Ops scripts and procedures

### Test-server procedures (summary of [`operations.md`](../operations.md))

- **Start the server:** from `testserver/` (the `-c` flag is broken), under gdb to catch crashes, **with the freeze
  variable**: `cd testserver && MANGBAND_FREEZE_FILE=$PWD/FREEZE nohup gdb -batch -ex run -ex bt --args
  ../github/mangband >> gdb_run.log 2>&1 &`. Stop with SIGTERM (clean save). Port 28346. A crash rolls characters back
  to their last save. Check processes with `pgrep -af "gdb -batch|pilot.py"`.
- **Freeze:** `tools/freeze.sh on|off|toggle|status` (or F5 / Ctrl-F in the viewer). Test server only.
- **Start or update the Pilot:** `tools/pilot/restart.sh Dive04` while Dive04 is idle in town; mid-mission,
  `tools/pilot/hotswap.sh Dive04`. Never kill a moving Pilot (queued walk commands on disconnect crash the server).
- **Characters:** the table in operations.md (Dive04 the player, Gandalf the DM, Scribe the messenger, Surveyor/Happy
  shop tools); passwords and configs in `runs/private/` (never in git); `newchar.py` for throwaways; `suicide NICK`
  kills one; a ghost floats up with `<` and resurrects in the Temple.
- **Orphans:** a dropped connection leaves the character in the world until idle 15 s (at once in town); a login
  before that resumes it in memory and ignores the savefile. So wait 20 s after a logout before copying a savefile
  (`charsave.sh` does); the freeze stops the idle timer, which is what makes `hotswap.sh` safe.
- **Keep tool characters out of the wilderness** on the test server (the arena crash).

### `freeze.sh`

`freeze.sh on|off|toggle|status` creates/removes `testserver/FREEZE` (contents "frozen by USER HH:MM:SS"). With the
server started with `MANGBAND_FREEZE_FILE`, no game turns run while the file exists (`net-server.c time_frozen`,
checked every 10 ticks; players see "*** Time is frozen (test server) ***"); the Pilot stops its game clock and holds (answers
requests, acts on nothing). Logins work while frozen. Without the variable (any other server) nothing freezes.

### `pilot/restart.sh` and `pilot/hotswap.sh` (operational use)

| | `restart.sh NICK [PORT]` | `hotswap.sh NICK [PORT]` |
|---|---|---|
| when | between missions, character idle in town; after a job/node restart | mid-mission, anywhere |
| how | `pilotctl park` as the Architect (the script passes the token; logs out at a safe moment), waits up to 330 s, starts `pilot.py`, prints status | freeze, SIGTERM the Pilot (KILL after 10 s; no park), start the new one, wait for it to answer, thaw (left frozen if it was) |
| keeps | savefile and the Pilot's state files | the character in memory, in place; the trip plan (`plan.json`) and a pending recall (`recall.json`) |
| loses | the Pilot's in-memory state (level map, refused stairs, fights) | the same |

Both pass `PILOT_ARGS` (e.g. `--hpwarn 0`) and append to `runs/pilot/NICK/pilot.log`. Tested live by set-pieces H1 and
H1r (~4 s swap). Internals: [pilot-core.md](pilot-core.md).

### `snapshot.sh` and `github/project/`

`tools/snapshot.sh` rsyncs the whole project directory (minus `github/`) into `github/project/tree/`, the Architect's
and Advisor's Claude memories into `project/memory/{architect,advisor}/`, and `~/.claude/CLAUDE.md` into
`project/claude/`, writes `project/SNAPSHOT_TIME`, and fails if anything token-like slipped in. It excludes secrets and
bulk on purpose (the repo is public: github.com/userjjb/Mangbot): `runs/private/`, `*.pass`, `*.mangrc`, savefiles
(`testserver/save/`, `runs/setpieces/saves/`), server logs and crash dumps, the forum corpus and other third-party
copies, raw event streams, packet logs, files over 5 MB. Run it before every commit and push (`git push origin
restructure --tags` per operations.md; `master` stays at the tag `pre-restructure`). `project/README.md` explains how to restore a
commit's state (copy `tree/` back, recreate `runs/private/` with `newchar.py`, copy the memories back).

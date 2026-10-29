# Refactor candidates (session 10, consolidated)

One de-duplicated list from the ten survey notes (now `history/survey-notes/*-candidates.md`) and their doc/code discrepancy
reports, **for the user to approve item by item**.

**Status (2026-10-29, session 10):** the user approved A1-A3, A6, A8-A11: **done** (commit dd2200d, 117 unit
cases, Pilot restarted 08:35, Advisor told). A13 added (found while fixing A3). B15 partly done (memory pointers).
The user then approved, and session 10 did, A4, A5, A7, A12, A13, A14 and group C's C1, C2, C5-C13 (C11 with a
`CHANGELOG.md` and code versions, `github/VERSION`): 120 unit cases. C8: the dead-character whitelist lost `events`,
`news`, `inventory`; the scorecard/viewer query lists were kept (Navigators did type those names, so they classify
real attempts; D7 will merge the lists). C3, C4, C14 still await the user; groups B, D-F are still open.

**Rules for every step**
- Behaviour unchanged unless the item says otherwise and the user agreed (all of group A, and items marked *behaviour*).
- After each step all 120 unit cases pass: `python3 tools/harness/unit.py`; Pilot changes also get a hotswap and one
  set-piece before the next mission.
- Advisor constraints: keep `tools/observe/shopmath.py` at its path (Advisor's `build_shops.py` imports it by absolute
  path); keep the log formats (decisions/events/state.jsonl kinds and fields, `levels/*.txt`, scorecards,
  `missions.json`) and `TICK_S`; tell the Advisor if `escape()`, `group_tick`, `speed_start_tick`, `berserk_tick` or
  `fear_cure` are renamed (its estimator mirrors them by name).

Format: **ID** what -- *evidence* -- risk/effort (S/M/L) -- **do / ask / skip**. **[N]** = Navigator-facing.

## A. Bugs found while surveying (behaviour changes: need the user's OK)

- **A1** `escaping_to_stairs` is never reset: after the first escape walk to stairs, `escape()` skips its rest/retreat
  branch whenever any mover runs, ticks *any* mover (e.g. Explore) as an escape walk and takes whatever stairs it reaches,
  and the emergency reflex stops stopping the mover. -- *set True in `escape()`, False only in `__init__` (verified by
  the Architect)* -- M/S -- **do** (clear on walk end / level change; tell the Advisor: base_policy).
- **A2** Flavour learning pairs the wrong item: the "You have no more X" branch of `learn_flavours_tick` takes any
  vanished unknown's tval; `learn_flavour` never checks type words. -- *`runs/flavours.json`: "Amber Amulet" = "Scroll
  of Identify"* -- S/S -- **do** (match tval by X's type word, reject mismatches, then delete the bad entry).
- **A3** Shadow snapshot passes the weapon's own (+h,+d), not totals; the estimator underrates our damage (rings,
  gloves, STR missing). -- *`shadow.weapon_profile`; Advisor memo 2026-10-28 §4 says totals; geareval's `sim_player`
  passes totals* -- S-M/S -- **do** (build from `gear_character().derive()`; tell the Advisor, agree-rates shift).
- **A4** `emergency_loop` counts every `emergency` notice, incl. non-actions ("waiting to use ... fighting on" every
  10 s, "potions too weak", kill_caster's "attacking X first"), so `until emergency_loop` can end trips early. --
  *pilot-combat survey* -- S-M/S -- **ask** (count escape actions from `log_escape`/cures instead). **done (session 10)**
- **A5** `order pickup=none` still walks to loot within `loot_radius` (`loot_step` not gated). -- *pilot-items survey;
  order comment implies otherwise* -- S/S -- **ask** (gate `loot_step` on `pickup == "all"`?). **done (session 10)**
- **A6** Gear: `optimize` keeps NO_LOSS+REQUIRED+resists but `compare(no_loss=True)` rejects losing *any* flag, so
  loadouts losing a sustain are simulated then ruled out with "an automatic swap never does". -- *geareval* -- S/S --
  **do** (one shared predicate).
- **A7** Gear eval's `encounters()` reads the whole decision log each time (no `since`); the "met fights" set includes
  fights from much earlier in Dive04's life. -- *gear survey* -- S/S -- **ask** (window it like `why_info`). **done (session 10)**
- **A8** `damage_mix.py` always uses the 700-800 ft band (`wrap.sh` passes no depth): EHP goes stale as we dive. -- *wrap.sh*
  -- S/S -- **do** (pass the mission's depth band).
- **A9** scorecard.py: no labels = rescore all 200 missions (incl. 156 `sp-*`) and rewrite every card, even with
  `--table`; `--all` is a no-op. -- *`pick = [m for m in missions if not a.labels or ...]`* -- S/S -- **do** (explicit
  `--all`, skip `sp-*` unless asked; card format unchanged).
- **A10** Mission watchers: `watch_mission.py` hard-codes `runs/pilot/dive04`, starts at file ends (events between exit
  and restart lost), and matches any "Error" in pilot.log; `wrap.sh` complaints window breaks across midnight;
  `notes.py --questions` has no time filter. -- *observe survey* -- S/S -- **do** (`--nick`, start offset,
  traceback-only match, time filters).
- **A11** `review wear NAME` is recorded as `keep` and in the dungeon silently wears nothing. -- *pilot-items* -- S/S --
  **do** (say so in the reply). **[N]**
- **A12** pilotctl prints notes twice (`DONE: ... -- note` then `NOTE:`; goal replies print JSON then `NOTE:`). --
  *commands survey* -- S/S -- **ask** (Navigator-visible output; HANDBOOK quotes no exact format). **[N]** **done (session 10)**

- **A13** (found while fixing A3) `geareval.Item` reads "a Ring of Damage (+6)" / "a Ring of Accuracy (+8)" as a pval,
  so their to-dam/to-hit count for nothing in gear verdicts and in the shadow snapshot's totals (the server's
  `object1.c` prints a lone to-dam/to-hit that way; Dive04 has met Rings of Damage). -- S/S -- **ask**. **done (session 10)**

- **A14** (the Advisor asked, memo 2026-10-29-s10-reply) Pass `slays`, `brands` and `weight` in shadow snapshots, as
  geareval's `sim_player` does: worth ~10-15% of our damage at 750 ft plus ~6% criticals. Shadow mode never acts, so
  only the estimator records change. -- S/S -- **ask** (small; the follow-up to A3). **done (session 10)**

## A2. Found by the doc verification (session 10, 10-29; behaviour changes: need the user's OK)

Ten agents checked each docs/ file against the code (~1,200 claims, ~100 doc fixes). These look like **code** bugs;
none is fixed. **[N]** = Navigator-facing.
- **A15** `auto_destroy` checks the keep list only for junk kinds: its pass by pseudo-ID feeling (`{cursed}`,
  `{worthless}`) destroys a kept item. -- S/S -- **ask** (check `is_kept` in both passes).
- **A16** `order autodestroy=` (empty) also turns off destroying `junk`-order kinds and `JUNK_DEVICES` (the method
  returns at once). -- S/S -- **ask**.
- **A17** `pack_value` treats every Mushroom as priceless (the `TV_FOOD` test precedes the junk check): unknown or
  table-junk mushrooms are never destroyed to make room. -- S/S -- **ask**.
- **A18** `request_trip` accepts `until "wor<=1"`, which holds as soon as the trip has recalled down (the guard
  `int(c[3]) - (c[2] == "<=") >= 1` looks reversed). **[N]** -- S/S -- **ask**.
- **A19** `supply_minutes` counts any worn light that isn't a lantern (a torch) as permanent: "light permanent", and
  `supply_watch` never warns. -- S/S -- **ask**.
- **A20** `reflexes`' hunger step returns early (food eaten < 10 s ago; Hungry with only Satisfy Hunger scrolls), which
  skips pickup, auto-destroy, engage and rest for that tick, possibly until Weak. -- S/M -- **ask**.
- **A21** `emergency_loop` with stairs known but the goal already Flee sends "no stairs known nearby". -- S/S -- **ask**.
- **A22** `order a=1 b=bad`: `a` is set in memory, then the error returns before orders.json is written (lost on
  restart). With F5. **[N]** -- S/S -- **ask**.
- **A23** `settle_hunt`: `status == "done" and "slain" in d or "killed" in d` -- a failed hunt whose detail says
  "killed" counts as slain, so no fight debt. -- S/S -- **ask**.
- **A24** scorecard `commands_per_min` counts `wait_report` records, which `commands` excludes. The Advisor's metric:
  memo it. -- S/S -- **ask**. **The Advisor (memo 10-29 commands-per-min): not intended; fix it** (same
  population as `commands`; a separate `reports_per_min` if wanted; regenerating past cards is fine), and reword the
  `deaths` comment to "deaths, emergencies and escalations come from acount (plan news excluded)".
- **A25** Set-pieces A2I (10-24) and A2L (10-25, "Lugdush never seen") last ran FAIL and were never re-run. -- S/S --
  **do** (re-run before the next mission). **Re-run 10-29 on 2.38.0: both FAIL "Word of Recall within 2 s", but the
  Pilot was right:** Ibun and Lugdush are no longer above clvl-29 Dive04, so it drank Speed + Berserk, killed the unique
  and its band (lowest HP 76-80%) and fetched the drop. The scenarios are stale, not the Pilot: to test the recall rule
  they need a unique above our level (A2's Ulwarth is also below 29 now). **ask** (rescale A2/A2I/A2L).
- **Text only (add to B11/B16):** `loadout_info`'s header tells the Navigator "slays, brands and criticals aren't
  simulated" (they are) **[N]**; geareval's module docstring (optimizer "not built", no resists/criticals);
  `group_danger` docstring (+150 drain weight); world.py's `arrived_by` 'recall'; `compact()` "map: dungeon only";
  TownKit "one more look after 40 s"; c-tool.c header `interactive 21` (13); hotswap.sh "untested"; setpiece.py
  `--depth`/`sid` help; harness/README traps "24-31" (16-31); unit.py's filtered total line; scorecard "16
  categories" (17); scribe.py's `--birth`; watch_mission's usage without `--backlog`; pilot.py installs no SIGTERM
  handler (hotswap's kill is Python's default exit).

## B. Doc fixes (stale docs vs code; no behaviour change)

- **B1 [N]** HANDBOOK names a `sell` command (lines ~17, 21: `sell !NAME`); it doesn't exist: `goal shop N sell
  [!]NAME`. Also: `inscribe`/`wearall` are blocked in the dungeon, undocumented. -- S/S -- **do**. **done (session 10, 2.38.0)**
- **B2 [N]** Stash "in the tavern (8)" in HANDBOOK (l.37), BRIEF-TEMPLATE (l.29), FIELD-NOTES (~l.65): since session 9
  it's the wilderness house (HouseBank, `stash_wanted`). -- S/S -- **do** (after D10 is decided, wording "the house"). **done (session 10, 2.38.0)**
- **B3 [N]** HANDBOOK "eats rations to Full" (l.40) and the `KITS` comment: code eats to Fed, <=3 rations, when Hungry or
  worse. -- S/S -- **do**. **done (session 10, 2.38.0)**
- **B4 [N]** HANDBOOK-reference: `goal goto`/`stairs` in ~5 places (refused to the Navigator); orders table lacks
  `autowear`, `enchant_max`, `band_frac`, `nopickup`; emergency "2.5 worst-case rounds" (code: worst 3 turns, <90% HP);
  `danger_seen` "dropped the goal" (it's resumed); newer escape steps missing. -- S/S -- **do** (or see C14). **done (session 10**, the user: B4 now, C14 later; and
  `danger_seen` really does drop the goal -- only a trip plan carries on -- so "resumed" above was wrong)
- **B5 [N]** HANDBOOK `plan trip ... until`: check the condition list against the code (`emergency_loop`,
  `unseen_attacker`). -- S/S -- **do**. **done (session 10, 2.38.0)**
- **B6 [N]** pilotctl.py docstring (its help): advertises `goal goto`/`stairs`/`raw`, lacks ~15 commands (ask, answer,
  debt, price, why, prep, gearcmp, loadout, react, review, keep, house...). -- S/S -- **do** (cut to a pointer to
  docs/commands.md now; generate from the table after E2). **done (session 10, 2.38.0)**
- **B7 [N]** BRIEF-TEMPLATE fixed text: gear (Rings [+12]/[+10], Brodda's boots; now [+16]/[+12], Boots of Stability),
  tavern stash, session-8 `[VACATION]` paragraphs. -- S/S -- **ask** (move gear into `{...}` fields; changes mission
  comparability). **done (session 10, 2.38.0)**
- **B8 [N]** `.claude/agents/navigator.md`: HANDBOOK "~110 lines" (198); add "never set PILOT_ROLE" (see F3). -- S/S --
  **do**. **done (session 10, 2.38.0)**
- **B9** `design_pilot.md` stale beyond its disclaimer (non-goals as goals, orders `danger`/`keep (min rations)`, `pilotctl
  log`, 10 Hz vs 20, "Phase 1 (C)"). -- S/S -- **do** (keep the architecture part, mark the rest history, point to
  docs/pilot-core.md, goals-and-plans.md).
- **B10** `design_gear.md`: score per game turn (code: per real minute); tie-break AC (code: lowest HP then EHP);
  slays/brands now simulated; hard set 22 not 21; awake 0.4. -- S/S -- **do**.
- **B11** Stale docstrings/comments in code (text only): pilot.py module docstring (2026-09 8-rule order); `escape()`
  (misses teleport, Speed, WoR, futility, kill-caster, crowd teleport); `Recover` ("arrival rule" is the reflexes');
  TownKit ("40 s"; code 4 x 35 s); HouseBank ("town house"); `loadout_info` and geareval module ("slays not
  simulated", "optimizer not built"); reflexes step numbers ("3a'" twice). -- S/S -- **do**.
- **B12** `c-tool.c` header: DM menu is 13 not 21; "(PKT_CLEAR...)" under the wrong verb; event list misses
  `local_browser`, `target`, `flags`, `floor`, `options`, `minimap`. -- S/S (comment, no rebuild needed) -- **do**.
- **B13** operations.md: `git push origin master` (we push `restructure`); "frozen logins wait" (H1: they work);
  "depth indicator is one signed byte" (live only; test server sends 16 bits); "Tools" section stale (link docs/);
  record the user's 10-27 decision to keep `ask_unlimited` under "User decisions". -- S/S -- **do**.
- **B14** roles.md: Navigator "to be built" (built 09-27); "Where knowledge lives" misses FIELD-NOTES, BRIEF-TEMPLATE,
  docs/. -- S/S -- **do**.
- **B15** Memory pointers: project-map "ARCHITECT HANDOFF" (now "WHICH HANDOFF IS YOURS"); inbox-watcher "lasts at most
  10 minutes" (script loops; 10 min is the Bash timeout); advisor-memos is a log ending 10-26 (point to memos/). --
  S/S -- **do** (with C11, per the SYNC RULE).
- **B16** Ops/harness headers: hotswap.sh "Untested in the dungeon yet" (H1/H1r passed 10-25); setpiece.py argparse help
  (`sid` lists 4 of 39, `--depth` 300-500 vs 300-650); harness/README misses A2I, A2K, C8; scorecard.py docstring "six
  groups/16 categories" (8/17); watch.py docstring omits F5/Ctrl-F and says it never sends a game command. -- S/S -- **do**.
- **B17** One home for the mission checklist (now spread over HANDOFF 8/11, VACATION-NOTES §5, BRIEF-TEMPLATE): docs/process.md
  §3, linked from brief and handoff. -- S/S -- **do**.
- **B18** Advisor-owned files (don't edit, memo the Advisor): `rulebook/README.md` (`build_all.sh`, missing
  `depth_value.csv`); `rulebook/fight_sim.py` hard-codes `Advisor/data/monsters/monsters.csv`. -- S/S -- **do** (memo).

## C. Remove / archive (dead scripts and code)

- **C1** `tools/pilot/replay_group.py`: no caller in tools/, hooks or scripts; one-off tuning script reading legacy
  `pilot/danger_table.csv` by absolute path. -- S/S -- **do** (move to `tools/attic/`). **done (session 10)**
- **C2** `observe/latency.py`: no caller since m22, last edit 10-23; scorecard group E covers report->action. -- S/S --
  **do** (attic; fold alert->contact into the scorecard only if the Advisor wants it). **done (session 10)**
- **C3** `observe/record.py`, `timeline.py`, `screen.py`, `scribe.py`: unused since 09-25, only operations.md lists them;
  timeline's commit says "untested draft"; record.py defaults to port 18346. -- S/S -- **ask** (move to `observe/study/`).
  **done (session 10**: the user will record their play again; moved, paths fixed, `study/README.md` warns of the
  live-port default)
- **C4** `shopcat/shopcat.py`, `nav.py`, `wild.py`, `report.py`, `runs/regress.py`: no importers, last run 09-25 (the
  Pilot has its own mover). Keep `mang.py` (see E7) and `newchar.py`. -- S/S -- **ask** (live shop tour wanted again?).
  **Kept (the user, 10-29):** the shop catalog will be updated once we deploy to live; repairing the tour is an item in
  `live-deploy-todo.md`.
- **C5** Dead second `plan` branch in `do_request` (`mover.plan` debug): the earlier `if c == "plan": return
  self.request_plan(args)` always wins. -- S/S -- **do** (delete, or rename to `path` if wanted). **done (session 10)**
- **C6** `choke_tick`: `ch in "<>" and False` is never true. -- S/S -- **do**. **done (session 10)**
- **C7** watch.py `feed_line`: `elif k == "attention" and what == "user_message"` follows `elif k == "attention"`, so never
  runs. -- S/S -- **do** (reorder if the display was meant, else delete; viewer only). **done (session 10)**
- **C8** Nonexistent command names in whitelists: dead-character whitelist (`events`, `news`, `inventory`), watch.py
  `NAV_QUERIES` (`flags`, `commands`, ...), scorecard/latency lists (`help`, `floor`, `quote`, `dump`). -- S/S -- **do**
  via D7 (scorecard list: check `--check` with the Advisor's definitions). **done (session 10)** (the whitelist only;
  the query lists kept, see Status)
- **C9** `pilot/danger_table.csv` fallback: `glyphs.load_danger` runs only if `rulebook/monsters.csv` is missing; 09-28
  table, duplicated as `rulebook/danger_table_v1.csv`. -- S/S -- **do** (missing monsters.csv = startup error). **done (session 10)**
- **C10** `kinds.csv`: read only as a fallback in `load_flavours` when `rulebook/kinds_by_level.csv` is missing. -- S/S --
  **do** (drop file + branch; update unit.py's "38 kinds of the old kinds.csv" check). **done (session 10)**
- **C11** next_steps.md is ~1,800 lines, ~1,500 history; the 09-25 "Read these first" table is wrong (memory holds
  passwords, shopcat main tool); watch_mission path stale. Move old handoffs + Reflections to `history/handoffs-s1-s9.md`;
  also move `restructure-step2.md`, `VACATION-NOTES.md`, `notes_merge.md`, `spells.md` to `history/`. -- S/S -- **do**
  (update memory pointers and snapshot paths). **done (session 10)**
- **C12** `runs/setpieces/saves/`: 158 snapshot dirs, 55 MB, never deleted; only named checkpoints (e.g.
  `dive04-pre-m43`) matter. -- S/S -- **do** (delete unnamed; setpiece deletes its tag dir after a good restore). **done (session 10)**
- **C13** `testserver/` clutter: `mangband.prefreeze` (Oct 17 binary), `crash1..4`, `gdb.log`, `watch.log`; and the
  snapshot copies `testserver/data/Makefile.am` into github/project. -- S/S -- **ask**. **done (session 10)**
- **C14** HANDBOOK-reference.md (569 lines, "not required reading", lessons of m1-23) overlaps HANDBOOK + docs/commands.md.
  -- M/M -- **ask** (shrink to the event/report-line glossary; the Navigator greps it). **[N]**
  **Deferred (the user, 10-29):** B4 first; shrink later as an **A/B test**: compare missions on the pre-C14 reference
  with missions after the shrink (Navigator questions/asks, held or refused orders, report-to-action latency,
  scorecard), same Navigator model and effort. Todo in next_steps.md.
- **Skip:** unused rulebook CSVs (Advisor's, sync.sh copies all); c-tool verbs no tool sends (`alter`, `suicide`,
  `minimap`, ...: manual use); `ask_unlimited` rate-limit code (the user kept it 10-27); old `runs/` dirs (data).

## D. Duplicates to merge

- **D1** Light fuel parsed ~10 times (`with (\d+) turns`): `Pilot.light_left`, nested `light_left` in `wear_step`
  (counts a no-turns lantern as 0, the static one as 1), `keep_light`'s `left()`, TownFarm, `supply_gate`, `lantern_fuel`,
  `supply_lines`, `world.light_fuel`; Recall and TownFarm wear a light by hand. -- S/S -- **do** (one helper in
  world.py + `wear_light`; pick 0 or 1: tiny *behaviour*).
- **D2** Name normalising `re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", n))` 12-15 times;
  `{cursed|worthless|broken|terrible}` regex 8 times. -- S/S -- **do** (`kind_key_of` + one `bad_inscription()`).
- **D3** Junk rules in three places (`is_junk_name`, `auto_destroy` + `JUNK_DEVICES`, the tick's `known_junk`) with
  different lists and tval limits. -- M/M -- **ask** (one `is_junk(it)`; changes what gets destroyed: *behaviour*).
- **D4** Phase Door lookup 7x (some honour `@r1`, the fear phases don't), WoR 6x, potions by name. -- S/S -- **do**
  (`find_item`, `phase_item()` always honouring `@r1`: small *behaviour*).
- **D5** Consumables dict built twice (`shadow_decision`, `gear_character`: same `n(word, tv)`, staff regex). -- S/S --
  **do** (`consumables_inv()`).
- **D6** Weapon (dice, +h,+d) parsing 5x (`shadow.weapon_profile`, `fight_sim`, `fight_estimate`, a top-level helper,
  `geareval.Item`). -- M/M -- **do** after A3 (use `geareval.Item`; hunt checks depend on it).
- **D7** Log loaders: `load()` in scorecard and latency, decision scans in notes.py and damage_mix.py; three disagreeing
  "query command" lists (scorecard `QUERY_CMDS`, latency `NOT_ORDERS`, watch `NAV_QUERIES`). -- M/M -- **do**
  (`observe/logs.py` + one list exported by pilot; scorecard equality checked with `--check`).
- **D8** Two damage attributions (scorecard `damage_by_monster` vs damage_mix's regexes/windows). -- M/M -- **ask**
  (Advisor's metric definitions).
- **D9** `SHOP_CUT = 0.38` in scorecard.py and pilot.py; scorecard's own `est()` + junk regex instead of
  `itemvalue.value` and owner-aware `pay_cut`, so its value estimates diverge from the Pilot's. -- M/S -- **ask** (changes
  scorecard numbers: Advisor).
- **D10** Stash recorded twice (`stash.json` items and `house.json` items; stash.json also keeps tavern squares,
  free-text `where`/`lost`); the tavern path is now a no-house fallback. -- M/M -- **ask** (house.json the source of truth).
- **D11** Three tval->slot tables (`ARMOUR_SLOTS`, `WEAR_TVALS`, `geareval.SLOT_OF_TVAL`), two `FLAVOURED`; `pickup_room`
  uses `23` though `PACK_SLOTS` exists. -- S/S -- **do**.
- **D12** `compact()` and `report()` duplicate monster/structure/weapon/"since" formatting (both reset `self.since`). --
  S/S -- **do** (shared formatters; report text unchanged).
- **D13** Three static AC "better than worn" checks (`gear_line`, `gear_review`, `upgrade_step` step 3) with different
  guards. -- M/M -- **ask**.
- **D14** Supply notice kinds `low_supply` / `supply` / `supplies`; `food_watch` overlaps `supply_watch`. -- S/S --
  **ask** (event kinds are a log format: Advisor + viewer + HANDBOOK).
- **D15** `goal recall`'s supply gate recomputes `planned_depth()` inline. -- S/S -- **do**.
- **D16** `inbox.sh` copied in `.claude/hooks/` and `Advisor/.claude/hooks/` with no check. -- S/S -- **do** (snapshot.sh
  warns on drift; never edit the Advisor's copy).

## E. Splits and structure

- **E1** Split pilot.py (10,558 lines; `class Pilot` 7,527). Move methods to mixins so names (and the Advisor's
  mirrored names) stay on `Pilot`. Proposed layout in `tools/pilot/`, approx lines:

  | module | contents (from docs/pilot-*.md, commands.md, goals-and-plans.md) | ~lines |
  |---|---|---|
  | `pilot.py` | `Pilot` core: `__init__` (all state), log/notify/cmd, verify/audit, `tick` loop, goals stepping, gains/rates, mission save, structures/level map | 1,300 |
  | `daemon.py` | `Handler`, `Server`, `main` (arg defaults: F1) | 170 |
  | `goals.py` | `Goal`, Wait, Goto, Explore, Dive, Search, Hunt, Recover, Reprieve, BandLeave, WalkAway, Flee, Recall, Resurrect, RestGoal, QuietWait + helpers | 1,250 |
  | `town_goals.py` | Town, TownFarm, Shop, StashDeposit/Fetch, HouseBank, TownKit | 1,050 |
  | `plan.py` | TripPlan, `plan_tick`, `request_trip/plan`, `supply_gate` | 700 |
  | `combat.py` | `reflexes`, `escape`, engage/group/still/status/unseen/choke ticks, Speed/Berserk/fear, danger_why, watches (band, drainers, thieves, traps, breeders, progress), react rules | 1,900 |
  | `items.py` | values/debt, pickup/loot/junk/auto_destroy, flavours, identify, review, `upgrade_step`, `wear_step`, light helpers | 1,300 |
  | `gear.py` | gear_line/review/character/eval, loadout_info, shadow_*, fight_* | 650 |
  | `town.py` | `town_*`, provision, price_of, stash/house state | 650 |
  | `commands.py` | command table, `request_goal`, refusals/stale check, why/prep/price/house/ask/answer | 1,100 |
  | `report.py` | compact, compact_changes, report, belief/since/movement/supply lines | 550 |

  Steps (each its own commit, unit.py + hotswap between): E6 first; then daemon.py + report.py; goals/town_goals/plan
  (top-level classes, easiest); gear, items, town, combat mixins; commands last (with E2). -- M/L -- **do**, in steps.
- **E2** `do_request` (626 lines of `if c == ...`) -> command table `{name: (method, roles, where, positional)}`; role
  checks now spread over `do_request`, `request_goal`, `house_info`, `answer_navigator`, `Shop.tick`, `wear`; extract
  the ~150-line item-action branch (`parse_item_args`, `action_refusal`, `action_reply`); pilotctl help from the table. --
  M/M -- **do**.
- **E3** `reflexes()` (374) and `escape()` (201): one method per numbered step, order kept in one list (keep the five
  Advisor-mirrored names). Moving light/hunger/pickup out of `reflexes` into `policy_tick` and `food_watch` into `tick()`
  changes order: *behaviour*. -- M/M -- **do** the split, **ask** the moves.
- **E4** `Pilot.tick` (238): extract `watch_items()`, `trail_tick()`, `clock_tick()`, avoid-zone build. -- S/S -- **do**.
- **E5** `TownKit.tick` (~210, flags created via `getattr`/`setdefault`: withdrawn, fetched, id_bought, stashed, ...),
  `Shop.tick` (~180), `HouseBank.tick` (~200), `TripPlan.tick` (~190): one method per step/phase (`_trade_sell`,
  `_cross`/`_door`/`_inside`, `_phase_down`/`_level`/`_home`). -- M/M -- **do** after set-pieces cover the town visit.
- **E6** ~190 lazily created attributes (`__dict__.get/setdefault`, `getattr`: `item_cmd_t`, `gold_found`, `since`,
  `walkaway_failed`, Dive's `scummed`/`kept`) and goal attributes set from outside (`role`, `by_navigator`, `by_plan`,
  `stop`, `abort`, `quiet`...): declare in `__init__` / on `Goal`; add `Pilot.for_test()` so unit.py's `pilot()` stops
  mirroring `__init__`. -- S-M/M -- **do** (first, before E1).
- **E7** `MangClient` lives in `tools/shopcat/mang.py` but pilot.py, harness/dm.py, observe/scribe.py import it via
  `sys.path` hacks: move to `tools/client/`, leave a shim. -- M/S -- **do**.
- **E8** `unit.py` (3,177 lines, 120 cases) -> files by family + `fixtures.py`; `setpiece.py` (1,492) -> `Run` framework
  vs 39 scenarios; harness/README -> reference table + findings log. -- S-M/M -- **do** (unit count must stay 120).
- **E9** scorecard.py `card()` (~170 lines) -> one function per group. -- S/S -- **do** (cards byte-identical).
- **Skip:** move shopmath.py (Advisor constraint; shim only if ever needed); c-tool.c `tool_do_command` verb table (C
  rebuild, low value).

## F. Defaults / safety

- **F1** Default `--port 18346` (the live server) in `pilot.py: main`, `MangClient.__init__`, `record.py`; every script
  passes 28346. -- S/S -- **do** (default 28346, or require `--port`).
- **F2** pilotctl default nick `dive01` (`$PILOT_NICK`): a bare `pilotctl status` hits a dead socket. -- S/S -- **do**
  (require `--nick`/env, or default to the one running Pilot).
- **F3** `PILOT_ROLE` is an unauthenticated env var: anyone can claim `architect` and skip hunt checks and debt. -- S/S
  -- **do** the navigator.md line now (B8); **ask** for a token file / socket-peer check.
- **F4** `mission` command has no role check (Architect's). -- S/S -- **do** (architect-only).
- **F5** `order` parsing: `type(cur)(v)` and `order KEY` without `=` surface a bare `ValueError` repr. -- S/S -- **do**
  (friendly usage error). **[N]**

## Suggested order for the session

1. **Doc fixes, Navigator-facing first** (B1-B8), then B9-B18. ~1.5 h total, no code risk.
2. **Dead code and archives** (C1, C2, C5-C12; ask C3, C4, C13, C14). ~1 h.
3. **Safety defaults** F1, F2, F4, F5. ~30 min.
4. **Cheap duplicates** D1, D2, D4, D5, D11, D12, D15, D16, then D6, D7. ~2 h.
5. **Structure, in steps:** E6 -> E7 -> E4/E9 -> E1 (one module per commit) -> E2 -> E3 split -> E5 -> E8. ~1-2 sessions.
6. **Bugs only with the user's OK:** A1, A2, A3 first (clear wins), then A6, A8-A11; ask A4, A5, A7, A12. ~2 h,
   each with a unit case added.

Rough effort per group: A ~2 h, B ~1.5 h, C ~1 h (+ asks), D ~3 h, E ~1-2 sessions, F ~30 min.

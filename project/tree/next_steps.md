# Next steps: the Architect handoffs

The handoff between Architect sessions: the current state, what the next session does, and its rules.
- The big picture and every component: `docs/CONDENSED.md`, then `docs/README.md`.
- What changed when, by version: `CHANGELOG.md`.
- Older handoffs (sessions 1-9, the 09-25 "state of play", Reflections): `history/handoffs-s1-s9.md`; other retired notes
  (VACATION-NOTES, restructure-step2, notes_merge, spells) are in `history/` too.

### USER TODO (the user, 2026-10-29)
- **Review the old handoffs in `history/handoffs-s1-s9.md`** for context worth keeping for future sessions (moved out of
  this file in session 10, C11). Bring anything worth keeping back into `docs/` or `CHANGELOG.md`. Architects: remind the
  user at the start of a session while this item is open.

### TODO (the user, 2026-10-29)
- **Live deployment:** the checklist is `live-deploy-todo.md` (project top). Add to it whenever something live-only
  comes up.
- **C14 as an A/B test:** shrinking HANDBOOK-reference.md (refactor-candidates C14) is deferred. Before doing it, run
  a few missions on the current reference (B4-fixed, version 2.37.1+) as the baseline; then shrink it and run the same
  number with the same Navigator model and effort. Compare Navigator asks/questions, held or refused orders,
  report-to-action latency and the scorecards (BRIEF-TEMPLATE's "did you need HANDBOOK-reference.md?" answers too).


### >>> WHICH HANDOFF IS YOURS? <<<
- **Session 10 is done** (2026-10-28 to 11-02): the Documentation (`docs/`), the cleanup list
  (`docs/refactor-candidates.md`) worked through groups A-D and F plus E6/E7/E4/E9 and E1 steps 1-3, `CHANGELOG.md` and
  versions (2.36.0 -> 2.44.7). Its full record: **"SESSION 10 RECORD"** at the bottom of this file. No missions ran.
- **Session 11 is done** (2026-11-02 to 11-04): group E finished -- E1 steps 4-6 (town.py, combat.py, commands.py;
  pilot.py now ~1.5k lines), E2 (cmdtable.py), E3, E5, E8 (2.44.8 -> 2.44.14); then the user's play changes and the
  docs audit (2.45.0 -> 2.49.0); one test mission, **m61** (Opus medium, 84.1 XP/dmin, clean; its food bugs fixed in
  2.48.1); the restructure merged into `master` (branch deleted, revert material removed); the GitHub front page
  updated. Its record: **"SESSION 11 RECORD"** at the bottom; what session 12 watches: **"SESSION 12 WATCH LIST"** at
  the top of HANDOFF 12. Its brief ("HANDOFF TO ARCHITECT 11") stays below for reference.
- **Session 12** (missions resume, **to test everything changed since m60**): read **"HANDOFF TO ARCHITECT 12"**;
  in progress since 11-04 (job 8406367): m62-m65 and 2.50.0-2.57.0, see **"SESSION 12 RECORD"** at the bottom.
- **Session 13** (the user, 11-03): **the separate local test server** for set-pieces (own port, saves, config,
  freeze file; copies of Dive04), then server-side test features (HANDOFF 12 item 3, TODOs 3-4). It unblocks A25's
  remaining half (a unique above the character's level: the recall branch), **and the repo as a patcher** (11-04).
  Read **"HANDOFF TO ARCHITECT 13"**. Missions come first (session 12).
- Sessions 1-9 are over: `history/handoffs-s1-s9.md`; session 10's own brief: `history/handoff-s10.md`.

### HANDOFF TO ARCHITECT 11: "Finish the refactor" (written 2026-11-02 by the session-10 Architect)

**What this session is (the user, 11-02):** continue session 10's work on the cleanup list. **No missions** (they
resume in session 12). Read first: `docs/CONDENSED.md`, then **"SESSION 10 RECORD"** below (what changed and why),
then `docs/refactor-candidates.md` group E. Start the inbox watcher first; remind the user of the USER TODO above.

**Where E stands (version 2.44.7, git `restructure` 09ea62a):** E6, E7, E4, E9 done; **E1** steps 1-3 done --
`pilot.py` went from 11,060 to **5,799 lines** with `daemon.py`, `report.py` (ReportMixin), `common.py`, `goals.py`,
`town_goals.py`, `plan.py`, `gear.py` (GearMixin), `items.py` (ItemsMixin). **Left, in this order:**
1. **E1 step 4, `town.py`** (a TownMixin): the `town_*` methods, `supply_minutes`/`supply_text`/`supply_watch` with
   `TURNS_PER_DMIN`/`FOOD_MID`, `identify_candidates`, provisioning, price/house/stash state helpers.
2. **E1 step 5, `combat.py`** -- **on its own, with care**: `reflexes`, `escape`, the engage/group/still/status/
   unseen/choke ticks, Speed/Berserk/fear, `danger_why`, the watches, react rules, `has_ability`, `watch_character`,
   `teleport_item`, `hard_fight`. **The Advisor's estimator mirrors `escape`, `group_tick`, `speed_start_tick`,
   `berserk_tick`, `fear_cure` by name: they stay on Pilot (mixin inheritance keeps that)**; memo the Advisor when done.
3. **E2** the command table (`do_request`'s ~600 lines of `if c == ...` -> a table of name, method, roles, where;
   role checks in one place; pilotctl help from the table) -- with `commands.py`, E1's last module.
4. **E3** split `reflexes()`/`escape()` into one method per numbered step (order kept in one list; the moves out of
   `reflexes` are *behaviour*: ask the user); **E5** TownKit/Shop/HouseBank/TripPlan ticks into per-step methods (and
   their own lazily created flags, left by E6); **E8** unit.py by family + fixtures, setpiece.py framework vs scenarios.

**How each step was done and checked -- reuse it:**
- A split script moves whole methods **verbatim** into the mixin module; `pilot.py` re-exports every module-level
  name tools and unit cases use (`P.X`); no mixin imports pilot.py (shared helpers go to `common.py`).
- Checks per step: `python3 harness/unit.py` (139, incl. `reports_match_golden`: the report text vs
  `harness/golden/reports.txt`; regenerate with `--golden` only when a change is meant); a **dry start** of the real
  `Pilot.__init__` on a fake client, old tree vs new; **`tick()` equivalence** over 28 scripted states, old vs new;
  **pyflakes with no undefined names** (a goal's tick runs inside `except Exception`: a missed name fails silently as
  "goal failed"); compare bytecode of moved methods if you can. The scripts were in session 10's scratchpad
  (`e3_dry.py`, `e3_equiv.py`, `e3_split.py`) -- scratchpads are per session, so ask an agent to rewrite them.
- Live: restart (Dive04 idle in town, **no set-piece running**), ~15 pilotctl commands, set-piece M2 (its staging often
  fails on dark levels: retry), and for town code a real Shop goal (`goal shop 5 list`) and `house deposit` -- **never
  test the town visit under a snapshot restore** (11-01: it lost the banked gold; docs/harness-rulebook-ops.md).
- Commit + `tools/snapshot.sh` + tag a patch version (`docs/process.md` "Versions") + push; restart the Pilot.
- Session 10 delegated each step to one agent (they read pilot.py; the main context stayed small): reuse that.

**Also open (not E):** A25 (set-pieces A2/A2I/A2L need a unique above clvl 29) waits for the separate test server;
C14 (shrink HANDBOOK-reference) is an A/B test in session 12+ (TODO above); the user's TODOs from session 9 (the user
playing the Navigator; a separate local test server; server-side test features -- HANDOFF 12 item 3).

**State (11-02):** see "State now" at the end of SESSION 10 RECORD. The SGE job 8327794 (scc-va4) ends **Tue 11-03
08:47** -- a new job needs the test server, the Pilot and the viewer restarted (operations.md).

### HANDOFF TO ARCHITECT 12: "Missions: test everything since m60" (written 2026-11-02 by the session-10 Architect)

**SESSION 12 WATCH LIST (session 11, 11-04; the version is 2.49.0, m61 ran on 2.48.0):**
- **Food and light (2.48.1, 2.49.0):** the first `stomach` record `pinned` (~1980-1999 at Fed -> Hungry), the status
  line turning `food >=N` into `food ~N`; no frequent `contradiction` records (a wrong digestion rate); make-room
  keeping the rations the horizon needs; `plan town` filling the lantern to ~15000; no mushroom ever eaten.
- **Items (2.48.0):** the first `plan town` sells of CLW (kit B), Magic Mapping scrolls (test server), torches and
  spare mushrooms; Boldness bought only if the Temple lacks Heroism; Enchant scrolls read, not sold; the first
  Enchant Weapon buy/read (`custom r item=N dir=24`; Dive04's axe at (+10,+9) won't need one unless disenchanted).
- **Combat (2.45.x):** the escape walk taking its stairs (also after its emergency lapses); Weak eating with monsters
  in view; the summoner hold (engage skipped); pickup mid-fight (the user: watch whether it causes issues).
- **The hunt check (2.45.0-2.46.0):** more permissive since fight_sim gets the gear totals -- it ALLOWS Khim (~28 turns,
  ~138 HP of 358); the disenchant figure in `monster`; the disenchant refusal (rare).
- **m61's leftovers:** M2's pickup took 13 s (was ~4 s); the Navigator's standing note still says to wield the
  Scimitar (the Battle Axe of Westernesse gives the same FA + SI): ask the user whether to drop it.
- **Open decisions for the user** (CHANGELOG 2.48.0, the SESSION 11 RECORD): the 2.48.0 judgement calls; whether the
  Pilot should eat a restore mushroom for a drain; Potions of Enlightenment as crutches; the USER TODO (old handoffs).

**What this session is (the user, 11-02):** missions resume, **to test all the changes** of sessions 10 and 11 in
real play. The last mission was **m60** (session 9, version ~2.34.0); since then 2.35-2.44.x (+ session 11's) changed
a lot of the Pilot's item, supply, junk, stash, scorecard and command behaviour, and the code was split into modules.
Read first: the SESSION 10 RECORD below, session 11's own record (it will add one), `CHANGELOG.md` (2.36.0 onwards),
`docs/process.md` §3 (the mission checklist), `github/tools/pilot/BRIEF-TEMPLATE.md` (gear/stats are now fill-in
fields), and Part "From session 9" below (Dive04, the model comparison, the routine).

**FOR THE USER (from session 11):** the user said "fix these issues now" (11-03): **done in 2.45.0** -- the command
role checks (park/quit/option/dump), the ghost's park/stop/order/plan stop, usage on bad arguments, the hunger early
stop, the escape walk taking its stairs (and finishing after its emergency), the disenchant cost in the hunt check
(shown and logged, no decision yet), the house record strike, M2's staging (see CHANGELOG 2.45.0). **Still open:**
- Not done on purpose: the moves out of `reflexes` (light/hunger/pickup -> policy_tick, food_watch -> tick): an order
  change with no bug behind it (refactor-candidates E3).
- Decided 11-03 (2.45.1): the summoner hold lets the later reflexes run (not engage); the hunt check refuses a
  disenchanter whose expected loss exceeds the kill's worth. A plus is valued by what the Pilot would do since 2.46.0 (the user's
  option 2 of the Advisor's disen-value memo): price/chance where the town kit re-enchants (armour, and now the wielded
  weapon, to +8), else resale; its in-play value is not priced. **Watch in session 12:** the first Enchant Weapon
  buy/read (`custom r item=N dir=24`; Dive04's axe at (+10,+9) won't trigger it unless disenchanted to +7); the reflex moves:
  decided 11-03 (2.45.2): only Hungry moved (to policy_tick), Weak stays a reflex and eats with monsters in view;
  light and pickup stay. **Watch in session 12:** pickup mid-fight (the user: monitor whether it causes issues); a
  character Weak in a fight now eats there (unless a monster is adjacent).
- **Watch in session 12:** the hunt check is more permissive since 2.45.0 (fight_sim gets the derived totals): it
  now ALLOWS Khim for Dive04 (~28 turns, ~138 HP of 358) and a Hill giant at 80% HP.

**New since session 11 for this session:** `tools/harness/refactor/` holds the equivalence harness (`equiv.py`, 168
scripted states on a fake client; `cmdmatrix.py`, every command x role x context) -- reuse it for any refactor.
The first `plan town` and `plan trip` are the first live runs of E5's split TownKit/TripPlan (only Shop and
HouseBank were run live): watch them (item 1 below).

**Before the first mission:**
- Restart the test server, the Pilot and the viewer if the job changed (operations.md). The Architect's pilotctl
  calls need **`export PILOT_ROLE=architect PILOT_TOKEN=$(cat /projectnb/jbrcs/mangband/runs/private/architect.token)`**
  (a bare PILOT_ROLE is refused and raises `role_refused`); `mission start/end` are the Architect's only.
- Check `status full` shows the expected version; `mission start` records it in missions.json.
- The HANDBOOK/HANDBOOK-reference/FIELD-NOTES/navigator.md changed (B1-B8, B4): the Navigator's sources are current.

**What to watch, in order of risk (each is new or changed and never seen in a mission):**
1. **The first `plan town` is its own test** (2.44.0, D3/D10/D13): the stash is in `house.json` only (stash.json
   retired); junk is one rule (union; **only the town's spellbooks** are junk for a warrior -- dungeon books are loot
   worth thousands: watch that they're kept and sold); "better AC" by the gear evaluator; withdraw/deposit (the 300
   reserve is normal). Watch the town visit closely; check `house` before and after.
2. **Rations and oil by need** (2.41.0): spare food/flasks go for worthy loot in the dungeon (horizon: the expected
   recall + 5 dmin, 40 dmin without a trip end); make-room eats and refuels first. Watch for "Food 0" or a dark lantern
   late in a trip.
3. **Mushrooms** valued by expected value (2.42.0); **D3's whole-word junk** (Cure Blindness mushrooms no longer junk);
   auto-destroy now destroys any junk in the pack.
4. **Supply notices** are one kind, `supplies` with `supply`/`level` (2.44.0 D14): the Navigator sees the same texts.
5. **Emergency loop** counts escape actions only (A4); "already fleeing" alert (A21); `until wor<=1` refused (A18);
   `order` all-or-nothing (A22); a failed override hunt charges fight debt (A23); kept `{cursed}` items survive (A15).
6. **The module split** (E1): any "goal failed: error ..." or a traceback in pilot.log is a missed name -- report it.
7. **Scorecards** (D8/D9): damage by monster now names uniques (2.44.1); values are what the Pilot believed. Compare
   new cards only with cards made by the same code (`defs` in the card).

**Missions:** the user decides number, models and lengths. Suggested: first a supervised short mission (Sonnet- or
Haiku-medium, 30 min, 700-800 ft) to shake out the town visit and the split; then the **C14 A/B baseline**: a few
missions on the current HANDBOOK-reference (same model/effort), before any shrink (TODO above). Each mission: the
checklist in docs/process.md §3, `observe/wrap.sh mNN` (refreshes the damage mix), a report, FIELD-NOTES lessons.

#### From session 9 (still current where session 10 didn't change it)

**State (end of session 9; session 10 changes nothing in play):** Dive04 in town, clvl 29, 358/358, AC ~94, Battle Axe
of Westernesse (FA, SI), Rings of Protection [+16]/[+12], Leather of Resistance, Boots of Stability; 300 gold carried +
19,327 banked in the **wilderness house** (the tile north of town: walk off town's north edge at 1,130, arrive at
64,130, door 60,129; operations.md "Houses and the gold bank"); the stash lives in that house (empty now).
`max_depth` 800 (the user: keep). `runs/pilot/dive04/ask_unlimited` kept (the user). Missions run in session 9:
m55-m60. Sessions 10-11 restructured the code: see the SESSION 10 RECORD.

**Session 9 built** (details: VACATION-NOTES.md "Session 9 triage", design_gear.md, operations.md "Houses", the
reports `runs/pilot/dive04/reports/2026-10-2[78]-mission5[5-9]*.md`, mission60):
- Theft news; make-room eating never gorges; the dive's loot detour; state.jsonl on the wall clock; bracketed egos
  valued; weight-limit shedding; trap door below max_depth news; ESCAPE LANDING / escaped / FAILED.
- `goal quiet [SECS]`, **`ask quiet TEXT`** (waits for the Architect's answer; "more" keeps it).
- **The loadout optimizer** (`pilotctl loadout [shops]`), **EHP** (`observe/damage_mix.py` + `geareval.ehp`) in gearcmp,
  loadout, the optimizer's proxy and gearcmp's verdict (a >5% EHP cut is ruled out; ties by EHP). Slays/brands in the
  simulator (the Advisor's options_sim 27k); MIN_GAIN scaled to play time (28l).
- **The gold bank** in a wilderness house (HouseBank: buy/deposit/withdraw, the edge crossing; plan town withdraws
  first, deposits last); the stash in the house; the tavern fallback drops inside the room.
- **plan town** also recharges empty useful staffs, enchants disenchanted armour to the +7/+8 stopping place
  (`order enchant_max=N`, announced in the opening note), waits up to 4 x 35 s for a restock of a critical item.
- Supplies in dungeon minutes (status line, plan town, arrival, alerts under 15/5; quiet waits capped).
- Confusion: cured after 8 s with monsters adjacent (every tick, the clock reset between confusions), then a teleport
  in the clear second; Recall cures first. Flee replans through unexplored squares after a phase; Flee replans twice.
- Item commands wait for the pack after a stack empties; react hunts resume their goal; worn items leave review;
  react de-duplicates; `dmin>N`; empty devices recharged or sold; the keep list matches plural stacks; no pickups
  mid-flee; `order autowear=off`. The M5 set-piece (not stageable). 112 unit cases (the flaky clock case fixed).

**Model comparison so far** (current Pilot, 700-800 ft): 45 min -- m56 Opus-medium 58.0 XP/dmin (low 87%, $1.05),
m57 Sonnet-medium 94.0 (65%, $0.22); 30 min -- m58 Opus-medium 73.9 (63%, $0.40), m59 Sonnet-medium 128.6 (71%,
$0.18), m60 Haiku-medium 47.1 (92%, $0.013); Haiku-low m43-m55 median 68.9. Sonnet-medium led twice; one mission each,
level luck dominates. More interleaved missions would settle it (offered to the user).

**Open items (from session 9, for session 12 unless done):**
1. **Verify live** (built, not yet seen in a mission): `ask quiet` / `goal quiet` used by a Navigator; recharging; the
   restock waits; the flee replan after a phase (m59's case); the confusion clock reset; the house stash drop/fetch;
   `loadout shops`; older: the breeder-pin teleport, the blind staff escape, `react hunt`.
2. **Small gaps:** the "this trip" XP rate isn't in the dungeon wait reports (m58); a full pack lost a wand pickup
   (m60 19:05); resist blindness (watch shops); the optimizer is 1-2 slot moves and advisory only.
3. **The user's TODOs (10-28):** (2) **the user plays the Navigator** for a mission (a way to issue pilotctl commands
   beside the viewer; the same brief; the Architect answers asks live); (3) **a separate local test server** for
   set-pieces (own port, saves, config, freeze file; copies of Dive04); (4) **server-side test features** for
   set-pieces on a test-server branch (place monsters/items/terrain, set player state, step AI, load levels, fixed
   seeds) -- the M5 lesson; builds on 3. (1, the Navigator's quiet wait, is built: verify it.)
4. **Waiting on the user:** the `ask` policy (still unused by most Navigators: require one check-in per trip?); the
   fight-vs-flee band rule (collect `trigger: band` estimator records first); more model-comparison missions.
5. **Routine:** after each mission `observe/wrap.sh mNN` (it also refreshes the damage mix), a report in
   `runs/pilot/dive04/reports/`, FIELD-NOTES lessons, complaints and asks read; snapshot, commit, push.
   (Session 10, B17: **the full mission checklist now lives in `docs/process.md` §3** -- this line, HANDOFF 8's "Per
   mission" and VACATION-NOTES §5 were its pieces.)


### HANDOFF TO ARCHITECT 13: "The patcher repo and the separate test server" (written 2026-11-04 by the session-11 Architect)

**What this session is (the user, 11-03/11-04):** two linked projects, after session 12's missions.

**1. The repo as a patcher (the user, 11-04: the GitHub repo is confusing -- most top-level files are unmodified
MAngband).** Today `github/` is a fork: commit `6963c00` "Pristine MAngband 1.5.3 sources" (399 tracked upstream
files: src/, lib/, build/, autotools), our C changes on top (16 files, +1,822/-9 lines, 26 commits, the last 10-31:
the tool client `c-tool.c`/`main-tool.c` and its hooks, the packet logger `c-pktlog.c`, the test-server time freeze in
`net-server.c`, the store-crash fixes in `store.c`, `tables.c`), plus ours: `tools/`, `project/`. The target:
- Top level only ours: `README.md` (what this is, how to build and run), `tools/`, `project/`, `patches/`, `build.sh`.
- `patches/`: our C changes against pristine 1.5.3, one readable patch per topic (`git diff 6963c00 HEAD -- src lib
  configure.ac Makefile.am` is the whole set today; split it by topic).
- `build.sh`: fetch MAngband 1.5.3 (find a reliable upstream source -- the MAngband GitHub repo's 1.5.3 tag or a
  release tarball -- and verify a checksum; if none is reliable, keep the pristine tarball in the repo as one file),
  apply the patches, `autogen.sh`/`configure`/`make`: the server (`mangband`) and the tool client (`mangclient`).
- C work afterwards: a local build tree (pristine + patches, its own git) and `export-patches.sh` to regenerate
  `patches/`; C changes are rare now.
- One-time path changes: everything that points at `github/mangband`, `github/mangclient`, `github/src`, `github/lib`
  -- the test-server start command (operations.md "Test server"), `tools/client/mang.py` (runs the `mangclient`
  binary), restart/freeze/hotswap/charsave/set-piece scripts, the snapshot script, docs, memory. Grep first; keep
  `github/tools/` where it is so the Pilot's paths don't move.
- Check: a clean checkout + `build.sh` builds both binaries; the unit suite, a set-piece and a short mission run on
  them. History stays (old commits keep the full tree); tag the switch.

**2. The separate local test server** (HANDOFF 12 item 3, the user's TODOs 3-4): its own port, saves, config and
freeze file, playing *copies* of Dive04, so set-pieces never touch the real character or its gold (snapshot
restores have caveats: one lost the banked gold). **Build it with `build.sh`** -- the patcher's first real test,
and proof that everything rebuilds from scratch (needed for the live deployment, `live-deploy-todo.md`). Then
server-side test features on it (place monsters/items/terrain, set player state, step the AI, load levels, fixed
seeds: the M5 lesson). **This unblocks A25's remaining half:** a set-piece with a unique above the character's level
to test the recall branch (A2's criterion since 2.44.10 checks recall only when a danger rule fires).

**Order:** the patcher first (the build script), then the test server built with it, then A25's set-piece.

### SESSION 10 RECORD (2026-10-28 to 11-02; formerly HANDOFF 11 Part B)

*Session 10 ran in two chats on 2026-10-29: the original session (morning, SGE job 8268425) and "Architect 10
parallel" (afternoon, job 8327794 on scc-va4, ends Tue 11-03 08:47), which carried on without the first chat's
context; the original chat then reviewed its work (agreed, with follow-ups below). Unified here 10-29 afternoon.
Later session-10 work appends below "State now".*

**The Documentation: `docs/`.** Start with `docs/CONDENSED.md` (3 pages); `docs/README.md` indexes ten component files
(client-server, pilot-core, pilot-combat, pilot-items, goals-and-plans, commands -- every pilotctl command --,
gear-and-estimator, observe, harness-rulebook-ops, process). They match the code at 2.38.0, **checked claim by claim against the code on 10-29** (~1,200 claims, ~100 doc
fixes). **Read the
component file before opening its source, and keep it in step when you change that component.** roles.md,
operations.md and the memory point to it.

**Versions (the user's decision):** `major.minor.patch`; **minor = play can differ, patch = it can't** (scorecards
compare within a minor). `github/VERSION` holds it; the Pilot shows it (`status full`, the `started` notice), `mission
start` records it in missions.json. `CHANGELOG.md` (project top) lists every version, newest first, with its missions;
2.36.0 and older were assigned retroactively (72 versions, m1-m60 mapped). The per-version checklist is in `docs/process.md`
("Versions"): **docs in step, VERSION, CHANGELOG, tag, push, Pilot restart.**

**The cleanup list: `docs/refactor-candidates.md`** (groups A bugs, B doc fixes, C remove/archive, D duplicates, E
splits incl. a pilot.py module plan, F defaults/safety). Done items are marked "done (session 10)". All by the user's
approval:
- **2.36.0 (dd2200d):** A1 escape's stairs walk no longer hijacks later walks; A2 flavour learning matches item type
  (bad "Amber Amulet" entry removed); A3 the shadow estimator gets total to-hit/to-dam (compare estimator records
  before/after 10-29 08:35 separately); A6 one auto-swap loss rule for gearcmp and the optimizer; A8 the EHP damage
  mix follows the mission's depth band (`damage_mix.py --mission`); A9 `scorecard.py` rescores only what is asked
  (`--all`, `--sp`); A10 `watch_mission.py --nick N` resumes from saved offsets (`--fresh` to start at the ends),
  alerts only on tracebacks; wrap.sh/notes.py filter to the mission; A11 `review wear` says what happens.
- **2.37.0 (a188d02):** A4 the emergency loop counts escape actions only; A5 `order pickup=none` makes no loot walks;
  A7 gear evaluation's "met" fights come from the log's recent tail; A12 pilotctl prints each note once; A13 Rings of
  Damage/Accuracy count; A14 shadow snapshots carry slays, brands, weapon weight (the Advisor asked). Group C: C1, C2
  to `tools/attic/`; C5-C10 dead code and fallbacks gone (the rulebook files must exist); C11 old handoffs and retired
  notes in `history/`; C12 set-piece snapshots pruned; C13 testserver clutter deleted.
- **2.37.1 (4ef8d55):** B4 HANDBOOK-reference fixed (`goal leave`/`goal fetch`, the four missing orders, the real
  emergency trigger and escape order; `danger_seen` drops the goal -- the survey's "resumed" was wrong); C3 the
  human-play study tools in `tools/observe/study/` (the user will record again; `record.py` still defaults to the live
  port); C4 the shop-tour tool kept for the live catalog; C14 deferred to an A/B test (TODO at the top).

- **2.38.0 (the user approved, 10-29 evening):** the review's follow-ups: A4 every `emergency` notice must pass
  `action=True/False` (a unit case fails otherwise) and one `count_escape()` counts; A7 the "met" fights come from the
  last 3 days, doubled until 20 fights; C12 set-pieces keep the newest 5 snapshots; C7 the viewer stays as it is (the
  user); `live-deploy-todo.md` pins the Advisor's simulator. **B1-B3, B5-B8 done** (HANDBOOK: `goal shop N sell`,
  the stash in the house, eats to Fed, the trip events; FIELD-NOTES stash; **BRIEF-TEMPLATE's gear and stats are now
  fill-in fields**; pilotctl's help is a pointer; navigator.md: ~200 lines, never set PILOT_ROLE). `docs/survey-notes/`
  moved to `history/`; the per-version checklist is in docs/process.md "Versions". **The docs were verified** by ten
  agents (one per file); they settled: logins work while frozen (operations.md was wrong), a bad password exits 255,
  restart.sh parks and the parked Pilot sends `clear`, `hotswap.sh Dive04` (capital D: its pgrep is case-sensitive).

- **2.39.0 (the user approved, 10-29):** bugs the verification found: A15 auto-destroy spares kept items in its
  pseudo-ID pass too; A18 `until` refuses `wor<=1` (and no longer `wor<1`); A20 the hunger step no longer skips
  pickup/auto-destroy/engage/rest while it waits; A23 a failed hunt never counts as slain (fight debt); A24 the
  scorecard's `commands_per_min` excludes wait reports (the Advisor's definition; every real mission rescored).
  124 unit cases.

- **2.40.0 (the user approved, 10-29):** A16 an empty `autodestroy` order stops only the feeling pass; A17 the junk
  test runs before the food/flask/light rule in `pack_value`; A19 a worn torch counts its turns (not permanent); A21
  the emergency loop says "already fleeing" when stairs are known and it is; A22 (+F5) `order` checks every pair
  first, a bad one changes nothing, with a usage error. 129 unit cases.

- **2.41.0 (the user's rule, 10-31):** rations and oil by need, as the user plays: leave town fed and topped up,
  recall before starving or going dark; when the pack is full, eat (if not Gorging) and fill the lantern, then
  discard the extra. In the dungeon, food and flasks that last to the expected recall + 5 dungeon minutes (40 when no
  trip end is known) are needed, worth the dungeon time they buy (`gold_per_dmin`); the rest is spare, worth its sale
  price. The town kit still eats only to Fed (the user). 130 unit cases.
- **2.42.0 (the user, 10-31):** mushrooms are valued, not priceless food: an unknown one at the average value of the
  mushroom kinds not yet known (~80 gold with none known), a known one at its kind's value (itemvalue read both as
  0).

- **2.43.1 (10-31):** B9-B18 -- stale design docs marked history, operations.md/roles.md/harness README fixed, code
  docstrings and help text (incl. the Navigator-visible `loadout` header), the c-tool.c header, the advisor-memos memory
  now a pointer, one home for the mission checklist (docs/process.md §3), and the Advisor's rulebook fixes synced
  (fight_sim reads the synced monsters_raw.csv).

- **2.44.0 (11-01/02):** group D. Pure merges (D1 light parser, D2 name helpers, D4 find_item/phase_item, D5, D7
  observe/logs.py, D11, D12 report formatters, D15, D16 inbox drift warning) and, by the user's choices: D3 one
  `is_junk` (the union; for a warrior only the **town** spellbooks are junk, dungeon books are loot), D10 house.json the
  stash's only record (stash.json retired), D13 the gear evaluator decides "better AC"; with the Advisor's
  definitions: D8 one damage attribution, D9 card values as the Pilot knew them (`aware` in state.jsonl,
  `shopmath.pay_cut`), D14 one `supplies` notice with `supply`/`level` fields. 138 unit cases.
  **Incident 11-01:** a `plan town` test under a snapshot restore lost the banked gold and the stash (the restore
  covers the character, not the world); recovered (DM drop, Dive04 picked it up, deposited) -- docs/harness-rulebook-ops.md
  Gotchas. **The town visit on 2.44.0 is untested live**: the first `plan town` of session 11 is its test; watch the
  stash and junk steps.

**Still open, waiting on the user:** group **E**. (A: only A25, waiting for the test server.) **A25** (set-pieces A2I/A2L, FAIL on a stale criterion: the Pilot fought and won
correctly; the scenarios need a unique above clvl 29) **waits until we have implemented the test server** (the
user). C8: only the Pilot's dead-character whitelist changed; the scorecard/viewer query
lists wait for D7. From the Advisor (29o): an optional `p["noise"]` in estimator snapshots (0 while the Pilot stands
still) -- not built.

**Defaults and the Architect's role (F1-F4, fixed in 2.43.0):** every port default is 28346 (the test server), and
`pilot.py` refuses 18346 without `--live`; pilotctl without `--nick` finds the one running Pilot; **the Architect's
commands need the token**: `export PILOT_ROLE=architect PILOT_TOKEN=$(cat /projectnb/jbrcs/mangband/runs/private/architect.token)` (the harness and wrap.sh read it themselves); a bare `PILOT_ROLE=architect`
runs as the Navigator and raises `role_refused`; `mission` is the Architect's only.

**Process note:** session 10 surveyed with ten parallel subagents (one per component, ~5 min each, writing the docs
directly), then one merging the candidates; bug fixes went to agents on disjoint files. The main context stayed small.
Reuse that for big reading jobs. And: before continuing a session in a new job, `claude --resume` it -- a fresh chat
lacks the context (how the parallel chat happened).

**Group E (the user, 11-02: in steps, a commit each; stop at a clean commit if the context runs short):** E6 done
(2.44.2), E7 done (2.44.3: tools/client/mang.py), E4 + E9 done (2.44.4), E1 steps 1-3 done (2.44.5: daemon.py, report.py, common.py; 2.44.6: goals.py, town_goals.py, plan.py, and a golden-
file report unit case; 2.44.7: gear.py, items.py mixins; pilot.py 11,060 -> 5,799 lines). **Next (session 11 or
later):** E1 step 4 `town.py` (town_*, supply_minutes/supply_watch with TURNS_PER_DMIN/FOOD_MID, identify_candidates),
step 5 `combat.py` -- on its own, it holds escape/group_tick/speed_start_tick/berserk_tick/fear_cure (the Advisor's
mirrored names: they stay on Pilot), has_ability, watch_character, teleport_item, hard_fight -- then E2 (the command
table, with commands.py), E3, E5, E8. **How each step was done and checked** (reuse it): a split script moving whole
methods verbatim into a mixin; unit.py (incl. reports_match_golden); a dry start of the real __init__ on a fake client,
old tree vs new (scratchpad e3_dry.py -- the scratchpad is session-local: rewrite it if gone); tick() equivalence over
28 scripted states (e3_equiv.py); pyflakes with no undefined names (goal ticks swallow exceptions!); live: restart,
~15 commands, a set-piece (M2; retry its staging failures -- dark levels); commit + tag a patch version. (docs/refactor-candidates.md E1's layout), then E2, E3, E5, E8.

**State now (11-02):** version **2.44.7**. Running in SGE job 8327794 (scc-va4, ends Tue
11-03 08:47): the test server (gdb, freeze-enabled), Dive04's Pilot (2.44.7), the viewer (`tmux -L mang attach -t
watch`). Dive04 idle in town, 358/358, 300 gold + 19,327 banked in the wilderness house. 139 unit cases pass (a golden-file report case).

### SESSION 11 RECORD (2026-11-02 on; "finish the refactor", no missions)
- **2.44.8 -- E1 step 4, `town.py`** (TownMixin, 50 methods + 19 constants, incl. `supply_gate`/`SUPPLY_STAGES` and
  the town stairs/edge helpers; `house_info`/`price_info` stay for commands.py/E2): pilot.py 5,799 -> 5,060 lines.
  Checks as in session 10 (bytecode identical, 139 unit, dry start, tick() equivalence over 33 states, pyflakes);
  live: ~14 commands, `goal shop 5 list`, `house deposit`, M2 PASS (2nd try: the 1st staging hit a dark room).
  The check scripts (split.py with its `MOVE` list, bytecode.py, dry.py, equiv.py, fake.py; run dry/equiv with
  `PYTHONHASHSEED=0`) are in this session's scratchpad `e1s4/scripts/` -- copied to `github/tools/harness/refactor/`
  for the next steps.
- **2.44.9 -- E1 step 5, `combat.py`** (CombatMixin, 53 methods + `escaping_to_stairs` + 13 names; `tick()` and its
  steps, shared primitives (take_stairs, resting, set_goal), perception helpers and the command side stay):
  pilot.py 5,060 -> 3,050 lines. Same checks; equiv.py now has 64 states (31 combat; `EQUIV_COVER` for line coverage);
  new helpers `bcdiff.py`, `names.py`, `covreport.py`, `summ.py`. Live: commands, A6 PASS, B3 PASS, **A2K FAIL** --
  Khim no longer dangerous for Dive04 (~173 HP of 358): A25's cause, noted there. Advisor memo'd (options_sim.py's
  mirror comment should point at combat.py).
- **2.44.10 -- A2 set-pieces' criterion** (harness only): recall only when a danger rule fires, else Speed + Berserk
  and lowest HP >= 60% (the Advisor's `to_architect/2026-11-02-khim.md`: its estimator agrees with fighting Khim).
  A2K PASS. **For the user (a play change, not done):** Khim's/Ibun's UN_BONUS blow disenchants ~1-2.5 times a fight
  (~100 gold a plus); neither the hunt check nor geareval counts it. **Lesson:** a set-piece restarts the Pilot from
  the working tree -- never run one while an agent may be editing `tools/pilot/`.
- **2.44.11 -- E1 step 6 + E2, `commands.py` + `cmdtable.py`**: E1 complete (pilot.py 11,060 -> 1,512 lines over
  sessions 10-11); `do_request` dispatches from the table; pilotctl help generated. A 6,090-case command matrix
  (`harness/refactor/cmdmatrix.py`/`cmpmatrix.py`) old vs new. 143 unit cases. Live: role refusals, Shop goal, B3 PASS.
  **Found, not fixed (behaviour; for the user to decide):** (1) `park`, `quit`, `option(s)`, `dump`, `goalstate` have
  no role check -- the Navigator can `quit`/`park` the Pilot; (2) a ghost refuses `park`/`stop`/`order`/`plan stop`,
  so `restart.sh` on a dead character waits 330 s and fails; (3) some bad arguments return a raw exception text
  (`goal explore radius=x`, `search x`, `view x`; `inscribe`/`option` with no args); (4) an unknown command to a
  ghost gets the ghost refusal. Each is now a one-line change in `cmdtable.py` or a `cmd_*` method.
- **2.44.12 -- E3**: reflexes/escape split into `REFLEX_STEPS`/`ESCAPE_STEPS` methods (pure; 99-state equivalence,
  100%/99% line coverage). Live A6, B3, A2K PASS. **For the user (behaviour, not done):** the moves out of reflexes
  (light/hunger/pickup -> policy_tick, food_watch -> tick); and the hunger step's `return self.wear_light(...)`
  skips adjacent/pickup/engage/rest for a tick when no light can be worn (A20's kind of early stop).
- **2.44.13 -- E5**: Shop/HouseBank/TownKit/TripPlan ticks into step/phase methods, 31 lazy flags declared (pure;
  168-state equivalence). Live: Shop buy + quote, house withdraw + deposit. The full `plan town`/`plan trip` were
  not run live -- session 12's first mission is their test (HANDOFF 12 item 1). Oddities for the user (not fixed):
  in refactor-candidates E5.
- **2.44.14 -- E8**: unit.py -> runner + `fixtures.py` + 12 family files; setpiece.py -> entry + `setpiece_run.py` +
  4 scenario files; harness/README -> reference table + findings log. Pure move; 145 unit; B3, A6, A2K PASS live.
  **Group E is complete.** Stale counts fixed in CONDENSED/ops/refactor-candidates.
- **2.45.0 -- the user's "fix these issues now"** (play changes; CHANGELOG 2.45.0): command roles/ghost/usage, the
  hunger early stop, the escape walk takes its stairs (and finishes after its emergency), the disenchant cost in the
  hunt check, the house record strike, fight_sim on derived totals (the Advisor), M2 tries 4 rooms, set-piece
  tracebacks in the result file. 151 unit cases. Live: Navigator refusals of park/quit/dump/option, usage text,
  `monster khim`, set-pieces A2I, A2L (PASS under the 11-02 criterion), A6, M2 PASS. The Advisor mirrored the
  escape walk (options_sim 2026-11-03p).
- **State at the end (11-03 ~01:40):** version **2.45.0**, git `restructure` tagged and pushed. SGE job 8327794
  (scc-va4) ends 08:47: the test server, Dive04's Pilot (2.45.0), the viewer. Dive04 idle in town, 358/358, 300 gold
  + 19,322 banked (5 gold went on a Flask of oil in E5's live Shop check). Open after session 11: the user's TODOs at
  the top; "FOR THE USER (from session 11)" in HANDOFF 12; C14 A/B; A25 (a unique above clvl 29).
- **11-03 ~07:35:** the user will /resume this chat (session 11) in a new SGE job. Then, first: start the inbox
  watcher; restart the test server (with `MANGBAND_FREEZE_FILE`), Dive04's Pilot (`tools/pilot/restart.sh Dive04`)
  and the viewer per operations.md; check `status full` says Pilot v2.45.0 and `house` shows 19,322 banked.
- **11-03 (2.47.0): the docs audit** -- three agents checked every doc against the code and fixed the text; five
  code bugs they found are fixed (CHANGELOG 2.47.0).
- **2.48.0 -- the user's two principles for spare items** (fallback: keep/buy while the better item is short;
  dungeon stopgap: sell in town, keep in the dungeon while the primary is short; scrolls the kit would read are
  read, not sold). Judgement calls to confirm with the user: Boldness is bought when Heroism is short for any
  reason (stock, the 1.5x cap, gold), once a visit, within the gold beyond the reserve; the whole Boldness stack is
  priceless in the dungeon while Heroism is short; stopgaps are never discarded while short (stronger than
  rations); CLW is still kept with a forced kit B/C on a 250-499 ft plan, on the buy list, or kit=none; restore
  mushrooms are kept but the Pilot never eats one for a drain (follow-up?); Potions of Enlightenment are not
  crutches. **Watch in session 12:** the first plan town's sells (CLW in kit B, Magic Mapping scrolls), M2's pickup
  took 13 s (was ~4 s), Boldness bought when the Temple lacks Heroism.
- **11-03 07:34, resumed in SGE job 8406367 (scc-va3, ends Sat 11-07 19:55):** the old job ended 07:32 (savefile
  from 07:25, Dive04 idle in town); restarted the test server (gdb, freeze-enabled), Dive04's Pilot (v2.45.0; now 2.49.0) and
  the viewer (`tmux -L mang attach -t watch`). Dive04 358/358, 300 gold + 19,322 banked.
- **m61 (11-03 18:03-18:45, Opus medium, 45 min, on 2.48.0)** -- session 11's test mission, the first since m60: 84.1
  XP/dmin, no close calls, the restructured code held (no errors). Found and fixed in **2.48.1**: rations destroyed as
  spare (the stomach counted at its level's middle), a food estimate that stood still, unknown mushrooms eaten, a
  Navigator recall credited to the Pilot. Report: `runs/pilot/dive04/reports/2026-11-03-mission61.md`. For the user: the
  town sold the only flask (lantern >= 9000: light ~41 dmin for a 35-min trip).
- **2.49.0 (the user after m61):** the lantern is filled in town (to 15000), and the stomach tracker (`stomach.py`)
  pins the food value at every hunger crossing. **Watch in session 12:** the first `stomach` record (`pinned`, ~1980-1999
  on Fed -> Hungry), `food ~N` on the status line, no frequent `contradiction` records (a wrong rate).
- **11-03: the restructure is declared done (the user).** `restructure` was fast-forwarded into `master` at 2.49.0
  (fba3d7e) and deleted locally and on GitHub; pushes go to `master --tags`. The revert instructions (`restructure.md`),
  the 10-22 backup (`runs/backup-pre-restructure-20261022/`) and the restructure memory were deleted; the tag
  `pre-restructure` and the version tags remain.

### SESSION 12 RECORD (2026-11-04 on; "missions: test everything since m60"; SGE job 8406367, scc-va3, ends Sat 11-07 19:55)
- **The user's decisions at the start (11-04):** store spares instead of selling ("spare items that are valuable and
  can't be bought should be stored when possible": gear backups + a user store list; house first, then INSIDE the
  tavern room; no room -> the Navigator `ask`s the Architect -- discuss buying another house); eat a restore mushroom
  for a STR/DEX/CON drain; Potions of Enlightenment are not crutches; stored finds count as mission income, fresh
  finds marked by a `{mNN}` inscription (the user's idea; acquired.json as the fallback).
- **2.50.0** (the above + the stash record checked against the floor: a live check found an unrecorded second Restore
  Charisma in the house and a Scimitar scattered by drop_near). The Scimitar of Westernesse is in the house (backup).
- **m62** (Sonnet medium, 45 min, 2.50.0): 79.5 XP/dmin, clean; the stash overflow to the tavern, `{m62}` labels, the
  first stomach pin all worked. Report `runs/pilot/dive04/reports/2026-11-04-mission62.md`.
- **2.51.0** (the user after m62): far fetch for kit/valuable potions and scrolls; a backup must be worth 1000+ at sale
  or add an ability the worn gear lacks (others fetched and sold); WoR 3 in kits B/C; make-room news counts; the
  Plan line shows the trip's end.
- **m63** (Sonnet medium, 2.51.0 -> 2.52.0): 58.7 XP/dmin. The Navigator's `plan trip` cut plan town's house visit
  short and the idle gold fetch took the 25k bank pile (the record still said banked): the Architect recalled home
  mid-mission. **2.52.0**: gold fetch never in the house; a stale bank record recovers; the login level bug (a Pilot
  started in town took its first dungeon level as "kept" -> stairs back held 300 s). Open after m63 -> 2.53.0 (being
  built): the avoid zone over an inner room's ring blocks the only `<` -> the Navigator decides (the user); a plan
  sent during plan town is queued (the user); the false food alert at a hunger crossing.
- **2.53.0** (the user after m63 + a live find): an avoid zone blocking the needed stairs -> the Pilot holds and the
  Navigator decides (`zone_blocks` alert; `avoid pass` = cross the ring, never the room; 90 s, else recall); a plan
  sent during plan town is queued; plan town's goal_done says `BANK: N gold still carried` when the bank step failed;
  no false food alert at a hunger crossing; **artifacts are never stashed** (MAngband forbids dropping a true
  artifact above its depth: object2.c inven_drop_okay -- plan town looped ~600 drops of m63's Phial); drops give up
  after 3 failures; **a permanent light beats a fuelled one** (Dive04 now wears the Phial; lantern and flasks sold).
- **m64** (Sonnet medium, 2.53.0): 78.0 XP/dmin; the plan queue worked. Trip 1 lost to stairs 2 squares past an
  unexplored room edge -> **2.54.0** (the dive walks through unexplored squares to known stairs). Plan town sold an
  unknown potion for 9 gold: a Potion of Strength (the user: no buy-back) -> **2.55.0** (identify every unknown before
  selling, except gear felt average/worthless/cursed/broken; stat-gain potions quaffed). Live: 4 identified, ok.
  Small, open: a Ring of Protection [+11] (weaker than both worn) kept as "kit/kept/useful".
- **m65** (Sonnet medium, 2.55.0): 75.7 XP/dmin; a summon trap at 750 ft (Gorbag, Uruk, Black orcs, Wargs): the
  Pilot's own escapes, low 46%. 10 flavours identified. **2.56.0**: buy caps from the normal price (a 50%-off CSW had
  capped later buys at 46 < 63); news for items destroyed by attacks; a Navigator `plan town` during plan town is
  queued. Make-room churn: the user calls it a non-issue (leave it). Live 14:44: plan town bought 25 Enchant Armor
  (5,025 gold) and restored 3 of 4 disenchanted pieces to +8 (boots still +7) -- the session-9 rule, `enchant_max` 25.
- **2.57.0** (the user, 11-04 afternoon): **equipment damage is danger.** m65's 22 lost armour points (+8 -> +0/+4
  in a minute) came from a Water hound pack breathing acid 31 times (26 unseen; resist acid kept HP up, so nothing
  reacted), not a Disenchanter. Now 2 acid/disenchant hits in 10 s (or 1000+ gold of repair in 30 s) -> kill a quick
  visible source, else leave; `gear_damage` alert with the repair cost; `monster` shows GEAR. Advisor memo'd
  (`memos/to_advisor/2026-11-04-gear-damage-reflex.md`: not in the estimator's mirrored functions).
- **2.58.0** (the user + the Advisor's estimator review): bands decided by the estimator (old rule the fallback),
  Speed only when losing, teleport first against breathers; acid/disen gold etc. for the estimator. **m66** started
  17:35 on it. 2.58.1 (patch): pilotctl prints the user-message line last too (the Navigator's `wait | tail -30` cut
  it). The user asked for a hot-swap at 18:00: it hit plan town mid house visit -- the bank's 28k in the purse, the
  goal and the tile's map lost, the queued trip about to recall with it; the Architect stopped it, walked out, banked.
- **m66** (Sonnet medium, 2.58.0/2.58.1): **115.2 XP/dmin**, the session's best; the first estimator band decision
  (fight Black orc x6, Warg x3, Umber hulk: low 82%). **2.59.0**: restart/hotswap wait for town/house visits
  (`swapsafe`, `--now`; live-tested: waited through plan town's stages); the Town goal goes home by the overworld
  offset (wilderness.c world_index: -1 N, -2 E, -3 S, -4 W, then rings; live-tested from mid-tile with no trail);
  the trip plan stops re-issuing a failing goal; `wait` repeats its alerts last ("ALERTS:").
- **m67** (Sonnet medium, 2.59.0 -> 2.60.0): **158.6 XP/dmin** (44 frozen min excluded), a lesser vault (zelazny);
  2.60.0 exact-kind junk; 2.61.0 frozen time excluded; 2.62.0 the vault detector + small fixes; 2.63.0 review decided in
  the same visit, `debt waive` (the mace's 276 waived), `price` for floor items. Dive04 wears the **Amulet of
  Weaponmastery** (STR, SUST_STR/CON, FA, RES_FEAR, RES_DISEN; gearcmp undervalued it -> 2.64.0 values them).
- **m68** (23:41, 2.63.0): the Pilot CRASHED at 23:53 on vault_found's log kind clash (uncaught in tick); the
  Architect froze time, renamed the key (pilot.py 1774-1775), restarted from the working tree (2.64.0 partly built
  there), thawed. 2.64.0 adds a crash guard.
- **2.64.0** gear evaluator values non-simulated abilities (ability_rates.py; Weaponmastery +16.5%; a warrior has
  resist fear at clvl 30), the tick crash guard. **2.65.0** hallucination (m68's "Draugluin" was a Magic mushroom
  patch's spores), the estimator's phase line = phase then fight, band_outcome records, queue fix, rations by digestion.
- **m69** (Sonnet medium, 2.65.0 -> 2.68.0 hot-swapped under the user's freezes): 52.4 XP/dmin (a secret-door level).
  **2.66.0** monsters in view are fought unless there's a reason not to (the user); **2.67.0** 2-wide dead ends =
  secret doors (the user); **2.68.0** the Rod of Door/Stair Location (detect_sdoor) before searching.
- **2.69.0** unfelt gear waits for its feeling; **2.70.x** the house by value, stacking, Restores only for
  unsustained STR/DEX/CON. **m70** (Sonnet medium, 2.70.2): 77.3 XP/dmin, 11 levels; the gear-damage rule fired live.
  **2.71.0** targeted reads in the dungeon, found enchant scrolls read at any chance.
- **Lessons:** never hot-swap (or restart) during a town or house visit (2.59.0 enforces it); a monitor started with
  `&` and output to /dev/null eats the saved offsets -- always run_in_background; watch for asks while frozen -- `hotswap.sh` should wait for one to end;
  `restart.sh` loads the working tree; hand-walking into the house picks up the bank pile (the step-in
  square) -- never do it; `goal goto` queued behind raw steps can path back through the house.

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
- **Session 10 is done** (2026-10-29: the Documentation in `docs/`, the cleanup list `docs/refactor-candidates.md`,
  bug fixes A1-A3/A6/A8-A11; continued that afternoon: A4/A5/A7/A12-A14, group C, B4, `CHANGELOG.md` and versions:
  2.37.0, 2.37.1, 2.38.0, then 2.39.0 (A15/A18/A20/A23/A24): review follow-ups, B1-B3/B5-B8, every docs/ file verified against the code; Part B
  has it all). If the user asks for more cleanup from that list, HANDOFF 10 below has the rules.
- **Session 11** (missions and implementation resume): read **"HANDOFF TO ARCHITECT 11"** below -- **Part B first**
  (by session 10), then Part A (by session 9).
- Sessions 1-9 are over; their handoffs are in `history/handoffs-s1-s9.md`.

### HANDOFF TO ARCHITECT 10: "Cataloging and housecleaning" (written 2026-10-28 ~20:00 by the session-9 Architect)

**What this session is (the user, 10-28):** a special session. **No missions.** Three phases, in order:
1. **The Documentation.** Go through everything that isn't data and isn't unmodified MAngband code, and write the
   Documentation that catalogs all our functionality and says what each piece does -- so someone can read it and
   understand the big picture *and* the components without reading the code. The user's examples: what does
   `gearcmp` do? what are the functions in the `pilotctl` interface and what do they do? what are goals, plans, etc.?
   what are the Architect, Advisor, Pilot, Navigator? Then a **condensed version** for future Architects and Advisors.
2. **If context allows:** from that survey, identify what should be **refactored, removed, or broken up** (e.g.
   pilot.py), and agree the list with the user.
3. **Carry out** the agreed improvements.

**In scope (not exclusive):** our modified MAngband code (the tool-mode client, the server changes), the Pilot
(`github/tools/pilot/`), the viewer and observers (`tools/observe/`), the harness (`tools/harness/`), the rulebook
(`tools/rulebook/`), `tools/shopcat/`, `tools/freeze.sh`, `tools/snapshot.sh`, the hooks (`.claude/hooks/inbox.sh`),
the Navigator agent (`.claude/agents/navigator.md`), the project docs (roles.md, operations.md, design_*.md,
HANDBOOK*.md, FIELD-NOTES.md, BRIEF-TEMPLATE.md, notes_*.md, restructure*.md, spells.md), the memory files, and
how the Advisor's pieces plug in (its memos, `options_sim`/`scenarios` that geareval and the shadow estimator import)
-- **describe the Advisor's side, don't edit `Advisor/`** (its territory). **Out of scope:** data (runs/: mission
transcripts, scorecards, decision/event logs, levels, reports) and unmodified upstream MAngband code (read it only
where needed to explain ours).

**The inventory to start from (10-28):**
- Pilot: `pilot.py` **10,558 lines** (the Pilot class, ~30 Goal classes, TripPlan, TownKit, HouseBank, the command
  dispatcher, the status report), `geareval.py` 966, `world.py` 642, `mover.py` 604, `glyphs.py` 332,
  `itemvalue.py` 318, `structures.py` 148, `pilotctl.py` 146, `shadow.py` 84, `replay_group.py` 71; shell:
  `restart.sh`, `hotswap.sh`; docs: HANDBOOK.md 198, HANDBOOK-reference.md 569, FIELD-NOTES.md 137,
  BRIEF-TEMPLATE.md 81.
- Harness: `unit.py` 2,992 (112 cases), `setpiece.py` 1,492 (~40 live set-pieces), `dm.py` 219, `charsave.sh`, README.
- Observe: `scorecard.py` 676, `watch.py` 567 (the user's viewer), `timeline.py`, `tokens.py`, `damage_mix.py`,
  `record.py`, `latency.py`, `notes.py`, `shopmath.py`, `scribe.py`, `watch_mission.py`, `screen.py`, `wrap.sh`.
- Rulebook: 34 files (CSV tables from the source, `build_monsters.py`).
- MAngband changes: 15 files, +1520 lines since the tool client was added -- `src/client/c-tool.c` (+1087, the tool
  mode), `main-tool.c`, `c-birth.c`, `c-init.c`, `c-pktlog.c`, `c-util.c`, `c-externs.h`, `client.c`,
  `net-client.c`, `c-files.c`, `c-xtra2.c`, `Makefile.am`; server `net-server.c`, `store.c`, `tables.c` (and the
  freeze build: operations.md "Test server"). `git diff --stat <first c-tool.c commit>^ HEAD -- src` lists them.
- Git: branch `restructure`, ~360 commits; tag `pre-restructure`.

**Suggested shape of the Documentation** (adjust as you see fit; the user cares about the content):
`/projectnb/jbrcs/mangband/docs/` with an index (`README.md`: the big picture -- the roles, how a mission flows from
brief to scorecard, the test vs live server, where state lives) and one file per component (tool client, Pilot core,
goals, plans, the town kit and bank, gear evaluation, the command interface (`pilotctl`, every command: what it does,
who may use it, what it refuses), observers and viewer, harness, rulebook, ops scripts, agents/hooks/memos). Then the
condensed version (one file, ~2-3 pages) for Architects and Advisors. Point roles.md, operations.md and the memory at it
(the SYNC RULE: memory pointers must match the docs).

**How to read without burning context (the session-9 analysis, 10-28; use it):**
- Session 9's output tokens: ~34% went to project code (thinking included, attributed per reply), ~24% to
  investigating/running (much of it really code design), ~10% prose to the user, ~10% docs, ~9% scratch analysis code.
- Its **input**: ~297M billed tokens, almost all cache reads -- the whole context (avg ~480k) re-read on each of 620
  turns, no compaction. Of what was read in, ~44% was **our own tooling's code** (pilot.py above all), ~27% logs and
  status, ~11% docs, ~7% MAngband source/data. Content read early is re-billed every later turn.
- So: **survey big files by structure first** (`grep -n "^class \|    def \|if c == "` on pilot.py, the docstrings),
  read only the parts you need, and consider **delegating per-component surveys to subagents** (Explore/general-purpose)
  that return summaries -- the per-file reading then never enters the main context. Keep the main thread for writing.
- `pilot.py` is the obvious split candidate (Goals, TripPlan/TownKit/HouseBank, the command dispatcher, the report,
  the item policy, gear, supplies...); also: two `light_left` helpers (world/pilot), old handoff history in
  next_steps.md (~1500 lines), HANDBOOK vs HANDBOOK-reference overlap, `shadow.py`/`replay_group.py` (still used?),
  `tools/shopcat/`. Phase 2 decides; ask the user before removing anything.

**Rules for phase 3 (the improvements):** behaviour must not change unless agreed; **all 112 unit cases pass after
every step** (`python3 tools/harness/unit.py`); load Pilot changes only with `pilot/hotswap.sh` or `restart.sh` while
Dive04 is idle in town; commit + `tools/snapshot.sh` + push after each step; keep the HANDBOOK/brief in step with any
renamed command. Don't run missions (session 11 does).

**State at the end of session 9 (10-28 ~20:00):** Dive04 idle in town, clvl 29, 358/358, AC ~94 (armour re-enchanted),
300 gold carried + **19,327 banked** in the wilderness house (tile north of town, door 60,129). Server, Pilot (all
session-9 code loaded), viewer running; SGE job 8268425 (scc-pc4) ends **Thu 10-29 09:47** -- session 10 may run in a
new job: check `pgrep -af "gdb -batch|pilot.py"` and operations.md for restarting. Start the inbox watcher first.

**The Advisor has already described its side for the Documentation: `memos/to_architect/2026-10-28-advisor-docs.md`**
(read; quote or link it): its role and method (studies, Clerks, METHOD.md, STATUS.md), memo conventions, the files our
tools import (`options_sim.py`, `scenarios.py`, the replays, the rulebook via `tools/rulebook/sync.sh`) and the
estimator contract (`choose`, the player-dict keys). **Constraints for the refactor:** nothing in Advisor/ imports
pilot.py/world.py -- except `data/rulebook/build_shops.py`, which imports **`tools/observe/shopmath.py`** (keep that
path or tell the Advisor); **the logs are the real interface** (decisions/events/state.jsonl kinds and fields,
levels/*.txt, scorecards, missions.json): keep their formats; `TICK_S = 0.625` (world.py) is mirrored in its replay.py;
if escape()/group_tick/speed_start/berserk/fear functions are renamed, tell the Advisor (its POLICY_VERSION comment
names them).

**Session 11's handoff already exists** (below, Part A, by session 9). Anything session 10 wants session 11 to know
goes in **Part B** of that handoff, marked as coming from session 10 -- don't rewrite Part A. Update the memory
pointer (mangband-next-steps) at the end of session 10.

### HANDOFF TO ARCHITECT 11 (missions and implementation resume)

#### Part A -- written 2026-10-28 ~20:00 by the session-9 Architect

**State (end of session 9; session 10 changes nothing in play):** Dive04 in town, clvl 29, 358/358, AC ~94, Battle Axe
of Westernesse (FA, SI), Rings of Protection [+16]/[+12], Leather of Resistance, Boots of Stability; 300 gold carried +
19,327 banked in the **wilderness house** (the tile north of town: walk off town's north edge at 1,130, arrive at
64,130, door 60,129; operations.md "Houses and the gold bank"); the stash lives in that house (empty now).
`max_depth` 800 (the user: keep). `runs/pilot/dive04/ask_unlimited` kept (the user). Missions run in session 9:
m55-m60. Session 10 may have restructured the code: read its Part B first.

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

**Open items for session 11:**
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

#### Part B -- from session 10

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

**Still open, waiting on the user:** groups **B** (B9-B18), **D**, **E**, **F**, and A16, A17, A19, A21, A22
(refactor-candidates "A2"). **A25** (set-pieces A2I/A2L, FAIL on a stale criterion: the Pilot fought and won
correctly; the scenarios need a unique above clvl 29) **waits until we have implemented the test server** (the
user). C8: only the Pilot's dead-character whitelist changed; the scorecard/viewer query
lists wait for D7. From the Advisor (29o): an optional `p["noise"]` in estimator snapshots (0 while the Pilot stands
still) -- not built.

**Defaults to beware (F1/F2, not fixed):** `pilot.py --port`, `MangClient` and `observe/study/record.py` default to
**18346, the live server**; always pass 28346 (restart.sh does). pilotctl's default nick is `dive01`: always pass
`--nick dive04`.

**Process note:** session 10 surveyed with ten parallel subagents (one per component, ~5 min each, writing the docs
directly), then one merging the candidates; bug fixes went to agents on disjoint files. The main context stayed small.
Reuse that for big reading jobs. And: before continuing a session in a new job, `claude --resume` it -- a fresh chat
lacks the context (how the parallel chat happened).

**State now (10-29 evening):** version **2.39.0**. Running in SGE job 8327794 (scc-va4, ends Tue
11-03 08:47): the test server (gdb, freeze-enabled), Dive04's Pilot (2.39.0), the viewer (`tmux -L mang attach -t
watch`). Dive04 idle in town, 358/358, 300 gold + 19,327 banked in the wilderness house. 124 unit cases pass.

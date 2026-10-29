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

### >>> WHICH HANDOFF IS YOURS? <<<
- **Session 10 is done** (2026-10-29: the Documentation in `docs/`, the cleanup list `docs/refactor-candidates.md`,
  bug fixes A1-A3/A6/A8-A11; continued that afternoon: A4/A5/A7/A12-A14, group C, `CHANGELOG.md` and versions --
  version 2.37.0; Part B has it all). If the user asks for more cleanup from that list, HANDOFF 10 below has the rules.
- **Session 11** (missions and implementation resume): read **"HANDOFF TO ARCHITECT 11"** below -- **Part B first**
  (by session 10), then Part A (by session 9).
- Sessions 8 and 9 are over; the older handoffs further down are history.

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

*Written 2026-10-29 ~08:40 by the session-10 Architect.*

**The Documentation exists: `docs/`.** Start with `docs/CONDENSED.md` (3 pages); `docs/README.md` is the index of ten
component files (client-server, pilot-core, pilot-combat, pilot-items, goals-and-plans, commands -- every pilotctl
command --, gear-and-estimator, observe, harness-rulebook-ops, process). They describe the code at dd2200d. **Read the
component file before opening its source**, and keep it in step when you change that component. roles.md,
operations.md and the memory point to it.

**Cleanup list: `docs/refactor-candidates.md`** (75 items in groups A bugs, B doc fixes, C remove/archive, D
duplicates, E splits incl. a pilot.py module plan, F defaults/safety). The user approved and session 10 did **A1-A3,
A6, A8-A11** (commit dd2200d, 117 unit cases; the Pilot restarted 08:35 on that code; the Advisor told by memo):
- A1: escape's stairs walk no longer hijacks later walks (`escaping_to_stairs` is tied to its walk and level).
- A2: flavour learning matches item type; the bad "Amber Amulet = Scroll of Identify" entry removed from runs/flavours.json.
- A3: the shadow estimator gets total to-hit/to-dam (agree rates will shift: compare estimator records before/after
  10-29 08:35 separately).
- A6: gearcmp's verdict and the loadout optimizer share one loss rule (`geareval.auto_swap_losses`).
- A8: `damage_mix.py --mission LABEL` (wrap.sh passes it): the EHP damage mix follows the mission's depth band.
- A9: `scorecard.py` with no labels only prints the table; `--all` rescores real missions, `--sp` adds set-pieces.
- A10: `watch_mission.py --nick N` (default dive04) **resumes where its last run stopped** (state in
  `runs/pilot/<nick>/watch_mission.state`; `--fresh` to start at the ends); pilot.log alerts only on tracebacks and
  "client exited". wrap.sh complaints and `notes.py --mission` filtered to the mission's time.
- A11: `review wear` in the dungeon says "kept, NOT worn ... wear it in town".
**Still open, waiting on the user:** groups B-F (the user hasn't chosen yet) and A4, A5, A7, A12, A13, A14 (A14: the Advisor asks for slays/brands/weight in shadow snapshots; A13: Rings of
Damage/Accuracy count for nothing in geareval). **Navigator-facing doc errors to know before briefing a Navigator**
(B1-B8, not fixed yet): the HANDBOOK names a `sell` command that doesn't exist (selling is `goal shop N sell
[!]NAME`); it says the stash is in the tavern (it's in the wilderness house) and that `plan town` eats to Full (Fed);
HANDBOOK-reference still offers `goal goto`/`stairs` (refused to the Navigator); BRIEF-TEMPLATE's fixed gear text is
dated (Rings [+16]/[+12], Boots of Stability now). Fix them (if the user agrees) before the first mission, or tell the
Navigator in the brief.

**Session 10, continued (2026-10-29 afternoon, new SGE job 8327794 on scc-va4, ends Tue 11-03 08:47): version 2.37.0.**
The user approved and this session did A4, A5, A7, A12, A13, A14 and group C (C1, C2, C5-C13; C11 with a new
`CHANGELOG.md` and **versions**). See `docs/refactor-candidates.md` ("done (session 10)") and CHANGELOG 2.37.0.
- **Versions (the user's decision):** `major.minor.patch`; **minor = play can differ, patch = it can't** (scorecards
  compare within a minor). `github/VERSION` holds it; the Pilot shows it (`status full`, `started`), `mission start`
  records it in missions.json. **Every session: bump VERSION, add a CHANGELOG entry (missions on it), tag `vX.Y.Z` on
  the version's last commit, push tags (`git push origin restructure --tags`).** 2.36.0 and older were assigned
  retroactively (72 versions; m1-m60 mapped).
- **Still waiting on the user:** C3 (old observers to `observe/study/`), C4 (shopcat tour scripts to the attic), C14
  (shrink HANDBOOK-reference); groups B, D, E, F. B1-B8 (the Navigator-facing doc errors above) are still unfixed.
  C8: only the Pilot's dead-character whitelist changed (the scorecard/viewer query lists also hold names Navigators
  really typed, `help`, `news`, `inventory`: merge them in D7).
- **Open from the Advisor (29o):** the estimator now wakes sleepers by noise and distance; an optional `p["noise"]`
  (0 = idle) would be right when the Pilot has been standing still (resting, band waits). Not built.
- Running at the end: test server (gdb, freeze-enabled), Dive04's Pilot (2.37.0), the viewer (`tmux -L mang attach -t
  watch`). Dive04 idle in town, 358/358, 300 gold + 19,327 banked.

**Process note for future sessions:** session 10 surveyed with ten parallel subagents (one per component; ~5 min
each, wrote the docs directly), then one merging the candidates; three more fixed the bugs on disjoint files. The main
context stayed small. Reuse that pattern for big reading jobs.

**Defaults to beware (F1/F2, not fixed):** `pilot.py --port` and `MangClient` default to **18346, the live server**;
always pass 28346 (restart.sh does). pilotctl's default nick is `dive01`: always pass `--nick dive04`.

**SGE:** job 8268425 ends 10-29 09:47 and takes the test server, the Pilot and the viewer with it: restart them per
operations.md in the new job (Dive04 was idle in town, 358/358, 300 gold + 19,327 banked).


# HANDOFF TO ARCHITECT 10 (history)

Moved here from `next_steps.md` at the end of session 10 (2026-11-02). Session 10's record of what it did is
still in `next_steps.md` ("SESSION 10 RECORD").

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


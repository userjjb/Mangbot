# Process: roles, agents, missions, memos, and the project docs

This project is run by several Claude agents and one program, each in a fixed role: the **Pilot** (a Python daemon)
plays the character second to second, the **Navigator** (an LLM subagent) steers it strategically, the **Architect**
(the main chat with the user) builds everything and runs missions, and the **Advisor** (a separate Claude project)
studies the game and our runs and writes memos. This file describes who decides and edits what, how a mission runs
from brief to pushed commit, how the Architect and Advisor exchange memos, where state lives, and every project doc
(current or history). Component details are in the sibling files: [commands.md](commands.md) (pilotctl),
[observe.md](observe.md) (viewer, monitor, scorecard), [harness-rulebook-ops.md](harness-rulebook-ops.md)
(restart/hotswap/freeze/snapshot), [pilot-items.md](pilot-items.md) (the item policy behind debts).

---

## 1. Roles and territories

Defined in `roles.md` (the user, 2026-09-26); territories from the Advisor's
`memos/to_architect/2026-09-27-territory-and-clerk.md` (the user's decision, 2026-09-27).

| Role | Who / where | Decides | May edit | Must not |
|---|---|---|---|---|
| **The user** | human | everything that matters: missions, `max_depth`, policies, what gets built, what the Advisor proposes | anything | -- |
| **Pilot** | `github/tools/pilot/pilot.py` (daemon owning the tool-mode client; one per character) | second-to-second play by policy: moves, fights, flees, cures, rests, eats, light, every item decision in the dungeon, leaving bad levels | its own state and logs in `runs/pilot/<nick>/` | set strategy |
| **Navigator** | Claude subagent, type `navigator` (`.claude/agents/navigator.md`), launched by the Architect per mission | the plan and the exceptions: town buys beyond the kit, trip depth range and conditions, standing orders, the odd hunt/fetch, overrides (`!`), talking to the user | nothing but its journal (via `pilotctl journal`) | read any file under `github/` except HANDBOOK*, FIELD-NOTES; read code; start programs other than `pilotctl.py` |
| **Architect** | the main Claude chat started in `/projectnb/jbrcs/mangband/` | how the system works: codes the Pilot, the C client and server patches, tools; writes the Navigator agent, HANDBOOK, brief; runs missions and answers asks; maintains project notes | everything under `/projectnb/jbrcs/mangband/` **except `Advisor/`**; its own memory; the subagents it manages | play as Navigator in the same session; edit `Advisor/` or the Advisor's memory |
| **Advisor** | a separate Claude project: chats started in `Advisor/` (own memory in `~/.claude/projects/-projectnb-jbrcs-mangband-Advisor/`) | what to recommend: studies, memos, the rulebook data, the estimator (`options_sim.py`) | everything under `Advisor/`; finished memos in `memos/`; notes in `memos/to_architect/`; its memory | the Pilot, Navigator, client, server, the Architect's notes and memory; a user-decided value (it proposes) |
| **Clerk** | Advisor's Sonnet subagent (`Advisor/.claude/agents/clerk.md`) | one bounded assignment of an Advisor study; returns a *dispatch* (findings with evidence tags) | its dispatch only | see the big picture, talk to the user |

Rules that cut across roles:
- **Who decides in play** (HANDBOOK "Who decides what"): the Pilot decides by policy from data. The Navigator may always
  order something safer (`goal leave`, `goal recall`, `plan stop`, `stop`, `avoid`, `keep`); something riskier or
  irreversible (a hunt, a fetch, selling or destroying over a refusal) is checked, and an override with `!` is scored as
  **debt** (section 3.6).
- **The `role` of a pilotctl call:** every request carries `role` from the env var `PILOT_ROLE` (default
  `navigator`). `PILOT_ROLE=architect` marks the Architect's and the harness's calls: they skip the value refusals,
  the override limits and the stale-order hold, may use `goal goto`, `stairs` and `raw` and item commands in the
  dungeon, and only they may `answer` asks. `mission start/end` is not enforced by role: the brief tells the Navigator
  not to touch it. The decision log tags each command `nav_cmd ... role=`.
- **Main chats** (Architect, Advisor) load Claude memory; subagents (Navigator, Clerk) don't. Memory only points into
  the project docs; anything another agent needs must be in a project file (section 6).
- **Terminology in old notes:** "agent" in `design_pilot.md` and `next_steps.md` means the Navigator; "the builder"
  means the Architect.

## 2. Agents, hooks and settings (`.claude/`)

| File | What it is |
|---|---|
| `.claude/agents/navigator.md` | The Navigator subagent definition (tools: Bash, Read). Its sources: `HANDBOOK.md` (read fully first), `FIELD-NOTES.md` (every mission start), `HANDBOOK-reference.md` (grep only), `notes_players.md`. How to run pilotctl (`wait 240` with a 300 s Bash timeout; `parked` / "Connection refused" during a Pilot update: retry every 20 s). Its loop (plan with `prep`, `plan town`, `plan trip`, react to attention events, end in town). User messages (`ATTENTION user_message`, the `USER MESSAGE(S) NOT YET ANSWERED` banner; answer with `say` first). Journal (`pilotctl journal "situation | decision | why"`, stamped by the Pilot; urgent alerts: order first, journal after). `complain` for what it lacked (vs its own mistakes). The final report's sections (state, close calls, Pilot problems, what I lacked, handbook suggestions). Kept outside the git repo (snapshotted into `github/project/tree/.claude/`). |
| `.claude/settings.json` | Wires `inbox.sh` into three Claude Code hooks for the Architect's inbox `memos/to_architect`: `SessionStart` (`hook-session`), `PostToolUse` matcher `*` (`hook-post`), `Stop` (`hook-stop`); and allows `Bash(.../inbox.sh *)` without a prompt. No other hooks. |
| `.claude/hooks/inbox.sh` | The memo notifier (section 4). The Advisor keeps an identical copy in `Advisor/.claude/hooks/inbox.sh` for `memos/to_advisor`. |
| `Advisor/.claude/agents/clerk.md`, `Advisor/.claude/settings.json` | The Advisor's side (not ours to edit). |

## 3. How a mission flows

A **mission** is one Navigator run of a fixed wall-clock budget (30 or 45 min) with character Dive04 on the local test
server, scored and compared across Navigator models. Missions are numbered `mNN` (m60 is the latest, 2026-10-28);
set-pieces from the harness use `sp-...` labels in the same records. The per-mission checklist below is distilled from
`next_steps.md` (HANDOFF 8 "Per mission", HANDOFF 11 Part A "Routine") and `BRIEF-TEMPLATE.md`.

**Before (once per session):** start the inbox watcher; check the processes (`pgrep -af "gdb -batch|pilot.py"`,
`tmux -L mang ls`): the test server (under gdb, with `MANGBAND_FREEZE_FILE`), Dive04's Pilot, the user's viewer
(`tmux -L mang attach -t watch`). Restart them per `operations.md` "Test server" and `tools/pilot/restart.sh Dive04`
if the SGE job ended. Ask the user what to run (model, effort, length).

| # | Step | Command / tool (in `github/tools`, `module load python3/3.12.4`, `export PILOT_ROLE=architect`) | Writes |
|---|---|---|---|
| 1 | Mark the start | `python3 pilot/pilotctl.py --nick dive04 mission start mNN navigator=MODEL [effort=L] [notes=..]` | `mission_start` in `decisions.jsonl`; a record in `runs/missions.json` (label, nick, start, navigator, effort); the Pilot's mission baseline for "this mission" rates |
| 2 | Fill the brief | Copy `tools/pilot/BRIEF-TEMPLATE.md` below its `---`; fill `{...}` from `status`, `equip`, `pack` (time budget START/END, clvl/HP/AC/gold, supplies, debts, "New since the last mission"); keep the rest word for word so missions stay comparable. `[VACATION]` lines only in a vacation session. | -- |
| 3 | Launch the Navigator | Agent tool: `subagent_type: "navigator"`, `model`/`effort` only as the user asks, `run_in_background: true`, the brief as prompt | its transcript (Claude's subagent jsonl; `observe/tokens.py` reads it for cost) |
| 4 | Monitor | `python3 observe/watch_mission.py 1500` in the background; it exits on a Navigator question (`NAV ASK`), an emergency or escape, a death, a stat drain, a user message, a stuck plan, a plan end, a gear swap, a Python error in `pilot.log`, or after 1500 s quiet. Look, act, **restart it every time**. Kill it only with a bracketed pattern (`pkill -f "watch_mission[.]py"`). | -- |
| 5 | Asks and answers | The Navigator's `ask TEXT` never blocks: it appends to `runs/pilot/dive04/asks.jsonl` and logs `nav_ask`. Rate limit 1 per 5 min and 4 per hour (`Pilot.ASK_GAP_S`, `ASK_PER_HOUR`) unless `runs/pilot/dive04/ask_unlimited` exists (it does: the user kept it, 10-27). `ask quiet TEXT` also starts a quiet wait (up to 10 min, ends on the answer or a threat). The Architect investigates (`status`, `why`, `decisions.jsonl`) and replies `pilotctl answer ID "text"` (logged `arch_answer`; shown to the Navigator as `ARCHITECT ANSWER #ID`). The Architect may also SendMessage the Navigator agent directly. | `asks.jsonl`, `decisions.jsonl` |
| 6 | User messages | The user types in the viewer (`watch.py`): `!text` goes to the Navigator (attention event `user_message`; answered with `say`), `?text` is a question for the Architect, plain text is commentary. | `commentary.jsonl`, `user_note` in `decisions.jsonl` |
| 7 | Interventions | Only when it clearly helps: `goal recall`, `goal leave`, `quaff ...`, `use Staff_of_Teleportation force`, `plan stop`, `stop`, `react ...` as `PILOT_ROLE=architect`. Don't change `max_depth` or orders without the user; the time freeze is a testing tool, not for deciding. | `nav_cmd role=architect` |
| 8 | Pilot updates mid-mission | Only `tools/pilot/hotswap.sh dive04` (freezes time, swaps, thaws) or `restart.sh` (parks first); never `pkill` the Pilot mid-move (crashes the test server). The Navigator sees `parked`, then "Connection refused" for a minute; a plan survives. | -- |
| 9 | The Navigator returns | Its final report: state, close calls, Pilot problems, what it lacked, verdicts on the brief's list. | -- |
| 10 | Wrap up | `bash observe/wrap.sh mNN` | `mission end` by label (a hotswap loses the in-memory label) -> `mission_end`, `missions.json` end; `tokens.py` -> the record's `tokens` (turns, cache, USD); `scorecard.py --table` -> `runs/pilot/dive04/scorecards/mNN.json` and a table row; `damage_mix.py` -> `damage_mix.json` (EHP); prints the last 2 h of `runs/complaints.md`, the viewer's `?` questions, `status` and `debt` |
| 11 | Mission report | Write `runs/pilot/dive04/reports/YYYY-MM-DD-missionNN.md` (header: mission, Navigator model/effort, times; then what happened, numbers, problems, verdicts). Templates: the latest reports (mission60.md). | report |
| 12 | Lessons | New play lessons into `github/tools/pilot/FIELD-NOTES.md` (newest first per section; Navigators read it each mission). System changes go in HANDBOOK.md instead. | FIELD-NOTES.md |
| 13 | Friction | Read the Navigator's complaints (`runs/complaints.md`, also "NAVIGATOR LACKS" in the viewer) and its "What I lacked": fix what you can; relay recurring/unfixable ones to the user in the mission summary (memory: relay-agent-friction). | -- |
| 14 | Publish | `github/tools/snapshot.sh`, commit (in `github/`), `git push origin restructure`. | `github/project/`, git |

**Debts and overrides** (`pilot.py: Pilot.override_allowed`, `settle_hunt`; HANDBOOK "Who decides what"). When the
Navigator overrides a refusal with `!` (`sell !NAME`, `destroy !NAME`, `goal hunt !NAME`): value lost on items is added
to its **item debt** (gold); HP lost when an overridden hunt goes wrong (not slain, HP below half, or an emergency
escape fired) is added to its **fight debt** (HP). Both live in `runs/pilot/<nick>/navigator_debt.json`; `pilotctl
debt` shows them; every brief states them. The limit is deliberately never a number: the user and Architect revoke
overrides by creating `runs/private/<nick>.overrides_revoked` (or `.hunt_overrides_revoked`) with the reason; the
Pilot's policy is then final.

**Who reads what afterwards:** the Architect reads the report, journal (`runs/pilot/dive04/navigator.md`), complaints,
asks, and scorecard, and decides fixes; the Advisor reads the same logs (they are its interface: keep the formats of
`decisions/events/state.jsonl`, `levels/*.txt`, scorecards, `missions.json`) and may send memos.

## 4. The inbox / memo protocol

Two inboxes under `memos/`: `to_architect/` (the Advisor writes, the Architect reads) and `to_advisor/` (the reverse).
Finished Advisor studies go in `memos/` itself (`YYYY-MM-DD-slug.md`, with an appendix directory where needed, e.g.
`memos/2026-09-26-forum/`); each gets a short note in `to_architect/` saying what to do.

- **Sending:** write `<outbox>/.tmp-SLUG.md`, then `mv` it to `<outbox>/YYYY-MM-DD-SLUG.md` (the rename makes delivery
  atomic; dotfiles are ignored).
- **Receiving:** `inbox.sh` tracks state in the recipient's inbox: `.seen` (read through its mtime), `.notified`
  (announced through its mtime), `.watcher` (host and pid of the running watcher). Mtimes are copied from memos with
  `touch -r`, so clock skew between nodes doesn't matter.

| `inbox.sh` command | What it does |
|---|---|
| `watch INBOX` | Polls every 30 s until a memo newer than `.seen` exists, prints it and the protocol, exits. Run in the background; its exit wakes the chat. Restart it after each exit (the Bash background timeout also ends it at 10 min). |
| `unread INBOX` | Lists unread memos. |
| `mark-read INBOX [FILE...]` (or `mark-read FILE...`) | Marks read through the newest given file (default: newest in the inbox). |
| `hook-session INBOX` | SessionStart hook: reports unread count and tells the chat to start the watcher if none is alive on this host. |
| `hook-post INBOX` | PostToolUse hook: after each of the main chat's tool calls (not subagents'), announces memos newer than `.notified`, once. |
| `hook-stop INBOX` | Stop hook: blocks the chat from stopping while memos are unread. |

The Architect's routine (memory "Inbox watcher"): start `inbox.sh watch memos/to_architect` first thing every session,
even if the hook says one runs (it may belong to a dead chat); read each memo, `mark-read`, restart the watcher. Memo
conventions (the Advisor's, `memos/to_architect/2026-10-28-advisor-docs.md` §2): findings first with evidence marks
(`[code ✓]`/`[log ✓]`, file:line), recommendations split into Pilot rules / Navigator doctrine / HANDBOOK text, a
contradictions table, coverage and gaps, and **What I lacked** (copied to `runs/complaints.md`). Questions for the
user go through the Architect; the Advisor proposes, never changes, user-decided values.

**The Advisor's side** (same memo, §1): it works in **studies** (`Advisor/METHOD.md`): a plan with 3-8 questions,
split into assignments for **Clerks**, whose dispatches carry `[SEEN]/[REPORTED]/[INFERRED]` tags; the Advisor
verifies the claims the memo relies on and writes the synthesis. Each study's trail is in
`Advisor/studies/<date>-<slug>/` (plan.md, briefs/, dispatches/, synthesis.md). Its chat-to-chat handoff is
`Advisor/STATUS.md`. §3-5 of that memo list the Advisor files our tools import (`options_sim.py`, `scenarios.py`,
replays, the rulebook via `tools/rulebook/sync.sh`) and what a pilot.py split must keep: see
[gear-and-estimator.md](gear-and-estimator.md).

**Advisor memos by topic** (finished studies in `memos/`; ~57 notes in `to_architect/`, ~54 Architect replies in
`to_advisor/`):

| Topic | Memos |
|---|---|
| Game knowledge | `2026-09-26-forum-distillation` (+ `2026-09-26-forum/` appendices), `2026-09-27-danger-table`, `2026-09-29-message-catalogue`, `2026-09-29-shops`, `2026-10-07-warrior-progression`, `2026-10-07-running` |
| Live server / versions | `2026-09-29-versions-and-forum-rules` (live-server rules a bot must follow) |
| Other bots | `2026-09-28-borg` |
| Our runs | `2026-09-28-run-postmortem`, `2026-10-03-game-state`, `2026-10-07-identify-and-sell`, `2026-10-07-mission15-answers`, `2026-10-08-navigator-decisions`, `2026-10-24-m24` |
| Restructure | `2026-10-19-starting-over` (the restructure's basis), `2026-10-23-scorecard`, `2026-10-24-setpieces`, `2026-10-24-structures` |
| Rulebook | `2026-10-24-rulebook`, `-r2`, `-r3` |
| Estimator | `2026-10-25-estimator`, `2026-10-25-replay` (then many short `to_architect/` notes: shadow, speed, xp-per-gold, gear evaluator, slays, min-gain, policy versions) |
| Backlog | `2026-09-27-advisor-study-topics` |

## 5. Where state lives

| Where | What | Notes |
|---|---|---|
| `testserver/` | The local test server's run directory: `mangband.cfg` (port 28346), `save/` (character and world savefiles, the real game state), `FREEZE` (exists = time frozen), `gdb_run.log`, `server.log`, `crash*/`, `bone/`, `data/` | Start it from this directory (`-c` is broken). SIGTERM saves cleanly. A crash rolls characters back to their last save. |
| `runs/pilot/<nick>/` (dive04 is live; dive01-03 old) | The Pilot's per-character state and logs: logs (`decisions.jsonl`, `events.jsonl`, `state.jsonl`, `pilot.log`, `levels/` level dumps), mission (`navigator.md` journal, `asks.jsonl`, `commentary.jsonl`, `navigator_debt.json`, `ask_unlimited`), persistent knowledge (`orders.json`, `standing.json`, `keep.json`, `review.json`, `rules.json`, `rates.json`, `recall.json`, `deepest.json`, `uniques_killed.json`, `stores.json`, `stash.json`, `house.json`, `damage_mix.json`), `ctl.sock` (pilotctl's socket), `reports/` (mission reports), `scorecards/` (`mNN.json`, `sp-*.json`) | Formats: [pilot-core.md](pilot-core.md). The logs are the Advisor's interface. |
| `runs/pilot/town.json`, `visuals.txt` | shared town map and glyph tables | |
| `runs/missions.json` | One record per mission and set-piece (label, nick, start/end, navigator, effort, tokens/USD) | Written by `mission start/end`, `tokens.py` |
| `runs/complaints.md` | What agents lacked: `pilotctl complain` appends; Advisor/Clerks by hand; marked FIXED when fixed | Read after every mission |
| `runs/flavours.json` | The learnt flavour table | |
| `runs/setpieces/` | Set-piece results (`<id>-<stamp>.json`, `results.md`) and `saves/` | [harness-rulebook-ops.md](harness-rulebook-ops.md) |
| `runs/private/` (mode 700) | Passwords `<nick>.pass`, configs `<nick>.mangrc`, override revocations | Never committed |
| `runs/docs/` | mangband.org player docs (HTML + text), the source of `notes_players.md` | |
| `runs/observe/` | Recorded human sessions, Scribe's fifo/log | |
| `runs/live-*`, `runs/regress.*` | The 2026-09-25 live shop tour and town catalogue; the shopcat regression run | History |
| `runs/backup-pre-restructure-20261022/` | Saves and files from before the restructure (restore point; `restructure.md`) | History |
| `runs/phase0/` | an early birth packet log | History |
| Claude memory | Architect: `~/.claude/projects/-projectnb-jbrcs-mangband/memory/`; Advisor: `...-Advisor/memory/` | Pointers only (section 6) |
| `Advisor/` | The Advisor's studies, data (rulebook, estimator, monsters, forum corpus), `STATUS.md` | Read-only for us |
| git: `github/` | Code; branch **`restructure`** (current work, ~360 commits, pushed), `master` (at tag `pre-restructure` = 767bf60, 2026-10-22); remote `origin` = https://github.com/userjjb/Mangbot | The public repo |
| `github/project/` | The snapshot of everything above that isn't code or secret: `tree/` (the project dir minus `github/`), `memory/architect/`, `memory/advisor/`, `claude/global-CLAUDE.md`, `SNAPSHOT_TIME` | Made by `tools/snapshot.sh` (excludes passwords, saves, server logs, the forum corpus, raw event streams, files > 5 MB; refuses if a secret-looking string slipped in). Restoring: `project/README.md`. |

## 6. The Architect's memory

`~/.claude/projects/-projectnb-jbrcs-mangband/memory/` (loaded only by Architect main chats; indexed by `MEMORY.md`):

| File | Points to / says |
|---|---|
| `mangband-roles.md` | You are the Architect; the roles (roles.md); the territory rule; `memos/` is shared |
| `mangband-next-steps.md` | READ FIRST: `next_steps.md` ">>> WHICH HANDOFF IS YOURS? <<<"; one-paragraph current state (branch, Dive04, job end) |
| `mangband-project-map.md` | Where every doc and tool lives; critical gotchas (restart/hotswap only, freeze env var, orphans, `pkill -f`, python module, `rm -i`); **the SYNC RULE** |
| `mangband-advisor-memos.md` | Log of Advisor memos to 10-26 and forum-scraping facts |
| `mangband-inbox-watcher.md` | Start the watcher first thing every session, restart on exit (feedback) |
| `mangband-relay-agent-friction.md` | A subagent's "my mistake" may be a missing capability; read `runs/complaints.md` after every mission; relay friction to the user (feedback) |
| `mangband-restructure.md` | Restructure on branch `restructure` since 10-22; revert per `restructure.md` only on request; the Navigator debt rule |
| `mangband-no-crutches.md` | Don't let test-server advantages (rare items, forged kits, DM help) hide live problems; `pilot.py --live`, crutch devices sold on test (feedback) |

**The SYNC RULE** (the user, 2026-09-27; in roles.md and the project-map memory): project docs hold the substance,
memory only points to them. Whoever adds, renames or restructures a doc or section, updates the handoff, or adds or
retires a critical gotcha must update the main chats' memory pointers in the same session. Learn something: write it in
the project docs first, then point to it. The Advisor has its own memory (forked from the Architect's on 2026-09-27).

## 7. Map of project docs

Status: **current** = maintained and true today; **reference** = still accurate for its subject, not updated as
routine; **history** = a record of a past phase (may be stale).

| Doc | What it is | Status |
|---|---|---|
| `docs/` (this set) | The Documentation (session 10): an index and one file per component | current |
| `roles.md` | The roles table, where knowledge lives, the SYNC RULE | current (the Navigator is "to be built": it is built) |
| `operations.md` | Practical facts for every agent: environment (python module, the public repo and push routine, build), the test server (start under gdb, the time freeze, known crashes and their patches), the characters table (Dive04 is the mission character; Surveyor, Gandalf the DM ghost, Scribe...; passwords in `runs/private/`), tool-mode client facts, verified server behaviour (incl. houses and the gold bank), the live server (mangband.org:18346; ask the admins before a live run), user decisions (never chat, throwaway build, ghosts on), agent-tooling gotchas (the viewer, `pkill -f`, logs), live-server rules a bot must follow | current |
| `next_steps.md` (~1800 lines) | The Architect handoff. Top: an old "Read these first"/"What exists"/"Hard-won facts" from 09-25; then **">>> WHICH HANDOFF IS YOURS? <<<"**, which names the handoff for each session number; then the handoffs, newest first (HANDOFF 10, HANDOFF 11 Part A/B, HANDOFF 8, ...). Each session writes the next handoff; session N+1 writes only its own Part. **~1500 lines below the current handoffs are history** (older handoffs, "Reflections from the agent who built this") | current at the top, history below |
| `restructure.md` | How to revert to before the restructure (tag `pre-restructure`, backups in `runs/backup-pre-restructure-20261022/`); only on the user's request | reference |
| `restructure-step2.md` | The design of restructure step 2, "who decides what" (log analysis of missions 17-23, the Pilot/Navigator split, intents with conditions, the user's decisions 10-23) | history (built) |
| `VACATION-NOTES.md` | Session 8 ("The Architect's Vacation": the Architect helped Navigators live, no coding): bugs, wishes, blind spots, interventions, the ask channel; plus session 9's triage at the top | history |
| `design_pilot.md` | The original Pilot design: architecture and reflex list (still roughly current); its goals/orders/events lists are superseded by the HANDBOOK | history / partly reference |
| `design_gear.md` | The gear evaluator (`geareval.py`, `gearcmp`), its limits, EHP, the loadout optimizer | current |
| `notes_players.md` | Digest of the mangband.org player docs, the user's advice, observed human play (game knowledge; the Navigator may read it) | reference |
| `notes_merge.md` | The original protocol/codebase survey (packets, login, stores, custom commands, file map) for the tool client | reference (pre-Pilot) |
| `spells.md` | MAngband priest prayers from the source (levels, mana, effects) | reference (unused: we play warriors) |
| `github/tools/pilot/HANDBOOK.md` | The Navigator's manual (~200 lines): who decides what, the loop, the report, commands, judgement calls, the deadly few, housekeeping | current (the Navigator's truth; wins over the reference) |
| `github/tools/pilot/HANDBOOK-reference.md` | The old full handbook: every goal, order, event, report line, lessons of missions 1-23; grep only | reference (partly stale) |
| `github/tools/pilot/FIELD-NOTES.md` | Lessons from missions for Navigators (where the XP is, dangers by depth, shops and money, gold/thieves/the house, Pilot habits, best Navigator moves); the Architect adds after each mission | current |
| `github/tools/pilot/BRIEF-TEMPLATE.md` | The mission brief and how to launch a mission | current (some fixed gear text is dated) |
| `github/tools/harness/README.md`, `rulebook/README.md`, `shopcat/README.md` | Component READMEs | see [harness-rulebook-ops.md](harness-rulebook-ops.md) |
| `github/project/README.md` | What the snapshot holds and how to restore from a commit | current |
| `memos/` | Advisor memos and the two inboxes (section 4) | current (each memo dated) |
| `runs/pilot/dive04/reports/` | One report per mission (46 so far, m17-m60) | records |
| `runs/complaints.md` | Agents' complaints and their fixes | current |
| `Advisor/METHOD.md`, `Advisor/STATUS.md`, `Advisor/CLAUDE.md` | The Advisor's method, handoff, instructions | the Advisor's |

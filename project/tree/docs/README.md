# The Documentation

What everything in this project does, so you can understand the whole and each part without reading the code.
Written in session 10 (2026-10-29) from the code at git `d53ba3b` and kept in step since (now version 2.39.0, every claim checked against the code on 10-29; `github/VERSION`, `../CHANGELOG.md`). Where a doc and
the code disagreed, these files follow the code. When you change a component, update its file here too.

**In a hurry?** Read [CONDENSED.md](CONDENSED.md) (the 3-page version for Architects and Advisors).

## The big picture

We built an AI system that plays **MAngband** (multiplayer Angband 1.5.3) with one character, **Dive04** (a warrior),
on a **local test server** (port 28346, our build with a time freeze). The live public server is the eventual target.
The system has four roles ([process.md](process.md), `../roles.md`):

| Role | What it is | Decides | Edits |
|---|---|---|---|
| **Pilot** | `github/tools/pilot/pilot.py`, a Python daemon, plays second to second through our headless client | fights, escapes, pickups, routine town shopping -- everything by policy | nothing (it is code) |
| **Navigator** | an LLM subagent (`.claude/agents/navigator.md`), steers the Pilot with `pilotctl` commands, taught by the HANDBOOK, never sees code | the plan (where, how deep, when home) and the exceptions; may override the Pilot's value refusals with `!` and pays "debt" for it | nothing |
| **Architect** | the main Claude chat in `/projectnb/jbrcs/mangband` | builds and changes the Pilot, client, tools; runs missions and answers the Navigator's asks | everything except `Advisor/` |
| **Advisor** | a separate Claude project in `Advisor/` with Sonnet **Clerks** | studies the game and our logs, writes memos, owns the rulebook tables and the fight estimator | only `Advisor/` and `memos/` |

**The user** decides policy questions; the Architect asks, the Advisor proposes through the Architect.

### The stack, bottom up

```
MAngband server (test: ../testserver, port 28346; freeze file stops game time)       client-server.md
  ^ network protocol
mangclient -mtool  (our headless client: JSON events out, one-line commands in)       client-server.md
  ^ stdin/stdout, via tools/shopcat/mang.py: MangClient
Pilot daemon  pilot.py (+ world, mover, glyphs, structures, itemvalue, geareval)       pilot-core.md
  |  every tick: reflexes (stay alive) -> the goal (Explore, Dive, TownKit...) -> item policy
  |                                     pilot-combat.md / goals-and-plans.md / pilot-items.md
  |  writes runs/pilot/<nick>/ : decisions/events/state.jsonl, levels/, rates, stash, house...
  ^ Unix socket runs/pilot/<nick>/ctl.sock (one JSON request per call)
pilotctl.py  (PILOT_ROLE=navigator|architect decides what is refused)                  commands.md
  ^ Bash
Navigator subagent (a mission)    Architect (missions, asks, code)    the user (watch.py viewer)
```

Side systems: the **gear evaluator** and the Advisor's **estimator** ([gear-and-estimator.md](gear-and-estimator.md)),
the **observers** -- the user's viewer, the mission monitor, scorecards ([observe.md](observe.md)), the **test harness**,
the **rulebook** tables and the ops scripts ([harness-rulebook-ops.md](harness-rulebook-ops.md)).

### How a mission flows (details: [process.md](process.md))

1. The Architect runs `pilotctl mission start mNN navigator=MODEL effort=E`, fills `github/tools/pilot/BRIEF-TEMPLATE.md`
   from `status`/`equip`/`pack` (including the Navigator's current debts) and launches the `navigator` subagent.
2. The Navigator plans with `plan town` (the town kit: sell, buy, bank, recharge, enchant) and `plan trip` (dive to a
   depth band, explore, come home on a supply or time limit), waits with `wait`, steps in with goals, items and `react`
   rules, and asks the Architect with `ask` when unsure.
3. The Pilot plays; the Architect watches with `observe/watch_mission.py` (exits on an ask, emergency, death, stuck
   plan...), answers with `pilotctl answer`; the user watches `observe/watch.py` and can leave notes or freeze time.
4. After: `observe/wrap.sh mNN` (mission end, scorecard, Navigator token cost, damage mix, complaints), a report in
   `runs/pilot/dive04/reports/`, lessons into `github/tools/pilot/FIELD-NOTES.md`, then `tools/snapshot.sh`, commit,
   push.

### Where state lives

| What | Where |
|---|---|
| Code (git, branch `restructure`, public repo https://github.com/userjjb/Mangbot) | `github/` -- our MAngband fork + `github/tools/` |
| Test server, its config and saves | `testserver/` (start/restart: `../operations.md`) |
| The Pilot's per-character state and logs | `runs/pilot/<nick>/` ([pilot-core.md](pilot-core.md) lists every file) |
| Missions, scorecards, reports | `runs/missions.json`, `runs/pilot/dive04/scorecards/`, `.../reports/` |
| The code's version and its history | `github/VERSION` (major.minor.patch), `../CHANGELOG.md` ([process.md](process.md)) |
| Retired scripts and data | `github/tools/attic/` (its README.md says why each went) |
| Old handoffs and retired notes | `../history/` |
| Live deployment checklist | `../live-deploy-todo.md` |
| Credentials | `runs/private/` (never in the public repo) |
| Advisor's work, memos | `Advisor/` (its own), `memos/` (shared: `to_architect/`, `to_advisor/`) |
| Handoffs between Architect sessions | `../next_steps.md` (">>> WHICH HANDOFF IS YOURS? <<<") |
| Whole-project snapshot for the public repo | `github/project/` (`tools/snapshot.sh`) |

## The files

| File | Covers |
|---|---|
| [CONDENSED.md](CONDENSED.md) | the short version of everything below |
| [process.md](process.md) | roles and territories, the Advisor's side, how a mission flows, memos and the inbox, every project doc (current vs history), where state lives |
| [client-server.md](client-server.md) | our MAngband changes: the tool-mode client (every command and event), login/birth automation, packet logs; the test server's changes (time freeze, store guard, depth indicator) |
| [pilot-core.md](pilot-core.md) | the Pilot's architecture: process model, the tick loop, the world model, pathing, glyphs and monster knowledge, structures, logs and state files, the status report, updating a running Pilot |
| [pilot-combat.md](pilot-combat.md) | staying alive: the reflex stack, `escape()` and its order, emergency and flee goals, fights and buffs, status cures, the watches, `react` rules |
| [pilot-items.md](pilot-items.md) | the item policy: values, pickup and room, junk, identify and flavours, wearing upgrades, the review queue, keep lists, value refusals, debts, the orders |
| [goals-and-plans.md](goals-and-plans.md) | goals (every Goal class), plans (`plan trip`, `plan town`), the town kit, supplies in dungeon minutes, the gold bank in the wilderness house, the stash |
| [commands.md](commands.md) | `pilotctl`: every command by family, who may use it, what it refuses, what it prints; `!` vs `force` |
| [gear-and-estimator.md](gear-and-estimator.md) | `gearcmp`, `loadout`, the simulator's fight sets, EHP, the verdict rules, auto-wear, shadow mode and the Advisor's estimator contract |
| [observe.md](observe.md) | the viewer, the mission monitor, `wrap.sh`, scorecards (every metric), token costs, the damage mix, shop maths, study tools |
| [harness-rulebook-ops.md](harness-rulebook-ops.md) | unit cases, live set-pieces and the Dungeon Master, the rulebook tables, shopcat, freeze/snapshot/restart/hotswap |
| `../history/survey-notes/*-candidates.md` | session 10's raw refactor/remove candidates per component (all merged into the refactor list; moved to history/ 10-29) |

## Other docs (not replaced by these)

`../operations.md` (how-tos: servers, characters, houses, gotchas), `github/tools/pilot/HANDBOOK.md` (what the
Navigator is taught; `HANDBOOK-reference.md` the long old one), `FIELD-NOTES.md` (lessons for Navigators),
`BRIEF-TEMPLATE.md`, `../design_pilot.md` and `../design_gear.md` (design reasoning), `../notes_players.md` (game
knowledge), `../roles.md`. [process.md](process.md) maps them all.

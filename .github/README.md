# Mangbot: a team of AI agents playing MAngband

**Mangbot** plays [MAngband](https://mangband.org) (multiplayer, real-time Angband) with a small team
of Claude agents and one fast rule-based program. Its aims:

- learn to play a character well and safely, in real time;
- **explore how agents with different speeds and depths of thinking can work together** on a task
  that never pauses;
- let a human watch, comment and steer.

This repository is the MAngband 1.5.3 source with our additions:
- a headless **tool-mode client** that speaks JSON;
- the **Pilot**, which plays second to second;
- an **observer** for watching live;
- `project/`, a snapshot of the whole working state.

The original MAngband README is [`/README`](../README); the code is under the MAngband License
([`/COPYING`](../COPYING)).

## How it works: the roles

```
            the user (watches live, comments, steers)
               │ ! messages / ? questions          ▲ viewer: map, alerts, reasoning
               ▼                                   │
   Advisor ──memos──▶ Architect ──builds/launches──▶ Navigator ──goals/orders──▶ Pilot ──▶ game
   (+ Clerks)          (Claude)                      (Claude subagent)            (Python)
   studies the game,   writes the Pilot, the client,  plays the strategy:         plays the next
   the code, our logs  the tools; reviews missions    where to go, what to fight,  second: moves,
                                                       buy, sell; journals why     fights, escapes
```

| Role | What it is | Speed | What it does |
|---|---|---|---|
| **Pilot** | Python (`tools/pilot/`: `pilot.py` and ~20 modules), rules | milliseconds | Moves, fights (the server's auto-retaliate, plus Speed/Berserk/Heroism in hard fights), escapes (stairs, Phase Door, Teleportation, Word of Recall), cures, rests, eats, keeps the light lit, loots, runs whole town visits and trips. Raises *alerts* when a decision is needed. |
| **Navigator** | Claude subagent (`project/tree/.claude/agents/navigator.md`) | ~5–30 s per decision | Plays one character through `pilotctl` (goals, orders, item commands). Reads only the Pilot's reports and its `HANDBOOK.md`, never code. Keeps a journal; answers the user. |
| **Architect** | the main Claude Code session | — | Designs and codes the Pilot and the client, launches missions, reviews reports and logs, turns every problem found into a fix. |
| **Advisor** (+ **Clerks**) | a separate Claude project; Clerks are its parallel subagents | — | Research: the forum, the server code, the Angband Borg, our own runs. Writes memos the Architect acts on. Never touches code. |
| **User** | the human | — | Sets direction, watches missions live (`tools/observe/watch.py`), messages the Navigator (`!`), asks the Architect why (`?`). |

The split is deliberate. The game is real-time: monsters act whether or not anyone is thinking. So
everything urgent lives in the fast, simple Pilot, and the slow, smart agents set strategy. Each
mission's problems become Pilot rules.

## What it can do now

- **Play a warrior at clvl 29, 700-800 ft**, in 30-45 minute scored missions (61 so far; the latest, m61:
  84 XP and 74 gold per dungeon minute, no close calls).
- **Whole plans, not just moves:** `plan town` (sell by a value policy, identify, enchant armour and weapon, buy the
  kit by depth, fill the lantern, bank gold in a house) and `plan trip LO-HI until CONDITIONS` (recall down, explore,
  leave bad levels -- breeders, traps, hounds, vaults -- and come home on the Navigator's conditions).
- **Survive by rules** learned from deaths and close calls: an ordered reflex and escape stack (`combat.py`), a
  danger estimate from the Advisor's duel simulator, a hunt check before any fight it's ordered into (HP, summoners,
  breath, disenchantment's cost), group and band awareness, cures and status handling.
- **Know the game state reliably:** a resist/ability grid, a fresh inventory per decision, a state audit, a game
  clock that follows the server's time bubble, a stomach tracker pinned by the hunger crossings.
- **Judge gear:** a gear evaluator and loadout optimizer (`geareval.py`), item values from the server's rules
  (`itemvalue.py`), learned item flavours (`runs/flavours.json`).
- **Be measured and tested:** a scorecard per mission, ~170 offline unit cases, 39 live set-pieces staged on a test
  server by a Dungeon Master character, and an equivalence harness for refactors (`tools/harness/`).
- **Watch and talk:** a colour terminal viewer (map, the Pilot's actions and alerts, the Navigator's reasoning), live
  messages to the Navigator (`!`), questions to the Architect (`?`), a complaints channel for missing tools.

## Repository layout

| Path | What |
|---|---|
| `src/`, `lib/`, autotools files | MAngband 1.5.3 (unmodified but for 16 files: the tool-mode client `src/client/c-tool.c`/`main-tool.c`, a packet logger, the test server's time freeze and store fixes). Most top-level files are upstream's |
| `tools/pilot/` | the Pilot: `pilot.py` (core and tick loop) and its modules -- `combat.py`, `items.py`, `town.py`, `gear.py`, `commands.py` + `cmdtable.py` (every `pilotctl` command), `goals.py`, `town_goals.py`, `plan.py`, `stomach.py`, `world.py`, `mover.py`...; `pilotctl.py` (the Navigator's interface); **`HANDBOOK.md`** and `FIELD-NOTES.md` (the Navigator's manual and lessons) |
| `tools/harness/` | unit cases (`unit.py`, `unit_*.py`), live set-pieces (`setpiece.py`), the DM driver, the refactor equivalence harness |
| `tools/observe/` | `watch.py` (live viewer), `watch_mission.py` (the Architect's monitor), `scorecard.py`, `tokens.py`, `wrap.sh` |
| `tools/rulebook/` | the Advisor's game tables (monsters, drops, danger) and duel simulator |
| `tools/client/` | `mang.py`, the tool-mode client wrapper |
| `project/` | snapshot of the working state (`tools/snapshot.sh`): **`tree/docs/`** (the Documentation: start with `CONDENSED.md`), `tree/CHANGELOG.md` (every version), `tree/next_steps.md` (the handoffs), `operations.md`, the Advisor's memos and studies, the agent definitions, the Claude memories. See [`project/README.md`](../project/README.md) |

To run it: build with `./autogen.sh && ./configure && make`, start a local server (port 28346; see
`project/tree/operations.md` "Test server"), create a character with `tools/shopcat/newchar.py`, start the Pilot with
`tools/pilot/restart.sh NICK`, then drive it with `tools/pilot/pilotctl.py`, or launch a Navigator agent.

Versions are `major.minor.patch` (`VERSION`, git tags `vX.Y.Z`; minor = play can differ): see
`project/tree/CHANGELOG.md`.

## Major TODOs

1. **Missions on the restructured Pilot** (the next session): test every change since m60 in real play.
2. **The repo as a patcher:** only our work at the top level, our C changes as patches against pristine MAngband
   1.5.3, and a `build.sh` that fetches, patches and builds.
3. **A separate local test server** (built with that script) for set-pieces on copies of the character, and
   server-side test features: a unique above the character's level, fixed levels and seeds.
4. **Model comparisons and the handbook A/B:** Haiku, Sonnet and Opus Navigators at different efforts; a shorter
   reference handbook against the current one.
5. **A live-server run**, only with the server admins' agreement (the checklist: `project/tree/live-deploy-todo.md`;
   the rules for bots: `operations.md`).

The current state is in `project/tree/next_steps.md` (">>> WHICH HANDOFF IS YOURS? <<<").

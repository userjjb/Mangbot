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
| **Pilot** | Python (`tools/pilot/pilot.py`), rules | milliseconds | Moves, fights by standing still (the server's auto-retaliate), escapes (stairs, Phase Door, Word of Recall), cures, rests, eats, keeps the light lit. Raises *alerts* when a decision is needed. |
| **Navigator** | Claude subagent (`project/tree/.claude/agents/navigator.md`) | ~5–30 s per decision | Plays one character through `pilotctl` (goals, orders, item commands). Reads only the Pilot's reports and its `HANDBOOK.md`, never code. Keeps a journal; answers the user. |
| **Architect** | the main Claude Code session | — | Designs and codes the Pilot and the client, launches missions, reviews reports and logs, turns every problem found into a fix. |
| **Advisor** (+ **Clerks**) | a separate Claude project; Clerks are its parallel subagents | — | Research: the forum, the server code, the Angband Borg, our own runs. Writes memos the Architect acts on. Never touches code. |
| **User** | the human | — | Sets direction, watches missions live (`tools/observe/watch.py`), messages the Navigator (`!`), asks the Architect why (`?`). |

The split is deliberate. The game is real-time: monsters act whether or not anyone is thinking. So
everything urgent lives in the fast, simple Pilot, and the slow, smart agents set strategy. Each
mission's problems become Pilot rules.

## What it can do now

- **Play a warrior from clvl 1 to 15**, at 0–550 ft so far, by stair-scumming, exploring and fighting.
  It recalls home, sells loot, buys supplies, and identifies unknown items or sells them by
  rule. Missions run 30–45 minutes.
- **Survive by rules**, many learned from deaths:
  - heal or escape according to the damage rate;
  - verify each escape and resend it if it didn't take effect;
  - a "group danger" estimate (worst-case melee of everything that can reach you);
  - a danger table for monsters up to level 40;
  - flee or recall when cornered;
  - keep away from monsters that drain stats or paralyse;
  - status cures only when they matter.
- **Know the game state reliably:**
  - a resist/ability grid read from the client;
  - a fresh inventory for every decision;
  - a state audit every 30 s (1 difference in 66 checks in its first mission);
  - a server resync on demand.
- **Learn item flavours** server-wide (`runs/flavours.json`) from selling, identifying and using.
- **Watch and talk:**
  - a colour terminal viewer with the map and a feed of the Pilot's actions, alerts and the
    Navigator's reasoning;
  - timestamped notes, live messages to the Navigator, and a "Navigator's view" panel;
  - review tools to replay notes against the decision log.

## Repository layout

| Path | What |
|---|---|
| `src/` | MAngband 1.5.3 server and client. Our client changes are in `src/client/c-tool.c` (tool mode: JSON events, `inven`/`map`/`status`/`flags`/`floor` queries, `redraw`, …) |
| `tools/pilot/` | the Pilot (`pilot.py`, `world.py`, `mover.py`, `glyphs.py`), `pilotctl.py` (the Navigator's interface), **`HANDBOOK.md`** (the Navigator's manual), `danger_table.csv` |
| `tools/observe/` | `watch.py` (live viewer), `notes.py` (notes beside the play), recording tools for human sessions |
| `tools/shopcat/` | client wrapper (`mang.py`), character creation (`newchar.py`), shop survey |
| `project/` | snapshot of the working state (`tools/snapshot.sh`): the handoff `next_steps.md` (**read first**), `operations.md`, game notes, the Advisor's memos and studies, the agent definitions, the Claude memories. See [`project/README.md`](../project/README.md) |

To run it: build with `make`, start a local server (port 28346), create a character with
`tools/shopcat/newchar.py`, start the Pilot with `tools/pilot/restart.sh NICK`, then drive it with
`tools/pilot/pilotctl.py`, or launch a Navigator agent. Details are in
`project/tree/operations.md`.

## Major TODOs

1. **Go deeper safely:** stage B of the progression plan (500–750 ft at clvl 12–15), then hold at
   1000 ft until Free Action and resists are found.
2. **Open Pilot issues:**
   - exploring sometimes stops early;
   - flavours identified by scroll aren't always learned;
   - the Navigator isn't woken by messages while it runs item commands.
3. **The Navigator's wishes:**
   - a movement trace in its reports;
   - run control;
   - protection from thieves;
   - sell-price quotes;
   - recognising vaults, pits and inner rooms from a partial map.
4. **Latency and models:**
   - measure alert → order times per mission;
   - test Haiku, Sonnet and Opus Navigators at different effort levels for competence against latency;
   - try **"Pinky and The Brain"**: a fast Navigator for the short-term loop that consults a slower
     one for hard and long-term calls.
5. **A complaints channel**, so agents can report missing tools and information instead of absorbing
   them.
6. **A live-server run**, only after asking the server's admins (the rules for bots are in
   `operations.md`).

The current state and the full TODO list are in `project/tree/next_steps.md` ("ARCHITECT
HANDOFF").

# Shared context (state survey)
MAngband 1.5.3 (real-time multiplayer Angband), source `/projectnb/jbrcs/mangband/github/src/`
(server `src/server/`, client `src/client/`, shared `src/common/`, packet ids `src/common/pack.h`).
Our bot: the **Pilot** (Python, `/projectnb/jbrcs/mangband/github/tools/pilot/`: pilot.py, world.py,
mover.py, glyphs.py, pilotctl.py; docs HANDBOOK.md) drives a headless client in **tool mode**
(`src/client/c-tool.c`, flag `-mtool`, events emitted as JSON lines). The **Navigator** is a Claude
subagent (`/projectnb/jbrcs/mangband/.claude/agents/navigator.md`) that talks to the Pilot through
`pilotctl.py` (status reports, goals, orders). Logs: `/projectnb/jbrcs/mangband/runs/pilot/<nick>/`
(decisions.jsonl, events.jsonl, navigator.md journal). Packet logs of a human playing:
`/projectnb/jbrcs/mangband/runs/observe/session{1,2,3}/pkt.jsonl` (see operations.md `--pktlog`).
**The problem:** the Pilot and Navigator are often wrong about game state — which item is in which
pack slot, which level/depth they're on, the character level (the level indicator is (max, current):
commit 72ec098), etc. We are mapping every piece of state end to end to fix this systematically.
Read only. Cite file:line. Use small Python scripts for logs. Output a dispatch (dispatch format) at
the path in your brief. Scratch: `/projectnb/jbrcs/mangband/Advisor/studies/2026-10-03-state/scratch/`.
State items to cover at least: position, depth/level (feet vs level, town/wilderness), HP/SP/max,
character level (current/max) and exp, stats (current/max, drained), AC, speed, blows, gold, food/
hunger, light (radius, fuel), status conditions (blind, confused, afraid, poisoned, cut, stun,
paralyzed, slow/fast, hero…), resists/abilities (FA, SI), inventory (letters, names, counts,
inscriptions, charges, weight), equipment slots, floor item under you, monsters in view (and their
health/asleep), the map (walls, doors, stairs, unknown), level feeling, recall pending, store contents,
messages, time/turn, party/other players.

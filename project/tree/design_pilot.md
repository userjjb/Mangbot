# Design: pilot + agent (light)

> **Status 2026-09-27:** the architecture and the reflex list below are current. The goals, orders
> and events lists further down aren't: `github/tools/pilot/HANDBOOK.md` is the reference for
> those (it is the Navigator's manual), and the handoff section in `next_steps.md` has the state.

Decided with the user 2026-09-26. The **pilot** (Python, long-running, owns the client) plays
second to second. The **agent** (Claude in chat now, later probably a dedicated subagent) sets
strategy through a small CLI. The agent must not need to know the code: it gets a player's handbook
(`github/tools/pilot/HANDBOOK.md`) and the CLI, nothing else. Game knowledge comes from
`notes_players.md` (docs digest + observed human play).

Roles were formalized 2026-09-26 (see `roles.md`): "agent" in this file is now the **Navigator**
(a subagent); whoever builds the pilot and the Navigator is the **Architect**.

```
mangclient -mtool  <--stdin/stdout JSON-->  pilot.py (daemon)  <--unix socket-->  pilotctl (CLI)
                                              |  events/decisions JSONL             ^
                                              v                                     |
                                            runs/pilot/<char>/*.jsonl  --Monitor--> agent
```

## Pilot responsibilities (reflexes, no waiting on the agent)
Priority loop in `Pilot.reflexes()`, first match wins, ~10 Hz (as of 2026-09-27):
1. **Dead/ghost** → stop, report. Shopping → nothing (any command leaves the store).
2. **Emergency** (HP < `flee_hp` with a monster within 7 or a recent hit) → `escape()`:
   - stairs underfoot → take them, then `Recover` (rest there) and resume the goal;
   - **out of combat** (nothing adjacent, no hit for 3 s, HP not falling with a monster in view)
     → rest, backing off over walked ground first if something is in view: never potions (user);
   - <30% HP → Word of Recall as a last resort (never a second one while one is pending);
   - adjacent → Phase Door (rate-limited unless HP is collapsing);
   - out of melee → walk to stairs within 20;
   - potions by numbers: the weakest that out-heals ~2 s of the measured damage rate
     (`World.damage_rate`, heal table `HEALS`); none can and death < 8 s → phase/recall instead;
   - three emergencies in 90 s → leave by stairs (`emergency_loop`).
3. **Arrival check** (≤6 s after stairs, on the staircase): a pack (`arrival_pack`) or a danger →
   take the stairs back.
4. **Danger in view** (within 12) → `Flee` to the nearest stairs. `danger_why()`: `danger_level`
   above ours, a unique above ours, a breather whose 2 max breaths ≥ HP, breathers whose breaths
   together ≥ HP, a paralyser without `free_action`, a summoner within 5 levels.
5. **Unseen attacker** ("It/Something <acts>", or HP falling with nothing in view and no poison,
   cut or hunger) → `Flee` (not while blind).
6. **Choke** (packs in the open → back into a corridor), **fear** (kite over walked ground; cure
   only in danger), **stationary monsters** (never stand next to NEVER_MOVE ones; the planner
   also avoids their neighbours), **repeat fearers** (walk/phase away).
7. **Light** (refuel), **hunger** (eat; none → recall).
8. **Adjacent monster** → stand still (server auto-retaliate); `fight_going_badly` below `think_hp`.
9. **Pickup** of what's underfoot (junk list aside; clears queued steps first).
10. **Rest** when hurt and alone. Then the **goal** step; with no goal, idle (recall after
    `idle_recall_s`).

Watchers every tick: stat drain/blows, breeders, recall cancelled, **no progress** (`stuck`: ≤10
squares in 2 min while not fighting → PKT_CLEAR, restart the move). The Mover sends PKT_CLEAR
whenever it replans off-path (a queued step otherwise runs every later step one behind).

Perception the pilot keeps (all from events):
- position;
- depth (`level` event);
- map (chars + attrs);
- monsters in view (name, position, from unique glyphs + monster list);
- floor items in view;
- **standing-on tile** (tracked: arrived by stairs and not moved = on the opposite staircase; a step
  onto a remembered tile = that tile);
- HP/SP/hunger/state indicators;
- inventory and equipment;
- recent messages.

## Goals (one at a time; the agent sets, the pilot executes, reports done/failed)
- `dive TARGET_FT [stop_on=interesting]`: stair-scum. Arrive; if a `>` is known and reachable, go
  and take it; otherwise `<` then `>`. **Stops and asks** when: an interesting item is in view; a
  vault; a lit room with items; a pillared room (a possible stairs room, per the user); a unique;
  the target is reached.
- `explore [room|level]`: frontier exploration (running corridors), until the room or level has no
  frontier, or a `>` is seen (configurable).
- `goto Y X` / `goto stairs|item|unknown`: move there.
- `pickup`, `drop ITEM`, `destroy ITEM`, `wear ITEM`, `takeoff ITEM`, `inscribe ITEM TEXT`,
  `use ITEM [target]` (quaff/read/eat/aim...), `fire` / `throw` at the nearest.
- `recall`: read Word of Recall and wait out the delay (safe-idle meanwhile).
- `shop STORE buy NAME×N, sell ITEM×N`: in town, walk to the store, trade, leave.
- `rest`, `wait SECS`.

## Orders (standing settings)
`flee_hp`, `think_hp`, `rest_to`, `danger` (monster names/patterns to avoid or flee), `pickup`
(all/none/list), `keep` (min rations, Phase Doors, CLW), `idle_recall_s`.

## Attention events (pilot → agent)
`goal_done`, `goal_failed(reason)`, `interesting(what, where)`, `danger_survived`, `pack_full`,
`low_supply(what)`, `level_up`, `unknown_item`, `new_monster(name)`, `idle`, `town`.
Each one comes with a **situation report**: character line, equipment, pack (letters, names,
inscriptions), a map crop (±12 rows, ±30 cols) with a legend, monsters and items in view,
standing-on, last ~15 messages, active goal and orders.

## CLI (pilotctl)
`status` (report), `goal ...`, `order key=value`, `stop` (cancel goal → safe idle), `log [n]`,
`wait-attention [timeout]` (blocks until the next attention event: the agent's "turn").

## What Phase 1 (C) must add, in priority order
1. `level` event on depth change.
2. `confirm yes` (answer the next confirm with yes; needed for selling).
3. Monster list / item list streams → `monlist` / `itemlist` events.
4. Unique glyphs for monster races, object kinds and flavours, plus a `visuals` export → names at
   positions. Spike first: which (char, attr) pairs survive the server's drawing.
5. Map attrs in `map` (and later push diffs if polling is too slow).
6. `option NAME yes|no` (e.g. `stack_force_costs`, per the user).
7. `target` (nearest) for missiles and wands later; low priority for a warrior.

## Test plan
- Each C piece: a scripted check on the local server (Dive01/02, throwaways).
- Pilot reflexes: scripted scenarios on throwaways at 50–250 ft (arrival into monsters, low HP,
  hunger).
- The dive goal: runs of N levels. Measure ft/min, deaths, attention events per minute.
- Unattended rule: agent silent → recall to town within `idle_recall_s` plus the recall delay.

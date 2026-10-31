# Pilot core: architecture, tick loop, perception, movement, logs, the report

The **Pilot** (`github/tools/pilot/pilot.py`, ~10.6k lines, plus `world.py`, `mover.py`, `glyphs.py`,
`structures.py`) is a Python daemon that plays one MAngband character second to second. It owns a tool-mode C
client (`mangclient -mtool`), builds a model of the game from the client's events and queries, and acts on it
about 20 times a second: reflexes first (survival), then the Navigator's standing reactions, the Pilot's own item
work, the current goal, and the trip plan. The Navigator (an LLM subagent) and the Architect steer it through a
Unix socket with `pilotctl`; the Pilot writes everything it sees and does to per-character logs in
`runs/pilot/<nick>/`. This file covers the skeleton those pieces hang on. The behaviour plugged into it is
described elsewhere:

- [pilot-combat.md](pilot-combat.md): the reflexes in detail (emergency/escape, danger flee, fights, status cures,
  choke, fear, safety watches).
- [pilot-items.md](pilot-items.md): item policy (pickup, loot, destroy, identify, upgrades, values, debts, review,
  flavours).
- [goals-and-plans.md](goals-and-plans.md): every Goal class, TripPlan (`plan trip`), TownKit (`plan town`),
  HouseBank, shops, the stash.
- [commands.md](commands.md): every `pilotctl` command.
- [gear-and-estimator.md](gear-and-estimator.md): geareval, loadout, the Advisor's estimator, shadow decisions.
- [client-server.md](client-server.md): the tool client (`mang.py`'s `MangClient`, the event/query protocol) and our
  server changes.
- [observe.md](observe.md): the viewer, scorecards and monitors that read the logs described here.

## Process model

```
mangclient -mtool  <--stdin/stdout JSON-->  pilot.py (daemon)  <--unix socket runs/pilot/<nick>/ctl.sock-->  pilotctl.py
   (child process,                           main thread: tick loop                                       (Navigator, Architect,
    reader thread -> World queue)            socket threads: Handler                                       viewer, harness)
                                                    |
                                                    v
                                     runs/pilot/<nick>/{decisions,events,state}.jsonl, levels/, *.json
```

- **Start**: `python3 pilot.py --nick Dive04 --port 28346 [--hpwarn N] [--live]`, normally through `restart.sh`.
  On import `pilot.py` reads the code's version once from `github/VERSION` (`VERSION`, "?" if missing; see
  [process.md](process.md)). `main()` writes the unique-glyph table (`visuals.txt`, see Glyphs below), starts
  `MangClient` (the C client as a child, with `--visuals` and `--hpwarn`; password `runs/private/<nick>.pass`, config
  `runs/private/<nick>.mangrc`), waits for it to log in, builds the `Pilot`, sets game options `avoid_other`,
  `stack_force_costs`, `disturb_near`, `disturb_panel`, logs the character's options, opens the control socket,
  notifies `started` (with `Pilot vX.Y.Z`) and loops `pilot.tick(); client.collect(0.05)` until `pilot.running` is
  false.
- **Options**: `--nick` (required), `--host` (localhost), `--port` (default 28346, the test server, since 2.43.0;
  the live port 18346 is refused without `--live`: F1), `--passfile`, `--config`, `--rundir` (default
  `runs/pilot/<nick lowercase>`), `--client`, `--libdir`, `--pktlog`, `--live` (live-server behaviour: keep
  mapping/detection devices instead of selling them as crutches), `--hpwarn N` (0-9, default 5: below N x 10% HP the
  server slows our time to 1/5; the Pilot's game clock follows).
- **Threads**: the client's reader thread only queues events (`World._on_event`) and writes `events.jsonl` /
  `state.jsonl`; all game logic runs on the main thread. The socket server (`Server`, a threading `UnixStreamServer`) runs a `Handler` thread per connection: it
  reads one JSON line, puts `(request, reply_queue)` on `Pilot.requests` and waits up to 30 s for the main thread's
  answer (`{"ok": false, "error": "pilot busy"}` on timeout). `wait-attention` is the exception: the handler thread
  blocks on `Pilot.att_cond` until an attention event arrives (or the timeout), then asks the main thread for a
  `status` report (the "wait report") and returns both.
- **Death**: on death the Pilot stays up as a ghost and keeps answering (`notify("dead")`); if the client exits
  after a death, `main()` keeps serving requests so the Navigator learns of it.
- **Exit**: `park` (log out at the next safe moment), `quit` (at once), SIGTERM (hotswap), or the client exiting.

### pilotctl transport (`pilotctl.py`)
One request per connection: `{"cmd", "args", "role"}` as a JSON line to `runs/pilot/<nick>/ctl.sock`, one JSON line
back. The nick comes from `--nick` or `$PILOT_NICK`, else the one Pilot whose socket answers (F2). `role` is `$PILOT_ROLE`
(default `navigator`; the Architect and harness set `architect` **with the token** `$PILOT_TOKEN`, from
`runs/private/architect.token`, made by the Pilot at startup; without it the claim is refused, F3): the Pilot refuses some commands to the Navigator (movement
verbs, item commands in the dungeon) and stamps who acted. `wait [SECS] [--brief]` sends `wait-attention` and
prints the events and the report (brief form on a quiet timeout). `rule ...` runs `tools/rulebook/rule.py` without a
Pilot. When the socket doesn't answer, `complain` appends straight to `runs/complaints.md`; other commands print
"Pilot not answering ... restarting". The commands themselves: [commands.md](commands.md).

## The tick loop (`Pilot.tick`)

Each tick runs, in this order (any `return` ends the tick):

1. **Perception**: `World.drain()` applies queued client events; `World.refresh()` polls the client (map every
   0.5 s or on a position change, status 0.3 s, pack every 10 s or when dirty, the ability grid every 10 s, the
   floor item every 1 s). `note_edge_cross` remembers the last town-edge crossing.
2. **Confusion**: `confusion_lock` (confused 8 s with a goal waiting or monsters adjacent: quaff a cure) and
   `confusion_window` (just cured among 3+ adjacent monsters: teleport now) can end the tick.
3. **Bookkeeping, every tick**: `supply_watch` (food/light minutes), the game clock's time factor (HP bubble model,
   fuel-measured speed-up; logged as `time_factor`), a redraw request for fuel readings, `note_town_stairs`,
   `wear_step` (queued wear), `verify_use` / `verify_effects` (did our read/quaff/command take effect; resend or
   report), `learn_flavours_tick`, `track_since` (the report's "since last" accumulator), HP minimum tracking.
4. **Floor items**: logs `itemlist` changes and `left_behind` on leaving a level; requests a full `redraw` after a
   level change or a loss (never in or near a store: a redraw closes the store server-side and once crashed the
   server); `found` news for special items picked up; `interesting_item` alerts for devices/jewellery seen (held
   2.5 s, longer if the loot step is fetching it); `lost` news for stolen/destroyed items.
5. **Periodic services**: `audit_tick` (every 30 s compare the model with fresh queries, log `audit`
   differences, resync), `structures_tick` (every 2 s: save the level map, scan for inner rooms/pits), avoid zones
   -> `World.avoid_zone`, the wilderness trail and `deepest.json`, the `mons` record (once a second with monsters in
   view), `belief_tick`, and the watchers: `watch_character` (drains, blows), `watch_weapons` (every 10 s),
   `watch_breeders`, `watch_drainers`, `watch_thieves`, `watch_kills`, `watch_band`, `watch_traps`,
   `watch_abilities`, `watch_progress` (no progress -> `clear` and `stuck`; also records the position history),
   `watch_perception` (server lists a monster the map decode misses), recall-cancelled news, `recall_memory`,
   `shadow_results`. Watchers only notify and log; they don't act (except `watch_progress`'s clear/abort).
6. **Requests**: `handle_requests()` answers everything queued from the socket (see below).
   If `running` went false (park/quit), stop.
7. **Test-server freeze**: if `tools/freeze.sh` has frozen time (`world.frozen()`), stop the mover, say so once,
   and act on nothing (requests are still answered).
8. **Acting**, first that acts wins:
   1. `reflexes()` -- survival rules ([pilot-combat.md](pilot-combat.md)). Order inside: dead/ghost;
      `busy_until` hold (after every command the Pilot waits ~0.4 s, blocking everything below); inside a store with
      a Shop goal do nothing; emergency (`escape`); group danger; speed/berserk/status cures; arrival into danger
      (stairs straight back); danger in view (walk away / flee); unseen attacker; choke (back into a corridor);
      summon traps; slowness; fear; stationary monsters; light; hunger; adjacent monster (stand and let
      auto-retaliate fight); pickup underfoot; auto-destroy; `engage_tick` (a worthwhile monster a few steps off);
      rest when hurt and alone.
   2. `park_tick` while parking.
   3. `rule_tick` -- the Navigator's `react` rules (leave on NAME, hunt NAME, kill thieves).
   4. `look_tick` -- never acts; asks the server's targeting which visible monsters are asleep (every 5 s at most).
   5. `policy_tick` -- the Pilot's item work at quiet moments (every 3 s at most, no monsters, HP >= 50%): restore a
      drained stat, fetch a unique's drop, pick up nearby gold, then `identify_step`, `upgrade_step`
      ([pilot-items.md](pilot-items.md)).
   6. `step_goal()` -- one step of the current goal; then `plan_tick(idle=False)` (the trip plan checks its
      conditions every 2 s).
   7. `plan_tick(idle=True)` -- no goal: the trip plan picks its next goal.
   8. `idle()` -- no goal, no plan: after `idle_recall_s` (600 s) without word from the Navigator in the dungeon,
      read Word of Recall (`idle_recall`).

`self.acting` is set around each layer (`pilot`, `plan`, `nav`, `arch`) and stamped as `by` on every `act` and
`goal` record, so the viewer can show who each action was for (`goal_origin`).

The module docstring at the top of `pilot.py` still lists the old 8-rule order; the list above is what runs.

### Goals: how they are driven
A goal is an object with `tick(pilot)` returning `None` (still working) or `(status, detail)` with status `done`
or `failed`, and `describe()`. Base class `Goal`; 22 subclasses (Wait, Goto, Explore, Dive, Search, Hunt, Recover,
Reprieve, BandLeave, WalkAway, Flee, Recall, Resurrect, Town, TownFarm, Shop, StashDeposit, StashFetch, HouseBank,
TownKit, RestGoal, QuietWait). `TripPlan` is not a goal: it sits in `Pilot.plan` and sets goals. See
[goals-and-plans.md](goals-and-plans.md).

- `Pilot.set_goal(goal)`: stops the mover, settles an overridden hunt's debt, tags the goal's `role`
  (navigator/architect) if set while handling a request, resets `goal_t` and the idle-recall flag, logs `goal`.
- `Pilot.step_goal()`: while blind or confused, Explore/Search/Dive just wait. Otherwise one `tick`; an exception
  in a goal becomes `("failed", "error: ...")` (a goal bug never kills the Pilot); a goal can also be aborted from
  outside by setting `goal.abort`. On end: if an emergency stashed the interrupted goal in `resume_after`, it is
  resumed (news `resumed`); a Hunt that lost a blinker becomes a `Reprieve`; a plan's goal (`by_plan`) is handed to
  `TripPlan.goal_ended`; otherwise `goal_done` / `goal_failed` is notified (as news if the goal is `quiet`); a failed
  flee/leave calls `flee_failed` (recall + phase with monsters close).
- Goal attributes the core reads: `quiet` (the Pilot's own small goals: news only), `by_plan`, `role`,
  `overridden` (a hunt the Navigator forced past a refusal: its cost is settled as a fight debt), `abort`, `sub`.

### Requests (`handle_requests`, `service_notes`)
Requests are answered on the main thread, once per tick, between the watchers and the acting layers, so a command
never races the game logic. Each non-viewer request updates `last_agent` (the idle-recall clock) and logs
`nav_cmd` (command, args, role, which report it answered and how old it was). `do_request` executes it (the
command catalogue is [commands.md](commands.md)); an exception becomes `{"ok": false, "error": ...}`; unanswered
user messages ride on every answer. `service_notes()` lets a long-running command (search, chest work) pull the
user's `note` requests out of the queue so they aren't stuck behind it.

### Attention and news (`notify`)
`notify(what, detail, news=False)` is the single way the Pilot tells the Navigator something. Every call logs an
`attention` record (with a map crop; emergencies also carry a 21x21 map and the monster list, and a shadow
decision from the estimator). Then either:
- **news** (`news=True`, kinds in `NEWS`, or -- while a trip plan runs -- kinds in `PLAN_QUIET` that the plan handles
  itself): kept in `Pilot.news` (last 20) and shown in the next report; doesn't wake the Navigator.
- **attention**: appended to `Pilot.attention` and wakes `wait-attention`.
A notification for an action that `cmd` held back (not actually sent) is dropped.

### Commands to the game (`cmd`)
`cmd(line, why, hold=0.4)` is how the Pilot (and the Navigator's item commands) send a client command. It refuses
a second read/quaff while the last is unconfirmed, and any item command until the pack has refreshed since the
last one (pack letters shift when a stack runs out). It sets `busy_until`, logs `act` (with `cmd`, `why`, `by`),
logs escapes, registers expected effects (`EFFECTS`: equip/pack/level signals checked by `verify_effects`) and, for
the Pilot's own reads/quaffs of escapes and cures (`USE_VERIFY`), a `pending_use` that `verify_use` confirms from
the server's "You have N ..." message or resends (twice at most; a Word of Recall or Teleport is never resent:
after 8 s without an answer it gives up). The mover sends walk/run/pathfind/clear commands
directly through the client, not through `cmd`.

## The world model (`world.py`)

### The game clock
The server runs each player's time at a factor: 1/5 in the low-HP "bubble" (below `hitpoint_warn` x 10%), up to
~5-10x while running or resting with no awake monster in line of sight, 1 otherwise. `world.py` keeps a **game
clock** `gnow()` that follows that factor: the model sets 0.2 in the bubble, else 1; while resting/running with
nothing in view (`set_fast_ok`), the factor is measured from the worn light's fuel (one turn of fuel per game tick,
`TICK_S` = 0.625 s at factor 1; the Pilot requests free redraws to read it). Every Pilot timer that means game time
(cooldowns, holds, damage per second, "out of view for N s") uses `gnow()`; timers that mean the network use
`wall_since(t)`; `waited(t, s)` needs both; `ghold(s)` turns a wall span into a game-clock deadline. While the test
server is frozen (the file `testserver/FREEZE`, or `$MANGBAND_FREEZE_FILE`) the clock stops. Logs and displayed
times stay on the wall clock (`wall_of`, `_lt`).

### `World` state
Built from client events (`drain`) and polled queries (`refresh`):

| Field | What |
|---|---|
| `pos`, `pos_t`, `arrive_pos`, `walked` | position, when it last changed, where we entered the level, squares stood on |
| `depth`, `depth_ft`, `level_t`, `in_dungeon` | depth (50 ft/level), arrival time on this level (the level's identity everywhere), dungeon vs town/wilderness (`_level_kind`: the depth byte wraps in far wilderness, so judged by how we got here) |
| `arrived_by`, `standing_on`, `last_stairs_cmd` | how we came (`>`/`<`, else `other`: recall, trapdoor, login); the tile under `@` (the map never shows it: after a stair trip we stand on the opposite stair; after a step, whatever memory had there) |
| `rows`, `attrs` | the latest full-level map (chars, colours) from the `map` query |
| `memory` | `(y, x) -> char` remembered terrain and floor objects for this level (cleared on level change); monsters are not stored, and a square seen only with a (non-wall-passing) monster on it is remembered as floor |
| `monsters` | `[(y, x, Race)]` decoded from the map by unique glyphs |
| `still_seen` | stationary (NEVER_MOVE) monsters seen this level, remembered out of view until killed |
| `monlist`, `listed_only()` | the server's monster list; races it names that the map decode doesn't place |
| `itemlist`, `floor` | the server's item list lines; the item underfoot |
| `ind` | status indicators (HP, gold, exp, stats, speed, hunger, flags, track bar ...); `hp`, `hp_frac`, `clvl`, `hunger`, `resting`, `flag(name)` |
| `inven`, `items(tval=, name=, equip=)`, `tagged(cmd, digit)` | pack and equipment |
| `flags`, `has(flag)` | the character sheet's resist/ability grid (re-read on equipment change) |
| `messages`, `recent(secs)` | last 300 messages with game-clock times |
| `last_hit_t`, `hits_taken`, `fight_t`, `explained_t`, `unseen`, `heard`, `hp_hist`, `damage_rate()` | combat signals parsed from messages (attacks on us incl. ranged, our hits, non-monster damage, unseen attackers) |
| `losses` | stolen/destroyed/eaten item messages (resync + news) |
| `recall_pending`, `recalled`, `recall_cancelled` | Word of Recall state from its messages |
| `store`, `store_t`, `last_confirm` | the open store listing; the last yes/no prompt |
| `avoid_zone`, `avoid_inside` | squares the planner won't enter (set by the Pilot each tick from the Navigator's avoid zones and avoided names) |
| `bump_walls` | walls learned by bumping (forgettable, see Mover) |
| `daytime`, `is_day()`, `targets` | town day/night; the server targeting's answers (`look`) |
| `need_redraw`, `inven_dirty` | resync flags |

### The Pilot's own beliefs (`belief_tick`, in `pilot.py`)
- `mons_mem`: each monster race seen on this level, where it was nearest, how many, danger/unique; feeds "Out of
  view (this level, last 2 min)" in the report.
- `hits`: our hits per (level, monster) since it was last slain; feeds "Fight so far" (estimated damage dealt vs
  the monster's HP from the rulebook).
- From messages: gold from sales (`gold_sold`), disenchantment and theft news (`gold_stolen`), kills.
- `track_gains`: gold found in the dungeon, XP gained, XP and minutes per depth (stored in `rates.json`
  under `depth`), the per-level XP base, a 15-s gain history (`gain_hist`), and every 15 s `save_mission` and
  `food_watch`.

### Rates (`rate_state`, `rate_tick`, `xp_per_gold`)
A rolling XP-per-gold exchange rate: every 10 minutes (`RATE_BUCKET_S`) the XP gained and gold earned (found +
sold) are closed into a bucket; the last 30 buckets with any gain are kept in `rates.json`. `xp_per_gold()` sums
the buckets plus a seed (m35-m42: 14190 XP per 34694 gold) weighted by the window's unfilled share, clamped to
0.1-3.0. Used by the gear estimator ([gear-and-estimator.md](gear-and-estimator.md)) and shown by `gear`.

### Missions (`save_mission`, `load_mission`)
`pilotctl mission start LABEL navigator=MODEL ...` sets `mission_label` and a base (time, XP, gold, gold found),
logs `mission_start`, and records it in `runs/missions.json` (read by the scorecard); both carry `version` (the
Pilot's `VERSION`). `save_mission` writes
`mission.json` every 15 s so a restart or hotswap carries the mission on (the report's "this mission" rates);
`load_mission` ignores a file older than 30 minutes. `mission end` logs `mission_end`, stamps the end in
`runs/missions.json` and removes `mission.json`.

## Glyph and monster knowledge (`glyphs.py`)

- **Unique glyphs**: `glyphs.assign()` gives every monster race a (char, colour) pair no other race has: the usual
  letter, a colour unique among races with that letter; races whose letter is also a terrain/object glyph only get
  colours 16-63 (terrain uses 1-15), so a monster can't read as terrain; overflow races borrow an unused char.
  `write_visuals()` writes `runs/pilot/<nick>/visuals.txt` (`r IDX CHARCODE ATTR`) at each start; the client
  uploads it with `--visuals` and the server draws the map with it. With `avoid_other` on, the server draws every
  monster that way (mimics and hallucination still lie). `Glyphs.monsters(rows, attrs)` decodes the map into
  `[(y, x, Race)]`; `check_monlist` flags names the server lists that our table would draw differently.
- **Race data** (`load_races`): from `lib/edit/monster.txt` (N/G/I/W/F/S/B lines): name, char, colour, level,
  speed, HP dice, flags, spells and frequency, blows. Derived properties: `repeat_fearer`, `summoner`,
  `paralyser`, `per_turn`, `drains`/`drained_stats`, `worst_melee`, `max_hp`, `max_breath` (breath table `BREATHS`).
- **Ratings** merged onto each race (`load_rulebook`): from **`tools/rulebook/monsters.csv`** (the Advisor's table,
  synced into the rulebook; all races): `rating` -> `Race.danger` (0 trivial .. 5 leave on sight), `veto_reason`,
  `speed_x` (actions per player turn), `melee_max`, `drain_blows`. Rows whose idx/name don't match this
  `monster.txt` are ignored. The file must exist: a missing one is a startup error (the old fallback to
  `pilot/danger_table.csv`, `load_danger`, went in session 10, C9). `pilot.py` also reads `monsters.csv` directly for the
  fight estimate (`fight_rows`). How these ratings drive danger decisions (`danger_why`, `worst_3turns`): see
  [pilot-combat.md](pilot-combat.md).

## Pathing and movement (`mover.py`)

`mover.plan(world, goals, avoid, ...)` is a Dijkstra search over `World.memory` from `pos` to the nearest goal
square (8 directions, a hair more for diagonals so straight paths win):
- **Dungeon**: unknown squares are not walkable (the dungeon is mostly rock) unless the job allows crossing unknown
  at extra cost (`unknown_cost`, used by escapes and gotos as a fallback); walls/veins/shop entrances are not;
  closed doors (cost 3, opened by bumping), rubble (cost 15, dug), traps (25; avoided entirely when another route
  exists) are. **Surface**: unknown is open (at night the floor isn't drawn); trees/fences block.
- Monsters cost +40; squares next to stationary monsters +40; squares next to a stationary **drainer** and the
  Navigator's avoid zones are impassable unless they are the goal (if we are inside a zone, its squares only cost
  more so we can get out).

`Mover` runs one movement job without ever blocking, so reflexes keep running. `go(goals, avoid, unknown)` plans
(retrying after forgetting bump-learned walls, then through unknown if allowed); `tick()` returns `moving`,
`arrived`, `stuck` or `idle`, and is called by goals. Each tick it:
- tracks progress along the path; off the path (pushed, phased, a run overshot) it sends `clear` (drops steps queued
  on the server, so later steps don't run one behind) and replans; at most 8 replans per job (`max_replans`);
- on "blocking your way" marks the square as wall/door/rubble and replans (or digs rubble with `T`, up to 40 tries);
- 1.5 s without progress: avoid that square and replan;
- moves as fast as the server allows: **stretch runs** along straight stretches of 3+ squares (stopped one tile
  early with `walk 5`); **server pathfind** (`pathfind Y X`, 4-20 steps ahead) when no monster is in view and no
  stationary drainer within 12 -- the server counts it as running, so time runs ~5x; **free runs** in corridors
  (the server follows the bends; stopped when moving away from the goal two steps running, or on a loop); else
  `walk DIR`, at most 2 steps queued ahead (`AHEAD`). No run with a monster within 5 (2 on the surface); free runs
  and pathfind only in the dungeon; surface runs keep 3 squares from the map edge, never onto a shop door, and run
  at most 10 squares over unknown ground.
- `_clear()` never empties the server queue while the Pilot has a read/quaff waiting there (`hold_clear_until`).
- `stop()`, `requeue()` (drop queued steps so a command sent now runs first), `in_corridor()`.

Movement is logged as `move` records (plan results, runs). Exploration's frontier (known open squares next to
unknown: `Pilot.frontier`) and stair finding live in the goals ([goals-and-plans.md](goals-and-plans.md)).

## Structures (`structures.py`, `Pilot.structures_tick`)

Inner rooms, monster pits and nests are generated as the same "double room" (11 x 25, a 1-wide ring corridor
around a 5 x 19 inner room with one secret door) centred on a fixed grid (Y = 5, 16, ... 60; X = 16, 49, ... 181
with `dungeon_align`, which our client always sets). `structures.scan(memory)` tests only those centres:
`match()` counts ring floor and inner wall consistent with the shape (two sides needed, three or two parallel =
`sure`) and rejects on contradictions. `classify()` names it from the monsters around and whether it came into view
lit: `orc pit` / `monster pit (c)` (4+ of one letter, dark), `nest` (3+ stationary inside), `large room` (lit),
`inner room` (dark, unknown). `door_spots()` gives the 4 possible door squares and the ring square to search from.

Every 2 s `structures_tick` scans the remembered map; a new pit/nest/inner room gets three avoid zones (radius 6)
over it and its ring and a `structure` notice (attention for a pit or nest, news for an inner room or a large
room). A pit stays a pit after its monsters leave. The report lists this level's structures. (Vaults are not
recognised here; the arrival feeling -- "special" at <= 850 ft means a pit, nest or vault -- is logged as
`arrival_feeling` and used by the trip plan.)

## Per-character state: `runs/pilot/<nick>/`

All paths relative to `runs/pilot/<nick lowercase>/` unless noted. "Pilot" = `pilot.py`.

| File | Written by | Read by | Format / contents |
|---|---|---|---|
| `decisions.jsonl` | Pilot `log()` (append, line-buffered) | viewer, scorecard, notes, set-piece harness, unit tests, damage_mix, the Architect/Advisor | one JSON object per line: `t` (wall epoch), `kind`, `depth`, `pos`, `hp` + kind fields. Kinds below |
| `events.jsonl` | `main()`: every client event except query replies | scorecard, damage_mix, set-piece harness | the client's event JSON + `epoch`; its `t` restarts at 0 with each Pilot process (a `pilot_start` line marks it) |
| `state.jsonl` | `main()` `log_state`, thinned | scorecard, set-piece harness (replays) | `{"ev": "status"\|"inven"\|"map", "epoch", ...}`: status (y, x, indicators) every 2 s when changed; the pack whenever it changes; the map's changed rows every 10 s |
| `levels/YYYYMMDD-HHMMSS-<ft>ft.txt` | `save_level_map` when we leave a dungeon level | the Architect/Advisor (checking the structure recogniser, post-mortems) | header `# <ft> ft, <start> - <end>; structures: ...; feeling: ...`, then the remembered map, 66 rows |
| `orders.json` | `order` command | Pilot at start (merged over `DEFAULT_ORDERS`) | standing orders `{key: value}` (only known keys are kept) |
| `rates.json` | `rate_tick`, `track_gains` | Pilot (`xp_per_gold`, `prep`) | `{"buckets": [[epoch, xp, gold], ...30], "depth": {ft: [xp, seconds]}}` |
| `mission.json` | `save_mission` (every 15 s while a mission runs) | `load_mission` at start (if < 30 min old) | `{label, age, exp, gold, found}` |
| `plan.json` | `TripPlan.save` | `TripPlan.load` at start (a restart mid-trip resumes); removed when the plan ends | the trip plan and this level's state |
| `recall.json` | `recall_memory` | the same, at start | `{pending, depth, t}`: a pending Word of Recall survives a restart |
| `rules.json` | `react` command | `rule_tick` | the Navigator's executable reactions `[{kind, arg}]` |
| `standing.json` | `standing` command | report ("Standing:") | standing instructions `[{text, by}]` (shown, not executed) |
| `keep.json` | `keep` command | item policy | item names the policy must not sell/destroy |
| `navigator_debt.json` | `add_debt`, fight debts | `debt`, review, reports | `{"entries": [...]}`: gold the Navigator's overrides cost ([pilot-items.md](pilot-items.md)) |
| `review.json` | item review | review, report ("Review") | items awaiting a sell/keep/wear decision and town-visit count |
| `stash.json`, `house.json` | stash / HouseBank | the same, `house` | items stored in town ([goals-and-plans.md](goals-and-plans.md)) |
| `stores.json` | `note_store` | town kit routing, prices | each store's owner and prices seen |
| `deepest.json` | tick (new deepest level) | Pilot | `{"ft": N}` |
| `uniques_killed.json` | `watch_kills` | gear estimator, hunts | uniques this character has killed |
| `damage_mix.json` | `observe/damage_mix.py` (run by `wrap.sh`) | `geareval` (EHP) | share of HP lost by damage type |
| `asks.jsonl` | `ask` command | Architect's inbox | the Navigator's questions to the Architect (rate-limited: 1 per 5 min, 4 per hour; the file `ask_unlimited` lifts it) |
| `commentary.jsonl` | `note` (the user's comments via the viewer) | `observe/notes.py` | the user's notes with the moment's context |
| `navigator.md` | `journal` command | humans | the Navigator's journal lines stamped with time, depth, HP |
| `world_dump.json` | `dump` command | the Architect | a dump of the World for debugging |
| `ctl.sock` | `main()` | pilotctl | the control socket (recreated at start) |
| `visuals.txt` | `main()` | the client (`--visuals`) | the unique-glyph table |
| `pilot.log` | the scripts' `nohup` redirect | humans | the Pilot's stderr (`say`): login, socket, stop, tracebacks |
| `reports/`, `scorecards/` | the Architect (after `observe/wrap.sh`), `observe/scorecard.py` | humans | mission reports and scorecards ([observe.md](observe.md)) |

Shared, outside the character directory: `runs/pilot/town.json` (the town's `>` position), `runs/flavours.json`
(the server-wide flavour table, [pilot-items.md](pilot-items.md)), `runs/missions.json` (mission list),
`runs/complaints.md` (`complain`).

### `decisions.jsonl` kinds
| Kind | Meaning |
|---|---|
| `act` | a command sent (`cmd`, `why`, `by`) |
| `goal` | goal set / resumed (`goal`, `by`, `why`) |
| `attention` | every `notify` (`what`, `detail`, `source`, crop; emergencies add `map21`, `map_at`, `mons`, `shadow`) |
| `note` | free-form Pilot notes (held commands, failures, explanations) |
| `move` | mover plans and runs |
| `mons` | monsters in view once a second (+ tracked monster's health bar, what we're hitting) |
| `itemlist`, `left_behind` | floor items in view; items left on a level we left |
| `arrival_feeling`, `trapdoor` | level feeling on arrival; trapdoor falls |
| `time_factor` | the game clock's factor changes / fuel measurements |
| `audit`, `audit_check` | state-audit differences; periodic snapshot (exp, stats, ...) |
| `perception_gap` | the server listed a monster the decode missed |
| `escape` | escape attempts and outcomes (for the post-mortems) |
| `estimator`, `gear_eval` | shadow-estimator answers; gear evaluations ([gear-and-estimator.md](gear-and-estimator.md)) |
| `looks` | the server targeting's sleep/wound answers |
| `report` | a report handed to the Navigator (`id`, `report_kind` status/full/wait, `chars`) |
| `nav_cmd` | a request received (cmd, args, role, `after_report`, `report_age`) |
| `order_refused`, `order_held` | a Navigator command refused / held as stale |
| `nav_say`, `nav_journal`, `nav_ask`, `nav_complaint`, `arch_answer`, `user_note` | conversation records |
| `navigator_debt`, `navigator_fight_debt`, `hunt_override`, `hunt_override_end` | overrides and their cost |
| `plan_start`, `plan_end`, `plan_resumed` | trip/town plans |
| `mission_start`, `mission_end` | mission markers |
| `options` | start-up options (`hpwarn`, `live`, the game options) |
| `bank`, `sale`, `town_kit` | town goals' records ([goals-and-plans.md](goals-and-plans.md)) |

## The status report

Three forms, all built on the main thread:
- **`status`** -> `compact(snapshot=True)`: the compact report.
- **wait report** (after `wait-attention`) -> `compact(news_since=<last wait>)`: the same, news since the last wait,
  and only the changes in the bottom section.
- **`status full`** -> `report()`: the long form (full pack and equipment, a 23 x 67 map, 12 recent messages,
  item squares, all orders); its first line ends with `| now HH:MM:SS | Pilot vX.Y.Z · rN`.

Every report is numbered (`numbered()`: ` · rN` on the first line, a `report` log record), so later commands can be
checked for staleness against what the Navigator saw.

`compact()` lines, in order:
1. Header: `Name L29 HP 358/358 · 750 ft · 12345g (+N banked) · max 800ft · 14:02:11 · goal: dive 800` (+ `TIME
   FROZEN`, + an escape-landing marker from `escape_line`).
2. `Plan:` the trip plan; `ARCHITECT ANSWER(S)`; `USER MESSAGE(S) NOT YET ANSWERED`.
3. Stats (with drain arrows), hunger, conditions, resting, speed, the wielded weapon's blows and damage.
4. Supplies (`supply_lines`: cures, escapes, food, light, devices).
5. `Here:` what we stand on, how we arrived, the 3 nearest stairs with distances.
6. `Monsters:` each race in view: count, level, UNIQUE, distance range, asleep, `DANGER: why`.
7. `Items:` the server's item list (known junk hidden) and the nearest item squares (`$` grouped).
8. `Map` (outside town: dungeon and wilderness): a square crop of radius 9 with row numbers.
9. `Structures:` this level's (with door found / searched).
10. Belief lines (`belief_lines`): `Out of view` (recent monsters by threat), `Fight so far`, `Rates` (HP lost in the
    last 10 s, XP and gold found in 10 min, this level, this trip, this mission), `Counts` (drains, traps, searches,
    emergencies and Phase Doors in 90 s), `Standing` (keep, avoid, standing instructions, react rules, nopickup),
    `Review` (items awaiting a decision and when they'll be sold).
11. `News:` the last 8 news items (since the last wait, or the last 10 minutes).
12. `Msgs:` the last 6 messages of the last 10 s, outside town when hurt or with monsters in view.
13. `Since last (...)`: lowest HP, monsters seen (most at once), uniques; reset by wait reports.
14. `Progress:` time since the last XP gain, on this level, under this goal.
15. `compact_changes`: Equip, Pack (not consumables), Weapons, Abilities, Gear (empty slots / better items),
    Orders changed, Audit differences -- all of them on `status` and the first report, only what changed (`+`/`-`
    per item) on a wait report.

`pilotctl wait --brief` (and quiet timeouts) keep only the first two lines and the lines starting with `USER
MESSAGE`, `Here:`, `Monsters:`, `News:`, `Since last (`, `Progress:`, `Cures` (and the long form's equivalents).
`since_lines` and `movement_line` (a point every ~8 s of the last minute's path) are used by the long form.

## Updating a running Pilot

- **`restart.sh NICK [PORT=28346]`** (the normal way): if a Pilot runs, `pilotctl park` (drop the goal unless it is a
  Recall; log out when nothing is within 15 squares, HP >= 70%, no store, no stairs just taken, no recall
  pending -- or after 5 minutes regardless; on logging out the Pilot sends a `parked` attention, then `clear`;
  restart.sh itself sends no `clear`), waits up to 330 s for the
  process to exit, starts `pilot.py` with `nohup` (extra options from `$PILOT_ARGS`, e.g. `--hpwarn 0`), appends to
  `pilot.log`, and prints the first status lines. The character logs out and back in, so the level is regenerated
  unless the server kept it.
- **`hotswap.sh NICK [PORT]`** (test server only): freezes time (`tools/freeze.sh on`), SIGTERMs the Pilot (SIGKILL
  after 10 s), starts the new one, waits until `status` answers, then thaws (unless it was frozen before). The
  character stays in the world because an orphaned player is freed only after 15 s of game ticks, which are
  stopped. The trip plan resumes from `plan.json`, the mission from `mission.json`, a pending recall from
  `recall.json`; the Pilot's in-memory state (level map memory, refused stairs, fight counters, news) starts over.
- What survives any restart: everything in the files table above. What doesn't: the World's map memory (a new
  level_t even on the same level), `mons_mem`, hits, news and attention queues, avoid zones, structures found,
  searched squares.
- The Navigator sees a restart as "Pilot not answering" from pilotctl, then a `started` news event (naming the Pilot's version); it must re-issue
  its goal (a plan resumes by itself).

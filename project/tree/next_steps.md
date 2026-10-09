# MAngband tool client — state of play and next steps

Handoff for the next agent (written 2026-09-25). The shop-cataloging goal is
**done and working on the live server**. The next goals are better movement and,
eventually, autonomous dungeon play. This file lists what exists, what was
learned the hard way, and a suggested plan.

## Read these first

| File | Why |
|---|---|
| `operations.md` (this dir) | **Environment, test server, characters (credentials in runs/private/), tool-mode client facts, verified server behaviour, live server, user decisions, agent-tooling gotchas.** |
| `roles.md` (this dir) | **Roles (2026-09-26): Pilot, Navigator, Architect, Advisor.** Which role you are in and what it may touch. "Agent" below means the Navigator. |
| `notes_merge.md` (this dir) | Original protocol/codebase survey: packet framing, login, store packets, custom commands, file map. Still accurate except where this file corrects it. |
| `notes_players.md` (this dir) | Digest of the mangband.org player docs (macros, inscriptions, `*t` targeting, auto-retaliate, survival lore) and how they change the plan. Raw pages in `runs/docs/`. |
| `github/tools/shopcat/README.md` | How the Python tool works, options, output format, limitations. |
| `github/src/client/c-tool.c` | The headless client's command/event interface (header comment lists every command and event). |
| `github/tools/shopcat/{mang,nav,wild,shopcat}.py` | Client wrapper, movement, wilderness travel, cataloger/upkeep. |
| `git -C github log` | 23 commits; every commit message explains *why* (the server quirks behind each change). |
| Claude memory: `~/.claude/projects/-projectnb-jbrcs-mangband/memory/*.md` | Test env (server, characters, passwords, quirks), verified server behaviour, live-server facts. |
| `runs/live-tour.jsonl`, `runs/live-tour-events.jsonl` | A real 2-hour live session: every event the client emitted. Useful for replay/offline testing of new logic. |

## What exists

**C side (`github/src/client/`, all additive, only active with `-mtool`):**
- `main-tool.c`: headless 212×70 term, so the dungeon stream subscribes at the full
  198×66 level. The server then pins the panel at (0,0): **map coordinates are
  absolute** and equal `pos` coordinates.
- `c-tool.c`: `tool_loop()` replaces `Game_loop`. JSON events on stdout, commands on stdin.
  Popups become events, confirms are always declined, and any prompt that reads a key
  gets ESC (plus a `blocked_input` event), so the client never blocks.
- `c-pktlog.c`: `--pktlog FILE` logs every packet (JSON lines, hex + text), for protocol work.
- Login without prompts: `--noprompt --passfile F` (the MD5 hash is identical to an interactive login).
- The house-door glyph is overridden to `0` via the uploaded visual tables (`tool_setup_visuals`).
  **The same mechanism can give every monster race / object kind a unique glyph** (see below).
- Position: the server's `MCURSOR_PLAYER` cursor packet (sent as vis, **y, x**) → `pos` events.

**Python side (`github/tools/shopcat/`):** `mang.MangClient` (subprocess, event queue,
`query()`, trail of positions, attack counter, arena flag, `meta_servers()`), `nav`
(Dijkstra on the glyph map, run/walk execution), `wild` (world coordinates, tour
planning, edge crossing, sweep exploration), `shopcat.Cataloger` (door visits,
upkeep: eat / light / refill / fight / rest / restock / arena escape, tour logic).

## Hard-won facts (not all written down elsewhere)

Protocol and client:
- An unknown packet or an unsubscribed stream disconnects you. Keep every handler.
- Keepalive: the C loop handles it. **Never block the C loop**; the Python side may
  block freely, because the client keeps pumping the network.
- Custom commands are server-defined (54 on 1.5.3). **Look them up by key** via
  `commands` (`custom KEY ...`). Useful keys: `<` / `>` stairs (SCHEME_EMPTY), `.` run
  (DIR), `R` rest toggle, `q` quaff (ITEM), `r` read (ITEM[+DIR]), `a` aim wand, `z` zap
  rod, `f` fire, `v` throw, `m` cast (ITEM_DIR_SMALL), `E` eat, `F` refuel, `w` wield,
  `t` take off, `d` drop (ITEM, value=qty), `g` pick up, `{` inscribe (ITEM, entry=text),
  `$` drop gold, `o` open, `+` alter, `c` close, `h` buy/sell house. Store: `p` purchase
  (store, item=slot, value=qty, entry=price), `l` examine. Items are inventory indices
  (a=0); equipment starts at `INVEN_WIELD` (index 24 in `inven` output).
- Indicators (`status` → `ind`): `hp [cur,max]`, `sp`, `hunger` (0-1 weak, 2 hungry,
  3 normal, 4 full, 5 gorged), `depth` (0 town, <0 wilderness, >0 dungeon), `gold`,
  `state [paralyzed, searching, resting]`, `speed`, `stat0..5`, `armor`, `cut`, `stun`,
  `blind`, `confused`, `afraid`, `poisoned`, `level`, `exp`, `study`, ...
- `inven` right after `ready` can come back empty: data arrives about 1 s later (`wait_ready` settles).
- Only an error event with the same `cmd` should fail a query (late errors happen).
- The client's stderr must be drained, or the client blocks.

Server behaviour that matters for movement and play:
- **Walking**: about 0.5 s per step (walking resets built-up energy). A walk request is
  **dropped if more than 2 are already queued**. A walk that arrives *during a run or rest
  stops it* and is itself swallowed (`recv_walk`). This is the only way to cancel a run or a rest.
- **Running** (`custom . dir=D`, i.e. shift+direction): about 0.1 s per tile, but the server's
  run logic stops whenever the surroundings change (openings, monsters, objects), so
  in practice runs are short. The tool averages ~0.25 s per tile by running straight stretches ≥5.
- **Server pathfind** (`pathfind Y X`): fast (run speed), but searches only 25 tiles around
  the player and **treats never-seen grids as open, including the row/column just past the
  level edge**, so it can walk you off the level. It also bumps unseen walls. That's why the tool
  plans its own path. In the dungeon there are no level edges to walk off, so server pathfind
  may be acceptable there (it can't leave the level); verify before relying on it.
- A command sent just as a run/pathfind ends is sometimes ignored: verify each move by `pos`.
- Map: only remembered grids (`CAVE_MARK`) plus currently visible ones are drawn; unseen is `' '`.
  The level border draws `' '` too. By night the wilderness floor isn't drawn, but lit rooms
  (houses) are. Trees `*` and logs `=` block movement; `#` walls; `+` closed doors; `'` open.
  **The map export currently has characters only**: the attr (colour) is in
  `stream_cave[].a` but not exported (see plan).
- Monsters appear as letters on the map (other players `@`). Attacks on you show up as messages
  ("The Crow bites you."); `mang.RE_ATTACKED` counts them. Walking into a monster attacks it.
- Food: digestion is `(extract_energy[speed]/100)*2` (+30 with REGEN) per tick. At normal speed
  that is **0 unless the race has REGEN** (Half-Troll: a ration every ~100 s outside town).
  Nobody digests in town. Faster speed means more food.
- Arenas ("ancient fighting pit") in the wilderness: bumping the wall teleports you in, and
  bumping it again from inside (alone) lets you out. The test server's `MAX_ARENAS` overflow bug
  (`wilderness.c:1171`) crashes it on generating an 11th arena (entering 2E); live servers are fine.
- Death is permanent (you become a ghost). The tool stops (exit 2) on ghost, falling HP while
  resting, starvation, or being stuck. **Use dedicated throwaway characters for dungeon work.**
- Ghost DMs (Gandalf on the test server) can't use NPC shops and behave oddly crossing levels.

Environment and workflow:
- Python: `module load python3/3.12.4` (the OS python3 is 3.6).
- Build: `cd github && make` (already configured GCU-only; `./autogen.sh -n` if regenerating).
- Test server: `cd testserver && ../github/mangband` (run it from that directory; the `-c` flag is
  broken). Port 28346. Characters/passwords are in memory and `runs/private/`. Stop with SIGTERM.
  To debug a server crash: `gdb -batch -ex run -ex bt ... --args ../github/mangband`
  (core dumps are disabled on this cluster).
- Live: `shopcat.py --list-servers`; mangband.org:18346 (1.5.3). Tool character **Happy**
  (password "a"; files in `runs/private/`). The operator allows automated clients.
- The client rewrites its config file on exit: one `--config` per concurrent client, and never let it
  rewrite `github/.mangrc` (tracked).
- Session scratchpads get wiped: keep run files in `runs/`.
- Agent-tooling gotchas: `pkill -f PATTERN` / `pgrep -f PATTERN` also match the shell running
  them, so anchor patterns (`'^python3 -u shopcat.py'`). Long runs: start with `nohup … &` and
  watch with a Monitor on the output file; monitors expire after 30 min and need re-arming.

## Known gaps / small unfinished items

- `interactive` (server-side remote browser) events were never exercised.
- Look/target mode (`PKT_LOOK`, `PKT_CURSOR` targeting) is not implemented in tool mode. Spells and
  wands that need a target currently only take a direction.
- Confirm prompts are always declined; there is no way to answer yes (needed e.g. to sell).
- Open house doors (`'`) can't be told from ordinary open doors, so open shops are missed.
- The non-autotools build files (VS/Xcode/Android/Borland) don't include the new C sources.

## Suggested plan: better movement, then an autonomous dungeon player

Keep the split that has worked: **C stays a thin, non-blocking I/O layer; all decisions in
Python.** Develop on the test server with throwaway characters; move to live only for
validation.

### Phase 0: throwaway character factory — DONE (2026-09-25)
- Client `--birth RACE:CLASS:SEX:STATS` (tool mode): creates the character without the birth
  menus, and **replaces a dead one** of the same name. `suicide NICK` tool command (NICK must
  match) kills a throwaway for good.
- `tools/shopcat/newchar.py --nick X --port P`: writes `runs/private/x.pass` (random) and
  `x.mangrc`, creates the character (default Half-Orc Warrior, DEX>STR>CON>WIS>CHR>INT), wears
  the starting kit (new characters start with it in the pack), prints stats and blows
  (`status` → `ind.skills2[0]`).
- Local test characters: `Dive01`, `Dive02` (Half-Orc Warriors, 2 blows with the starting
  Broad Sword). Still to do: outfitting for 4 blows (buy a light weapon; selling the kit needs
  the Phase 1 confirm answer), inscribing key items, and the live character "Sneezy".
- The user's player lore and plan changes are in `notes_players.md` (read it).

### ARCHITECT HANDOFF 2026-10-08 (READ THIS FIRST; the sections below are history)

**Start of every session:** start the inbox watcher first (memory `mangband-inbox-watcher`), read
unread `memos/to_architect/`, check what's running (`ps -u $USER`, `tmux -L mang ls`). After every
mission, relay agent friction to the user (memory `mangband-relay-agent-friction`).

**State (2026-10-08 16:15, job 7918400 on scc-wg3, walltime to Mon 10-12 08:03):**
- Running on scc-wg3: the test server under gdb (`testserver/`, port 28346, rebuilt 10-07 with the
  16-bit depth indicator), Dive04's Pilot (`tools/pilot/restart.sh Dive04`), the user's viewer
  (`tmux -L mang attach -t watch`; `tools/observe/watch.py`), the inbox watcher. A new job/node
  means restarting the server (`cd testserver && nohup gdb -batch -ex run -ex bt --args
  ../github/mangband >> gdb_run.log 2>&1 &`), the Pilot, and the viewer (`export
  TERM=xterm-256color` in its tmux).
- **Dive04** (Half-Orc Warrior): clvl 15, 170 HP, CON drained 18 → 14 (also WIS, CHR), STR 18/50,
  Main Gauche (+0,+2) 4 blows, Ring of Resist Fire + Slow Digestion, lantern; 72 gold, 2 WoR,
  3 CCW, 5 CSW, 5 CLW, 10 Phase; deepest 550 ft (`max_depth` 550); in town.
- **The user watches missions live** in the viewer: `!` notes = messages to the Navigator
  (`user_message`, it answers with `pilotctl say`), `?` notes = questions for the Architect
  (answer them after the mission: `tools/observe/notes.py --nick dive04 --questions --today`),
  plain notes = comments. Tab = the Navigator's view. Navigator journals via `pilotctl journal`
  (Pilot-stamped). Urgent alerts: order first, then journal (`.claude/agents/navigator.md`).
- Missions 7-16 + demo are summarised in the 2026-09-27/29 and 10-07 entries below; Advisor memos
  acted on: forum, danger table, Borg, post-mortem, shops, messages, game-state, identify-and-sell,
  flavour messages, mission 9/13 replays, warrior progression, running, mission 15 answers.
- **Public repo** https://github.com/userjjb/Mangbot (remote `origin` of `github/`, branch `master`):
  **first pushed 2026-10-08** (the user's fine-grained token is in git's credential store, repo-local
  helper). To publish: `github/tools/snapshot.sh`, commit, `git push` (`project/README.md` explains
  the snapshot and its exclusions). The GitHub front page is `github/.github/README.md` (the root
  `README` is MAngband's and the autotools build needs it): keep its capabilities/TODO current.

**TODO (priority order):**
1. **Push to GitHub** after each session's work (snapshot, commit, push).
2. **Dive04 next:** Restore CON (~470), 3 CCW kept, then stage B (500-750 ft at clvl 15; gate
   clvl × 50 = 750). Stage table in the HANDBOOK and `memos/2026-10-07-warrior-progression.md`.
3. **Pilot bugs open:** `explore` declared a level done with open ground on the map (mission 16,
   500 ft); explore "frontier unreachable" with an exit 6 squares away (mission 15, a Bloodshot eye
   nearby); flavour learning missed Beryl/Calcite rings identified by scroll (check the pack diff
   with the ring worn/destroyed); a Navigator busy in item/chest commands isn't woken by user
   messages (40 s "Pause").
4. **Navigator wishes:** movement trace in `status`; explicit run control (town runs need known
   ground ≥ 3 from the edge, so at night it walks); steal protection in townfarm (rogues);
   sell-price quote for pack items; an inner-room/pit recogniser from the Advisor's spec
   (`memos/2026-10-07-mission15-answers.md` §2) feeding `interesting`/`avoid`.
5. **Measure** alert → order → journal latency per mission (mission 14/15 median ~5 s, urgent
   tail to 112 s; the method: decisions.jsonl `attention` → next `goal`/`agent:` act/`nav_journal`).
6. **FUTURE IMPROVEMENTS (the user):** Navigator effort (now Opus high, inherited; user wants to
   watch before changing); model × effort trials; "Pinky and The Brain" two-tier Navigator; a
   complaints channel for agents. Details in the 10-07 entries below.
7. Smaller: server `pathfind` experiment (running memo change 6); doc fix (RUN_MIN is 3); a
   live-server run only after asking the admins (`operations.md`).

### ARCHITECT HANDOFF 2026-09-29 (history; read the 2026-10-08 section first)

New session (job 448491 on scc-wi2). Test server restarted under gdb 21:34 (gdb costs nothing: the
server's timers are a select loop, no signals; one crash ever, 09-26 15:41, none since; the user
asked, 2026-09-29, and agreed to keep it if harmless).
- **Torch bug** (commit after baeb276): Dive04's torches all burned out while it idled in town
  between sessions, and `keep_light` swapped the dead torches ~2100 times. Now it swaps only for a
  torch with more light, else `low_supply` once per 2 min.
- **Mission 9** (launched ~21:40, Dive04 clvl 6, 40 min, depth rule (clvl+4)×50 ft): first a
  light, then level up; tests escape verification, group danger, `@R` verify, danger-table
  reasons.
- **All of the above deployed mid-mission 9 (~21:50) with e2e741f**: group danger no longer phases
  at good HP (a lone Giant red frog, level 7, worst case 58 vs 97 HP incl. +50 drain, cost 4 Phase
  Doors); at 0.6-1.0× only the stairs underfoot, or Phase below think_hp; early WoR only above 1.0×.
  The worst-case sum is pessimistic at low clvl: watch whether it still over-fires.
- **Mission 12** (2026-10-03 12:18-12:50, job 7861666 on scc-pf3): safe, 300 ft, clvl 8 → 10
  (exp loss recovered), lowest HP 95%. Worked: fast unique = danger at first sight (Bullroarer
  adjacent on arrival → left by the stairs at once), climbs (no long `>` detour), current-level
  status, unseen "It fires an arrow" at full HP = news only. No emergency, so held uses / no-choke
  flee / HP-loss floor are STILL untested. The Navigator sold 2 unknown Potions of Speed (8 each).
  **Dive04 now: clvl 10, 135 HP, idle in town, 233 gold, 7 CLW, 7 Phase, 2 WoR, Heroism, Boldness,
  Staff of CLW, lantern, soft armour + Small Metal Shield; STR drained 18/20.**
- **2026-10-07 (job 7918400 on scc-wg3, the user: "implement the rest of the features")**: the rest
  of the game-state survey is done in 67acff1 (deployed 08:5x; server rebuilt and restarted 08:48):
  tool queries `flags` (resist/ability grid) and `floor`; depth indicator 16-bit on the test
  server; Free Action / resists from the grid (`Abilities:` line); listed-but-undecoded monsters
  count as dangers; effect confirmation for wear/takeoff/destroy/drop/eat/fuel/pickup/stairs (+
  agent replies say "no change"); wait reports show news since the previous wait; shop refuses
  unknown flavours unless forced; a 30-s state audit (`audit` records, counts in the report,
  redraw on a difference and every 2 min in town). Not done: a single `in_dungeon` definition
  (left as is; the 16-bit depth removes the wrap on the test server, the live server still wraps).
  Mission 13 launched right after.
- **Mission 13** (08:49-09:22, Dive04 clvl 10 → 11, 300-450 ft, lowest HP 80%): the `@R` inscription
  worked (landed at 300 = max reached); a WoR stayed pending across stairs; `Abilities:` right; the
  state audit found 1 difference in 66 checks (an hp race in a fight; the Advisor's
  `memos/to_architect/2026-10-07-mission13-audit.md`, script `Advisor/data/runs/audit_stats.py`).
  Still no emergency, so the escape fixes remain untested. Fixed after it (a516853 + audit tweak,
  deployed): **a run at night crossed town and left the map into the wilderness** (no runs on the
  surface now; `goal town` walks back by the arrival edges: it brought Dive04 home), recall goal
  lights up before reading / quotes the refusal / ends only on the real recall, one meal per 10 s,
  numbered map rows. The Navigator drank a Potion of Weakness (STR 18, 2 blows now).
  **Dive04 now: clvl 11, 146 HP, in town, 345 gold, 12 CLW, 11 Phase, 0 WoR, Sabre (2 blows).**
- **Identify-and-sell memo** (`memos/2026-10-07-identify-and-sell.md`, the user's request): acted on in
  efb18c3 (deployed): server-wide flavour table `runs/flavours.json` (51 seeded, learned on every
  unknown sale), reports show "(= kind; not aware)", the shop sells junk / one of a stack / shallow
  potions+scrolls and refuses unknown devices+jewellery, wearall skips unknown jewellery,
  per-character `deepest.json`, HANDBOOK fixed per the memo's §5. Flavours are also learned from
  Identify and use by diffing the pack (the Advisor's `to_architect/2026-10-07-flavour-messages.md`,
  deployed). Not done: quaff-test as a Pilot action; "sell to the right owner" quotes.
- **Observer (2026-10-07, the user's idea):** `tools/observe/watch.py` (live view + timestamped
  commentary; `?` notes are questions for the Architect) and `notes.py` (each note with the
  play around it); how-to in `operations.md` ("Watching a Pilot character"). After a watched
  mission: run `notes.py --questions`, answer each `?` from the decision log, and turn bad-play
  notes into fixes. Also from the Advisor's mission 13 replay: rest now continues to rest_to;
  exp logged in `audit_check`. Open from it: a stuck check for runs that make no progress
  (probably moot: no runs on the surface now); Navigator prompt "wield found weapons at once,
  read a carried Identify before testing anything".
- **Live talk with the Navigator** (1961e18): `!` notes in the viewer become `user_message` attention
  events; the Navigator answers with `pilotctl say` (its definition and the HANDBOOK say so).
- **Warrior progression memo** (`memos/2026-10-07-warrior-progression.md`, the user's request): acted on
  in 228bc3b (deployed): `Weapons:` report line (blows + damage per round per carried weapon, the
  server's formula) and a tip to wield a better one; `stat_drained` names Restore <Stat> at the
  Alchemist; `order max_depth=` warns past the gate (clvl × 50 ft to 1000, then (clvl − 5) × 50;
  1000 ft needs FA); HANDBOOK stage table. **Next for Dive04 (stage A): Restore Strength (~470),
  then a Main Gauche (4 blows once STR is 18/50), then a WoR; 250-450 ft until then.** Dive04 has
  345 gold. Not done: Staff of Teleportation as an escape at clvl ≥ 18 (the Pilot uses no staffs).
- **`goal townfarm GOLD [MIN]`** (the user's advice, 2026-10-07; zig-zag sweep also the user's): kills
  gold-dropping townspeople; tested 372 → 495 gold in ~40 s. **Dive04 now has 495 gold: enough for
  Restore Strength (~470).** Public repo: https://github.com/userjjb/Mangbot (remote added; the user
  will add a token tonight; nothing pushed yet; run `tools/snapshot.sh`, commit, push).
- **Mission 14** (17:47-18:25): **STR restored (18/50), Main Gauche 4 blows (+0,+1)**, clvl 12, 2 WoR,
  15 CLW, 3 CSW, 10 Phase, 83 gold; escapes all took effect (news = pack counts). Close call: Lagduf
  + 12 orcs at 450 ft, flee "stuck" (stairs 66 away) left the Pilot idle at 49% (the Navigator
  recalled). Fixed in 54c4368 (deployed 18:26): failed flee with monsters close → WoR + phase;
  early WoR when stairs are > 25 away; lantern counts for townfarm/torch upkeep; mushrooms in the
  flavour table; `found` news for special pickups (Farmer Maggot's Lance sold for 391).
- **Running memo** (`memos/2026-10-07-running.md`, the user's request): changes 1-5 in e912370,
  deployed 18:26 with 54c4368 (disturb_near/panel confirmed on); measure travel speed in the next
  mission (the memo expects ~2× in the dungeon, ~5× for town
  errands). Not done: server `pathfind` for long known routes (change 6, an experiment); doc fix
  (RUN_MIN is 3).
- **Mission 15** (22:42-23:36, the user watched live and sent 19 `!` messages; replies took 5-15 s):
  clvl 12 → 14, 450 ft, STR restored again (a Red jelly drained it), 2 WoR, 15 CLW, 9 Phase, 39
  gold. Fixed in 2765956 (deployed): `search [N]`, `disarm`/`open [DIR]`, no melee vs stationary
  drainers, confusion cure only with mobile monsters near, no long flee from slow weak-melee
  casters (Wormtongue), `interesting_item`, unanswered user messages on the report's 2nd line.
  Asked the Advisor (`memos/to_advisor/2026-10-07-mission15-requests.md`): vault/pit recognition
  from a partial map (the user's question), the corridor zig-zag, chests. Navigator wishes not done
  yet: a movement trace in `status`; explicit run control (town runs need known ground ≥ 3 from the
  edge, so at night townfarm still walks); steal protection in townfarm; "explore gave up with an
  exit 6 squares away" (23:19, a Bloodshot eye nearby: check stationary-avoidance costs).
- **Mission 16** (2026-10-08 15:31-16:08, watched; 19 user messages, replies 4-30 s, one 40 s while
  running chest commands): clvl 15, 550 ft, lowest HP 64%; first secret door (the user spotted it)
  and first chest by the safe procedure (+90 gold); Ring of Resist Fire found. Losses: CON 18 → 14
  (Purple mushroom patch, twice), CHR (Rot jelly), 14 CLW destroyed by `destroy Light all`, a
  Trident {good} (+3,+7) sold unidentified for 42. Fixed in 7d608cb (deployed): search reports
  finds; rings/chests in Item squares; interesting_item skips junk + dive pauses 20 s; drainers
  (CHR too) never meleed or stood beside; cures gated by threat; ambiguous item names refused;
  {good} unknown-pluses flagged and not sold; `avoid` zones (the user); viewer Tab = Navigator's
  view (the user). Open: explore ending early with open ground on the map (500 ft); flavour
  learning missed Beryl/Calcite via Identify; Restore CON (~470) needed. **Dive04: clvl 15,
  170 HP (CON 14), 72 gold, 2 WoR, 3 CCW, 5 CSW, 5 CLW, 10 Phase, rFire ring, max_depth 550.**
- **Demo mission** (23:49-23:56, 50 ft and back by stairs, the user messaged twice): fine. Fixed and
  deployed with the mission 15 answers (b26c14a: corridor zig-zag → run along the axis, map crops
  in attention/journal/note records, HANDBOOK inner rooms/vault walls/chests) and 7c16bc5 (stuck
  watchdog counts from the goal's start; `Town (day|night)` in the header; townfarm says when 2 min
  bring no gold). Dive04: clvl 14, 51 gold, max_depth left at 50 (raise it before a real dive).
  Open wish: a sell-price quote for pack items.
- **Navigator urgency rule (2026-10-07, the user):** on urgent alerts the Navigator sends the order
  first in its own call, then journals; otherwise journal first (`.claude/agents/navigator.md`).
  Effort deliberately unchanged for now: the user wants to watch the current Navigator (Opus 5.5,
  effort high, inherited from `~/.claude/settings.json`) to put the earlier missions in context.
- **FUTURE IMPROVEMENTS (the user, 2026-10-07):**
  1. **Navigator effort:** lower it (`effort: medium` in the agent's frontmatter) to cut the
     alert → order latency (typically 10-30 s at high effort); the urgent/non-urgent journal
     rule above keeps a written reasoning step for strategic decisions.
  2. **Model × effort trials:** run comparable missions with a Haiku, Sonnet and Opus Navigator at
     different effort levels; measure competency (XP/gold per minute, deaths, close calls,
     consumables used, mistakes in the journal) against latency (alert → order → journal, from
     `decisions.jsonl`: `attention`, `goal`/order acts, `nav_journal`).
  3. **"Pinky and The Brain":** a two-tier Navigator. Pinky (Haiku: fast, cheap, still far smarter
     than the Pilot's rules) handles the short-term loop (alerts, goals, routine shopping) and
     confers with The Brain (Opus) for harder calls and long-term planning (depth, stage
     progression, purchases, unfamiliar dangers). Design questions: how Pinky decides to escalate
     (a list of triggers plus "when unsure"), how The Brain is reached (a subagent Pinky launches
     or messages; it must answer in seconds), and a shared plan file The Brain keeps current so
     Pinky acts on it without asking.
  4. **A complaints channel for agents (the user):** the Navigator worked for 14 missions without a
     reliable clock and it never reached the user: it noted "my times were estimates" twice (missions
     8, 14) as its own mistake, and the Architect filed that as a Navigator slip instead of a
     missing capability. Ideas: a "What I lacked / what got in my way" section in every Navigator
     report (separate from its mistakes) and a `pilotctl complain "..."` that appends to
     `runs/complaints.md` at any time; the same for the Advisor and its Clerks (a section in each
     memo); the Architect reviews complaints after every mission, fixes what it can, and **relays
     anything recurring or unfixable to the user** in its summary instead of absorbing it.
- **Inbox lesson (2026-10-07):** that memo sat unread ~1 h because the Architect didn't start the
  inbox watcher at session start (the hook asks for it), and the post-Bash hook only fires on the
  Architect's own commands. Start the watcher first thing every session; it lasts ≤ 10 min, so
  restart it when it ends.
- **Game-state survey** (`memos/2026-10-03-game-state.md`, the user asked the Advisor for it): §6
  quick wins done in 771d141 (deployed): tool verb `redraw` (sent after each level change and
  loss), fresh inventory per decision, `recall_pending` survives level changes, handlers for
  destroyed/stolen/overflow/purse → `lost` news, `Supplies:` line (also --brief), news no longer
  cleared by `status`, wearall picks the best light. Open from the survey: generalise
  `pending_use` confirmation to every item/shop/stairs action; emit the floor item and the resist
  grid from tool mode; depth indicator NORMAL on the test server; a state-audit log.
- **Mission 11** (22:33-23:07, 50-150 ft, safe, lowest HP 95%): a rebuild. Gold 87 → 239; light
  on in the dungeon and off idle in town worked; stationary blockers killed. No emergency, no
  group danger, no uniques: those fixes are still untested. Fixed in 72ec098 (deployed): **the
  pilot used the MAX level everywhere** (indicator `level` = (max, current), xtra1.c:166; status
  now "level 8 (max 10)"), and a climb walked 15 squares to a `>` (scum now only by a `>` within 8
  squares and within max_depth). The torch burning 1600 → 454 in 9 min is resting (time runs 10×
  while resting with nothing in view, in the dungeon too). **Dive04 now: clvl 8 (max 10), 115 HP,
  idle in town, 239 gold, 7 CLW, 5 Phase, no WoR, cloak/cap/gloves only, 2 low torches.**
  Next: buy a WoR (~235) or armour, then 150-300 ft to exercise the escape/group-danger fixes.
- **Mission 10** (22:06-22:29): **Dive04 died at 250 ft** to Mughash + kobolds (1 CLW, 5 Phase,
  1 WoR carried); **`goal resurrect` worked** (floated up 5 levels, resurrected; exp halved).
  Escapes executed this time (Phase ×3, WoR charged). Fixed in df69d21 (deployed): held uses were
  reported as done (the CLW never ran: held behind a pending Phase), `choke` hijacked the Flee
  twice, resends after death, group danger minus the drain term plus an HP-loss floor, fast
  unique = danger at first sight, `explore until=(up)stairs` needs reachable stairs (all from the
  Advisor's mission 9 replay, `memos/to_architect/2026-09-29-mission9-replay.md`). Open: the
  status line says level 10 after resurrection although the game said "dropped back to level 8"
  (check the `level` indicator vs `C` sheet); lantern turns rose 4929 → 9900 with no flask used;
  gold changed with no event. **Dive04 now: idle in town, 87 gold, a Dagger, empty pack.**
- **Versions memo** (`memos/2026-09-29-versions-and-forum-rules.md`, read): facts added to
  `operations.md` (source = develop c97e873; live-server rules; ask the admins before a live run).
- **Mission 9 result** (21:35-22:02): clvl 6 → 8 (115 HP), 250-300 ft, lowest HP 24/115 vs
  Bullroarer; STR drained (blows 4 → 3). Worked: escape items took effect, lantern, light off in
  town, `shop list`, danger_seen "melee ~N per turn", "drained twice → leave". Fixed after it
  (22a436d + the list-parse fix): **every buy was broken by 8082af5** (Shop name unpacked 2-tuples),
  a stale pack letter read a WoR twice (now one use at a time until confirmed), a ration eaten
  with Bullroarer just out of view. Open: stuck with "no known path" to a listed `<` (21:49,
  dead end 59,91; the Advisor is asked), Bullroarer's alert only at 2 squares, pickup=all
  re-picks dropped items. **Dive04 now: clvl 8, idle in town, ~248 gold, 1 CLW, no Phase/WoR.**
  Asked the Advisor to replay mission 9 (`memos/to_advisor/2026-09-29-mission9-ended.md`).
- **Shops + message-catalogue memos** (`memos/2026-09-29-shops.md`, `memos/2026-09-29-message-catalogue.md`,
  read): acted on in 7160211: RE_UNSEEN/RE_HURT_OTHER fixed from the catalogue,
  light off when idle in town (resting burns ~10×), HANDBOOK store facts. Open: replace the hand
  regexes with `Advisor/data/messages/catalogue.csv` lookups (catalogue §4.3); "You have killed
  it." not counted by Hunt/fight_t; "closed door/tree blocking your way" would mark a wall
  (mover.py bump); shop routing by store in the Pilot (catalogue: 15 cure buys went to shop 5);
  staff of Teleportation as a goal item.
- **0090192**: `RE_RANGED` counts visible ranged attacks ("The X fires an arrow!",
  "breathes", "casts a magic missile") as hits; RE_ATTACK needed a trailing "you" (the Advisor's
  early message-study finding, `memos/to_architect/2026-09-29-studies-running.md`).
- **8082af5**: `goal shop N list` (stock + prices),
  `buy NAME:N@MAX` (price cap), `pilotctl monster NAME` (this server's data + the pilot's verdict;
  post-mortem §5).
- **Asked the Advisor** (`memos/to_advisor/2026-09-29-study-requests.md`): (1) shops and economy
  (stock, prices at CHR 4, torch burn in town, a shopping list per depth band), (2) the message
  catalogue for escape confirmation and unseen-attacker false alarms, (3) optionally a replay of
  mission 9's logs.

### ARCHITECT HANDOFF 2026-09-27, late evening (read after the 2026-09-29 section)

Commit 6274e8b (deployed; Pilot restarted 22:15) did evening items 1-5 and next step 0:
- **Privacy**: the tool-mode client logs in as `player@localhost` (verified in `gdb_run.log`).
- **Time bubble**: tool mode sends `hitpoint_warn` 6 (`--hpwarn N` to change).
- **Status cures** (`status_tick`, in a fight only): stun → CCW+; confused → CSW+; blind → CLW+;
  poisoned below `think_hp` → Cure/Neutralize Poison or CCW. Items 4-5 (uniques per character,
  resurrection halves exp) went into `notes_players.md`; the HANDBOOK had no wrong wording.
- **Mission 6 fixes**: `still_fight_tick` kills a weak stationary monster that disenchants or sits
  by the mover's target (never a paralyser without `free_action`; a strong disenchanter → Flee);
  `stat_drained` compares values (a second DEX drain was silent); `stuck` ignores windows with
  fighting; minor unseen attacks (teleport-to, magic missile, arrows) at good HP are news only;
  "quaffed a Potion of X" wording.
- Commit 04ac768 (not deployed yet, like 785f608): the Recall goal checks the `@R` the server will read (`recall_level`,
  mirrors spells2.c: last `@R` wins, multiples of 50 are feet), and `choke` ranks squares for
  two-wide corridors (`choke_tier`). Still open from item 6: a fresh name per throwaway. A floating eye blocking the only stairs still
  stalls the Pilot (it won't melee paralysers): the Navigator is told to pick other stairs.
- **Mission 7 (22:14-22:28): Dive03 DIED at 750 ft, and is gone for good**: the user chose to
  resurrect, but the disconnected ghost lingered in the level, was hit and poisoned ("It touches
  you", 22:28:40-51), and at the next login (23:17) "Your incorporeal body fades away - FOREVER".
  Commit 1011e37: `goal resurrect` (untested). A new character is needed for the next mission. A summon trap put 4 Uruks + a Giant red scorpion (STR
  drains, blows 3→1) next to it. Root cause (commit 785f608, not deployed: no live character):
  when `escape()` had nothing usable that instant it returned False and the explore goal ran; its
  Mover sent `clear` + walks every ~2 s, wiping all 8 queued Phase Doors, 2 potions and the WoR
  (none ran; events.jsonl acks vs gdb_run.log). Fixed: the emergency always holds; no new stairs
  move within 2 s of a use; `--hpwarn 0` for now (timers are wall-clock; below 60% HP we got a
  turn per 1.5-2 s); the Pilot stays up after death. Worked in play: confusion cure (CSW),
  `stat_drained` on every drain, no `stuck` in fights, "quaffed a Potion of X".
  Navigator suggestions still open: repeated stat drains from a visible monster → leave (like
  `fearer`); breaths from a partly visible pack at good HP → news; HANDBOOK: CCW costs 152 at the
  Temple (4), the Alchemist had none; what to do if the Pilot drops out.
- **Danger-table memo acted on** (commit 63ef06b): the Pilot loads a copy of the table
  (`tools/pilot/danger_table.csv`; re-copy if the Advisor revises it) and has its §3 rules 1-4, 6-8
  (new orders `resist_blind`, `resist_conf`); HANDBOOK and `notes_players.md` have §5/§6. Not done:
  §3.5 (teleport-to escape mode). Told the Advisor (`memos/to_advisor/2026-09-27-danger-table-adopted.md`),
  and suggested a study of pack melee / repeated stat drain as leave triggers.
- **Borg memo** (`memos/2026-09-28-borg.md`, read): §3.1-3.2 done in commit 7b592c5 (deployed 02:10
  after mission 8): group danger (the
  Borg's worst-case melee sum vs HP, tiers 0.3/0.6/1.0) and "second stat drain on a level → leave".
  Tuned with `tools/pilot/replay_group.py` over Dive03's logs (stationary monsters had to be
  excluded). Still open: §3.3 stuck ladder, §3.4 escapes per level, §3.5 go-back cooldowns, §3.6
  rest gate, §3.7 unseen-hit regions, §3.8 items by name. **§4 needs the user's decision**: the
  depth-by-level doctrine (Borg: clvl ≥ dl; suggested middle ground: max_depth ≤ (clvl+4)×50 ft
  to 1000 ft, clvl ≥ dl below, never below 1000 ft without FA) and gear gates.
- **Run post-mortem memo** (`memos/2026-09-28-run-postmortem.md`, read): §4.1-4.3 and 4.6 done in
  baeb276 (deployed ~02:30): escapes verified by "You have N ... left" and resent (Mover clears held
  meanwhile), drain weight 50, 0.3× backs away, 0.6× with no stairs → WoR at once, `mons` log
  records each second. Open: §4.4 (after a Phase/potion escape don't resume the goal on that
  level), §4.5 (unseen-attacker false alarms after kills), §4.7 (dedupe `low_supply`), §5 (a
  `pilotctl` query for the danger table so the Navigator stops using Vanilla lore).
- **Mission 8** (01:36-02:07, Dive04, 50-100 ft): safe. **Dive04 now: clvl 6, 77 HP, idle in town,
  159 gold**, Dagger (+1,+2) 4 blows, soft armour in every slot, 3 CLW, 8 Phase, 1 WoR (uninscribed),
  8 flasks. The user's outfitting advice was applied (Main Gauche not stocked). Worked: WoR
  without `@R` refused in town, `choke` (5 times, packs killed), stationary blockers killed (4),
  fear cure, `fight_going_badly`. Didn't come up: an emergency (the 785f608 fix is still untested),
  `@R` verify on recall down, the new danger reasons, group danger (deployed after). Open ideas:
  `shop N list` (see a store's stock), a price cap/confirmation on `buy`, CLW stock runs out.
  Next mission: deeper (150-300 ft) so the emergency and danger rules get exercised; the user's
  depth-doctrine decision (Borg memo §4) is pending.

### ARCHITECT HANDOFF 2026-09-27, evening addendum (read this first, then the afternoon section)

This is where the Architect left off after the Advisor split (the afternoon section below is still
the current Pilot/Navigator state; nothing in the Pilot changed since).

**Project structure changed (user's decision, 2026-09-27)**
- The **Advisor is a separate Claude Code project**: sessions started in `Advisor/` (own memory).
  **The Architect edits everything except `Advisor/`**; the Advisor edits only `Advisor/`. `memos/`
  is shared.
- **Inbox:** the Advisor's suggestions arrive in `memos/to_architect/`. The session-start hook reports
  unread ones: read them, `.claude/hooks/inbox.sh mark-read FILE`, then run the watcher in the
  background (`.claude/hooks/inbox.sh watch memos/to_architect`). Send suggestions to the Advisor
  via `memos/to_advisor/` (write `.tmp-SLUG.md`, then mv to `YYYY-MM-DD-SLUG.md`).
- The Advisor runs studies with **Clerk** subagents (`roles.md`, `Advisor/METHOD.md`). The Architect
  never launches Clerks.
- The forum corpus lives in `Advisor/data/forum/`. `runs/forum/` was deleted (the user's decision;
  the copy was verified complete first).

**The forum memo is complete:** `memos/2026-09-26-forum-distillation.md`. The Architect acted on
Addendum 2 (afternoon). Still to act on, from **Addendum 3 and the Erratum** (read them):
1. **Privacy (live server):** the player list shows every client's `realname@hostname`. Our client
   sends the Unix login (`src/client/client.c:48`, `getpwuid`) and host name (`c-init.c:999`). Send
   neutral values in tool mode before the next live-server session. Not done.
2. **Time bubble (Addendum A1):** set `hitpoint_warn` (client pref `H:n`, 0–9) to about 5–6 so fights
   below 50–60% HP run 5× slower. Not done (no `hitpoint_warn` in the Pilot or C tool code).
3. **Cures (Erratum, code-checked):** only CCW or better cures **stun and poison**. CSW cures blind,
   confusion and cuts; CLW cures blind and only reduces confusion and cuts. Verify that the Pilot's
   status-cure choice (e.g. `CURE_POTIONS` at `pilot.py:45`) uses CCW for stun and poison. The heal
   amounts in `HEALS` already match the code.
4. **Uniques are per character** (Addendum 3 #1): each throwaway meets the early uniques (Grip, Fang,
   Bullroarer, Wormtongue, Grishnákh, Azog). Check the HANDBOOK and danger text.
5. **Resurrection halves experience permanently** (Erratum; Restore Life Levels can't recover it).
   Update HANDBOOK/P15 wording if it says "3–5 levels".
6. Smaller items: 2-wide corridors (A5; `choke` prefers doors and corners), a second WoR cancels
   the first (done), mold auto-melee confirmed (done), check the `@R` inscription before reading,
   chaos resistance isn't confusion resistance, read resists from the `C` sheet, a fresh name per
   throwaway, and one tool character online at a time.
- The Advisor's study backlog (for context; the Advisor owns it):
  `memos/2026-09-27-advisor-study-topics.md`. The danger table from `monster.txt` would overlap the
  Pilot's danger model, so compare when it arrives.

### ARCHITECT HANDOFF 2026-09-27, afternoon (read this first)

Roles are in `roles.md`. This section is the current state; the sections below are history. This
session ran Navigator missions 3, 4 and 5 and fixed the Pilot between them (all in `git log`,
from f0a23a1 "track a pending recall" to the mission-5 fixes, f1c0579, all deployed).

**State**
- **Pilot** (`github/tools/pilot/`): features in `HANDBOOK.md` (the Navigator's only manual); the
  rule order as the code runs it is in `design_pilot.md` ("Pilot responsibilities", now current).
  Logs: `runs/pilot/<nick>/{decisions,events}.jsonl` (events' `t` restarts every run; see
  `operations.md` gotchas), orders in `orders.json`, the Navigator's journal in `navigator.md`.
- **Navigator**: `.claude/agents/navigator.md`. Missions: 3 (49 min, safe, clvl 19→20, found the
  queue bug), 4 (35 min, clvl 20→21, found the unseen-attacker false alarms, rubble, mold),
  5 (22 min, 550 ft, safe: the kill-time false alarm is gone; a graze + spiked pit still read as
  an unseen attacker → fixed in f1c0579, not yet seen in play).
  6 (13:34-13:58, 700-800 ft, safe, lowest HP 74%, gold 106 → 717): no `danger_seen` at all at
  these depths; `unseen_attacker` fired ~8 times, all real (teleport-to, dark archer/shaman, an
  invisible DEX-draining ghost), no false HP alarms. A Flee crash (None in "<>") fixed in b034b0e.
  Its other problems are next step 0 below.
  Mission prompts that worked: character state, objectives, depth range, time budget, stop
  conditions, and "report worked/failed/didn't come up" for each new feature.
- **Character**: Dive03 (Half-Orc Warrior, clvl 21, 251 HP, DEX drained to 14, CON to 17, Rapier
  of Slay Troll now (+2,+4) and armour disenchanted by a Disenchanter eye, unknown Silver Amulet
  worn) idle in town after mission 6. 249 gold, 2 WoR, 12 CLW, 4 CSW, 10 Phase Door, 1 Boldness,
  1 Berserk, an unsold Staff of Object Location. `max_depth=800`, flee_hp 0.5.
- **Advisor memo**: Addendum 2 acted on (see below). The memo is now complete; for what's still open,
  see the evening addendum above.

**Done this session (all deployed and at least partly seen in play)**
- Recall: pending recall tracked from the server's messages; the Pilot never reads a second WoR by
  accident (`read ... force` to cancel on purpose); `recall_cancelled` event.
- Heal or escape by numbers (heal table + measured damage rate) — seen working in mission 4.
- **Out of combat: rest, never potions** (the user) — seen working.
- Danger model from monster.txt (breathers, hound-pack breath, paralysers without `free_action`,
  summoners); `danger_seen` gives the reason. Not yet seen in play.
- Unseen attackers ("It ..." messages; HP loss with nothing in view, tightened after mission 4's
  false alarms; order `unseen_hp`). Real cases worked in mission 4.
- Stationary monsters (molds, jellies, floating eyes) avoided by the planner and stepped away from.
  **Mission 4: a Yellow mold wasn't in the Pilot's monster list at all**; the `perception_gap`
  log (decisions.jsonl) now records such cases with a map crop: read it first.
- **Queue bug**: a step left in the server's command queue made every later step run one behind
  (10-minute circling). The Mover sends PKT_CLEAR on every replan; auto-pickup clears first.
  `stuck` watchdog event. Parking with `clear` verified twice.
- Rubble digging (`T`), Flee prefers `<` at/below max_depth and reports after the level change,
  `wait --brief`, quiet `wait` timeouts print the short report, weak breeders are news only.
- Checked, not a risk: detection "freeze" (`pause_after_detect` only sends a flag).

**Operating rules (unchanged, still true)**
- Start the test server under gdb: `cd testserver && nohup gdb -batch -ex run -ex bt --args
  ../github/mangband >> gdb_run.log 2>&1 &`. Start or update the Pilot only with
  `tools/pilot/restart.sh Dive03` (it parks first; never kill the Pilot mid-move).
- Never park or restart during a recall. Keep tool characters out of the wilderness.
- Edit HANDBOOK/code with assert-checked replacements (a helper `sub()` that asserts the count).
- Tell a running Navigator via SendMessage after a Pilot update. Keep memory in sync (`roles.md`).

**Next steps (priority order)**
0. **Mission 6's problems** (report summary in this section's mission list; journal 13:35-13:58):
   - **Stationary monster blocking the path/stairs**: the Pilot paths around a NEVER_MOVE monster
     and so stalled next to a Disenchanter eye beside the only way to a `>`, taking many
     disenchanting gazes. Rule: a weak stationary monster (level well below ours) that blocks the
     path or sits by the target stairs gets killed (auto `hunt`); a disenchanter (`DISENCHANT`
     blow/gaze) is "kill now or leave", never "path around".
   - **`stuck` counts fighting time**: it fired during a corridor fight with a wolf pack (the
     check only excludes *adjacent* monsters at the moment; exclude any recent hit/attack too).
   - **Stat drains raise no `stat_drained`** (DEX 15→14 here, CON in mission 5): check
     `watch_character` against the live `stat*` indicator values.
   - "It commands you to return" (Tengu, Blink dogs) and weak "It casts a magic missile" at
     high HP needn't make the Pilot flee the level.
   - The "quaffed ... Boldness" news said 2; 1 was left (item-count wording).
1. **Perception gaps.** Mission 4: a Yellow mold hit us while the map decode showed nothing.
   Mission 5's 9 `perception_gap` records (decisions.jsonl) all had a fresh map (0.1-0.26 s) and
   were probably monsters just coming into view (the log now keeps only gaps lasting > 1.5 s).
   Next mission: check for lasting gaps; if the mold case recurs, compare the map attr at its
   square with the glyph table (`glyphs.assign`: Yellow mold = ('m', 2)).
   Also: mission 5 saw no `stat_drained` when CON went 18→17 (check `watch_character` against
   the live `stat*` indicators), and `autodestroy=average` destroys an item the Navigator fetched
   on purpose (consider skipping autodestroy after a `goto` to that item).
2. **Still never exercised in play**: `danger_seen` with the new reasons, `stuck`,
   `recall_cancelled`, fear kiting, digging (unless mission 5 hit rubble), the shop's refusal to
   sell probable specials. Deeper levels (650-800 ft) will bring breathers and summoners.
3. **Act on the full Advisor memo** when the user says it's complete. Remaining items from the
   first memo: arrival check after trap teleports; P4 status triggers (stun → CCW at once;
   confused/blind → no scrolls, needs a staff); P5 escape verification; P7 lag gate; P12
   aggravation guard; P15 death handling (ghost: float up, resurrect).
4. **Money/gear loop for Dive03**: Restore DEX (351 gold), Cure Critical Wounds, Free Action and
   See Invisible before 1000 ft (memo depth table).
5. **Speed**: exploring is ~3 tiles/s; stair travel slow.
6. **Live validation** with "Sneezy" on mangband.org:18346 (`newchar.py`), only after the
   test-server missions are stable.
7. Small items: shop "can't afford 99 Scrolls" wording when a discounted stack runs out (say how
   many were bought and why it stopped); "Standing on" lags after a pickup of gold in town;
   `target` for missiles/wands; pushed map diffs; the goals/orders/events lists in
   `design_pilot.md` (the HANDBOOK is the reference for now); log maps (a crop per decision) to
   make stalls diagnosable.

### Status 2026-09-26: Phase 1 mostly done, pilot v0 running (see design_pilot.md)
- Architecture agreed with the user: **Python pilot** (tools/pilot/) plays second to second; an
  **agent** (Claude in chat now, later a subagent that only reads tools/pilot/HANDBOOK.md) sets
  strategy via `pilotctl.py`. Unattended characters recall to town.
- Done in C: `level` event, `confirm yes`, monlist/itemlist events, map attrs, `--visuals` glyph
  upload, `option NAME yes|no` / `options`, `rest` (PKT_REST toggle; shopcat's `custom R` never
  worked), `suicide NICK`, `--birth`. Not done: `target`, pushed map diffs.
- Unique monster glyphs work (tools/pilot/glyphs.py; needs option avoid_other): every monster on the
  map decodes to the right name (checked against the server's monster list).
- Pilot played by the agent (Claude via pilotctl) with Dive03: town outfitting/selling, stair-scum
  dive to 650 ft, two uniques killed (Brodda, Lagduf fight), several town trips via Word of Recall.
  Each problem found became a commit (see git log from e726f47). State and how-to: memory
  `mangband-pilot`, tools/pilot/HANDBOOK.md.
- Gotcha: the depth indicator is one signed byte; far wilderness squares (index < -127) show up
  as positive "dungeon" depths. The pilot should track surface/dungeon from how it changed level.
- Human play observed and digested: notes_players.md (stair-scum dive, fight by standing still,
  escape by the stairs underfoot, food/pack management).

### Phase 1: richer observations (C, small, additive)
1. **Map with attrs**: add `map attr` (or a second `rows_a` array) exporting `stream_cave[].a`.
   Colour distinguishes e.g. monster kinds sharing a letter, lava/water, lit and unlit floor.
2. **Unique glyphs for recognition**: in `tool_setup_visuals()` give each monster race
   (`Client_setup.r_char/r_attr`, `VISUAL_INFO_R`) and object kind (`k_char/k_attr`) a unique
   (char, attr) pair and export a lookup table. Then the map says *which* monster/item is at a tile.
   (The value 0 means "server default": avoid it. Chars must stay printable in the stream.)
3. **Event on level change**: emit `level {depth}` from the depth indicator (today it's polled).
4. **Monster list**: subscribe the `MONLIST_TEXT` stream (and `ITEMLIST_TEXT`) and emit its
   rows. It's the server's own list of visible monsters with names, so no guessing from glyphs.
5. **Look/target**: implement `target` (`PKT_LOOK` with `NTARGET_KILL` + direction keys, or
   `MCURSOR_META` cursor) so spells/missiles can pick a monster; capture `PKT_TARGET_INFO` text.
6. Optionally a `yes` answer for the next confirm (for selling), guarded by a flag.

### Phase 2: movement layer (Python, `nav.py`)
1. Make a `Mover` object: plan → execute (run/walk/pathfind) → verify, with interrupt hooks
   (monster appears, HP drops, level changes), so higher layers never micro-manage steps.
2. In the dungeon, test server pathfind (no level edges there) and use it when the path stays
   within 25 tiles and no no-go zones; fall back to own-path running/walking otherwise.
3. Auto-explore for dungeon levels: frontier exploration (known floor next to unknown), doors
   (`+` open with `o`/`+`), stairs as goals. The sweep in `wild.py` suits open wilderness,
   not corridors.
4. Replace fixed timeouts with event-driven waits (pos/message) to cut latency: the game is
   real-time and monsters act while you think.

### Phase 3: a rules-based survival agent
1. State model built from events: position, map (+attr), visible monsters (Phase 1),
   inventory, indicators, recent messages.
2. Priority rules, first match wins:
   - escape when HP < X: quaff Cure/Heal potions, read Phase Door, take stairs, or read
     Word of Recall;
   - fight adjacent weak monsters;
   - avoid or flee dangerous ones (a table by monster name/level);
   - eat; refuel; rest when hurt and nothing is in view;
   - pick up and identify loot;
   - explore;
   - descend when the level is explored and the character is strong enough.
3. Town loop: recall up, sell/buy (needs the confirm answer), restock potions/scrolls/food/oil,
   recall down. Word of Recall behaviour and store buy/sell are already understood (`notes_merge.md` §4/§6).
4. Logging for learning: reuse `--events` logs; add per-decision logs (state summary → action → outcome).

### Phase 4: smarter play (optional)
- An LLM or learned planner on top of the rules layer, choosing goals (descend, farm, shop)
  while the rules layer keeps it alive. Budget latency carefully: react to danger in Python
  rules, never wait on a slow planner mid-fight.
- Offline replay: the events logs let you replay sessions to test decision logic without a server.

### Risks to plan for
- Permadeath: test on the local server; expect characters to die; automate re-creation
  (birth needs interactive prompts; `c-birth.c` could get a no-prompt birth path, or drive
  it through tmux as was done for Surveyor).
- Server-side DM/ghost characters behave differently; don't use Gandalf as a stand-in player.
- The test server crashes if anything generates an 11th arena (wilderness only).

---

## Reflections from the agent who built this

**1. The survey was a good map, but the territory decided everything.** `notes_merge.md` was
accurate and saved days. Yet almost every decisive fact came from contact with the running
system, not from reading code:
- the cursor packet's y/x order;
- server pathfinding treating the row past the level edge as walkable;
- the Half-Troll's regeneration eating a ration every 100 s;
- trees blocking movement;
- arena walls teleporting you;
- the eleventh arena corrupting memory.

Reading the source told me what *could* happen. Only running it told me what *did*. Budget for
cheap experiments early, and treat any belief you haven't observed as a hypothesis.

**2. Build instruments before automation. It paid off every time.** The packet logger, the
per-event JSON log, `pos` events and, at the end, a gdb hardware watchpoint turned mysteries into
one-line answers. The most expensive stretches of this project were the ones where I patched
behaviour *without* first looking at a trace. Whenever I did look, the real cause was usually
different from my guess:
- the "overshoot" that was really server pathfinding;
- the "missing gold" that was really Gandalf on another level;
- the "bad walking" that was really a fence of `=` logs.

When something surprises you, look at the log before you write code.

**3. When the same surprise happens twice, stop patching and model the mechanism.** 2S→3S
happened three times. I added two plausible fixes before reading the trace properly and
understanding server pathfinding's 25-tile search window. Likewise the arena re-entries came from
my own safety margin boxing the character in, and then my "escape" logic walked it straight back
in. Patches made under time pressure pile up and interact. The later code review found bugs that
my own fixes had introduced:
- a toggled rest command that switched resting *off*;
- the removal of careful stepping near no-go zones.

Reactive fixing is sometimes necessary during a long live run, but schedule a calm review
afterwards.

**4. The client is a stream of requests into an authoritative, real-time world.** Nothing you
send is guaranteed to happen:
- commands get dropped, swallowed or ignored at run boundaries;
- monsters act while you plan;
- the level can change under you.

The working pattern was: act, then verify from events, then re-plan, never assume. This matters
even more for autonomous play. The hard part of a game agent isn't the decision
policy. It's reliable **perception** (what is actually on this tile?) and **actuation** (did my
step happen, and where am I now?).

**5. The human knew things I spent hours inferring. Ask sooner.** The user casually mentioned:
- that you can *run* with shift+direction;
- that the live servers don't have the arena bug;
- that a lantern is the normal answer to night.

Each of those would have saved time if I had asked "what movement options does a player
actually have?" at the start. The general lesson: before engineering around a limitation of the
interface, ask the domain expert how a human does it. Also note which decisions the user wanted
to own:
- which character to create;
- which server to use;
- lantern or waiting for day;
- Half-Troll or another race.

**6. Many failures happened at boundaries between layers.** This system has at least five
layers:
- wire protocol;
- client UI loop;
- server game rules;
- world generation;
- the social layer (other players and their houses).

Most bugs lived where two meet:
- the UI loop blocking on prompts the protocol didn't need;
- game rules (the "you own it" door behaviour) shaping catalog semantics;
- world generation state (the arena count) persisting through saves;
- the metaserver list replacing the "host/port" the user never typed.

When something is weird, ask which boundary you're standing on.

**7. My own tooling was a source of bugs too.**
- `pkill -f` killed my own shell.
- Monitors whose `pgrep` matched themselves never finished.
- A wiped scratchpad took the first catalog and all the password files with it.
- A ghost admin I used as a helper wandered off to depth 66.

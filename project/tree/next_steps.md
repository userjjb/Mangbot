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
  in practice runs are short. The tool averages ~0.25 s per tile by running straight stretches ≥3 (RUN_MIN 3 since 6c3cea5; corridors are free runs).
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

### ARCHITECT HANDOFF 2026-10-26, end of session 6 (READ THIS FIRST; the session-6 section below has its details)

**Where we are (2026-10-26 ~08:05).** Same SGE job 8268425 on scc-pc4, walltime **Thu 10-29 09:47**: test server (freeze
build), Dive04's Pilot (git `restructure` 7534708, pushed, all loaded), viewer (`tmux -L mang attach -t watch`). **Start
your own inbox watcher** (a "running" one may belong to a dead chat).
- **Dive04:** clvl 28, 340 HP, AC ~77, idle in town (on the tavern entrance, 27,89), **24901 gold**, `max_depth` 750
  (a trial since 10-25: 650-750 ft). **Battle Axe of Westernesse (2d8) (+10,+9)** wielded (Free Action, See Invisible);
  Scimitar of Westernesse in the pack; Leather of Resistance; Rings of Protection [+12] and [+10]; Amulet of Resist
  Lightning (redundant); Staff of Teleportation (6); 20 CCW, 4 CSW, Healing, 18 Phase, 2 WoR, 3 Heroism; WIS drained.
  **The tavern stash** (stash.json): Restore Dexterity, Restore Constitution, 2 Wands of Stone to Mud -- plus an old
  1977-turn lantern on the tavern floor (an Architect test drop). Debts 44 / 0. Checkpoint
  runs/setpieces/saves/dive04-pre-m43 (clvl 27, before the Haiku runs; restore only on the user's word or a death).
- **Last missions:** Haiku at LOW effort m43-m45: 68.8 / 73.2 / 77.6 XP/dmin at $0.014-0.019 each, no close calls --
  as good as Sonnet (series m35-m42: 62-87 at $0.17-0.24) for ~1/10 of the cost; Opus dearest and not better. n is
  small and the Pilot changed between missions.

**Next session, start here:**
1. Inbox watcher; check the processes (`pgrep -af "gdb -batch|pilot.py"`, `tmux -L mang ls`); if the job died: server
   (operations.md, with `MANGBAND_FREEZE_FILE`), Pilot (`tools/pilot/restart.sh Dive04`), viewer.
2. Ask the user what to run. Missions so far use the m45 brief (Agent prompt: state, max_depth 750, "plan first",
   the verdict list). Wrap-up per mission: **`github/tools/observe/wrap.sh mNN`** (mission end by name, tokens,
   scorecard, complaints, ? notes, status), then 
   `tools/observe/tokens.py mNN`, `scorecard.py --table`, a report in runs/pilot/dive04/reports/, complaints, the viewer's `?`/`!`
   notes (commentary.jsonl), **new lessons into FIELD-NOTES.md**; during missions watch decisions.jsonl for
   emergencies/deaths **and `nav_ask`** (answer with `PILOT_ROLE=architect pilotctl answer ID TEXT`).
3. **Verify live on the next missions:** the stash fetch (a drained stat -> StashFetch picks the Restore up in the
   tavern; only unit-tested), engage_tick (46 engagements in m44, judged sensible by m45's Navigator), unfelt-gear
   values (pack churn), blind-cure cap, `ask`/`price` (not used yet).

**The 4 open issues (noted 2026-10-26, not yet fixed):**
1. **A plan `dive` stalls on a quiet level** (m45 00:38-00:46: 'dive 700ft' stuck at one square on a quiet 750 ft
   level, the stuck notices repeated, the quiet-level rule didn't fire; the Navigator's `goal explore` + `plan resume`
   got it moving). Look at the stuck watchdog's second-stall abort and why `TripPlan.quiet` didn't fire.
2. **A Ring of Strength (+2) sold right after identifying it** (m45 01:04): both ring slots hold Protection; for a
   warrior short of blows (2 blows), STR may beat AC -- a judgement the user should make (blows table at STR 18/70
   vs 18/90).
3. **A hot-swap loses the trip's in-memory state**: the "special level: find stairs first" mode (m45 00:33 at 700 ft
   went back to plain exploring) and the mission label (`mission end mNN` by name). Persist both (plan.json / a
   mission file).
4. **No Potion of Speed at the Black Market** twice (m45): the kit's 2-Speed line stays short; the Speed-at-start rule
   rarely has a potion. Options for the user: the cap (450), the Alchemist never stocks it; or accept.

**Routine reminders:** after each piece of work `github/tools/snapshot.sh`, commit, `git push origin restructure`
(the public repo's project/ copy: run at the end of session 6). The user's session-6 decisions: XP_PER_GOLD rolling
(the Pilot's rate overrides the estimator's constant); max_depth 750 trial; Speed kit line (BM, cap 450) and Speed at
a hard fight's start; the tavern stash; Navigator `ask` rate-limited (1/5 min, 4/h) with the Architect answering live;
hot-swaps allowed mid-mission (in the dungeon: in town a swap is a plain restart and loses a running plan town).
**Also open (older):** the Advisor's MIN_GAIN 50 (its own addition, kept); the per-monster asleep flag (proposed);
a fight-vs-flee rule for fast bands with far stairs (m35); the Advisor's structures lattice (needs dungeon_align on);
L3's BLIND half; `Weapons: none` display; Navigator empowerment items not built: executable standing orders, an
item-review queue, dungeon pack control.

### ARCHITECT HANDOFF 2026-10-25, session 6 (details; read the 2026-10-26 section above first)

**Where we are (end of the shadow series, 2026-10-25 ~19:40).** Same SGE job 8268425 on scc-pc4 (to **Thu 10-29
09:47**): test server (freeze build), Dive04's Pilot (git `restructure` at the latest commit, loaded 19:36, **not
pushed**), viewer. Start the inbox watcher (the SessionStart hook's "already running" watcher may belong to a dead
chat: start your own).
- **Dive04:** clvl 27, 326 HP, AC ~77, idle in town, **18170 gold**, **max_depth 750 (trial)**. Scimitar of Westernesse (FA, SeeInv), Leather of
  Resistance, Rings of Protection [+12] and [+10], Amulet of Resist Lightning (redundant: `gear` says so), Metal Cap
  [3,+5], Gauntlets [2,+5]; Staff of Teleportation (6), 25 CCW, 21 Phase, 2 WoR, 3 Heroism; WIS drained. Debts 44 / 0.
  Keeps now: the scimitar, the Leather of Resistance, the staff (the Architect removed the stale Main Gauche/Aspen
  Staff keeps after m38).

**Session 6 (the user: "45-min missions rotating Sonnet/Opus x medium/high for 5.5 hours; fix bugs and small
improvements, no major breaking changes"):** m35-m42 run, all reports in `runs/pilot/dive04/reports/`, summary
**`reports/2026-10-25-shadow-series-m35-m42.md`** (table, by-cell averages, all fixes, open items). Sonnet high best
(87.2, 62.5 XP/dmin), Opus dearer and no better -- confounded (the Pilot changed between missions, n=2). One close
call (m41 afraid; fixed). Brief template: the m42 Agent prompt (state + `gear` line + the verdict list); wrap-up per
mission: `mission end`, `tokens.py`, `scorecard.py --table`, report, complaints.
**Advisor:** reviewed the 19 estimates (memo to_architect 10-25 shadow-review): its pricing caused all 6
disagreements; options_sim **2026-10-25d** (XP_PER_GOLD 1.0 kept -- it briefly set 0.2, then restored the user's
value; staff/scroll 250 g; afraid rule; MIN_GAIN 50) agrees 17/19. Loaded at 19:36.

**Done after the series (the user: "push it, and build the hard-fight estimator"):** pushed (`restructure` 7a18f03);
**shadow mode at the start of hard fights** (`hard_fight_shadow`: berserk_tick's test, once per fight, options fight /
speed / berserk / speed+berserk / phase, rules label berserk|fight; records `trigger: hard_fight`; scorecard `estHF`),
loaded ~19:50; Advisor told (to_advisor 10-25 hard-fight-shadow). Dive04 rarely carries Speed/Berserk, so most
hard-fight records will compare fight/phase only -- stocking Speed is a kit decision for the user. The Advisor
(to_architect 10-25 hard-fight-kit): found Speed pays at the start of hard fights (gain up to a ~200 g price), not at
3000 -- but the Black Market price seen was 383 (m40); its re-run at 383 (to_architect 10-25 speed-383): Speed first
beats the rules in 3 of 4 replays, Speed+Berserk in 4 of 4; break-even ~500 g -> a 1-2 Speed kit line (cap ~450 g)
pays, if quaffed at the start of hard fights.
Slope rechecked (to_architect speed-slope: the rules drink the same Speed later, so price bites on ~0.2 extra potion).
**The user then: "set XP_PER_GOLD rolling, and build both Speed changes" -- built, loaded, pushed (643465e):**
`xp_per_gold()` (XP / gold found+sold over the last 30 active 10-min buckets, rates.json, seeded 0.41 from the
series; fed to the estimator per snapshot; shown by `gear`); kits B/C keep 2 Potions of Speed (Black Market, cap
450); `speed_start_tick` quaffs a carried Speed at a hard fight's start. Advisor asked to mirror it in base_policy
(to_advisor 10-25 speed-built). -> options_sim **2026-10-25e** (to_architect policy-25e): base_policy quaffs Speed then
Berserk at a hard fight's start, PRICE speed 400, the module XP_PER_GOLD only a fallback; with the rules doing it,
choose() keeps the rules in all 5 replays at 0.41. Loaded (Pilot restarted ~22:0x).
**Navigator tools (the user: "build 4, 5 and 6" of my empowerment list; 5512cdc, loaded, pushed):** `why [HH:MM[:SS]]`
(the decision log around the last escape/emergency/trip end: HP, monsters, timeline; a trip ending in the Pilot's
escape now names its trigger); `prep` (the planning report: character, gear review, plan town forecast, affordable
shop stock, XP by depth -- tracked in rates.json "depth", seeded from m35-m42: 600 ft 31, 650 ft 54, 700 ft 125
XP/min over 14 min -- XP per gold, standing orders); **`github/tools/pilot/FIELD-NOTES.md`** (lessons from m24-m42).
HANDBOOK loop step 0 "plan first" and .claude/agents/navigator.md (FIELD-NOTES in its sources, prep in its loop).
**Architect's routine from now on:** after each mission, add the mission's lessons to FIELD-NOTES.md (newest first,
short, with the mission number) alongside the report; briefs start with "plan first: `prep`, FIELD-NOTES.md".
Not built (the user chose 4-6 of 7): executable standing orders, an item-review queue, dungeon pack control.
**Depth (the user, 10-25 late): `max_depth` 750 -- a trial for 2-3 missions, trips 650-750**; then 800-850 if the
lowest HP and close calls hold (650 ft: lowest 36-80%, 1 close call in 8). 1000 ft waits for resist poison (Air hound
packs) or clvl ~30; resist confusion matters from 800 ft (Umber hulks, Hummerhorns). Briefs must say "max_depth 750".
Also set the stale `free_action` order to yes (the sheet's flags win once read; the order is the fallback).
**Checkpoint + Haiku trial (the user, 10-25 23:13):** `tools/harness/charsave.sh save Dive04 dive04-pre-m43` (savefile
+ Pilot state incl. rates/recall -> runs/setpieces/saves/dive04-pre-m43/); m43 = Haiku at LOW effort, 45 min, the
standard brief with max_depth 750. **On death or a permanently bad outcome: `charsave.sh restore Dive04
dive04-pre-m43`** (server-wide state -- uniques killed, shop stock, levels -- isn't rolled back).
**Who acted (the user, 10-25 23:2x; a654037, hot-swapped into m43 at 23:29:48 at 750 ft, viewer restarted):** every
act/goal record has `by` = pilot | plan | nav | arch; the viewer shows NAV>/ARCH> commands (queries left out) and
[P]/[plan]/[N]/[A] tags with a legend; `why` shows them. Records before 23:29:52 have no `by`.
**m43 (Haiku low, 68.8 XP/dmin, $0.019) and the user's m43 notes, fixed (c218514, da5d277, loaded 23:53):** unfelt gear
valued by apply_magic's odds; staffs aren't kit (CLW staffs sold), rod-duplicate staffs sold; Restore drunk at a quiet
moment; blindness cured when it matters; engage_tick (fight a killable monster a few steps off, never over flee/
danger/low HP); `ask`/`answer` (asks.jsonl, 1 per 5 min, 4/h; **the Architect watches asks.jsonl during missions
and answers with `pilotctl answer ID TEXT`**); `price`; buy specs keep [..] commas; 'Staffs' valued; Haiku prices
in tokens.py. **The user then: run low-effort Haiku missions until 01:30** -- m44 from 23:53.
Hot-swap gotchas: the swap loses the in-memory mission label -> `mission end mNN` by name; and a trip's
"special level: find stairs first" mode (m45 00:33: at 700 ft it went back to plain exploring) -- worth persisting.
m44 (Haiku low): 73.2 XP/dmin, $0.017, Nar slain; its `time>00:26` at 23:54 held at once (string compare) -> fixed
(40449f1); live check of the m43 fixes: engage 46x, floor junk 23x (re-sent on empty squares -> once per sighting),
blind cures 16x vs re-blinding Light hounds (-> capped at 2 in 30 s) (37d5601, hot-swapped into m45 00:33).
**Haiku low runs done (the user: until 01:30): m43 68.8, m44 73.2, m45 77.6 XP/dmin at $0.014-0.019 each**, 0 close
calls, no deaths (checkpoint dive04-pre-m43 never needed). Dive04 now: clvl 28, 340 HP, 24901 gold, Battle Axe of
Westernesse (FA, SI) wielded, Scimitar of Westernesse in the pack, max_depth 750. Open from m45: a plan 'dive' goal
stalled ~8 min on a quiet level (the quiet rule didn't fire); a Ring of Strength (+2) sold right after identify
(STR rings vs Protection rings for a warrior short of blows); the hot-swap loses the special-level mode.
**Waiting on the user:** (2) the Advisor's MIN_GAIN 50 floor (its own addition); (3) the per-monster asleep flag (tool-client `look` cycling the server's
look mode, ", asleep" in xtra2.c:3371; ~40 lines C + rebuild + ~60 Pilot) -- proposed, not built; (4) a fight-vs-flee
rule for a fast band with far stairs (m35).
**Open (not yet fixed):** plan town leaves unidentified junk in the pack when the identify budget doesn't cover it
(full pack on arrival, m42); an escape-recall plan end gives no reason in the report; thieves reach us (m41 -1590);
the pack fills ~10 min into long trips; `Weapons: none` after town sales (display); L3's BLIND half; the structures
lattice (CENTRE_X step 33 only with dungeon_align on -- a player option on live servers, so left as is).

### ARCHITECT HANDOFF 2026-10-25 (session 5; history -- read the session-6 section above first)

**Where we are (end of session 5, 2026-10-25 ~13:15).** The chat ended, not the job: SGE job 8268425 on scc-pc4 runs to
**Thu 10-29 09:47**, so a new chat in it finds everything running:
- **Running:** the test server under gdb, port 28346, **the new build with the time freeze** (started with
  `MANGBAND_FREEZE_FILE=$PWD/FREEZE`, operations.md); Dive04's Pilot on the latest code (git `restructure` 33c580e,
  pushed: everything below is loaded); the viewer (`tmux -L mang attach -t watch`; F5/Ctrl-F freezes time). The inbox
  watcher must be restarted in the new chat (SessionStart hook).
- **Dive04:** clvl 25, 310 HP, idle in town, 2998 gold. Scimitar of Westernesse (2d5) (+9,+8) (+1): **Free Action and See
  Invisible**; Staff of Teleportation (10 charges); CCW 14, CSW 4, Phase 19, WoR 2, Speed 1, Heroism 6, Berserk 1,
  Magic Mapping 4, Rod of Door/Stair Location; DEX restored, **WIS drained**; Orcish Shield [5,+4] (disenchanted once).
  Debts: item 44 gold, fight 0 HP. max_depth 650 (deepest 700).

**Next session, start here:**
1. Start the inbox watcher; check the processes (`pgrep -af "gdb -batch|pilot.py"`, `tmux -L mang ls`). If the job died:
   server (operations.md, **with the freeze variable**), Pilot (`tools/pilot/restart.sh Dive04`), viewer.
2. **Proposed, not yet chosen by the user:** run 3-5 missions to collect shadow-mode estimates (scorecard `est` column;
   the Advisor reviews the `estimator` records from m35 on). Keep `XP_PER_GOLD` at 1.0 (the user, 10-25).
3. **Open (todo):** a between-mission **gear optimization step** (the user, 10-25; below); the Advisor's structures memo
   (pits / one-wide hallways); L3's BLIND half; plan town's forecast "at 5" (the shop number reads like a price);
   `Rates:` gold counts purchases; an asleep flag per monster (the estimator's top data gap); an intermittent unit-test
   failure (~1 in 20 runs of `unit.py`, twice, not reproduced since).
   Also open (from m31-m34's reports and complaints): `plan town` replies before its own identify step ends (m32: the
   Navigator's `read Identify` collided with it); a per-level XP rate in the report (the Navigators' "stay or leave"
   question); HANDBOOK additions -- Moaning spirits at 600-650 ft drain DEX and See Invisible counters them; Restore
   Dexterity can be out of stock; `time>HH:MM` needs 2-3 more minutes for the recall and the town visit; short missions
   shouldn't bother with a second recall trip; the TIME FROZEN report (only the briefs mention it so far).
   **Set-piece uniques:** today's runs killed Lugdush, Khim and others; a unique can't be summoned twice, so A2/A2L/A2K
   need other uniques next time (harness README). **Shadow mode** imports the Advisor's estimator live: if its code
   breaks, the Pilot logs "shadow mode off" and plays on.
   **Fixed at the very end (loaded):** the armour upgrade went by AC alone (a plain mail would have replaced the Leather
   of Resistance and its four resists); now armour that loses an ability or resist the worn piece gives isn't worn, nor
   over a worn artifact (the ego table, as for weapons; unit `ability_armour_kept`).

**The user's rules added in session 5 (keep them):** set a Navigator's effort only when the user asks (Agent `effort`);
after every mission: `mission end`, `python3 tools/observe/tokens.py mNN`, `scorecard.py --table`, a report in
`runs/pilot/dive04/reports/`, complaints and `?` notes; **the time freeze is a testing tool, never part of a decision**
(everything must work on live servers); Pilot changes may be loaded mid-mission with `tools/pilot/hotswap.sh Dive04`
(tested: H1, H1r); don't restart the Pilot during a matrix unless the user asks or a bug is breaking.

**Session 5 in brief** (details in the 2026-10-24 section below, under "Session 5"):
- **Missions:** m29 Opus/high 71.3 XP/dmin (best); m30 Sonnet/high 46.9 (one close call, 38%); **baseline matrix m31-m34**
  (30 min each: Sonnet medium 24.5, Opus high 31.1, Opus medium 53.5, Sonnet high 15.8 XP/dmin; cost per mission
  $0.13 / $0.85 / $0.43 / $0.15) -- `runs/pilot/dive04/reports/2026-10-25-matrix-m31-m34.md`. Efforts so far: Opus
  defaults to high, Sonnet to medium.
- **Pilot fixes, all loaded:** stairs beside a harmless mold (M1); loot passed up / devices within 30 (M2); provisions (one
  food, no oil; eat and fuel in town); Speed first in emergencies, Teleport one turn from death; Berserk in hard fights;
  Boldness sold, fear cure Heroism > Boldness > Berserk; the m30 stall loop; leave after an unseen drain (M3); `band`
  condition only while live; town makes pack room; `plan resume`; item replies `DONE:`; the cave run loop; ability
  weapons never swapped for damage; bands by expected fight cost, weak drainers fought; quiet levels left;
  disenchanters fought only when in the way; a flee with no known path reads Magic Mapping; the Advisor's four rules
  (no resent recall/teleport, no second escape in flight, kill a quick caster, teleport over phase in a crowd, no HP cure
  with 2+ adjacent); a pending recall survives a Pilot restart; emergency records carry a 21x21 map; **shadow mode**.
- **Tools:** `tools/observe/tokens.py` (Navigator tokens and cost at list prices per mission; scorecard `usd`, `usd/dh`,
  `usd/kxp`, `gold/usd`, `est`); `tools/freeze.sh` (+ server `time_frozen`, Pilot holds); `tools/pilot/hotswap.sh`;
  `tools/pilot/shadow.py`; set-pieces M1-M4, H1, H1r (harness README).
- **Advisor:** memos 10-25 estimator, replay, shadow-policy. Shadow mode imports `Advisor/data/estimator/options_sim.py`
  live (`POLICY_VERSION pilot-escape-2026-10-25b`): tell the Advisor whenever `escape()`, `berserk_tick` or `fear_cure`
  change, so its base policy stays in step.

### ARCHITECT HANDOFF 2026-10-24 (history; read the 2026-10-25 section first -- session 5's details are in here)

**Where we are (end of session 4, 2026-10-24 09:40): the RESTRUCTURE, steps 1-4 done, step 5 (missions) under
way: m25-m28 run.** On 2026-10-22, after mission 23 (which the user ended: "you're fired"), the user decided to stop
patching per mission and restructure the Navigator/Pilot system: **restructure, not rewrite; keep Dive04; instruments
first.** Missions run only when the user asks for them.

**Next session, start here:** (1) restart the four processes on the new node (below); (2) the question left open
for the user: keep running 40-min missions, alternating Sonnet and Opus on the same Pilot (now that both run the
same code, the comparison means something: m28 Sonnet 58.8 XP/dmin vs m27 Opus 30.1, but m27 started broke);
the m29 brief is m28's with the current character state, `--hpwarn 5`, mission markers, an emergency Monitor, then
`scorecard.py --table` and a report in runs/pilot/dive04/reports/. (3) Open, not requested yet: the Brown mold
beside the stairs (m25 loop); the Advisor's structures memo (lattice/ring geometry, an asleep flag in the monster
list); L3's BLIND half; a fair model comparison (same starting state). Read runs/complaints.md after each mission.

**Session 5 (2026-10-24 19:57-, job 8268425 on scc-pc4, walltime Thu 10-29 09:47):** the four processes restarted
on scc-pc4. **m29 (Opus, 20:12-20:48, m28's brief):** **71.3 XP/dmin** (best yet; m28 Sonnet 58.8), 39.6 gold/dmin,
lowest 57%, 0 close, 3 escape recalls, 7 cures; clvl 25, 5621 gold, Golfimbul slain; report
`runs/pilot/dive04/reports/2026-10-24-mission29.md` (complaints: shop buy takes the cheapest name match; no light
wielded but status showed one; leaving 650 ft = max_depth with only '>' known searched 6.5 min for '<' without Magic
Mapping). **The user's `?` (m29 20:26): items and gold left behind** -- loot is off while any monster is in view and
never revisited beyond loot_radius 10; under a plan the interesting-item pause doesn't happen (the notice says it
does). **Fixed (the user: "fix the loot issue", 10-25):** one shared `loot_step` for dive and explore: items
within loot_radius; items passed up while a monster that matters was in view (within 10 levels of ours or dangerous;
weak ones and molds don't count; a band does) fetched within 25 once clear; devices/jewellery within 30; a walk cut
short is retried (3 tries; the old code marked the square looted when the walk began); the interesting_item notice
says the Pilot fetches those. Unit `loot_owed_and_valuables`; live set-piece **M2** PASS (after 3 fixes it found);
M1 still passes. HANDBOOK updated.
**m30 (Sonnet at HIGH effort, the user; 06:11-06:45 10-25):** 46.9 XP/dmin, lowest 38% (1 close call: a mixed crowd
at 650 ft, fire burned WoR), $0.56; two DEX drains (dart trap on arrival; an unseen wailer, likely a Quasit, as in
m29); a 6-min stall beside a '>' refused as "just fled"; the `band` condition fires on weak bands; plan town can't
make pack room. Report `reports/2026-10-25-mission30.md`. Not yet fixed: all of these (listed to the user).
**Provisions (the user, 10-25: food AND Satisfy Hunger, oil by the handful, potions never used):** one food
source (rations); plan town eats rations to Full (no digestion in town, dungeon.c) and fills the lantern to 9000+
(FUEL_TOPUP; flasks bought only for that), kits carry 3 rations and no flasks; other food, surplus flasks and the
unused Treasure/Object Location staffs are sold (USEFUL_DEVICES keeps only Door/Stair Location); near a trip's end
(`trip_minutes_left`: recall pending, or <=3 min, or <=20 while Full) spare rations/flasks go first for room.
Unit `provisions_one_food_no_oil`; live plan town: pack 18 -> 10 slots. Proposed, not built: Speed in emergencies,
one fear cure (Heroism; sell Boldness/Berserk).
**Fixed 1/7, the m30 stall:** a dive refusing the '>' back to a fled level started `explore until stairs`, which
ended at once on that same '>' (a silent loop, 5 min); Explore now skips the dive's refused stairs
(`Explore.skip`, `Dive.refused`, unit `refused_stairs_dont_end_explore`), and the 2-minute stuck watchdog ends a
goal on its second stall (`goal.abort`) instead of restarting it again.
**Fixed 2/7, the unseen drainer:** both DEX drains (m29, m30) were a Moaning spirit (invisible, PASS_WALL,
+10, TOUCH:LOSE_DEX). A STR/DEX/CON drain with no drainer in view and no trap message now leaves the level (the
plan's drainer leave; without a plan, Flee). Unit `unseen_drainer_leaves`; live set-piece M3 PASS.
**Fixed 3/7, the `band` condition:** it counted any band ever warned on the trip; m30's beaten Novice warrior
band ended the trip 3 min later on a new level. Now it holds only while the band is live (`band_live`: warned <20 s
ago on this level, or 3+ monsters within 10). Unit `band_condition_only_while_live`.
**Fixed 4-7/7:** plan town makes pack room before a buy needs a new slot (`town_make_room`: sells/destroys the
cheapest unprotected item; unit `town_makes_room_before_buying`); `plan resume` ends the Navigator's goal and hands
back to the paused plan; item commands reply `DONE: <item> (N -> M left); moved ...` (m30's `read Teleportation`
worked but looked like it hadn't: both scrolls used); HANDBOOK: plan resume, item commands and `goal shop sell`,
the `band`/`drained` condition caveats. **All 7 m30 items fixed (2026-10-25).**
**Potions (the user, 10-25):** an emergency quaffs Speed first, unless one turn from death (adjacent worst turn >=
90% HP): then Teleportation, else Phase Door; Berserk at the start of a hard melee (a unique or a monster within
5 levels adjacent, or 2+ adjacent under 75% HP); Boldness no longer kit (Heroism covers it; sold). Haste/hero/
berserk tracked from the game's messages (`buff_on`: the status had no indicator, `flag("fast")` was always
False). Unit `emergency_speed_first_berserk_hard_fights`; live A1, A2L PASS (A2L: Speed at 4.3 s, Berserk 6.9 s).
The user's idea of a danger-time option estimator (simulate options, take the best; real time under hpwarn): asked
the Advisor (to_advisor 10-25 emergency-estimator).
**Fear cure order (the user, 10-25, during the baseline matrix m31-m34):** Heroism, then Boldness (only without
Heroism), then Berserk (`fear_cure`; unit `fear_cure_order`). **Committed but NOT loaded: the user said not to
restart the Pilot during the matrix; restart it after m34.**
**Cave run loop (m31, 07:49-07:57):** explore's free runs looped 157x through a cave corridor (the server's run
followed it back to the start; 'moving away' is straight-line). Fix: `Mover.run_loop` -- two free runs from one
square within a minute -> walk from it (unit `run_loop_walks`). **Committed, NOT loaded** (asked the user whether to
load it mid-matrix; no answer yet). m31 report saved.
**Time freeze (the user, 10-25):** built, **not deployed** (the matrix runs on): server `time_frozen` in
net-server.c (file `testserver/FREEZE`, only with `MANGBAND_FREEZE_FILE` set), Pilot `world.frozen()` (clock factor
~0, the Pilot holds, report says TIME FROZEN), `tools/freeze.sh`, viewer F5/Ctrl-F. The binary is rebuilt
(`github/mangband`; the old one kept as `testserver/mangband.prefreeze`); the running server is the old one. **After
m34: restart the server with the variable (operations.md), the Pilot (loads fear order, run loop, freeze) and the
viewer; test the freeze live.** -> **Deployed after m32 (the user: "after this mission"), 08:34-08:36:** the first
live test let one queued step through (post_process_players runs commands as they arrive, with stored energy);
fixed, rebuilt, restarted; live: a step sent while frozen waited 5 s and ran at the thaw. m33-m34 run on the new
server and Pilot (fear order, run loop, freeze); m31-m32 ran on the old ones.
**TODO (the user, 10-25): a between-mission gear optimization step.** After each mission (and before the next), go
over Dive04's gear as a whole: wear/wield by abilities and resists, not damage alone (m32: the Pilot's weapon policy
compared 28 vs 30 and never flagged a Scimitar of Westernesse with Free Action and See Invisible; the Navigator
wielded it by hand); spares worth keeping or selling; what to buy toward the next upgrade (Free Action, See
Invisible, resists, a better weapon, a launcher for the empty bow slot); standing restores (Restore Dexterity was out
of stock in m32 -- buy when it comes back). Who runs it (the Pilot's policy, a `plan gear` step, or the Architect
between missions) is open.
**Hot swap (the user, 10-25: "with the freeze we can deploy Pilot changes whenever"):** `tools/pilot/hotswap.sh NICK`
-- freeze, stop the Pilot at once (no park: a frozen Pilot never reaches its safe moment), start the new one, wait
for it to answer, thaw. Why it should be safe: an orphan is freed after 15 s idle by a timer in the game tick, which
the freeze stops, and a login before that resumes the character in memory. **Not tested yet** -- test after the
matrix in a dungeon set-piece (in town orphans are freed at once): monsters near, a trip plan running, a recall
pending (park avoids logouts during a recall: "a logout reset its depth once"); check Dive04 resumes in place, the
plan resumes, nothing acted meanwhile, and whether logins wait for the thaw.
-> **Tested (2026-10-25 11:00-11:20): set-pieces H1 and H1r PASS.** The swap takes ~4 s, all frozen; logins work while
frozen (no wait for the thaw); Dive04 resumes in place (same square, HP, monsters); the plan resumes and acts 0.4 s
after the thaw. **H1r found a bug, fixed:** a pending recall survived in the game but not in the new Pilot's memory, and
the resumed plan read a second scroll, cancelling it -- now kept in `runs/pilot/NICK/recall.json` (`recall_memory`).
**Hot swap is now the way to load Pilot changes mid-mission** (`tools/pilot/hotswap.sh Dive04`).
**Estimator memo (the Advisor, 10-25): the user approved its calibration replay; no time freeze per decision (it must
work live).** Its four rule fixes, built and loaded 11:40: Word of Recall and Teleportation never resent (8 s for an
answer, then give up); the Navigator's second escape within 3 s refused (`force` overrides); an adjacent summoner or
status caster that dies in 2 rounds is attacked first (`kill_caster_step`); Teleportation (scroll, or the staff) over
Phase Door with 4+ about in the open; with 2+ adjacent no HP cure (read an escape; blind/confused: cure that first).
Emergency attention records now carry a 21x21 remembered map (`map21`, `map_at`, `mons`) for the replay. Unit
`estimator_memo_rules`; live A6, M4 PASS, but no live emergency reached the new rules (the Pilot beat or escaped
the staged crowds first).
**Shadow mode (the user, 10-25; the Advisor's replay memo):** `tools/pilot/shadow.py` -- at each emergency decision the
Pilot hands a snapshot (HP, buffs/status, weapon profile, consumables, stairs distance, pending recall, the monsters in
view and those only in the server's list at 3 squares) to the Advisor's `options_sim.choose` (n=40) in a background
thread, imported from `Advisor/data/estimator` (the Advisor owns it: keep its base_policy in step with the Pilot's
rules); never waits, never acts. Logged as `estimator` records: rules vs choice, `agree` (None when it knew no
monster), compute_s, `in_time_turn` (within one player turn at the decision's time factor) and `before_next_act`;
the emergency record says `shadow: started|skipped|off`. Scorecard: an `H estimator` line and an `est` column.
Unit `shadow_estimator_logs`; live A2K: 1 estimate, agreed, 0.012 s (its fight was empty -- Khim in the server's list
only -- hence the listed-monster fix). Run 3-5 missions, then compare.
**Baseline matrix done (m31-m34, 07:42-09:29):** summary `runs/pilot/dive04/reports/2026-10-25-matrix-m31-m34.md`.
Cost is clear (Opus high $0.85, Opus medium $0.43, Sonnet $0.13-0.15 per 30 min); XP (16-54/dmin) is dominated by
level luck and Pilot problems at n=1 per cell, with the Pilot changed after m32 and Free Action + See Invisible found
in m32. Breaking fix between m33 and m34: an ability weapon is never swapped for damage (`weapon_abilities`).
Next Pilot fixes from the matrix: weak drainers / weak bands make the plan leave; slow quiet levels; meleeing
disenchanter molds beside the path; recall arrival fights before locating stairs. Dive04 now: clvl 25, 310 HP, 2998
gold, Free Action + See Invisible, DEX restored, WIS drained, Staff of Teleportation.
**Matrix fixes done (the user, 10-25, in order; loaded 10:27):** (1) bands judged by the expected cost of fighting
them one by one (`band_cost`: rulebook melee_exp at our AC x speed, quickest kills first, 8 at once in a room, 2 in a
corridor; serious above 50% HP or a dangerous member) and weak drainers are news, not a leave; (2) a level under 10
XP a minute over 3 minutes is left (`TripPlan.quiet`); (3) disenchanters fought only when in the way; (4) a flee
with stairs known but no known path reads Magic Mapping first. Units 38-41; live A1, B2, M1, M2 PASS.
**The Brown mold (m25) fixed:** `stairs_beside_still` -- stairs underfoot or a step away beside a stationary monster
harmless for a turn (no drain/paralyse/disenchant, melee < 25% HP) are taken, not stepped away from; Dive presses '>'
only on its stairs (a step-away's "arrived" pressed it 6 squares off). Unit `stairs_beside_mold`; live set-piece
**M1** (a mold summoned beside a painted '>') reproduced the loop, then PASS (8.7 s).

| doc | what |
|---|---|
| `restructure.md` | **how to revert** to before it (tag `pre-restructure` = 767bf60; saves and non-git files in `runs/backup-pre-restructure-20261022/`). Only on the user's request |
| `restructure-step2.md` | the step 2 design (who decides what), agreed with the user; decisions in its §6 |
| `memos/2026-10-19-starting-over.md` | the Advisor's reflection the plan comes from |
| `memos/to_advisor/2026-10-22-restructure-plan.md` | the plan as sent to the Advisor |

**Git:** all work is on branch **`restructure`** in `github/` (pushed to GitHub, userjjb/Mangbot); `master` stays at
the tag. Push after each piece of work (`tools/snapshot.sh`, commit, `git push origin restructure`).

**Was running (job 8181626 on scc-pe7, ENDED Sat 10-24 09:50; all of it stops with the job):** the test server under gdb (`testserver/`, port
28346, with the 10-17 store patch), Dive04's Pilot, the user's viewer (`tmux -L mang attach -t watch`), the inbox
watcher. A new node means restarting all four (commands in the 2026-10-08 section and `restructure.md`).

**Dive04 now (after m28, end of session 4):** clvl 24, 288 HP, in town, ~4057 gold, CCW 8, CSW 4, Phase 18,
**WoR 2**, food 8; DEX restored, WIS drained; max_depth 650 (deepest 700; the recall inscription keeps @R650);
Rod of Enlightenment sold (the user: a crutch); Staff of CLW sold. **No Free Action.** Navigator debts 0. The Pilot
on the new node: `tools/pilot/restart.sh Dive04` (`--hpwarn 5` is the default; don't pass `--live` on the test
server). Last commit on `restructure`: 37cbfac (pushed).

**Restructure steps:**
1. **Instruments: done** (to the Advisor's `memos/2026-10-23-scorecard.md`). `tools/observe/scorecard.py` (`--table`,
   `--check` against the Advisor's baseline: matches), `shopmath.py` (exact fair pay from the source),
   `runs/missions.json`. New logging: numbered reports + `report_age` on every command, `sale`, `itemlist` /
   `left_behind`, `escape`, per-check state in audit_check, the tracked monster's health bar, `mission_start/end`.
2. **Who decides what: in progress.** 2.1 **done**, the Pilot's item policy: `tools/pilot/itemvalue.py`
   (object_value_real + the rulebook; 37/38 past sales matched), Navigator item commands refused in the dungeon,
   value refusals with `!` override → **the Navigator's debt**, `keep`, Free Action inferred from "You are
   unaffected!", pickup by value (unique drops always; use a flask/ration, then destroy the cheapest non-kit item),
   no loot after a `band`, a policy step at safe moments (identify, wield/wear upgrades, jewellery), gold within 10
   when idle. **2.2 the town kit: done (session 4):** `plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@MAX],...]`,
   the `TownKit` goal in pilot.py: upgrades, sells by policy at the shop that buys (store.c store_will_buy; best
   payer by owner), buys + reads Identify for unknowns worth more than a scroll, sells again, then buys by tier (WoR 2,
   gate minimums, Restore STR/DEX/CON and quaffs it, the kit, the Navigator's list), one more look after 40 s for a
   missing essential. Prices and owners remembered in `runs/pilot/NICK/stores.json`. Tested live on Dive04 (sold Main
   Gauche 79 + Staff of Treasure Location 111; bought WoR, CSW, Phase, flasks, Restore CON; identified cloak and
   boots). Fixed on the way: reading Identify without a light at night (it now lights up, 3 tries per item);
   itemvalue missed the feeling in `{good - Brodda, the Easterling}`. HANDBOOK section "Town: plan town".
   After the Advisor's rulebook-r3 memo: never-sell devices widened (escape, travel, detection, mapping, Perception,
   Stone to Mud, healing), Restore Charisma as tier 6 (3 -> 4 only, ~125 gold a mission). **Rulebook release 3
   synced** (drops.csv, drops_by_depth.csv: drop expectations per monster; feelings.csv fixed); drops not used yet
   (candidates: hunt vetting in 2.4, loot value). **2.3 the trip plan: done (session 4):**
   `plan trip LO-HI [until "COND or ..."] [then recall|town] [level_min=N] [force]`, the `TripPlan` layer in pilot.py
   (above the goals: reflex goals replace a plan goal without ending the plan; a Navigator goal pauses it; saved in
   `runs/pilot/NICK/plan.json` across restarts). Down by stairs near town else WoR (Recall now takes a depth); explore
   each level until done or level_min, then the next (down while above HI, up one at HI); leaves at once for band
   (Flee), pit/nest, breeders, STR/DEX/CON drainer, fearer, trap-laden; home when a condition holds (stairs from
   <=150 ft, WoR after 3 min without a way up; else WoR), `then town` runs plan town. While a plan runs, the events it
   handles are news (PLAN_QUIET); idle recall is off (90-min cap built in). Tested live at 50-150 ft (two trips: 1
   and 4 levels, home by the stairs, a restart mid-climb resumed). **Cost of the test: a dart trap at 50 ft drained
   Dive04's STR 18/50 -> 18/40 (still 3 blows); Restore Strength ~480, Dive04 has 190 gold.** **2.4 order checks: done
   (session 4):** hunts vetted (`hunt_refusal`: the Advisor's rating AVOID/LEAVE, paralysis without Free Action,
   pessimistic loss = 2x turns to kill with spells at max > 60% HP, breath > 60% HP, a band about; the m19 Ranger and
   m22 Boldor are refused, frogs/orcs/wolves allowed; the Hill giant (rated FIGHT) is refused at 265 HP: maybe too
   strict). New goals `fetch Y,X` (refused with a band or danger) and `leave`. Stale orders held (`stale_order`:
   position orders after a level change, hunts of monsters out of view with a report >5 s old, goto/fetch after HP
   fell >25 points). Override with fight debt (the user's answer, below). The Advisor's answer (to_architect 10-24 hunt-strictness):
   the doubling was the problem; now its **duel simulator** decides (`fight_sim.py` + `monsters_raw.csv`, synced by
   `sync.sh`; `Pilot.fight_sim` at the live profile, p90 loss > 60% HP refuses), plus a **summoner rule** (only if p90
   <= 30% HP, HP >= 80%, alone, 5+ Phase) and a **blinker rule** (Hunt gives up if the target blinked and isn't reached
   in ~2.5 s). The user's answer on the memo's "don't quaff
   while closing in": **rest is free, spend resources only when turns matter** (notes_players.md): after a blinker
   escapes, the `Reprieve` goal flees if mortal danger is near, else steps out of sight and rests. Audit of m17-23
   spends: the cure reflexes mostly follow it already. Set-pieces A7 (Hill giant at 60/80/100% HP) and A8 (Ranger replay) will test it. Hunt override built (`goal hunt !NAME`, `settle_hunt`: wrong = not slain / HP < 50% / an emergency; fight debt in
   HP, `debt` shows both). **2.5 belief state: done (session 4):** `belief_tick`/`belief_lines` add to the report
   `Out of view` (monsters seen in the last 2 min on this level, last position; uniques and dangers first), `Fight so
   far` (hits x damage per hit vs the rulebook's HP, the health bar), `Rates` (HP lost in 10 s, XP/gold per 10 min),
   `Counts` (drains, traps, searches here; emergencies, phases in 90 s), `Standing` (keep, avoid, and the new
   `standing TEXT` instructions in runs/pilot/NICK/standing.json). Tested offline (stub world) and in town; the
   dungeon lines not yet live. **2.6 the new toolset: done (session 4):** `HANDBOOK.md` is now the
   ~110-line Navigator handbook (who decides what, the plan loop, commands, judgement calls, the deadly few); the old
   one is `HANDBOOK-reference.md` (search it, not required reading). `goal goto`, `stairs`, `raw` are refused to the
   Navigator (the Architect keeps them); the Pilot's hints point at `goal leave` / `goal fetch`. navigator.md updated
   (sources, loop, urgent alerts, debts in the report; backup of the old one in the session scratchpad and in git's
   project/ snapshot). **2.7 done: mission 24** (Opus, 40 min, 12:24-12:58; report
   `runs/pilot/dive04/reports/2026-10-23-mission24.md`): no close calls, lowest HP 58%, 1 cure, debts 0, but XP low
   (0.56 lv/dh; trip 1 recalled onto an orc-pit level and spent both WoR in 3 min, so trip 2 was a 300-400 ft stairs
   trip). Navigator commands 1.5/min (m23: 6/min). Fixed after it: bands serious only at >= 30% of current HP worst-
   case or with a dangerous member (weaker are fought and looted; the user's `?`); dark inner rooms get an avoid zone
   on their ring (the user's `?`: surrounded in the pit's ring corridor); the plan waits for a pending recall instead
   of a new dive; `plan trip ... via=stairs|recall` and a gate that matches it; town Identify only at >= 2x the
   scroll's price; the report says why the light is off in town. Open from m24: `Rates:` gold counts shop spending;
   latency.py counts plan news as alerts; a recall-arrival fallback when the first landing is bad (the Navigator's
   problem 3). The Advisor's m24 answers (to_architect 10-24 m24) built: the **arrival protocol** in the trip plan
   (Door/Stair Location after a recall or on a "special" feeling, then explore until stairs on a special level), its
   **depth band** advice in the HANDBOOK (work 500-650 ft: 58 XP/min vs 8.5 at 300-450), plan news tagged
   `source: plan` (latency.py skips it), the hunt veto skipped where the Advisor's `veto_reason` column says "strength"
   (synced 10-23: Brodda and Ulfast now go to the simulator; Wormtongue/Boldor stay vetoed); the scorecard counts
   plan news apart (`plan_news`). **Step 3, the rulebook, done (session 4):** the Pilot now runs on the
   Advisor's tables instead of its interim ones. Monster ratings, speed and melee come from `rulebook/monsters.csv`
   (`glyphs.load_rulebook`: all 616 races; only 5 differ at level 40 or below, 3 re-rated 2 -> 3). Junk kinds come
   from `kinds_by_level.csv` (the same 38 as kinds.csv). Jewellery of a known kind with unknown plusses is valued from
   `jewellery.csv` (E[value], P(cursed copy) ~45% for plussed rings; known=False, so never worn unidentified). The
   ability proofs come from `abilities.csv` (`ABILITY_PROOFS`: rBlind, rNexus, hold life, sustains, feather fall as
   well as Free Action). Shop pay is per shop and owner (`Pilot.pay_cut`, from shopmath: six recent sales exact)
   instead of SHOP_CUT 38%. `monster NAME` shows the hunt verdict and the expected drop (`drops.csv`); `pilotctl rule
   ...` queries the rulebook (rule.py synced). The Recall goal rests while it charges when hurt and alone (time 10x
   while resting). Fixed on the way: the Shop goal called `self.iv` (a crash when a forced sale had no re-listing).
   **Step 4, the harness: built (session 4)**, `github/tools/harness/` (README.md):
   the tool client's `interactive`/`keys`/`special` verbs drive the DM menu; `dm.py` scripts Gandalf (summon a race
   at a square, invoke a player, descend/ascend, hooks always cleared); `charsave.sh` snapshots/restores a character
   around a run (**waits out the 15-s orphan timeout: see operations.md**); `setpiece.py` runs **A7, A8, A8o, A9:
   all PASS** (`runs/setpieces/results.md`); `unit.py`: 10 unit set-pieces, all pass; the Pilot logs status/pack/map
   replies thinned to `state.jsonl` (replays). Found and fixed: no light after an unexpected recall (A7 fought in the
   dark), Satisfy Hunger never eaten (went Weak, recalled with 4 scrolls). A8o showed the danger rule reading WoR at full
   HP on sight of a summoner with no stairs known; **the user: walk away if we just walked into its sight, other
   action only if that isn't safe**: the `WalkAway` goal (A8w passes; it needs walked ground, so after a recall or
   teleport arrival the escapes still apply). **Batch 2 (session 4): A1, A6, A2 (Ulwarth), A2L
   (Lugdush), C3 (Ulfast) all PASS**; C8 not stageable (the Forge's items come out identified; covered by the unit
   test). Fixed from it: a simulator danger reason (average loss > 80% HP: Lugdush, Ugluk), strength-only ratings
   left to the simulator in the danger rule too (Ulfast), hunts refused when their average loss ends below the
   emergency rule's 2.5 worst rounds (Ulfast; the Hill giant from 80% -- a change to the Advisor's A7 criterion,
   asked), confusion not cured against visible weak monsters (C3 spent 6 potions), a unique's drop fetched after a
   hunt. Staging facts in the harness README (repeat unique kills drop nothing; escorts; levels persist; depths
   rotate). The Advisor's answer (to_architect 10-24
   emergency-threshold, rulebook r4 synced): the emergency rule and the hunt check now use the worst melee in 3 turns
   at our AC (`Pilot.worst_3turns`), not 2.5 raw worst rounds; uniques already killed are refused as hunts
   (`uniques_killed.json`). **Batch 3: A3, B1, A7 rerun: PASS; C4, C5 as unit tests (14 unit tests pass).**
   Batch 4 (the Advisor's fleehp-live memo): B2, B3, L1 (boulders do
   0 damage: confirmed live) PASS; D6 FAILS: walking is ~1.5 tiles/s, and **server pathfind counts as running (time
   x5 with nothing in sight) but the mover never uses it**: a 3-5x explore speed-up queued; L2 (recall 10x sooner
   while resting) still open. Unit: C1, C2, C6, C7 (new guard: the Navigator can't wear unidentified jewellery), C9,
   E1, F1 (21 unit tests). **Open question for the user:** flee_hp 0.4 only in vetted solo hunts (the Advisor; 0.5
   elsewhere). **The time bubble: built (session 4).** A game clock (`world.gnow`, factor 1/5 below
   hpwarn x 10% HP, set each tick) for every Pilot/World/mover timer; logs and displays stay wall-clock (`_lt`,
   `wall_of`); `pilot.py --hpwarn N` (default 0; `PILOT_ARGS` in restart.sh/charsave.sh; `setpiece.py --hpwarn`).
   Regression A7 on the clock: PASS. A/B: A2I with hpwarn 5 entered the bubble (51% HP, factor 0.2 for 2.4 s until the
   recall) and behaved (1 Phase, no doubled reads, lowest 51%) vs A2/A2K without (45-48%, 2 Phase, 4-5
   emergencies): one run each, so a smoke test, not proof. (Decided 2026-10-24: missions run with --hpwarn 5.)
   Staging note: a unique exists once, so repeat set-pieces rotate uniques (A2I Ibun, A2K Khim).
   **Batch 5 (session 4, evening):** the **pathfind speed-up** is in (mover.py `path_run`: server `pathfind` for legs of
   4+ steps with nothing in view; D6 PASS, 3.2 tiles/s overall vs 1.4; the Advisor's ceiling estimate is 3-4 after
   stops at new rooms). A3 restaged with a Sabre-tooth tiger (the Wolf chieftain brings 38 wolves): PASS. **`dm.paint`**
   (the DM's Build page; Gandalf sees the whole level) builds scenes: **D3** (a carved pocket behind a secret door)
   found 3 Pilot faults, fixed (walled in with known ground out of reach -> search the dead ends; Search counts doors;
   a refused run made the next step time out; searches paced at a player turn); 5/6 PASS. **B4, B4w** (town thief),
   **B6** (pit on the line), **A7f** (fear casters: Boldness at once) PASS as built. **A5/A5s** (unseen caster):
   the rule fled down known stairs at any HP above think_hp; now news only above 80% unless it may be a paralysing
   gaze (unit test; 22 unit tests). **A4** (Wormtongue) not stageable while he lives on another level. Still open:
   L2/L3 (need forging: asked), D4 inner room (paintable), B5, A10, A11, D7 (level import?). **Next:** step 5 missions,
   (no open questions left from batch 5). **Decided (the user,
   2026-10-24): missions run with `--hpwarn 5`**, now the Pilot's default (HANDBOOK tells the Navigator); A2I and A1
   pass with it.
   **The game clock, measured (session 4, late; the user: it must work on live servers, no server change):** the
   worn light's fuel is a per-player game-tick counter (one turn of fuel per tick of our bubble), resent by a free
   redraw. `world.py`: the model is now the server's whole rule (town 1; nothing in sight: resting 10x, running
   5x while actually moving; HP bubble 1/5), the fuel rate overrides it while resting/running (other servers'
   constants, other players' bubbles) and checks it otherwise (normal play measures 0.85-1.0: TICK_S 0.625 s is
   right). Network waits now need the time on both clocks (`waited`, `ghold`): busy windows, read/quaff
   confirmation, store replies, stairs pending, the mover's step/run timeouts, world's polling of our own client
   (in the HP bubble it polled the map only every 2.5 s: fixed). Unit `game_clock_from_fuel`; live D6, A3, A9,
   B3 PASS after it. Not yet seen live: a long rest measured at ~10x (rests so far were 2-3 s, too short to
   measure; the model covers them). **Then L2 measured it (fuel every second):** resting ran at 1x for 6 s and
   the recall took ~25 ticks (15-16 s): the server's speed-up needs no awake monster in line of sight, seen or not
   (`monsters_in_los`), and after a fight there usually is one in the dark. So the model now leaves the speed-ups
   out (1x, or 1/5 in the HP bubble, also when resting hurt); the fuel raises it only when it sees one. (A model
   running fast where the game doesn't ends game timers early: a recall "overdue" and read again cancels it.)
   The server doesn't answer a redraw while resting: a rest is measured when it ends.
   **Decisions (the user, 2026-10-24): flee_hp stays 0.5 everywhere; the forge may be used for set-pieces.**
   **Step 5 started (session 4, 02:10-03:25):** m25 (Opus, 40 min): 10.9 XP/dmin, lowest 63%, 22 min walking down
   (loops fixed live: explore runs with a radius, stair-scum on kept levels, stairs straight back into a fled level,
   a free-run crash, pickups that stack). m26 (Sonnet, 40 min): **53.0 XP/dmin** at 650 ft but lowest 14%, 6 escape
   recalls, 14 cures, broke at the end (14 gold, 0 WoR). Fixed after them (reports in runs/pilot/dive04/reports/):
   Satisfy Hunger only when Weak (it fills to just under Gorged; the next potion made m26 Gorged at -10 speed in its
   worst fight), rations in the kit; group danger and the 3-turn worst case scaled by our slowness; a Speed potion
   when slowed in a fight; afraid among 2+ attackers counts as danger; no stairs-underfoot bouncing with nothing in
   view; far stairs with danger beside us -> recall at once; an upgrade pass after town Identify (a [+12] ring was
   sold); buy NAME:N = have N; Restore Charisma only with 3000+ gold; spare lights/food can make room; multi-word
   item names; time conditions to the second; identified plain unique drops sell; blindness cures only when it
   matters; **a band with no stairs known at high HP locates stairs or walks away before Word of Recall (the user)**.
   Gandalf reset the player counts on 50-650 ft (Unstatic): the set-pieces had left levels the server kept.
   **Decisions (the user, 2026-10-24, later): `auto_scum` stays ON (lib/user/options.prf; it rerolls levels below
   500 ft until special or rich: the Advisor's structures memo); m27 (Opus) starts from a kit forged to m26's start.**
   The Advisor: m26's Nar group was a summon trap, not a pit (now: Phase Door at once on "enveloped in a cloud of
   smoke"); arrival feelings are logged per level. Stationary monsters are remembered on the level (the drain zone).
   **m27 (Opus, 04:19-04:50, kit forged to m26's start, auto_scum on):** 30.1 XP/dmin, lowest 47%, 1 escape recall,
   3 cures (m26 Sonnet: 53.0, 14%, 6, 14 -- but on the Pilot before m26's fixes). Reached 700 ft (deepest.json now 700;
   the recall inscription keeps @R650). Fixed after it: climbing back to max_depth isn't "straight back"; `goal shop
   buy NAME:N` = have N (`+N` more); plan town saves gold for a short Word of Recall and sells unknown devices when
   broke; interesting-item notices give squares. Dive04 now: 30 gold, WoR 2, CCW 4, CSW 3, DEX/WIS drained.
   **m28 (Sonnet, 05:18-05:52, current Pilot, 4089 gold from the sold Rod of Enlightenment):** **58.8 XP/dmin, 43.3
   gold/dmin, lowest 45%, 0 close calls, 3 escape recalls, 3 cures** -- the Advisor's target at m27's safety. The best
   mission yet. (m27 Opus on the same Pilot: 30.1, but it started broke.) After it: identified junk (Haste Monsters,
   the `junk` list) is autodestroyed. **The user (2026-10-24): sell the Rod of Enlightenment (a crutch); `pilot.py
   --live` (default off) switches test/live behaviour: on test, mapping/detection devices are sold; keep the gold.**
   **Session 4 ended 09:50 with no mission running**; the user set `idleCompaction: false` in ~/.claude/settings.json.
   **Open:** ranged stationary drainers (fixed: it was adjacency out of view); pits/structures (the user: a one-wide long
   hallway is a giveaway; asked the Advisor); the Brown mold beside the stairs (m25); a fair model comparison needs an
   Opus run on the current Pilot from a similar state (Dive04 is broke now: 14 gold, 0 WoR, DEX/WIS drained).
   The CON-ring swap can't set HP (HP scales with max HP). A2I found the flee-failed escape ignoring a dangerous
   caster beyond 5 squares (Ibun cast for 7 s from 12): fixed, A2f passes. (`plan trip LO-HI until COND then recall`), 2.4 order
   checks (hunt/fetch vetted, stale orders held via `after_report`), 2.5 belief state in the report, 2.6 the new
   toolset + a ~100-line HANDBOOK + navigator.md, 2.7 a short supervised mission scored against m17-23. Then the time bubble (timers to game turns; decided below).
3. **Rulebook:** the Advisor's **release 2** is in `Advisor/data/rulebook/`, synced into `github/tools/rulebook/`
   (`sync.sh` after each release; the Advisor owns it). Used so far: kinds_by_level, unknown_expect, feelings, and
   abilities.csv's rule for Free Action (only after a HOLD/SLOW spell or a paralysis blow line). Not yet:
   **jewellery.csv** (ring/amulet plusses and P(cursed): wire into itemvalue for unknown jewellery), **`rule.py fight`**
   (turns to kill, HP lost: for hunt vetting in 2.4), monsters.csv (set-piece A1's reach sum), constants.csv. The rest
   of abilities.csv (rBlind, rNexus... and "lacks" evidence) could extend watch_abilities. The Advisor's next: drop
   expectations.
4. **Harness:** the Advisor's 41 set-pieces (`memos/2026-10-24-setpieces.md`, P1: A1 A2 A3 A6 B1 C1 C3 C4 C5 C8 D3
   F1). Its enablers come first: a key-sending verb in the tool client so Gandalf (DM) can stage scenes, and logging the
   map/status/inventory replies (or `--pktlog`) for replays.
5. Missions again, with scorecards; then a fair Sonnet/Opus comparison (levels per dungeon hour, like depth bands).

**SECURITY (2026-10-23, session 4): credentials leaked to the public repo.** `snapshot.sh` excluded `/runs/private/`
but not its copy in `runs/backup-pre-restructure-20261022/private/` (plaintext `*.pass` of every character,
**including the live server's Happy** and the test DM Gandalf) nor `runs/setpieces/saves/` (savefiles). They were on
origin/restructure from commit afbbdc7 (2026-10-22) to 8f640ab; removed from the tip in 5a92257, and snapshot.sh now
excludes `private/`, `*.pass`, `*.mangrc`, `runs/backup-*/`, `runs/setpieces/saves/`. **The user (2026-10-23): the passwords aren't for
anything important: no rotation, no history purge; follow best practice from now on** (nothing secret in the repo).

**Rules from the user (keep them):**
- **The Navigator's debt limit is never a number.** Overrides are revoked by creating
  `runs/private/dive04.overrides_revoked` (text = why). Every mission prompt states the current debt
  (`PILOT_ROLE=architect pilotctl --nick dive04 debt`) and that past a limit it isn't told, its freedom to
  sell/destroy is taken away. Never tell it a figure or how close it is.
- **Hunt overrides (the user, 2026-10-23, session 4):** the Navigator may override a refused hunt (`goal hunt !NAME`);
  if it goes wrong (not slain, HP < 50%, or an emergency) the HP lost goes into a **fight debt**, separate from the
  item debt (`debt` shows both). Revoke with `runs/private/dive04.hunt_overrides_revoked`. Same rule as items: state
  both debts in every mission prompt, never a limit.
- **Item commands:** refused to the Navigator in the dungeon, allowed in town between trips.
- **`PILOT_ROLE=architect`** in front of my own pilotctl calls (otherwise they're treated as the Navigator's).
- **Mission markers:** `pilotctl --nick dive04 mission start mNN navigator=MODEL [effort=..] [notes=..]` at launch,
  `mission end` at the end (they keep runs/missions.json for the scorecard).
  **Then `python3 tools/observe/tokens.py mNN`** (the user, 2026-10-25): the Navigator's tokens (turns, output,
  cache read/write by TTL, input; from its transcript) and its cost at API list prices (`usd`; PRICES in
  tokens.py, from the pricing page 2026-10-25) into missions.json; `scorecard.py --table` shows `usd`, `usd/dh`
  (per dungeon hour), `usd/kxp` (per 1000 XP) and `gold/usd` (gold found per dollar).
  m17-m23 have no output count (their transcripts lack the final usage); m17-m29 backfilled. Effort is recorded
  too: so far Opus ran at high and Sonnet at medium (their defaults), a confound in model comparisons.
- The Navigator model is chosen per launch (`model: sonnet` on the Agent call); the agent file still inherits Opus.
- Save each Navigator report to `runs/pilot/dive04/reports/`, read `runs/complaints.md`, answer the user's `?`
  viewer notes (`tools/observe/notes.py --nick dive04 --questions`): **I missed some in m21-23; check them after
  every mission.**

**Open questions / decisions:**
- **Time bubble: decided (the user, 2026-10-23, session 4): after step 2.** Finish 2.2-2.7 first (2.7 stays a
  clean comparison with m17-23), then move the Pilot's wall-clock timers to game turns and A/B `--hpwarn 5` on the
  Advisor's set-pieces A1/A2 before using it in missions. It's a **constant 1/5** time factor below hpwarn×10% HP
  (xtra2.c 5180-5207), not proportional (operations.md corrected).
- The Advisor asked what rulebook tables come next; I suggested an ability-inference table, jewellery plusses, kill
  time per monster, then drop expectations.

**Advisor exchange (latest):** to_architect 10-23 scorecard, 10-24 setpieces, 10-24 rulebook, 10-24 rulebook-r2, 10-24 rulebook-r3 (all
read; also 10-24 batch5-reply: fast loners, pathfind ceiling, D3 ok); to_advisor 10-23 setpieces-batch2, 10-22 restructure-plan, 10-23 scorecard-built, 10-23 step2-items, 10-24 rulebook-in, 10-24 r2-in, 10-23 step22-town-kit.

### ARCHITECT HANDOFF 2026-10-08 (history; read the 2026-10-24 section first)

**Start of every session:** start the inbox watcher first (memory `mangband-inbox-watcher`), read
unread `memos/to_architect/`, check what's running (`ps -u $USER`, `tmux -L mang ls`). After every
mission, save the Navigator's final report to `runs/pilot/NICK/reports/YYYY-MM-DD-missionN.md` (the
Advisor can't see it otherwise), read `runs/complaints.md` (agents' `complain` lines) and the report's
"What I lacked" section, fix what you can, and relay recurring or unfixable friction to the user
(memory `mangband-relay-agent-friction`).

**State (2026-10-08 23:25, job 7918400 on scc-wg3, walltime to Mon 10-12 08:03; moved 2026-10-16 13:30 to
job 8105290 on scc-wh2, walltime to Mon 10-19 20:47, Dive04 restored from its 10-12 07:59 save):**
- Running on scc-wh2 (was scc-wg3): the test server under gdb (`testserver/`, port 28346, rebuilt 10-07 with the
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
3. **Pilot bugs open:** none catalogued (all fixed 2026-10-08 evening, see the entry below; tested
   offline only, so watch mission 17 for them).
4. **Navigator wishes:** all built 2026-10-09 (entries below), untested in play: watch mission 17.
   Left: vault recognition (irregular shapes; only inner rooms/pits/nests are recognised), monster
   HP logging (Advisor complaint 3), the older Advisor items (post-mortem §4.4, Borg §3.3-3.8,
   catalogue regex→CSV, shop routing).
5. **Measure** alert → order → journal latency per mission (mission 14/15 median ~5 s, urgent
   tail to 112 s; the method: decisions.jsonl `attention` → next `goal`/`agent:` act/`nav_journal`).
6. **FUTURE IMPROVEMENTS (the user):** Navigator effort (now Opus high, inherited; user wants to
   watch before changing); model × effort trials; "Pinky and The Brain" two-tier Navigator. (The
   complaints channel is built.) Details in the 10-07 entries below.
7. Smaller: server `pathfind` experiment (running memo change 6); a
   live-server run only after asking the admins (`operations.md`).

- **Mission 17 (2026-10-16 13:57-14:40, Navigator report `runs/pilot/dive04/reports/2026-10-16-mission17.md`):**
  clvl 15 → 16, Restore CON bought (CON 18, 197 HP), Amulet of Resist Acid; deepest 650 ft. The dive ended 4 min after
  arrival at 650: Black orcs + breeders, Phase Door landed past a corridor seen only with orcs in it, so goto/flee
  found "no known path"; the Pilot read the last WoR and spent 3 CCW in 15 s. Supply gate fixed first (278df42: it
  only counted a worn light, the lantern is off in town). **Fixed after (deployed 17:40):** monster squares recorded
  as floor (world.py; not PASS_WALL/KILL_WALL); `Mover.go(unknown=True)` fallback through unseen squares (cost +6)
  for Goto and Flee, replayed on the saved 650 ft map (30-step path); shrieks news only; a climb never goes down
  (`goal dive FEET scum` to allow); names match singular/plural; `fuel` wears the lantern first; townfarm hits an
  adjacent thief directly (auto-retaliate killed idiots while urchins stole); the audit ignores light-turn ticks.
  Not yet seen in play: everything from 10-09 except the gate, `complain`, name refusal, report lines.
  **Dive04 now: max_depth 100 (raise before a recall), 46 gold, 1 WoR, 1 CCW 4 CSW 3 CLW, 8 Phase, unknown Robe {good}.**

- **Mission 18 (2026-10-16 18:46-19:26, report `runs/pilot/dive04/reports/2026-10-16-mission18.md`):** clvl 16 → 17,
  215 HP, 46 → 315 gold, 2 WoR + 4 CCW bought, Hard Studded Leather [7]; STR drained 18/50 → 18/40 (Giant red
  scorpion; Restore STR ~480 next). Recall at the first `fight_going_badly` (Ufthak + orc bands, 600 ft) worked.
  Before it: viewer polls counted as Navigator activity, so town_light never took the lantern off (f519491).
  **Fixed after (deployed 19:5x):** shop buy names singular/plural (`singular()`); Goto held while a faster
  monster is hitting (Nighthawk 215 → 102 over a 25 s goto); "Standing on: $" cleared on "You have found N gold";
  interesting_item held 2.5 s and dropped if the item reached the pack; the shop refuses a lone unknown scroll
  (read it; curse scrolls are native to 2500 ft); Dive uses a Staff/Rod of Door/Stair Location once per level with
  no stairs known (flavour table counts); townfarm's adjacent-thief hit now actually runs (step 5 returned before
  the goal ticked: 0 hits in mission 18). `use`/`aim`/`zap` existed; now in the HANDBOOK.

- **Mission 19 (2026-10-16 22:14-22:55, report `runs/pilot/dive04/reports/2026-10-16-mission19.md`):** clvl 17 → 18,
  220 HP, STR drained to 18/10 by a Giant red ant + frog (unflagged), restored (498); Shadow Cloak, Ring of Resist Cold;
  a hunted Ranger took 220 → 67. Door/Stair Location dive step, `use`, shop plurals, item-alert hold, gold-underfoot
  all worked. **Fixed after (deployed 23:40):** a refused run ("You cannot run in that direction", resent 61 times)
  falls back to walking from that square (`Mover.no_run_at`); `stuck` after 20 s on one square; `drainer` event on
  sight + `drainers [STAT] [MAXLEVEL]` query (`Race.drained_stats`); second drain by a weak (clvl-5), no-faster,
  non-unique adjacent drainer → Hunt it, not Flee; "weak melee" caster exemption needs worst case < HP/8 too
  (Ranger 40 no longer passes; Wormtongue 10 does); "was eaten!" is `lost` news; townfarm clears before each thief
  hit (a stale walk moved us), item thieves first, and ends itself after 2 min without gold (57 thief hits seen in
  mission 19: the step-5 fix works); `use/aim/zap` with a game reply skip the "no change" note.

- **Mission 20 (2026-10-16 23:41-00:18, report `runs/pilot/dive04/reports/2026-10-16-mission20.md`):** 52 → 793 gold,
  Spear (+5,+5) wielded (3 blows ~26), Ring of Acid sold 900; lowest HP 91%. First recogniser hit in play: inner room
  27,49 at 450 ft (dump `levels/20261016-235015-450ft.txt`): a true positive, its west door at 27,39 already open, so
  searchroom searched 26 s for nothing. **Fixed after (10-17, deployed):** unseen curses/fear minor, and any unseen
  cause with a weak caster (clvl-5) in view within 10 is news (Novice priests in the dark → 2 flees below max_depth;
  the Navigator's `hunt` never reached the Pilot); door-burst news only; 20 s `stuck` skips lock-picking/digging;
  searchroom refuses when the door shows (`room_door`; Structures says "door at"), replies with per-spot counts;
  interesting_item waits up to 10 s while a matching glyph is within loot_radius; item replies wait up to ~2 s for
  the pack to change; shop buys the remainder at the next price within the cap and says when gold stops it.

- **Mission 21 (2026-10-17 00:47-01:35, user watching; report `runs/pilot/dive04/reports/2026-10-17-mission21.md`):**
  clvl 19, 793 → 2621 gold, deepest 700, Hard Studded Leather of Resistance, Spear (+5,+7), Wormtongue killed, a jelly
  nest found behind a searchroom door. Server crash at 00:48:48 (store[-1]: the Pilot's town redraw closed the store
  silently on the server): patched server (bb56313) + Pilot/client guards (f4082b0). **Fixed after (deployed):**
  dungeon `thief` event + hit the thief first when several are adjacent; `unique_slain` event; Hunt sees a kill in any
  message since it began (messages deque 60 → 300); pickup skips flavour-table junk; `use L TARGET`; Weapons line shows
  brand damage (Hammer of Venom ~63 vs non-resistant, sold for 1707!); surface runs start with townspeople within 2;
  paralysis hint on unseen gazes without FA; "Standing on" explains unknown after login; searchroom summary includes the
  spot it was at; `complain` writes directly when the Pilot is down.

- **Mission 22 (2026-10-17 01:45-02:15): the first Sonnet Navigator** (per-launch `model: sonnet`; the agent file still
  inherits Opus). Report `runs/pilot/dive04/reports/2026-10-17-mission22.md` has the latency table
  (`tools/observe/latency.py`): alert → order median 8.9 s for both, p90 30 s (Sonnet) vs 81 s (Opus m21); cadence
  3.9 vs 5.1 s; but 111 alerts vs 17 (mob levels), so not comparable yet. Gold 2621 → 475, clvl 19 → 21. Its 7
  Pilot problems (loot rooms while a band gathers, Phase Door burn, junk weapon pickups, identify-by-name with twin
  stacks, equipment letters, hunt overridden by flee, traps): **fixed 10-22** (see the compact-report entry).
- **Compact report (2026-10-22, the user):** `wait` and `status` now return `Pilot.compact()` (~0.4-1.4 KB vs
  ~5 KB): character, stats, Cures|Escapes|Food|Light, Also, Here+stairs, Monsters (DANGER why), Items, a 19 x 19
  dungeon map (none in town), Structures, News, Msgs, Since last, Progress, then changes only (Equip, Pack
  non-consumables, Weapons, Abilities, Gear, Orders changed, Audit), all of them on an explicit `status`.
  `status full` = the old report; new queries `pack`, `equip`, `orders`, `map [R]`. The viewer still uses
  report() (the user will handle the viewer separately). Runs on scc-pe7 now (job 8181626, to Sat 10-24 09:50).

- **Mission 22 fixes (2026-10-22, deployed):** `band` event (5+ mobile monsters with 6+ worst-case melee within 10,
  or together over 40% max HP; once per level, again at +50%); after 3 Phase Doors in 20 s with monsters still adjacent
  the emergency reads WoR and phases only below 20% HP (`phase_hist`, all 5 phase sites); bulky gear (|/\([])}{,
  not ~ chests) skipped with ≤5 free slots unless {good}/ego (news, `pickup` overrides); equipment letters A, B...
  (`equip`, compact Equip, takeoff/inspect/read TARGET; `takeoff b` too); twin same-name unknown stacks → the first;
  a Navigator-ordered hunt isn't replaced by the danger/unseen flees for 120 s (`by_navigator`, `hunt_ordered`);
  Mover plans round known traps first; 3 traps sprung on a level → news. Tested offline + `inspect B` live.

- **RESTRUCTURE (2026-10-22, the user):** after mission 23 (user-ended; report `reports/2026-10-22-mission23.md`) the
  user decided: restructure (not rewrite), keep Dive04, instruments first; mission-by-mission patching frozen. Plan:
  `memos/to_advisor/2026-10-22-restructure-plan.md` (from the Advisor's `memos/2026-10-19-starting-over.md`). Work is on
  git branch `restructure`. **To revert (only if the user asks): `restructure.md`** (tag `pre-restructure` = 767bf60,
  backups in `runs/backup-pre-restructure-20261022/`).

- **Restructure step 1, instruments (2026-10-22, branch `restructure`):** `tools/observe/scorecard.py` (one card per
  mission from runs/missions.json: dungeon minutes, XP and gold found per dungeon minute, gold flows, lowest HP and
  close calls < 40%, recalls, consumables used, value lost = items sold then offered by a store at 10x+, forced sales,
  losses, Navigator latency/commands/reports, Pilot stuck/goal_failed/audit/server crashes; `--table` compares; JSON in
  runs/pilot/NICK/scorecards/). Missions 17-23 registered. Pilot: every Navigator report is numbered (`· rN` on its
  first line, a `report` record with kind and size) and every nav_cmd carries `after_report` and `report_age`; `mons`
  records carry the server's health bar of the tracked monster (`track`: [colour, tenths]) and `fighting` (the monster
  last hit). **Then (10-23) rebuilt to the Advisor's definitions** (`memos/2026-10-23-scorecard.md`): groups A-F, levels
  per dungeon hour (player_exp x 110%), the 16-category time budget, close/near calls, escapes split, value lost with
  exact fair pay from the source (`tools/observe/shopmath.py`: relist x (400-G)/(G-200), /9 at the Black Market;
  other losses = object.txt kind cost x 0.38), damage by monster; `--check` matches the Advisor's baseline CSV (all
  core measures equal; WoR-escape +0-1 by the memo's fuller rule). Logging added (§5): `sale` records (name before,
  aware/pluses known, received, owner, relist), `itemlist` on change + `left_behind` on leaving a level, `escape`
  records (phase / wor_escape / wor_travel / stairs / teleport), per-check state in audit_check (resting, in_combat,
  recall_pending, goal, hp_min), and **mission markers: run `pilotctl --nick dive04 mission start mNN navigator=MODEL
  [effort=..] [notes=..]` at launch and `mission end` at the end** (they keep runs/missions.json).

- **Step 2.1, the Pilot's item policy (2026-10-23, branch `restructure`; design `restructure-step2.md`):** itemvalue.py
  (object_value_real from the edit files; 37/38 sales matched), Navigator item commands refused in the dungeon
  (`req_role`; `PILOT_ROLE=architect` marks my own pilotctl calls), value refusals with `!` override → **the
  Navigator's debt** (`navigator_debt.json`, `debt` query), `keep`, Free Action inferred from "You are unaffected!",
  pickup by value (unique drops always; use a flask/ration, then destroy the cheapest non-kit item), no loot detours
  after a band, policy step at safe moments (identify, wield/wear upgrades, jewellery), gold within 10 when idle.
  **The debt limit is never a number** (the user): we revoke overrides by creating
  `runs/private/dive04.overrides_revoked` (text = why). **Every mission prompt must give the Navigator its current
  debt (`PILOT_ROLE=architect pilotctl --nick dive04 debt`) and the notice that past a limit it isn't told, its
  freedom to sell/destroy is taken away.**

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
- **After mission 16 (2026-10-08 evening, deployed):** `explore` no longer calls a level done
  while corridor dead ends are unsearched (the 500 ft "nothing left" and the 550 ft secret door the
  user spotted): with no frontier it digs rubble bordering unknown ground, then searches each
  strict corridor dead end 15 times, nearest first, once per level (`p.searched`; `goal search`
  shares it and now goes nearest-first). Reply: "nothing left to explore (searched N dead ends)".
  Tested offline on stub maps only; watch the first mission for time spent searching.
- **"Fix all catalogued bugs" (the user, 2026-10-08 evening, deployed 23:38):** (1) "frontier
  unreachable" (mission 15): four "There is a wall blocking your way" bumps while blind+confused
  were written as walls on real floor; now no bump-walls while confused/blind (`Mover._astray`), a
  closed-door bump is a door, and `Mover.go` forgets bump-learned walls (`w.bump_walls`) and
  replans when no path is found (also mission 9's "no known path" to a `<`). (2) Flavours: learned
  from the Identify reply "In your pack: a Ring of X (q)." matched to the target's letter (the
  pack diff missed Calcite, autodestroyed at once, and Beryl, spoiled by that destroy's "no more"
  message); Beryl/Calcite added to `runs/flavours.json` by hand. (3) User messages during long
  agent commands: notes are taken out of the request queue inside `search`/`open`/`disarm`/
  pack re-reads, and every pilotctl reply starts with `USER MESSAGE(S) NOT YET ANSWERED` until
  `say` (navigator.md, HANDBOOK). Older ones: light `low_supply` once per state per 10 min, news
  in town (573 "lantern at 0 turns" alerts; post-mortem §4.7); "You have killed it." counts as a
  fight and ends a `hunt`; dropped items aren't auto-picked up again (mission 9); RUN_MIN doc fix.
  Checked and already fixed: unseen-attacker alarms after kills (§4.5), clvl after resurrection,
  Bullroarer seen late. Still open as features, not bugs: post-mortem §4.4/§5, Borg §3.3-3.8,
  catalogue regex→CSV, shop routing.
- **Advisor's missions 15-16 replay** (`memos/to_architect/2026-10-08-missions15-16-replay.md`, read;
  reply `memos/to_advisor/2026-10-08-missions15-16-adopted.md`), deployed 23:44: Brodda (HP 151 → 27,
  the closest call yet) → `flee_failed` sees listed-only dangers and isn't blocked by `flee_t`;
  emergency also at HP ≤ 2.5 × the hardest adjacent monster's worst round (×speed, HP < 90%);
  `goal goto` held beside a dangerous monster (`force` overrides); blind/confused + still hit →
  cure with nothing in view, explore/search/dive pause; the `destroy Light all` bug was still live
  (by-name branch) → `item_index(pack_only=True)`; goals inside a drainer zone dropped; `monster`
  prints unique HP as the max (Wormtongue 250); slow-caster no-flee distance 25 → 8. {magical}:
  doesn't exist here (`memos/to_architect/2026-10-08-magical.md`: warriors' heavy sensing gives
  terrible/special/worthless/excellent/cursed/broken/good/average). Watch mission 17 for the 2.5×
  phase count.
- **Features, 2026-10-09 (the user: "go ahead, in your suggested order"), deployed 00:07:**
  complaints channel (`pilotctl complain` → `runs/complaints.md`, "NAVIGATOR LACKS" in the viewer
  and notes.py, a "What I lacked" report section; the Advisor adopted it for memos and Clerk
  dispatches; review after every mission); **supply gate** (`goal dive` deeper / `goal recall`
  from town refused below the stage minimums: cures, Phase, WoR 1/2, a fuelled light; `force`
  overrides; `pilotctl gate FEET [recall]`); report lines `Since the last report` (lowest HP,
  monsters at most-at-once, uniques), `Progress:`, `Movement:`, `Gear:` (empty slots, better AC),
  `Orders changed from the defaults:`; townfarm attacks thieves (EAT_ touch) within 8 first;
  recall time 8-23 s in the docs; night town runs over unknown ground (≤ 10 squares, edge guard);
  `goal shop N quote NAME` (offer + decline: the price, nothing sold); `shop sell NAME` now uses
  `item_index` too (it took the first substring). Logs (the Advisor's complaints 1, 2, 4, 5):
  events.jsonl has `epoch` on every event and a `pilot_start` record; `nav_cmd` records every
  Navigator command; runs logged as `move` records with `run`; an `options` record per login.
  **Dive04's lantern is at 0 turns with no flask: the gate will refuse the next dive until it's
  fuelled.** The user's viewer needs a restart to show complaints (`tmux -L mang`).
- **Inner-room / pit / nest recogniser (the user, 2026-10-09, deployed 00:18):**
  `tools/pilot/structures.py` per the Advisor's spec (geometry re-checked in generate.c: centres
  at 11·k+5, 11×25 box, 7×21 inner block, one secret door at a side's middle; pits/nests are the
  same room, never lit). Every 2 s it tests the grid centres against map memory (1.6 ms): ≥ 2 ring
  sides seen, each ≥ 60% of its length beside the inner wall, no contradicting square ("likely";
  3 sides or 2 opposite = sure). Lit = ≥ 75% of the ring known at first sight. Classified by
  monsters: dark + ≥ 4 of one kind = pit (orc pit for `o`), dark + ≥ 3 stationary inside = nest.
  `structure` event (news for rooms; wakes for pits/nests, which also get avoid zones), report
  line `Structures:`, `goal searchroom Y,X` (20 searches at each of the 4 door spots), explore's
  "done" names unopened inner rooms. Tested on synthetic maps only. From now on each dungeon level's
  remembered map is saved on leaving to `runs/pilot/NICK/levels/` (header: depth, times, structures
  found), so missed or false rooms can be checked.
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

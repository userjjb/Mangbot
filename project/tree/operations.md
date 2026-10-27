# Operations: environment, characters, server facts, rules

Practical facts for anyone working on this project: the Architect, the Advisor, the Navigator,
and humans. (Moved here from the Architect's private memory on 2026-09-27, so that every agent
can read them. Memory now only points here.) Credentials are **not** in this file: see
`runs/private/`.

## Environment

- Shared SCC cluster, Alma 8, SGE batch jobs (sessions end at their walltime; the node changes
  between jobs). No sudo.
- Python: `module load python3/3.12.4` (the OS python3 is 3.6).
- **Public repo: https://github.com/userjjb/Mangbot** (remote `origin` of `github/`, the user's,
  2026-10-07). Before a push run `tools/snapshot.sh` (copies the project state, both memories and
  the global CLAUDE.md into `github/project/`, minus secrets and bulk; see `project/README.md`),
  commit, then `git push origin master`. Auth: the user's token in git's credential store.
- Source tree: `github/`, a git repo (commit 1 = pristine MAngband 1.5.3; per the Advisor's
  versions memo, `memos/2026-09-29-versions-and-forum-rules.md`, it is upstream develop at
  2022-03-13, c97e873, not the v1.5.3 tag: 6 files differ, mostly archery energy; plays as 1.5.3). Build: `cd github &&
  make`. To regenerate: `./autogen.sh -n` (plain autogen fails once `.git` exists; its
  config.guess/sub download gives empty files, so copy them from `/usr/share/automake-1.16/`),
  then a GCU-only configure.
- Run output, logs and credentials go in `runs/` (credentials in `runs/private/`, mode 700).
  Session scratchpads get wiped.
- The client rewrites its config file on exit. Give every concurrent client its own `--config`,
  and never let it rewrite the tracked `github/.mangrc`. The interactive client also rewrites
  `github/lib/user/options.prf` / `window.prf` when options change: revert those with
  `git checkout` rather than committing them.

## Test server

- `testserver/` has its own `mangband.cfg` (port 28346, `NEWBIES_CANNOT_DROP=false`). The `-c`
  flag is broken (init2.c:2362), so run it from that directory. Stop it with SIGTERM (clean save).
- Run it under gdb to catch crashes: `cd testserver && MANGBAND_FREEZE_FILE=$PWD/FREEZE nohup gdb -batch -ex run
  -ex bt --args ../github/mangband >> gdb_run.log 2>&1 &`.
- **Time freeze (test server only, 2026-10-25, the user):** with `MANGBAND_FREEZE_FILE` set, the server processes
  no game turns while that file exists (net-server.c `time_frozen`; checked every 10 ticks; players get "*** Time
  is frozen ***"). Toggle: `github/tools/freeze.sh on|off|toggle|status`, or F5/Ctrl-F in the viewer. The Pilot
  stops its game clock and holds (answers requests, acts on nothing) while it exists. A Pilot or client
  connecting while frozen waits until thawed. Without the variable (any other server) it never freezes.
- **Known crashes:**
  - A player disconnecting while walk/run commands are queued: NULL `pcommands[pkt]` in
    `process_player_commands` (net-game.c:2428). A crash rolls characters back to their last save.
    Update the Pilot only with `tools/pilot/restart.sh` (it parks first and sends `clear`).
  - A store purchase arriving when the player is no longer in a store (`store_num` -1): `get_store_item`
    read `store[-1]` and segfaulted (store.c:1625, 2026-10-17, mission 21's Gauntlets buy). Patched in the
    test server: get_store_item, store_purchase and store_sell refuse when not in a store or past the stock.
    **Cause, and the client-side fix that also protects live servers:** the server leaves the store on any
    non-store command (walk, rest, pathfind, a non-store custom command) and on a redraw, without sending
    store_leave. The Pilot's 2-minute town redraw fired mid-shop. Now the Pilot never redraws in a store or
    during a shop goal, and the client tool (c-tool.c `tool_in_store`) refuses redraws and store commands
    when not in a store and reports a store_leave {why} after any non-store command.
  - `MAX_ARENAS=10` with no bounds check (wilderness.c:1171): an 11th wilderness arena corrupts
    `k_name` and the server segfaults in `object_desc`. Entering 2E did this on the test server.
    Keep tool characters out of the wilderness there. Live servers are patched (user).

## Characters

| Name | Where | What | Notes |
|---|---|---|---|
| Surveyor | test | Dwarf Warrior | shopcat tour character (non-REGEN) |
| Scout | test | Half-Troll Warrior | retired from tours: REGEN eats a ration every ~100 s outside town |
| Gandalf | test | DM ghost, all dm_flags, ~9.9M gold | owns the town house with "Test Shop" (door at 16,88). Ghost DMs can't use NPC shops and misbehave crossing levels. Don't use him for errands; a far-wilderness ghost can't float up (walk it home, reading its position from the (M)ap) |
| Dive01, Dive02 | test | Half-Orc Warriors (throwaways) | made with `tools/shopcat/newchar.py` |
| Dive03 | test | Half-Orc Warrior | dead for good (mission 7, 2026-09-27: its ghost faded away) |
| Dive04 | test | Half-Orc Warrior (throwaway) | made 2026-09-28 01:35 for mission 8 |
| Scribe | test | messenger | `tools/observe/scribe.py`: answers the user in game while they play (local server, at the user's request only) |
| Happy | live | shop-catalog tool character | the user stocked it; no purchases wanted |
| Sneezy | live | (not created yet) | the live dungeon character for validation (user's choice; not Happy) |

Passwords: `runs/private/<nick>.pass` (mode 600), configs: `runs/private/<nick>.mangrc`.
`newchar.py` writes both for new throwaways. `suicide NICK` (tool mode) kills a throwaway for good;
`--birth` recreates a dead one. A dead character (ghost) floats up with `<` and resurrects by walking
into the Temple (4), but everything it carried is dropped where it died.

## Tool-mode client facts (`mangclient -mtool`, `src/client/c-tool.c`)

- **Orphans (2026-10-23, the set-piece harness):** a dropped connection (every Pilot restart or park) leaves the
  character in the world, orphaned and vulnerable, until it has been idle 15 s, or at once in town (net-server.c
  `player_drop`, the idle timer in dungeon.c). A login before that **resumes it in memory and ignores the savefile**.
  So never copy a savefile in less than 20 s after a logout (`tools/harness/charsave.sh` waits). The server also
  saves every player, orphans too, every few minutes, so the savefile's time proves nothing.
- **Server screens:** `interactive TYPE` (13 = the DM menu) opens one and keeps it open while `keys TEXT` has keys
  queued (escapes `\e` `\r` `^X` `\xNN`); its redraws arrive as `special` events (`special` asks for one).
  `tools/harness/dm.py` drives Gandalf with them (see `tools/harness/README.md`).

- JSON events on stdout, commands on stdin (see the header of c-tool.c). `-mtool` implies
  `--noprompt` (which must come before another `--option`, not before SERVER). Password from
  `--passfile`, `MANG_PASS` or the config. A bad password or missing character exits 255.
- Tool mode logs in as `player@localhost` (not the Unix login and host: the live player list shows
  them) and sends `hitpoint_warn` 6 (`--hpwarn N`, 0-9): below N×10% HP the server slows our time
  bubble to a **constant 1/5** (`CONSTANT_TIME_FACTOR`, xtra2.c 5180-5207; the Advisor's rulebook memo
  2026-10-24 §3; not in proportion to HP). **Since 2026-10-23 the Pilot's timers run on a game clock**
  (`world.gnow`; logs and displayed times stay wall-clock). **`pilot.py --hpwarn` defaults to 5 since
  2026-10-24 (the user: missions run with it)**; `PILOT_ARGS="--hpwarn 0" tools/pilot/restart.sh Dive04` turns
  the bubble off (`setpiece.py --hpwarn 0` for an A/B). Both in `c-init.c` (commit 6274e8b).
- **`pilot.py --live`** (default off = test server): on the test server, devices that map or detect for us
  (Enlightenment, Detection, Magic Mapping rods/staffs/wands) are sold like loot, not kept -- the user: no crutches
  the live server won't give us. On a live server pass `--live` (`PILOT_ARGS="--live"`): they're kept.
- **The game clock is measured, with no server change** (works on live servers): a worn light loses one
  turn of fuel per game tick of our bubble (dungeon.c "Burn some fuel", scaled by our time factor), the
  fuel shows in its name, and a redraw (free: no game time; never in a store) makes the server resend it.
  At factor 1 a tick is ~0.625 s (1.6 ticks/s in m24's pack log). The server speeds us up (~5x running,
  ~10x resting) only with nothing in view, so the Pilot uses the fuel rate only then (asking for a redraw
  every 2 s; every 10 s otherwise, logged as `measured` in the `time_factor` records), and the model
  elsewhere: 1.0, or 1/5 in the HP bubble. With no burning light worn it's the model alone. Timers that wait
  on the network (a step showing up, a read confirmed, a store reply, "busy" windows) need the time on
  both clocks (`waited`, `ghold`): at 10x, 1.5 game seconds is 0.15 s, shorter than a round trip.
  Live D6: the factor while exploring averages 2.2-3.7 (runs at 5x between stops).
- The map is 198x66 in absolute coordinates; closed house doors are drawn as `0`. `--visuals`
  gives every monster race a unique glyph (needs option `avoid_other`).
- The depth indicator is **one signed byte**: wilderness squares beyond index -127 wrap to
  positive values (14N 2W = index -543 showed as -31). The `minimap` query (after `custom M`)
  gives the true position, e.g. `[14N, 2W]`.
- `--pktlog FILE` logs every packet (and keys in the interactive client). Password hashes are
  blanked. Verified on the wire: store rows come before STORE_INFO; leaving a store = PKT_WALK
  dir 0.
- Inventory data arrives ~1 s after `ready`.
- Client `quit(msg)` treats a message starting with '-' as an exit code. Stat names arrive as
  "STR: ".
- Floor for-sale items are only protected (purchase confirmation) if inscribed `!g`.

## Tools

- `github/tools/shopcat/`: the shop cataloger (README). Regression run: `runs/regress.py`
  (Surveyor: home from 1E, restock twice, 6 town doors, a 1N tour).
- `github/tools/observe/`: `record.py` (record a human's session), `timeline.py` / `screen.py`
  (study it), `scribe.py` (answer the user in game).
- `github/tools/pilot/`: the Pilot, `pilotctl.py`, `restart.sh`, `HANDBOOK.md` (see
  `design_pilot.md`).

## Verified server behaviour

- Wilderness depth = `world_index(x, y)` (ring formula, `tools/shopcat/wild.py`). Stepping off an
  edge changes level. At night the floor isn't drawn but house walls and doors stay lit. Trees `*`
  and logs `=` block.
- Server pathfind: 25-tile radius, treats the unseen as open (it walked off level edges): the
  tools plan their own paths.
- Walking ~0.5 s/step; running ~0.1 s/step (a walk request stops a run and is swallowed); a command
  sent just as a run ends may be ignored.
- Arenas ("ancient fighting pit"): bumping the wall teleports you in; bump again (alone) to leave.
- Digestion: 0 at normal speed unless the race has REGEN; nobody digests in town.
- Resting is PKT_REST (a toggle), not a custom command.
- The server auto-retaliates against an adjacent visible monster when no command is queued.
- Stairs are connected: after `>` you stand on `<` and vice versa. A stairs command right after
  arriving can be ignored (retry).
- Level persistence (`dungeon.c:2035-2046`, `1832-1860`): a level is freed the moment nobody is on it
  (`players_on_depth` 0), so stairs back to a level just left lead to a fresh one -- unless the level
  is "static": another player is on that depth (all players at one depth share one level), or a
  character logged out there (a Pilot restart, park or hot-swap in the dungeon does this). A static
  level with nobody in it unstatics at random, 1 in `LEVEL_UNSTATIC_CHANCE x (depth+5)/5` per check
  (30 here: 1 in ~119 at 750 ft), so it can last a long time. Arriving on a kept level puts you on a
  fixed square (`level_up_y/x` coming up, `level_down_y/x` going down: m25 landed on 33,24 each time).
  Special levels (`check_special_level`) and the town are never freed. The Pilot's dive refuses the
  stairs back to a fled level for `Dive.FLED_HOLD` (2 minutes) on a live server only; on the test server (one player)
  not at all, unless the level is kept: one seen kept, or the one the Pilot logged in on (the user, 10-26).
- Word of Recall: from town it goes to the deepest level ever reached, unless the scroll is
  inscribed `@R<feet>`. A logout during a pending recall reset that depth once.
- The command queue: a walk sent while the character lacks energy waits on the server. A step
  queued ahead and never used stays there, so every later step runs one behind (mission 3 circled
  a `>` for 10 minutes). PKT_CLEAR (tool `clear`) empties the queue at once; it also drops a
  `walk 5` sent before it. A `,` (stay/pickup) right after a step waits ~0.6 s for energy.
- A second Word of Recall cancels the first: "The air about you becomes charged..." starts one,
  "A tension leaves the air around you..." cancels it (`spells2.c:1191-1199`).
- Auto-retaliate picks any visible adjacent monster at random (the tracked one first), molds
  included (`dungeon.c:777`).
- `pause_after_detect` (on by default) only sends a pause flag; the server doesn't wait and the
  tool client never blocks on it.
- Potion heals (`use-obj.c:483-540`): CLW 15, CSW 20-24, CCW 25-29, Healing 300, *Healing* 1200.
  Breath = monster HP / 3 or / 6, capped by element (`melee2.c`; table in `tools/pilot/glyphs.py`).
- More, from the forums and the code: `memos/2026-09-26-forum-distillation.md`.

### Houses and the gold bank (session 9, 2026-10-27; research from the source)
- A town house is bought with `h` toward its door (cmd2.c:4378): price = interior area x 20 x (81..120) x the CHR
  factor (130 at CHR 3 .. 100 at CHR 18) x 5 in town. Opening an unowned door says "This house costs N gold."
  Ownership is saved with the server state, keyed by character name, never expires (lost only by selling -- refund
  ~1/10 -- a DM reset, or permanent death, which also deletes the contents: cmd2.c:920).
- Owner's `open` makes the door walkable; others get a store screen showing only "for sale" items. Floor objects in
  houses persist (town levels are never wiped); monsters can't spawn in or enter closed houses and never take floor
  gold. Gold is dropped with `custom $ value=N` ("You drop N pieces of gold."), picked up by stepping on it.
  **Gold piles never merge and a drop with no free square vanishes** (object2.c:4142): the bank keeps one pile.
- **Wilderness houses are far cheaper** (wilderness.c:1189-1195: area x (900..1099) + 33 x area^2 (+ a cube term past
  40 squares), x CHR, **no x5**): ~1,200 for 1 square, ~5,500 for 4 at CHR 4. The tile beside town has extra for-sale
  ("town home", door `0`) houses. Walking off the town's edge (TOWN_WALL false on both servers) enters the tile; its
  objects aren't wiped when it empties (generate.c:4090: verified, a pile was there after the tile emptied).
- **Dive04's bank is the 4-square house in the tile NORTH of town** (depth -1, "-50 ft"): door 60,129, stand at 60,130,
  reached by walking north off town at 1,130 (you arrive at 64,130); bought 18:00 10-27 for 5455 (the user: practice for
  the live server, where we won't buy in town). A bank trip from the north edge takes ~20 s each way.
- Dive04 also still owns the **town** 1-square house (door 38,155, bought 17:34 for 10125, empty; on record in
  house.json `old_houses`; selling refunds ~1000). State in `runs/pilot/dive04/house.json`;
  `pilotctl house` / `house deposit [KEEP]` / `house withdraw` (`house buy` is the Architect's). `plan town` withdraws
  first and deposits all but `BANK_FLOAT` (300) last. Live: NEWBIES_CANNOT_DROP is on (level 1 only); a house there
  may already be owned by someone; keep the door closed.

## Live server

- mangband.org:18346 (1.5.3), found with `shopcat.py --list-servers` (metaserver
  mangband.org:8802). The operator allows automated clients; it's a shared world with real players.
- First full live shop tour 2026-09-25 (~2 h, town + 12 levels): 416 doors, 111 owned houses, 40
  with stock (395 item lines). Output: `runs/live-tour.jsonl`, `runs/live-tour-stock.csv`.
- House prices (from the live tour): wilderness = ((a-40)^3*3 [a>40] + 33a^2 + a*(900..1099)) *
  CHR factor; town = a*100*(81..120) * CHR factor (the source says *20; live differs). Happy (CHR 4)
  pays x1.25. `runs/live-tour-houses-for-sale.csv`.

## User decisions and rules

- The tool's characters **never chat**; ignore players who talk to them. (Exception, by request:
  Scribe answering the user on the local server. The user's own commentary goes in chat as a
  private message to themselves: `:Name: note`, max 59 chars.)
- Throwaway build: Half-Orc Warrior, DEX > STR > CON > WIS > CHR > INT, a light weapon for four
  blows, +to-dam scrolls on it (`notes_players.md`).
- Keep ghosts ON (mirrors the live servers).
- Night travel: a Brass Lantern and oil rather than waiting for day.
- Roles: `roles.md`. Main chats are the Architect unless the user says otherwise (e.g. Advisor).

## Agent-tooling gotchas

- `pkill -f PATTERN` / `pgrep -f PATTERN` also match the shell running them: anchor patterns
  (`'^python3 pilot.py --nick Dive03'`) or use pidfiles.
- In the Bash tool `rm` is aliased to `rm -i` (it hangs): use `rm -f`.
- `runs/pilot/<nick>/events.jsonl` timestamps (`t`) restart at 0 with every Pilot run (the file is
  appended across runs; the last run starts where `t` drops). `decisions.jsonl` has epoch times.
  Maps aren't logged.
- Foreground `sleep` is limited; wait with Monitor or `run_in_background` loops. Monitors expire
  after 30 min.
- Driving the GCU client through tmux: a lone Escape is swallowed; send `Escape Escape`. Ctrl-X
  saves and quits.
- **Watching a Pilot character (the user's commentary):** on the job's node,
  `module load python3/3.12.4; python3 github/tools/observe/watch.py --nick dive04` (or attach to
  the one the Architect starts: `tmux -L mang attach -t watch`; detach with Ctrl-b d). Type a note
  + Enter; start it with `?` to ask why the Pilot did something (for the Architect), or with `!`
  to message the Navigator live (a `user_message` attention event wakes it; it answers with
  `pilotctl say`, shown in the feed as NAVIGATOR: ...). The feed also shows the Navigator's journal
  lines (NAV: ..., magenta) as they're written, between the Pilot's alerts (red) and actions (green). Notes land in
  `runs/pilot/<nick>/commentary.jsonl` (with a snapshot) and as `user_note` in `decisions.jsonl`;
  `python3 github/tools/observe/notes.py --nick dive04 --today` shows each with the decisions
  around it. From any shell on the node: `pilotctl.py --nick dive04 note "text"`. The control
  socket is local: the viewer must run on the job's node.
- Human play is recorded with `tools/observe/record.py` (tmux -L mang; attach from a shell on the
  job's node). The OnDemand web terminal adds key lag.
- Forum research (Advisor): mangband.org/forum was down (502) on 2026-09-26. The Wayback Machine
  allows ~12 requests/min (faster gets connection refused for a while). Many Aug–Oct 2025
  captures return HTTP 500. Some pages exist only as print-view captures. Topic IDs above ~2250
  in General Discussion are spam. Details: `memos/2026-09-26-forum-distillation.md`.

## Live-server rules a bot must follow (Advisor versions memo, 2026-09-29)

Recall to town before logging out (no saving in the dungeon); never idle inside a store; destroy,
don't drop, junk in town; never pass items between our own characters; no power-levelling. The
current rules and version are unknown (the News ends in 2020): **ask the admins before a live run.**
Uniques come back on every death (not on resurrection).

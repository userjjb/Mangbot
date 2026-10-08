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
- Run it under gdb to catch crashes: `cd testserver && nohup gdb -batch -ex run -ex bt --args
  ../github/mangband >> gdb_run.log 2>&1 &`.
- **Known crashes:**
  - A player disconnecting while walk/run commands are queued: NULL `pcommands[pkt]` in
    `process_player_commands` (net-game.c:2428). A crash rolls characters back to their last save.
    Update the Pilot only with `tools/pilot/restart.sh` (it parks first and sends `clear`).
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

- JSON events on stdout, commands on stdin (see the header of c-tool.c). `-mtool` implies
  `--noprompt` (which must come before another `--option`, not before SERVER). Password from
  `--passfile`, `MANG_PASS` or the config. A bad password or missing character exits 255.
- Tool mode logs in as `player@localhost` (not the Unix login and host: the live player list shows
  them) and sends `hitpoint_warn` 6 (`--hpwarn N`, 0-9): below N×10% HP the server slows our time
  bubble in proportion to HP (xtra2.c ~5190). Both in `c-init.c` (commit 6274e8b).
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

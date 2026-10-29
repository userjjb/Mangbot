# The tool-mode client and our server changes

MAngband is client/server: the server (`mangband`) runs the world, and a client (`mangclient`) draws it and sends
commands. We play through a modified client: `mangclient -mtool` is a headless mode with no screen and no keyboard
that prints what happens as JSON lines on stdout and takes one-line commands on stdin. Every program of ours that
plays (the Pilot, shopcat, the set-piece harness, scribe) starts this client as a child process through the Python
wrapper `tools/shopcat/mang.py: MangClient`. All client changes are client-only and work against any 1.5.3 server,
the live one included. The few server changes (a time freeze, store guards, a wider depth indicator) exist only in
our build, which runs only as the local **test server**.

Upstream is MAngband 1.5.3 (commit 1 of `github/`, "Pristine MAngband 1.5.3 sources"; really upstream develop of
2022-03-13). Our changes: `git diff 6963c00 HEAD -- src` (17 files, ~1800 lines added, ~1100 of them `c-tool.c`).
Related docs: [pilot-core.md](pilot-core.md) (how the Pilot uses the client), [commands.md](commands.md)
(`pilotctl`, including `raw`, which passes a line straight to this client), [harness-rulebook-ops.md](harness-rulebook-ops.md)
(set-pieces, `dm.py`, ops scripts). Protocol background: `notes_merge.md` (survey of the upstream protocol).

## Files

| File | Ours? | What it does |
|---|---|---|
| `src/client/main-tool.c` | new | The `tool` display module: one big in-memory terminal, output hooks that do nothing, no keyboard. Selecting it sets `tool_mode` and `no_prompt`. |
| `src/client/c-tool.c` | new | The tool loop (`tool_loop`) that replaces the interactive `Game_loop`: pumps the network, answers server requests without UI, reads stdin commands, prints events. Its header comment is the protocol summary. |
| `src/client/c-pktlog.c` | new | The optional packet logger (`--pktlog PATH`). |
| `src/client/client.c` | changed | Registers the `tool` module (`-mtool`, only when asked for explicitly) and the help text for our options; starts the packet logger. |
| `src/client/c-init.c` | changed | `--noprompt` login (`read_noprompt_password`), `--birth` automation in `Setup_loop`, neutral login names, `--hpwarn`, extra window subscriptions, `tool_setup_visuals`, then `tool_loop()` instead of `Game_loop()`. |
| `src/client/c-birth.c` | changed | `get_char_name` skips the name/password prompts under `--noprompt`; `tool_birth_apply` parses `--birth`. |
| `src/client/c-util.c` | changed | `inkey_ex` answers ESC in tool mode (reporting `blocked_input`) and logs consumed keys to the pktlog; `askfor_aux` mutes key logging for private (password) input. |
| `src/client/c-xtra2.c` | changed | `do_handle_message`: in tool mode, every game message becomes a `message` event (no `-more-` prompt). |
| `src/client/c-files.c` | changed | `show_popup`: in tool mode a finished popup becomes a `popup` event instead of being drawn. |
| `src/client/net-client.c` | changed | Hooks: pktlog records for every packet received and sent; `recv_term_info` (monster/item lists, the special screen), `recv_cursor` (own position), `recv_target_info` (`look` results); `pktlog_recv_name`. |
| `src/client/c-externs.h`, `c-variable.c`, `Makefile.am` | changed | Declarations, the `no_prompt` flag, the new source files. |
| `src/server/net-server.c` | changed | The test-server time freeze (`time_frozen`). |
| `src/server/store.c` | changed | Guards against a purchase/sale arriving when the player is not in a store. |
| `src/server/tables.c` | changed | The `depth` indicator sent as 16 bits instead of one signed byte. |
| `tools/shopcat/mang.py` | ours (Python) | `MangClient`: starts the client, reads events on a thread, `send`, `wait`, `query`, `wait_ready`, `quit`. Also `meta_servers()` (the metaserver list). |
| `tools/freeze.sh` | ours | `on | off | toggle | status` for the test-server freeze file. |

## Launching the client

```
mangclient -mtool --libdir github/lib [--visuals FILE] [--hpwarn N] --config CFG [--birth SPEC] [--pktlog LOG] \
           --passfile PASSFILE --nick NICK HOST PORT
```

`MangClient` builds exactly this line (SERVER and PORT must come last). The Pilot (`pilot.py: main`) adds
`--visuals runs/pilot/<nick>/visuals.txt` (written at start by `glyphs.write_visuals`) and `--hpwarn` (Pilot default
5); passwords and configs default to `runs/private/<nick>.pass` and `runs/private/<nick>.mangrc`. The Pilot is
normally started by `tools/pilot/restart.sh NICK [PORT]` (port 28346, the test server).

| Option | Effect |
|---|---|
| `-mtool` | Headless tool mode. Implies `--noprompt`. |
| `--noprompt` | Log in without any prompt; the character must exist (unless `--birth`). Put it before another `--option`, not right before SERVER (the bool flag's parsing). |
| `--passfile PATH` | Password for `--noprompt` (first line). Else env `MANG_PASS`, else `pass` in the config. There is deliberately no `--pass` (command lines are visible to other users). Truncated to 15 characters like the interactive prompt; empty or the placeholder `passwd` quits. |
| `--nick NAME` | Character name (upstream option). |
| `--config PATH` | Config file (upstream). The client **rewrites its config on exit**: give each concurrent client its own. |
| `--birth RACE:CLASS:SEX:STATS` | Create the character if it doesn't exist **or is dead**. E.g. `Half-Orc:Warrior:m:DEX,STR,CON,WIS,CHR,INT`. |
| `--visuals FILE` | Extra glyphs uploaded to the server (see Visuals). |
| `--hpwarn N` | Tool mode: the `hitpoint_warn` setting, 0-9, default 6 (see Time bubble). |
| `--pktlog PATH` | Append a packet log (also env `MANG_PKTLOG`). Works in the interactive client too. |

Exit: a bad password, a missing or dead character without `--birth`, or a lost connection makes the client quit
(stderr says why; a bad password or missing character exits 255). `MangClient` drains stderr and raises
`ClientExited` with its last lines. EOF on stdin (the parent died) also quits the client.

### Login and birth automation

- `get_char_name` hashes the preset password exactly as the prompt would (`MD5Password`) instead of prompting.
- `client_login` sends the real name and host as `player` / `localhost` in tool mode, so the live player list
  doesn't show our Unix login and host.
- `client_failed`: under `--noprompt` a failed connect gives up instead of asking "keep trying?".
- `Setup_loop`: if the server says the character doesn't exist (`PLAYER_NAMED`) or is dead (`PLAYER_BONE`), tool mode
  quits unless `--birth` was given. With it, the client waits (up to ~5 s) for the race/class/stat lists that come
  with the login reply, `tool_birth_apply` fills race, class, sex and stat order from the spec (names match the
  server's lists case-insensitively; stats not listed follow in their usual order; errors quit with a message), then
  sends the character and `PLAY_ROLL`. A dead character is replaced with `PLAY_RESTART` (a new one of the same name).
- Used by `tools/shopcat/newchar.py` (creates a throwaway and writes its `.pass` and `.mangrc`). The Pilot does
  **not** pass `--birth`, so a dead Pilot character stops the client instead of being silently reborn.

### What tool mode changes at setup

- **Terminal size** (`init_tool`): 198+sidebar wide x 70 high, big enough that the server streams the whole level
  (MAX_WID x MAX_HGT = 198 x 66) and pins the panel at (0,0). So **map coordinates are absolute**.
- **Subscriptions** (`init_subscriptions`): also the monster-list and item-list windows (for `monlist`/`itemlist`).
- **Visuals** (`tool_setup_visuals`, before the visual tables are uploaded; the server draws our map with them):
  closed house doors (features 0x71-0x78) are drawn as `0`, which no game data uses (an *open* house door still
  looks like a plain open door). `--visuals FILE` adds lines `KIND INDEX CHARCODE ATTR`, KIND `r` (monster race,
  not race 0), `k` (object kind) or `v` (flavour); chars 33-126, attrs 1-63 (the map stream can't carry bit 0x40).
  The Pilot's `glyphs.py` gives every monster race a unique glyph this way (needs the option `avoid_other`).
- **Time bubble** (`gather_settings`): sends `hitpoint_warn` = `--hpwarn` (default 6). This upstream setting also
  makes the server run our time bubble at a constant 1/5 speed while HP is below N x 10% (server `xtra2.c`,
  `CONSTANT_TIME_FACTOR`), giving the Pilot time to react. 0 turns it off.

## The I/O protocol

Commands go in on stdin, one per line. Events come out on stdout, one JSON object per line, always with `ev` (the
kind) and `t` (seconds since `tool_loop` started). Non-ASCII and control characters are `\uXXXX`-escaped.

The loop (`tool_loop`), forever: run the network (this also sends the ~1 s keepalive; the server kicks a client
silent for ~15 s), service server requests (`tool_process_requests`), report a depth change, read stdin
(non-blocking), send one queued key to an open server screen, then `flush_updates()` so client state is current.

A command is acknowledged with `ack {cmd}` once sent to the server, or answered with `error {text, cmd}`. Queries
answer with a reply event named after the query instead of an ack. An ack only means "sent": the result shows up
later as messages, `pos`, indicators, and so on. `MangClient.query` waits for the reply event or an `error` whose
`cmd` matches.

### Commands

DIR is a keypad digit 1-9 (5 or 0 = none). ITEM is an inventory index (a = 0). Several verbs (walk, pathfind, rest,
non-store `custom`) end with `store_leave {why}` when the client thought it was in a store (see the store gotcha).

| Command | What it does |
|---|---|
| `walk DIR` | One step (PKT_WALK). `walk 0` inside a store leaves it. |
| `pathfind Y X` | Server-side pathfinding to an absolute square (PKT_PATHFIND; ~25-tile radius, treats the unseen as open: the Pilot plans its own paths). |
| `open DIR`, `alter DIR` | The server's `o` / `+` custom commands (e.g. enter a player shop). |
| `eat ITEM` | The `E` custom command. |
| `examine SLOT` | In a store: the `l` store command; the reply is a `popup`. Refused outside a store. |
| `leave` | Leave the store (PKT_STORE_LEAVE). |
| `custom KEY [store] [item=N] [dir=N] [value=N] [entry=TEXT]` | Any server-defined custom command, found by its key (indices are never hard-coded; `store` picks the store variant of the key). `entry=` takes the rest of the line (max 59 chars). Examples the Pilot uses: `custom q item=3` (quaff), `r` read, `w` wield, `t` take off, `k` destroy, `F` fuel, `,` stay/pick up, `c dir=` close, `h dir=` buy a house, `s store item=I value=N` sell, `p store item=SLOT value=N entry=TOTALPRICE` buy (`entry` is the offer the server checks), `M` the map screen. `commands` lists them all. |
| `rest` | Toggle resting (PKT_REST: not a custom command; the `state` indicator shows it). |
| `look N` | N steps (default 10, max 30) of the server's targeting in kill mode: it cycles visible monsters in line of sight, nearest first, then ESC. Each step returns a `target` event. Takes no game time. |
| `clear` | PKT_CLEAR (what ESC sends): the server empties our queued commands. Sent before logging out and to unstick a queue that runs one step behind. |
| `redraw` | PKT_REDRAW: the server resends inventory, equipment, indicators, map. Refused inside a store. No game time. |
| `confirm yes|no` | `yes` answers the next confirm prompt with yes, if it arrives within 5 s; `no` cancels that. |
| `option NAME yes|no` | Set a game option (same path as a pref-file `Y:`/`X:` line) and send the options to the server. |
| `chat TEXT` | Send a chat line as typed after `:` (`Name: text` is private). Our characters never chat except at the user's request. |
| `suicide NICK` | Kill this character for good (NICK must match the logged-in name; for throwaways). |
| `interactive TYPE` | Open a server screen and keep it open (e.g. 13 = SPECIAL_FILE_MASTER, the DM menu, as `tools/harness/dm.py` uses). Its redraws arrive as `special` events. |
| `keys TEXT` | Queue keys for that screen, sent one per loop pass. Escapes: `\e` ESC, `\r` or `\n` Enter, `\t`, `\b`, `\xNN`, `\\`, `^X` = Ctrl-X. Queue of 2047 keys. An ESC that empties the queue closes the screen. |
| `quit` | Exit the client (drops the connection; see Orphans). |
| Queries: | |
| `status` | `status {y, x, ghost, ind}`: own position and every indicator by its server name (`ind.depth`, `ind.hp`, `ind.state`, ...): a string or an array of numbers. |
| `inven` | `inven {items: [{item, equip, name, tval, number, weight}]}`: pack and equipment (`equip` for slots from INVEN_WIELD up). |
| `map` | `map {stream, wid, hgt, rows[], attrs[]}`: the whole level, full-width rows (columns line up); `attrs` has one character per cell, `chr(48 + attr)` (`~` for attr >= 64). |
| `flags` | `flags {flags: {res_acid: "ab@", ...}}`: the character sheet's resist/ability grid; for each of 32 flags the equipment slots (`a`-`l`) granting it, `@` = the character itself. |
| `floor` | `floor {name, tval, number}`: the top item under us (the client keeps no piles). |
| `options` | `options {list: {name: bool}}`: every option. |
| `commands` | `commands {list: [{i, key, pkt, scheme, flag, store, display}]}`: the server's custom commands. |
| `minimap` | `minimap {rows[]}`: the `(M)ap` screen's rows after `custom M`; its frame shows the true wilderness position, e.g. `[14N, 2W]`. Unused by our Python tools. |
| `special` | A `special` event with the special screen's current rows. |

Anything else gives `error {text: "Unknown command"}`.

### Events

| Event | Fields | When |
|---|---|---|
| `ready` | `nick, door, visuals` | In the game. `door` = the closed-house-door glyph (`0`), `visuals` = glyphs set from `--visuals`. Inventory, indicators and map arrive ~1 s later (`wait_ready` waits 1.5 s). |
| `message` | `type, text` | Every game message (`type` is the MSG_ code). Also kept in the client's message history. |
| `pos` | `y, x` | Own absolute position, on change (from the server's player cursor). |
| `level` | `depth` | The `depth` indicator changed (also once at start). Depth in levels; negative = wilderness index. |
| `monlist` | `lines[]` | The server's list of visible monsters, on each refresh. |
| `itemlist` | `lines[]` | The server's list of seen objects, on each refresh. |
| `target` | `y, x, win, text` | One `look` step, e.g. `a Warg (unhurt, asleep) [r,...]`. |
| `store` | `flag, name, owner, num, items[{slot, name, number, price, weight, ga, gc, attr}]` | Entered a store or a player shop (`ga`/`gc` = glyph attr/char, `attr` = tval colour). |
| `store_leave` | `why?` | The server closed the store (no `why`), or the client concluded it did because we sent a non-store command (`why` says which). |
| `popup` | `header, lines[]` | A server popup is complete (MOTD, examine text, ...). |
| `pause` | — | The server asked for "any key" (e.g. `pause_after_detect`). The server doesn't wait; nothing is sent back. |
| `confirm` | `type, id, prompt, answer` | A yes/no prompt (sell, destroy, disarm...). Declined unless `confirm yes` came within 5 s; `answer` says which. |
| `interactive` | `header, kept` | The server opened a remote browser screen. Closed with ESC at once unless we opened it with `interactive` or have keys queued (`kept`). |
| `special` | `lines[]` | The kept special screen (the DM menu) was redrawn, or the `special` query. |
| `local_browser` | `header` | The server asked for a local file browser; reported only. |
| `blocked_input` | `where` | Some client code path wanted a key; it got ESC. More than 1000 in one loop pass quits ("stuck in an input prompt"). |
| `ack` | `cmd` | A command was sent. |
| `error` | `text, cmd?` | A command was refused or failed. |
| reply events | see the queries | `status`, `inven`, `map`, `flags`, `floor`, `options`, `commands`, `minimap`. |

## Packet logging (`c-pktlog.c`)

`--pktlog PATH` (or `MANG_PKTLOG`) appends one JSON object per line, flushed at once:

- `R` (server to client): one record per parsed packet: `{t, dir, id, name, len, res, hex, txt}`. `name` is the packet
  constant, or `STREAM:<mark>` / `IND:<mark>` for the dynamically numbered streams and indicators. `res` is the
  handler's result (-1 = fatal).
- `S` (client to server): one record per flushed chunk (leading keepalives split out), named from the server's table.
- `E`: notes (`pktlog started epoch=...` gives the wall clock of t=0; `connected to server`; `connection closed`).
- `K`: a key consumed by a command or prompt in the interactive client: `{key, code, keymap, icky}` (`keymap` = from a
  keymap expansion, `icky` = a menu/popup was up). Used by `tools/observe/record.py` to study a human's play next to
  the packets it produced.

Privacy: password hashes in sent packets (`$1$` + 32 hex, from login and password change) are blanked to `X`,
because on the wire the hash works like the password; keys typed at private (password) prompts log as
`{"muted":true}`. Everything else, chat included, is logged. The Pilot logs packets only when started with
`--pktlog`.

## Server changes (test server only)

### Time freeze (`net-server.c: time_frozen`)

While the file named by `$MANGBAND_FREEZE_FILE` exists, the server runs no game turns: `dungeon_tick` returns
before `dungeon()`, and `post_process_players` doesn't execute queued player commands (otherwise a step with stored
energy would still run at once). Connections, keepalives and the command queue keep working; commands wait.
The file is checked every 10 ticks; on a change the server logs "Time frozen"/"Time thawed" and tells every player
`*** Time is frozen (test server) ***` / `*** Time flows again ***`. Without the variable the server never
freezes, so the feature is inert anywhere else. Why: the user wanted to pause the world to look at a situation (or
let the Architect think) without the character dying. Toggle with `tools/freeze.sh on|off|toggle|status` (file
`testserver/FREEZE`) or F5/Ctrl-F in the viewer. The Pilot watches the same file (`world.py`, `FREEZE_FILE`) and
holds its game clock. A client logging in while frozen waits until thawed.

### Store guards (`store.c`)

`get_store_item`, `store_purchase` and `store_sell` refuse when the player's `store_num` is outside 0-8, and
`get_store_item` refuses a slot past the stock. Why: the server leaves a store silently on any non-store command
and on a redraw (`store_num` = -1, no store_leave packet); a purchase arriving after that read `store[-1]` and
segfaulted the test server (2026-10-17, mission 21). The client-side fix (below) protects live servers, which lack
this patch.

### Depth indicator (`tables.c`)

The `depth` indicator is sent as 16 bits (NORMAL) instead of one signed byte (TINY). Why: far-wilderness indices
below -127 wrapped (14N 2W = -543 showed as -31). The client learns indicator formats at login, so the stock
client reads either. On the live server depth still wraps: use the `minimap` query for the true position.

## Building

`cd /projectnb/jbrcs/mangband/github && make` builds both `mangclient` and `mangband` in `github/` (already
configured GCU-only: `--with-gcu=yes`, X11/SDL off). To regenerate the build system: `./autogen.sh -n` (plain
autogen fails once `.git` exists; copy `config.guess`/`config.sub` from `/usr/share/automake-1.16/`), then the
GCU-only configure. New client source files go in `src/client/Makefile.am`. A rebuilt client is picked up by the
next Pilot start (`restart.sh` parks first); a rebuilt server needs the test server restarted.

## Test server vs live server

| | Test server | Live server |
|---|---|---|
| Where | local, port 28346, `testserver/` (own `mangband.cfg`, `save/`, `bone/`, `data/`; game data from `github/lib`) | mangband.org:18346, a shared world with real players; the operator allows automated clients |
| Binary | our `github/mangband` (freeze, store guards, 16-bit depth) | upstream 1.5.3 (patched by its admins for the arena overflow) |
| Started | `cd testserver && MANGBAND_FREEZE_FILE=$PWD/FREEZE nohup gdb -batch -ex run -ex bt --args ../github/mangband >> gdb_run.log 2>&1 &` (run from its directory: `-c` is broken); stop with SIGTERM (clean save) | — |
| Config | DM `Gandalf` (secret), `NEWBIES_CANNOT_DROP=false`, `LEVEL_UNSTATIC_CHANCE=30`, `MAX_HOUSES=0`, not on the metaserver | unknown |
| Players | ours only | others; rules in `operations.md` (recall before logout, never idle in a store, ask the admins first) |
| Pilot flag | default (mapping/detection devices are sold: no crutches) | `pilot.py --live` (keeps them; holds off the stairs back to a fled level) |

The client is the same for both.

## Gotchas

- **Orphans after logout.** A dropped connection (every `quit`, Pilot restart or park) leaves the character in the
  world, vulnerable, until it has been idle 15 s (at once in town; `player_drop`). A login before that resumes it
  from memory and ignores the savefile. Never copy a savefile less than 20 s after a logout
  (`tools/harness/charsave.sh` waits). The server saves all players, orphans too, every few minutes.
- **Queued commands at disconnect crash the test server** (NULL `pcommands` in `process_player_commands`): send
  `clear` before quitting; `restart.sh` parks the Pilot, which does.
- **The silent store exit.** The server leaves a store on any non-store command and on a redraw without telling the
  client. The client tracks `tool_in_store`: it reports `store_leave {why}` after walk, pathfind, rest or a non-store
  `custom`, refuses store commands outside a store and `redraw` inside one. The Pilot also never redraws while
  shopping.
- **Passwords.** Plaintext passwords live only in `runs/private/` (mode 600/700) or `MANG_PASS`. Packet logs blank the
  hash and mute password keys, but a log made with an older client, or anything else in a log (chat, names), is not
  scrubbed: treat pktlogs as private.
- **Wilderness arenas crash the test server:** an 11th wilderness arena overflows `MAX_ARENAS` (no bounds check,
  `wilderness.c`) and the server segfaults later. Keep tool characters out of the far wilderness there (live is patched).
- **Same nickname twice:** a second login kicks the first ("Reconnect from other location").
- **Ports:** `pilot.py` and `MangClient` default to port 18346 (the live port) on localhost; the scripts pass 28346.
- **Config rewrite:** the client rewrites its `--config` file on exit; never point it at the tracked `github/.mangrc`.
- `quit(msg)` treats a message starting with `-` as an exit code. Stat names arrive as `"STR: "`.
- Inventory data arrives ~1 s after `ready`.
- A command sent just as a run ends may be ignored; a stairs command right after arriving can be ignored (retry).
- `recv_cursor`: the server sends the player cursor as (vis, y, x), so the client's variable named `x` holds y;
  `tool_note_cursor` is called accordingly.

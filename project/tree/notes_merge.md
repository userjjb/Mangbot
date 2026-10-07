# MAngband — merged survey notes for a tool-driven shop-cataloging client

Survey of the client, common and server code, with the key claims checked against source. §13 lists easy-to-make
wrong assumptions and the verified facts. §14 is the handoff guide for implementation. Items marked **(unverified)**
have not been re-checked against source.

Repo root: `/projectnb/jbrcs/mangband/github` (MAngband 1.5.3; `CLIENT_VERSION_EXTRA == SERVER_VERSION_EXTRA == 0`).
Paths below are relative to `github/src/`. `server/` and `common/` are reference-only; all edits go in `client/`
(plus build files).

**Goal:** a modified `mangclient` that an external tool can drive to find player-owned shops, enter them, and record
their stock (name, count, price, weight, glyph, owner, store name, and optionally the full "examine" text).

---

## 1. Layout & build

- `common/` — packet IDs (`pack.h`), wire (de)serializer (`net-pack.c`), sockets/timers/event loop (`net-imps.c`,
  `net-basics.c`), shared defines/types (`defines.h`, `types.h`). Built into `libcommon.a`.
- `client/` — `mangclient`. Core logic in `c-*.c`, `net-client.c`, `client.c`. Display frontends are `main-*.c`
  (gcu/curses, x11, sdl, sdl2, win, crb), selected with `-m<name>`.
- `server/` — `mangband`. Read for protocol understanding only.
- Build: `./autogen.sh && ./configure && make`. Minimal GCU-only build:
  `./configure --with-x11=no --with-sdl=no --with-sdl2=no --with-crb=no --with-gcu=yes` (needs only ncurses).
- A new source file (headless frontend / tool bridge) must be added to `client/Makefile.am` and registered in
  `client/client.c: main()` (191), the same way as `init_gcu`.
- Runtime needs the lib dir: `ANGBAND_PATH`, `--libdir`, or `LibDir` in `~/.mangrc` (`c-init.c: init_stuff()`).
- Host/port/nick/pass come from the config (`conf_get_string("MAngband", ...)`, `--config PATH`), the positional
  `SERVER [PORT]` args, and `--nick`. If a host is given, the metaserver is skipped (`client_init()`, c-init.c 905).

---

## 2. Protocol fundamentals

**Framing:** a byte stream of `[1-byte packet type][payload]` with **no length prefix**; each handler knows its own
format. A handler returns `1` = ok, `0` = incomplete (read position is rewound and the whole packet is retried when more
bytes arrive), `-1` = fatal, `2` = ok but stop the read loop (`net-client.c: client_read()` ~92).
**An unregistered packet type → `recv_undef` → disconnect.** Keep the full handler table.

**Encoding** (`common/net-pack.c`, `cq_printf`/`cq_scanf`) — big-endian, packed by hand:

| Code | Meaning |
|---|---|
| `%b` / `%uc` | u8 |
| `%c` | s8 |
| `%d` / `%ud` | s16 / u16 |
| `%l` / `%ul` | s32 / u32 |
| `%uv` | variable-length uint (1/3/9 bytes) |
| `%s` / `%S` | NUL-terminated string, max `MAX_CHARS` (81) / `MSG_LEN` (256) |
| `%n` / `%N` | length-prefixed string (u8 / u16 length) |
| `%T` | raw unterminated blob |

Map rows use RLE via `cq_scanc` (`RLE_NONE/CLASSIC/LARGE/COLOR`).

**Packet tables:** the client's is in `client/net-client.h` (X-macro `PACKET(id, scheme, handler)`), installed by
`setup_tables()` (net-client.c ~2175). The server's is in `server/net-game.h`. Most game commands are **custom
commands** (§6), not fixed packets.

**Server-driven data negotiated at login** (`c-init.c: sync_data()` ~406): indicators (dynamically bind packet IDs
191–254), streams (IDs 170–190), custom commands, item testers, options. Packet IDs for indicators and streams are
**not fixed** — keep this negotiation code.

**Unused packet constants** (defined in `pack.h`, never referenced anywhere): `PKT_PLAYER_STORE_INFO` (67),
`PKT_PURCHASE` (107), `PKT_STORE_CONFIRM` (109).

---

## 3. Session lifecycle, login, keepalive, survival

**Setup sequence** (`c-init.c`):
1. `client_init()` → `get_char_name()`. This **always blocks** on `askfor_aux()` prompts for name and password, even
   when they're pre-set.
2. `call_server()` → `Setup_loop()` (440).
3. `send_handshake(CONNTYPE_PLAYER)`.
4. On `PLAYER_EMPTY` → `client_login()` sends `PKT_LOGIN` `%ud version %s real %s host %s nick %s pass`.
5. On `PLAYER_NAMED` → birth (`get_char_info()`, interactive menus).
6. `client_setup()` sends settings, options, and the **visual tables** (§5).
7. `PLAY_ENTER` → `client_ready()` (keepalive timer, `init_subscriptions()`, `cmd_init()`).
8. `PLAY_PLAY` → `Game_loop()` (597).

**Password is hashed, not sent raw.** `enter_password()` (c-birth.c ~63) calls `MD5Password(pass)`
(`common/md5.c:333`), which turns it into `"$1$" + 32 hex chars` before login. A no-prompt path **must still call
`MD5Password`**, or the server rejects the login with "Incorrect password." (`net-server.c` ~875). This is not real
security (no TLS; the hash works like a password), just a compatibility requirement.

**Version:** `client_version_ok()` (net-server.c 1172) needs `extra` to match exactly and version ≥ 1.5.0. Inside the
session, the server picks packet formats by declared version (e.g. `send_store` vs `send_store_DEPRECATED` below
1.5.3), so the declared version must match the parsing code compiled in.

**Keepalive:** the client sends `PKT_KEEPALIVE` every ~1 s from a timer inside `network_loop()`. The server kicks after
~15 s with no traffic ("Ping timeout", net-server.c ~678). **Never stop pumping `network_loop()`**, including while
idle or waiting on the tool.

**Same-nickname reconnect kicks the older session** (net-server.c ~885–900, "Reconnect from other location.").
**Use a character dedicated to the tool.** Reusing an already-created character also avoids automating birth.

**AFK and hunger:**
- `afk_seconds` resets only in `do_cmd__before()` (net-game.c 2352), i.e. when a real gameplay command runs — not on
  keepalives or incoming data.
- Food drains every turn; below `PY_FOOD_STARVE` the character takes damage and can die (permadeath). If the server
  was built with `DISCONNECT_STARVING`, a starving AFK player is disconnected (dungeon.c ~1157).
- The driver should carry food and periodically issue Eat (`'E'`, custom command, `SCHEME_ITEM`).

**`PKT_CONFIRM` prompts** (`recv_confirm_request` → `process_requests` → blocking `get_check`) for pickup and
house/store-sell confirmations. The tool needs a non-interactive default answer, e.g. always decline.

**Policy:** no anti-automation code exists in the source. That is not permission — check the server operator's rules.

---

## 4. How player shops work (server rules)

**Entering:**
- Any **owned** house acts as a shop for **non-owners**. `do_cmd_open_aux()` (server/cmd2.c 1188–1263) on a
  `FEAT_HOME_HEAD..TAIL` door does one of three things:
  - **You own it** (or have `DM_HOUSE_CONTROL`): the door opens (`FEAT_HOME_OPEN`) and anyone shopping there is
    ejected ("The shopkeeper locks the doors." + `PKT_STORE_LEAVE`). You do **not** get a store view this way.
  - **Someone else owns it:** `do_cmd_store(p_ptr, house_idx)` runs → `store_num = 8`. The door stays closed.
  - **Unowned:** you get the message "This house costs N gold." and nothing else happens.
- You must be **adjacent** to the door and **not a ghost**. Ways to trigger it:
  - Custom command `'o'` Open (`SCHEME_DIR`) or `'+'` Alter, aimed at the door. **Recommended.**
  - Walking into the door, if option **`easy_alter` (default ON**, tables.c 2558**)** or `bump_open` (default OFF) is
    set **and** the door is already marked as seen (`CAVE_MARK`). `do_cmd_walk` → `do_cmd_alter` → `do_cmd_open_aux`
    (cmd2.c 2958, ~2722).
  - Otherwise walking into it gives "There is a closed door blocking your way." (cmd1.c ~1929).
- NPC shops (`FEAT_SHOP_HEAD..TAIL-1`, digit doors `1`–`8`) are entered by walking into them (cmd1.c ~1962).
- Door "strength"/colour only changes the door colour and whether look says "Home" or the store name.

**Listing** (`server/store.c: display_inventory()` 1145, `display_entry_live()` 1093):
- Every grid in the house rectangle is scanned row by row (y, then x). Each object whose inscription contains
  `"for sale"` is listed. **Max 48 entries** (`STORE_INVEN_MAX`); the rest are silently dropped.
- Name: `object_desc_store(..., mode 4)`, forced aware + known (always the true name), inscription stripped,
  **truncated to 65 chars**.
- Price (`price_item()` 183, store 8): `max(3 × object_value, askprice)`. The askprice is the integer after
  `"for sale "`. There's no charisma or haggling adjustment. **The owner sees 90%** of that.
- The price is per item, `num` is the stack size, and weight is per item.

**Store name and owner:**
- The store name comes from any object inscribed `"store name <X>"` (default `"Store"`; `get_player_store_name()` 1229).
- The owner is `houses[].owned`.

**Locks:**
- If any player is physically inside the house, entering gives "The doors are locked." (`do_cmd_store` 2221).
- Trying to buy while someone is inside gives "The shopkeeper is currently restocking." plus a forced leave.

**Leaving:**
- Any non-store command (walk, rest, a non-`COMMAND_STORE` custom command) sets `store_num = -1` on the server.
- The client leaves by sending `PKT_WALK` dir 0 (`send_store_leave()`, net-client.c 425).
- **Never send movement while you intend to stay in the store.**

**Examine** (`'l'` in the store → `do_cmd_observe`, cmd3.c 893):
- The server re-scans with `get_store_item()` (store.c 1561) to find the Nth for-sale item, identifies a copy, and
  sends "Examining <name>..." plus a popup (`send_prepared_popup`, util.c 3034):
  1. `PKT_TERM` activates `NTERM_WIN_SPECIAL`.
  2. A header line.
  3. Clear.
  4. N rows of `STREAM_SPECIAL_TEXT`.
  5. `NTERM_POP`.
- The rows are attr/char cells in `stream_cave(window_to_stream[NTERM_WIN_SPECIAL], row)`, readable text (no OCR
  needed).
- Examine gives the **untruncated name plus flags/abilities**. Indices can shift if the owner moves items between
  listing and examining.

**No way to list other players' shops.** `houses[]` is never broadcast, and `display_houses` (cmd4.c 245) lists only
your own houses. Discovery means exploring the map (§5).

---

## 5. Store packets, map data, and discovery

### Server → client store packets

| Packet | Format | Client handler | Notes |
|---|---|---|---|
| `PKT_STORE` (51) | `%b pos, %b ga, %c gc, %c attr, %d wgt, %d num, %ul price, %s name` | `recv_store` (net-client.c 508) | One row per item. No tval/k_idx field. `ga/gc` = the item kind's colour/symbol (`object_attr_p/char_p`) — in text mode these are the normal item glyphs (`!`, `?`, `|`...). `attr` = `tval_attr[tval]`. Stored in `store.stock[pos]` (the `.sval`, `.ix`, `.iy` fields are reused for colour/glyph), `store_prices[]`, `store_names[]`. |
| `PKT_STORE_INFO` (52) | `%c flag, %s store_name, %s owner, %d num_items, %l max_cost` | `recv_store_info` (542) | Flag bits `STORE_NPC 1 / STORE_PC 2 / STORE_HOME 4` (defines.h 306). Sets `enter_store = TRUE`. |
| `PKT_STORE_LEAVE` (108) | — | `recv_store_leave` (567) | Server-initiated forced exit (server→client only). |
| `PKT_MESSAGE` (46) | `%ud type, %S msg` | `recv_message` (1771) → `do_handle_message` (c-xtra2.c 300) | Locked / restocking / "exclusive" / "costs N gold" messages. |
| `PKT_TARGET_INFO` (53) | `%c x, %c y, %c win, %s text` | `recv_target_info` (1712) | Look text. |
| `PKT_TERM` / `PKT_TERM_INIT` / stream packets | — | `recv_term_info` (1526), `recv_term_header` (1639), `recv_stream` (1330) | Carries the examine popup. |

**Order on entry:** all `PKT_STORE` rows come **first**, then `PKT_STORE_INFO` (`display_store()`, store.c 1292). So
store info marks the end of the initial listing. Rows received before it have to be kept, not discarded. Mid-visit
refreshes (`refresh_store`) may resend info and/or rows in either order. `store.stock[]` is never cleared between
visits; only `store.stock_num` marks which rows are valid.

If a forced leave (`recv_store_leave`) arrives before a full listing, treat the visit as incomplete and retry later.

### Map

- The map arrives through the stream system: stream 0 `DUNGEON_ASCII` (`NTERM_WIN_OVERHEAD`) is stored in
  `p_ptr->stream_cave[0]`. Cells are `cave_view_type {a, c}`, i.e. rendered colour and character, not feature IDs.
- Streams must be subscribed before the server sends them; an unsubscribed stream → -1. Keep `init_subscriptions()`,
  including the SPECIAL stream that examine popups need.
- **Full-level view:** stream 0's max size is 66×198 = `MAX_HGT×MAX_WID`, which is the size of every level (town,
  wilderness, dungeon). The server sets its screen size from the subscription (`recv_stream_size`, net-game.c 1523)
  and recomputes the panel. Subscribing at 66×198 puts the panel at (0,0), so **map coordinates are absolute** and the
  whole level is streamed, which makes `send_locate` scrolling unnecessary.
  - Client size comes from `net_term_manage()` (net-client.c 2350) using `Term->wid/hgt` minus offsets, or the
    `query_size_aux` hook (z-term.h 371).
  - Only grids the character remembers (`CAVE_MARK`) are shown.
- **Custom glyph tables.** The client uploads its own colour/character tables (`send_visual_info`, net-client.c 263;
  server `recv_visual_info`, net-game.c 1333) and the server draws the map with them (`map_info`, cave.c 793).
  - By default house doors look like ordinary doors: `+` closed, `'` open (terrain.txt 113–120, 81). The tool can
    give `FEAT_HOME_HEAD..TAIL` (0x71–0x78) and `FEAT_HOME_OPEN` (0x51) a **unique** symbol, which makes house doors
    unambiguous on the map.
  - Unique `k_attr/k_char` per item kind (`VISUAL_INFO_K`) make `ga/gc` identify the **exact item kind** for kinds the
    character has already identified. Unidentified kinds show their flavour glyph instead.
  - Unique `tval_attr` (`VISUAL_INFO_TVAL`) makes `attr` identify the item **category (tval)**.
  - Avoid the value 0, which means "use the default".
- A second way to tell doors apart is to try opening each one and see what comes back: unowned → "costs N gold",
  owned → `STORE_INFO` with `STORE_PC`, ordinary door → nothing shop-related.
- **Owner check without opening:** look mode reports "the entrance to X's Store/Home" or "a door to foreign house"
  (xtra2.c ~4197). Owned house doors count as "interesting" to look mode (~3872). Two ways to trigger it:
  - `PKT_LOOK %c mode %c key`.
  - `PKT_CURSOR` with `MCURSOR_META` at a panel-relative x,y (`target_set_interactive_mouse`, xtra2.c 4812).
- **Location:**
  - The `IN_DEPTH` indicator carries the raw `dun_depth` (0 = town, negative = wilderness index).
  - The locate command reports "Map sector [y,x]".
  - Wilderness world coordinates appear as `[3N, 2E]` (`wild_cat_depth`).
- **(unverified)** Houses are scattered across the wilderness, densest near town (wilderness.c building generator).
  Search outward from town. Most houses will be unowned.

### Movement

- `PKT_WALK %c dir`. Movement costs energy, and the server may skip a walk if two more walks are already queued
  (net-game.c `recv_walk`). Track your real position from the map instead of assuming each packet moved you one tile.
- **Pathfinding works:**
  - Send `PKT_PATHFIND %c y %c x` directly, with absolute level coordinates. It is a normal server command (`PCOMMAND`,
    net-game.h). The client has no `send_pathfind()` yet; it's trivial to add. Reach is up to 25 tiles, and
    `findpath` fails beyond that.
  - Alternatively, `send_mouse(MCURSOR_LMB, x, y)` with panel-relative coordinates → `recv_mouse_hack` → pathfind.
    This is what the live `cmd_mouseclick()` already does.
  - The `#if 0` `do_cmd_pathfind` in `c-cmd0.c` is dead code, but that is irrelevant.
- Confusion randomizes walk direction (`do_cmd_walk`).
- **(unverified)** Paralysis blocks command execution (dungeon.c ~987). Detect it from the state indicators.

---

## 6. Custom commands (how open/examine/buy/eat actually work)

- Defined server-side in `server/tables.c: custom_commands[]` (line 43). Sent at connect via `PKT_COMMAND` →
  `recv_custom_command_info` (net-client.c 1812) into the client's `custom_command[]`.
- Relevant keys:
  - `'o'` Open (`SCHEME_DIR`), `'+'` Alter (`SCHEME_DIR`).
  - `'E'` Eat (`SCHEME_ITEM`).
  - `'h'` Buy/sell house (`SCHEME_DIR`).
  - Store commands (flag `COMMAND_STORE`):
    - `'p'` Purchase (`SCHEME_ITEM_VALUE_STRING`; the server parses the price string but doesn't use it).
    - `'s'` Sell (not allowed in player stores).
    - **`'l'` Examine** (`SCHEME_ITEM`).
- Send with `send_custom_command(i, item, dir, value, entry)` (net-client.c 445). Look up `i` by `m_catch` letter
  (and the `COMMAND_STORE` flag for store commands) after connecting. **Never hard-code indices**; they are
  server-defined.
- `cmd_custom()` (c-cmd.c 9) is the interactive driver (prompts for item/amount/direction). For store items it uses the
  page-relative `get_store_stock()` (c-store.c 181, 12 items per page). A tool should skip it and call
  `send_custom_command` directly.
- The `Send_store_purchase` / `Send_store_sell` / `Send_observe` / `Send_run` / ... macros in `c-externs.h` (~620–641)
  are **stubs that only log an error**. Don't use them.

---

## 7. Client architecture (what we're working against)

- Single-threaded and **blocking on the UI**. The network is pumped inside the key-wait loop `inkey_aux()`
  (c-util.c 252): `Term_inkey` → `network_loop` → `flush_updates`, repeated. Every prompt (`get_com`, `askfor_aux`,
  `c_get_quantity`, `get_check`, `prepare_popup`) blocks there.
- Handlers mostly set globals and flags. State changes happen in `process_requests()` (c-cmd.c 553):
  - pause / popup / browser requests
  - confirm prompts
  - **`enter_store` → `display_store()`**
- `display_store()` (c-store.c 449) is its own modal loop until `leave_store` is set, then it calls
  `send_store_leave()`.
- `Game_loop()` (c-init.c 597): `network_loop` → `request_command` (keyboard) → `process_command` →
  `process_requests` → `flush_updates`.
- Frontend contract: `term` hooks in `z-term.h` (`init/nuke/xtra/curs/wipe/text/pict_hook`; `TERM_XTRA_EVENT` for
  input). `main-gcu.c` (1155 lines) is the simplest template.
  - Input can be injected with `Term_key_push()` / `Term_keypress()`, keymaps/macros, or `inkey_next`.
  - Existing hooks: `cave_char_aux`, `query_size_aux`, `z_ask_command_aux`, `z_ask_dir_aux`.
- `recv_term_header` ignores headers when `screen_icky && !shopping`, or while `looking`. If the tool bypasses
  `display_store()`, it must set these flags so examine popups aren't dropped.
- The client's `store_num` is never set from the network (only `store_flag`), so the `store_num == 7` checks in
  `c-store.c` are stale.
- The borg/debug hooks in `c-cmd0.c` are `#if 0` dead code.

---

## 8. Files to MODIFY (priority order)

| File | What / why |
|---|---|
| `client/net-client.c` | The main file. Hook `recv_store`, `recv_store_info`, `recv_store_leave`, `recv_message`, `recv_target_info`, `recv_confirm_request`, and `recv_term_info`/`recv_term_header`/`recv_stream` (examine popup) to send structured events to the tool. Add `send_pathfind()`. Optionally log raw packets in `client_read()`. |
| `client/c-init.c` | Non-interactive startup. Replace or extend `Game_loop()` with a tool-driven loop that keeps pumping `network_loop()` and handles `process_requests()`-type duties. Force the 66×198 map subscription in `init_subscriptions()`. Push custom glyph tables in `client_setup()`. |
| `client/c-birth.c` | `get_char_name()`/`choose_name()`/`enter_password()` always prompt. Add a no-prompt path that **still calls `MD5Password`**. Birth menus (`get_char_info`) only matter if we auto-create a character; not recommended. |
| `client/c-store.c` | `display_store()` is modal. Either bypass it (capture the data, never enter the loop) or drive it. Add non-interactive examine/list helpers (no `get_stock` prompts, no paging). |
| `client/c-cmd.c` | `process_requests()` (store entry, popups, **auto-answer `PKT_CONFIRM`**). Add a direct "run custom command by key with arguments" path alongside `cmd_custom()`. |
| `client/client.c` | CLI flags for tool mode (IPC path, headless module), plus frontend registration. |
| **new** `client/main-tool.c` (or similar) + `client/Makefile.am` (+ `configure.ac` if a switch is wanted) | Headless `term` frontend and IPC bridge (stdin/stdout JSON or a socket). |
| `client/c-files.c` | `prepare_popup()`/`show_popup()` (1745/1787) block on `inkey()`; capture examine text here or bypass it. Optionally put the custom glyphs in a pref file (`process_pref_file_command`) instead of code. |
| `client/c-util.c` | `inkey_aux()` network pump and the blocking prompt functions. `show_char`/`show_line` (2586/2635) if capturing map updates. |
| `client/c-xtra2.c` | `do_handle_message()`: one central place to forward all server messages to the tool. |
| `client/c-externs.h`, `client/c-defines.h` | Declarations and tool-mode flags. |

## 9. Files to READ (reference; probably unchanged)

- **Protocol:** `client/net-client.h`, `server/net-game.h` (packet tables); `common/pack.h` (IDs, `NTERM_*`,
  `MCURSOR_*`, `SCHEME_*`, `PLAYER_*`); `common/net-pack.c` (encoding); `common/net-imps.c` (sockets, timers).
- **Shared definitions:** `common/defines.h` (`STORE_*`, `COMMAND_*`, `MAX_CHARS`, `STORE_INVEN_MAX`, `MAX_HGT/WID`);
  `common/types.h` (`house_type`, `object_type`, `custom_command_type`, `stream_type`).
- **Client:**
  - `c-variable.c` — the store globals: `store`, `store_prices`, `store_names`, `store_flag`, `store_name`,
    `store_owner_name`, `shopping`, `enter_store`, `leave_store`.
  - `c-xtra1.c` (window/indicator redraw), `z-term.[ch]`, `main-gcu.c`, `c-cmd0.c` (keystroke helpers).
  - `c-inven.c` / `c-tables.c` — not needed for read-only cataloging.
- **Server:**
  - `store.c` — shop logic.
  - `cmd2.c` — houses, open/alter/walk/pathfind, purchase house.
  - `cmd1.c` — movement and bumping.
  - `cmd3.c` — observe, look, locate.
  - `xtra2.c` — look text, target interest, panels.
  - `net-game.c` / `net-server.c` — send/recv, login, timeouts, reconnect.
  - `tables.c` — custom commands, streams, indicators, options.
  - `cave.c` — map rendering.
  - `birth.c` — `player_verify_visual`.
  - `mdefines.h` — `FEAT_*`, item glyph macros.
  - `dungeon.c` — hunger, AFK.
  - `wilderness.c` — house placement.

---

## 10. Catalog record (suggested)

```
{ timestamp, depth, door_y, door_x, store_name, owner, flag (STORE_PC),
  slot, name (≤65 chars), full_name/examine_text (optional), count, price_each, weight_each,
  ga, gc, attr  (→ decoded k_idx / tval if custom glyph tables are used),
  complete (bool: full listing received before any forced leave) }
```

---

## 11. Gotchas (consolidated)

1. An unknown packet type disconnects the client; an unsubscribed stream also disconnects.
2. Keepalive: never go more than ~15 s without pumping `network_loop()`.
3. The password must be MD5'd (`$1$…`) even on a no-prompt path.
4. Same-nickname login kicks the other session — use a dedicated character.
5. Listing order: rows first, `STORE_INFO` last. Don't clear rows when info arrives.
6. 48-item cap; names truncated to 65 chars. Use examine for full names.
7. A forced leave or "doors are locked" means incomplete or blocked — retry later.
8. Any movement or non-store command exits the store.
9. Opening your *own* house doesn't show a store (and ejects shoppers). The tool character should own no shops.
10. You must be adjacent and not a ghost. Bump-open only works on already-seen doors with `easy_alter`/`bump_open` on.
11. Hunger and AFK: eat periodically; the AFK timer resets only on real gameplay commands.
12. `PKT_CONFIRM` and every UI prompt can hang an unattended client — auto-answer or bypass them.
13. `store.stock[]` is stale between visits; trust only `store.stock_num`.
14. Examine indices can shift if the owner rearranges items.
15. The declared client version decides which packet formats the server uses — keep it at 1.5.3 stable.

---

## 12. Implementation plan (summary)

1. Build the GCU-only client (§1) and create a dedicated, already-created character.
2. Non-interactive boot: host/port/nick/pass from config or CLI; skip prompts but MD5 the password; skip the metaserver.
3. Headless frontend + IPC bridge; replace `Game_loop()` with a tool loop that pumps the network, handles
   `process_requests` duties, and auto-answers confirm prompts.
4. At setup, push custom glyph tables (unique house-door symbol; optionally unique per-kind and per-tval glyphs) and
   subscribe the map at 66×198.
5. Look up custom command indices by key: `'o'`, `'+'`, `'l'`, `'E'`.
6. Discovery: scan the full-level map for house-door glyphs. Optionally use look for the owner. Pathfind (≤25 tiles)
   or walk to an adjacent tile.
7. Enter with `'o'` + direction. On `STORE_INFO` with `STORE_PC`, record the rows. Optionally examine each slot and
   capture the popup text. Then leave with walk dir 0.
8. Handle locked, restocking and forced-leave cases by marking the visit incomplete and retrying later.
9. Eat periodically; avoid long idle periods; search outward from town.

---

## 13. Easy-to-make wrong assumptions (verified against source)

| Tempting assumption | Verified fact |
|---|---|
| Walking into a house door never enters a shop; `'o'` is required | `easy_alter` is ON by default, so walking into an *already-seen* house door runs alter → open. `'o'` + direction is still the most reliable. |
| Opening any owned house (including your own) enters the store | Owner → the door opens, shoppers are ejected, no store view. Non-owner → store view, the door stays closed. |
| Credentials go over the wire in cleartext | The password is MD5'd to `$1$<hex>` client-side before `PKT_LOGIN`. A no-prompt login must do the same. |
| `STORE_INFO` comes first with the count, then the rows | Rows come first, `STORE_INFO` last (it marks the end of the initial listing). |
| `PKT_STORE_LEAVE` is sent by both sides | Server→client only. The client leaves with `PKT_WALK` dir 0. |
| Client-side pathfinding is dead, so the tool must walk tile by tile | `PKT_PATHFIND y x` (absolute) and mouse-click pathfinding both work; the path is computed server-side (≤25 tiles). |
| `ga/gc` only matter in graphics mode; item category must be parsed from the name | In text mode they are the item's glyph (`!`, `?`, `|`...). Custom glyph tables can encode the exact kind and tval. |
| House doors can't be told apart from ordinary doors on the map | True with default glyphs (`+` / `'`); fixed by uploading a unique glyph for `FEAT_HOME_*`. |
| Examine output needs OCR | It is plain characters in the SPECIAL stream buffer. |
| Player-shop prices are identical for every viewer | True except for the owner, who sees 90%. |
| The server sends the whole map/monsters and the client hides them | The server filters per player (`map_info`: `CAVE_MARK`, `obj_vis`, `mon_vis`, `play_vis`). Unseen areas arrive blank. |
| A modified client could move or teleport the character arbitrarily | The server is authoritative: the client sends only directions, destinations and command arguments, all validated server-side. Admin actions need server-side `dm_flags`. |

---

## 14. Handoff: environment, testing setup, and how to proceed

### Environment (checked on this machine)

- Shared cluster, Linux Alma 8, custom SGE batch system. User is staff: elevated privileges but **no sudo**.
- Available: gcc 8.5, make, autoconf 2.69, automake 1.16, pkg-config, git, and the ncurses headers and libraries
  (`/usr/include/ncurses.h`, `/usr/lib64/libncurses.so`). The GCU-only build should need no extra installs.
  An `autoconf/2.72` module also exists.
- **Python: load a module; do not use the OS `python3`** (it is 3.6.8, too old). For example
  `module load python3/3.12.4` (3.13.8 and others are available; check with `module avail python3`).
- The project directory is **not a git repository**.
- The default game port 18346 could clash with other users on a shared machine — pick another port for the local
  server. Long-running processes may be limited on login nodes.

### Test setup: local server

- The same tree builds `mangband`; the repo includes `mangband.cfg` and a `runserv` script. Run a private local
  server for all development — don't touch a live server until the tool is solid, and check the operator's policy on
  automated clients first.
- **Test character: create and use a Half-Troll Warrior, and explore only in town.** It's rugged and town threats are
  weak. Keep it dedicated to the tool (a same-name login kicks the other session).
- To create test shops, use a *second* character that owns a house. Opening your own house doesn't show a store.
  1. Buy a house (`h` + direction; town houses cost 5×).
  2. Drop items inside inscribed `for sale 500`.
  3. Optionally drop an item inscribed `store name Test Shop`.
- On a local server the admin menu (`&`, gated by `dm_flags`) can help with debugging, e.g. house control or seeing
  the whole level.

### Server-authoritative facts that shape the design

- The client sends only requests (a direction, a destination, a command plus arguments), and the server validates
  each one. No packet sets position, and there are no shortcuts.
- The server sends only what this character can see or remember. Unexplored grids arrive blank; items, monsters and
  players are filtered per viewer. The full-level map subscription only changes the viewport, not what's visible.
- So the tool must physically walk, see doors, stand next to them, and open them.

### Suggested order of work

1. **Put the tree under git** (`git init`, commit the pristine sources) before any change.
2. **Stock baseline:**
   1. Build the server and the GCU client.
   2. Run the local server, log in by hand, and create the Half-Troll Warrior.
   3. With the second character, set up one or two test shops in town.
   4. Note the messages seen when entering a shop, examining an item, and hitting a locked door.
3. **Packet logger first.** Add an optional decoded dump in `client_read()` (net-client.c ~92) and around sends, so
   assumptions (row/info order, what the examine popup looks like on the wire) can be checked directly.
4. **Build in small steps, testing each against the local server:**
   1. Non-interactive login: credentials from CLI/config, password still hashed with `MD5Password`.
   2. A headless frontend plus a tool loop that just stays connected (keepalives) and logs events.
   3. A simple command channel. Line-based JSON over stdin/stdout or a Unix socket is enough, with commands such as
      walk, pathfind, open(dir), examine(slot), leave, eat and look, and events for map rows, store rows, store info,
      messages, popups and confirm requests.
   4. Store capture with no modal `display_store()` UI.
   5. Full-level map subscription (66×198) plus a custom house-door glyph.
   6. Custom item-kind and category glyph tables, only if category decoding is needed.
5. **Keep C thin.** Put exploration, route planning, retries and catalog storage in the external tool (Python, from a
   module); the C client is an I/O layer.
6. **Make changes additive and flag-gated** (e.g. `--tool` / `-mtool`), so the normal interactive client keeps
   working for manual debugging.
7. **Never block, never hard-code indices.**
   - Every wait in tool mode must keep calling `network_loop()`.
   - Look up custom command indices by key letter after login.
   - Don't bypass stream subscription (an unsubscribed stream means a disconnect).
   - Auto-answer `PKT_CONFIRM`.

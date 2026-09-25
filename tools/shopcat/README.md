# shopcat — catalog MAngband player shops

`shopcat.py` drives the modified client in headless tool mode
(`mangclient -mtool`, see `src/client/c-tool.c`) to find every closed house
door on a level, open each one, and record what player shops sell. With
`--wilderness` it also tours the 12 wilderness levels around town.

Requires Python 3.8+ (on the SCC: `module load python3/3.12.4`; the OS
`python3` is too old). No third-party packages.

## Usage

```sh
# Private files: password (first line) and a client config per character.
# Keep them out of the source tree and away from other users.
mkdir -p ~/.mang && chmod 700 ~/.mang
umask 077; echo 'secret' > ~/.mang/surveyor.pass
printf '[MAngband]\nLibDir %s\n' "$PWD/../../lib/" > ~/.mang/surveyor.mangrc

python3 shopcat.py --nick Surveyor --passfile ~/.mang/surveyor.pass \
    --config ~/.mang/surveyor.mangrc --host localhost --port 28346 \
    --out ~/mang-runs/catalog.jsonl           # town only
python3 shopcat.py ... --wilderness --resume  # town + 12 levels around it

python3 report.py ~/mang-runs/catalog.jsonl -o stock.csv
```

| Option | Meaning |
|---|---|
| `--list-servers` | Print the metaserver's server list with `--host`/`--port` for each (the list the normal client shows); the client speaks 1.5.3 only |
| `--wilderness` | Also cover 1N 2N 1E 2E 1S 2S 1W 2W and the four diagonals (1N 1E, …), then walk back to town (`--no-return` to stay put) |
| `--explore-secs N` | Time to spend uncovering each wilderness level's map (default 480) |
| `--resume` | With `--wilderness`: skip levels that have a `level_done` record in `--out` |
| `--door Y,X` | Only visit this door (repeatable) |
| `--max-doors N` | Stop after N doors |
| `--no-examine` | Record the listing only (no per-item examine) |
| `--retries N`, `--retry-delay S` | Revisit locked/ejected/open doors up to N times, S seconds later (2, 30) |
| `--events FILE` | Append every client event (debugging) |
| `--pktlog FILE` | Raw packet log from the client |

Exit codes: 0 done; 2 stopped for safety (HP falling while resting, weak from
hunger with no food, stuck in an arena, repeatedly unable to move); 1 anything
else (client exited e.g. server down, or an unexpected error such as failing to
leave a level). Put `--out` outside the source tree; `--resume` and the no-go
file make a stopped tour easy to restart.

### The character

- Must already exist (create it once with the normal client), be dedicated to
  the tool (a login elsewhere with the same name kicks the other session) and
  own no houses (opening your own house doesn't show a store).
- **Not a Half-Troll** or anything else with REGEN: regeneration costs food in
  the wilderness (a Ration of Food every ~100 s); other characters at normal
  speed use very little, and nobody digests in town.
- It needs a light for night travel: a Brass Lantern and Flasks of oil. With a
  little gold (~50 for the lantern, 5 per flask or ration) the wilderness tour
  buys them itself at the General Store before leaving town.
- Each concurrently running client needs its own `--config` file (the client
  rewrites it on exit).

## How it works

1. The client subscribes the map at the full level size (198×66), so map rows
   and positions are absolute, and draws closed house doors as `0`.
2. Doors are visited nearest-first. `nav.py` plans a shortest path on the map
   and walks it step by step (two steps queued; ~0.5 s per tile). The server's
   own pathfind is not used: it treats never-seen ground as open, including the
   row past the level edge, so it can walk off the level, and it bumps arena
   walls it hasn't seen.
3. Standing next to a door, `open DIR` gives one of:

   | result | meaning |
   |---|---|
   | `shop` | a player shop (`STORE_PC`): listing recorded, each slot examined |
   | `for_sale` | unowned house; `house_price` recorded |
   | `locked` | someone is inside — retried later |
   | `ejected` | the owner opened the door mid-visit — retried later |
   | `no_door` | the door is open (owner around?) — retried later |
   | `none` | no answer — retried later |
   | `unreachable` | no route to a tile next to the door |

4. Upkeep between doors and legs:
   - eats when Hungry; stops if weak with no food outside town;
   - keeps a light burning: wields a lantern (else a torch), refills the
     lantern with `F` from a Flask of oil below 3000 turns;
   - fights back when attacked (walks into adjacent monsters), rests (`R`)
     below half HP, stops if HP keeps falling while resting;
   - in town, buys a Brass Lantern if it has none, and restocks food (to 10)
     and oil (to 6) with the gold it has; when
     down to one ration elsewhere, walks back to town to restock.

### Wilderness (`wild.py`)

- World square (x, y) has depth `world_index(x, y)` (the formula in
  `server/wilderness.c`; +y is north). The 12 default levels are depths
  −1…−12. Stepping off a level edge moves to the neighbouring level.
- Each level is swept: a coarse grid of waypoints (every 12 rows × 20
  columns), skipping ones already passed within 8 tiles of. At night the
  floor only shows within the lantern's radius, but house walls and doors are
  lit and show up at a distance, which is what the catalog needs.
- Trees (`*`) and logs/fences (`=`) block movement; unseen ground is assumed
  walkable and bumps are routed around.
- Arenas ("ancient fighting pit"): bumping an unseen arena wall teleports you
  inside. The tool walks back out (bumping the wall from inside, alone, lets
  you out) and marks the arena as no-go for that level, saved in
  `<out>.nogo.json`.
- If the position jumps (level change, teleport), the plan is dropped and the
  tour re-plans from wherever the character is.

## Output

`--out` gets one JSON record per door visit, plus a `level_done` record when a
level is finished:

```json
{"time": "2026-09-25T00:20:52Z", "depth": 0, "world": [0, 0], "level": "Town",
 "door_y": 16, "door_x": 88, "result": "shop", "store_name": "Test Shop",
 "owner": "Gandalf", "flag": 2, "num_items": 4, "complete": true, "attempt": 1,
 "items": [{"slot": 1, "name": "a Ring of Speed (+30)", "count": 1,
            "price_each": 4800000, "weight_each": 0.2, "ga": 10, "gc": "=", "attr": 4,
            "full_name": "A Ring of Speed (+30)", "ask_price": 1000000,
            "examine_text": "It increases your speed by 30."}]}
```

- `price_each` is what a (non-owner) buyer pays: `max(3 × value, ask_price)`.
- `ask_price` is the owner's number from the `for sale N` inscription, or
  `null` if they didn't give one (examine only).
- Listing names are truncated to 65 characters; `full_name` isn't.
- `ga`/`gc` are the item kind's display colour/glyph and `attr` the category
  colour; with default visuals they identify the category only roughly.
- A store shows at most 48 items; extra stock is silently not listed.

`report.py` keeps the latest complete visit per door and writes one CSV row per
item.

## Limitations

- Covers the current level, or with `--wilderness` the town and the 12 levels
  around it (`wild.DEFAULT_TARGETS`).
- Travel is slow (~0.5 s per tile): a full wilderness tour takes a few hours.
- Fighting is minimal (melee whatever is adjacent); a low-level character can
  still get into trouble, and the HP checks then stop the run.
- A shop whose door is open looks like an ordinary open door on the map, so it
  is only found if it was seen closed.
- **Server bug (MAngband 1.5.3): an 11th wilderness arena crashes the server.**
  `wild_add_dwelling()` (`server/wilderness.c:1171`) stores each arena in
  `arenas[num_arenas]` with no bounds check; `MAX_ARENAS` is 10 and the count
  only grows. Generating the 11th arena overwrites neighbouring globals
  (`k_name`) and the server segfaults shortly after (in `object_desc()`). On
  the test server this happens on entering 2E. Only the operator can fix it.
- The tool-mode client code (`c-tool.c`, `c-pktlog.c`, `main-tool.c`) is only
  wired into the autotools build (`src/client/Makefile.am`) and uses POSIX
  stdin handling; the Visual Studio/Xcode/Android/Borland project files would
  need those sources (and, on Windows, a different stdin reader) to link.
- Check the server operator's policy on automated clients before using this
  anywhere but a private server.

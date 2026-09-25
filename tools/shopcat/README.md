# shopcat — catalog MAngband player shops

`shopcat.py` drives the modified client in headless tool mode
(`mangclient -mtool`, see `src/client/c-tool.c`) to find every closed house
door on the current level, open each one, and record what player shops sell.

Requires Python 3.8+ (on the SCC: `module load python3/3.12.4`; the OS
`python3` is too old). No third-party packages.

## Usage

```sh
# password on the first line of a private file (never on the command line)
umask 077; echo 'secret' > ~/.mang/scout.pass

python3 shopcat.py --nick Scout --passfile ~/.mang/scout.pass \
    --host localhost --port 28346 --config ~/.mang/scout.mangrc \
    --out catalog.jsonl

python3 report.py catalog.jsonl -o stock.csv
```

Add `--wilderness` to also cover the 12 levels around town: two screens out
along each cardinal direction (1N, 2N, 1E, 2E, 1S, 2S, 1W, 2W) and one along
each diagonal (1N 1E, 1N 1W, 1S 1E, 1S 1W). The character walks off level
edges to travel, uncovers each level's map (`--explore-secs`, default 480),
catalogs its doors, and walks back to town (`--no-return` to stay put).

Useful options: `--no-examine` (listing only, faster), `--door Y,X`
(repeatable; visit only these doors), `--max-doors N`, `--retries N` and
`--retry-delay SECS` (for locked/ejected visits), `--events FILE` (every client
event, for debugging), `--pktlog FILE` (raw packet log from the client).

Give each concurrently running client its own `--config` file: the client
rewrites its config file on exit.

The character must already exist (create it once with the normal client) and
should not be a Half-Troll (or anything with REGEN): regeneration costs food
in the wilderness -- a Ration of Food every ~100 s -- while other characters
at normal speed use almost none (and nobody digests in town). It
should be dedicated to the tool: logging in elsewhere with the same name kicks
the other session. It should own no houses (opening your own house doesn't
show a store).

## How it works

1. The client subscribes the map at the full level size (198×66), so map rows
   and positions are absolute, and draws closed house doors as `0`.
2. Doors are visited nearest-first. Routes longer than the server's pathfind
   reach are split into waypoints (`nav.py`).
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

4. Between doors it eats when the hunger indicator says Hungry or worse,
   keeps a light burning (wields a Brass Lantern if it has one, else a torch;
   refills the lantern with `F` from a Flask of oil when it drops below 3000
   turns; swaps torches when they burn down), rests (`R`) when HP falls below half,
   stops if HP keeps falling while resting (exit code 2), and stops if the
   character has died.

### Wilderness (`wild.py`)

- World square (x, y) has depth `world_index(x, y)` (same formula as
  `server/wilderness.c`); the 12 default levels are depths −1…−12. Records
  carry `depth`, `world` ([x, y], +y = north) and `level` ("1N, 1E").
- Stepping off an edge moves to the neighbouring level. The tour is planned
  through target levels only and backtracks out of the far ones (20 crossings
  including the walk home).
- The map only shows what the character has had in line of sight, so each
  level is swept: a coarse grid of waypoints (every 12 rows × 20 columns),
  skipping those it has already passed within 8 tiles of.
- Day or night: by day the whole wilderness is lit; by night the floor only
  shows within the lantern's radius, but house walls and doors stay lit and
  show up at a distance, which is what the catalog needs. Unseen ground is
  treated as walkable (as the server's own pathfinding does), so travel works
  in the dark. Trees block movement.
- If the position jumps (a level change or teleport), the current plan is
  dropped and the tour re-plans from wherever the character is.

## Output

`catalog.jsonl` gets one record per door visit (appended):

```json
{"time": "2026-09-25T00:20:52Z", "depth": 0, "door_y": 16, "door_x": 88,
 "result": "shop", "store_name": "Test Shop", "owner": "Gandalf", "flag": 2,
 "num_items": 4, "complete": true, "attempt": 1,
 "items": [{"slot": 1, "name": "a Ring of Speed (+30)", "count": 1,
            "price_each": 4800000, "weight_each": 0.2, "ga": 10, "gc": "=", "attr": 4,
            "full_name": "A Ring of Speed (+30)", "ask_price": 1000000,
            "examine_text": "It increases your speed by 30."}]}
```

- `price_each` is what a (non-owner) buyer pays: `max(3 × value, ask_price)`.
- `ask_price` is the owner's number from the `for sale N` inscription, or
  `null` if they didn't give one (examine only).
- Names in the listing are truncated to 65 characters; `full_name` isn't.
- `ga`/`gc` are the item kind's display colour/glyph and `attr` the category
  colour. With default visuals they give the category only roughly.
- A store shows at most 48 items; extra stock is silently not listed.

`report.py` keeps the latest complete visit per door and writes one CSV row per
item.

## Limitations

- Without `--wilderness` it covers only the level the character is on. With
  it, the town and 12 levels around it; farther levels would need more targets
  (`wild.DEFAULT_TARGETS`).
- Wilderness monsters can hurt a low-level character; the HP checks only
  rest or stop, they don't fight or flee.
- Open house doors look like ordinary open doors on the map, so a shop whose
  door is currently open is only found if it was seen closed.
- Only grids the character has seen are on the map; in the town by day that's
  nearly everything.
- Check the server operator's policy on automated clients before using this
  anywhere but a private server.

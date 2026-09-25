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

Useful options: `--no-examine` (listing only, faster), `--door Y,X`
(repeatable; visit only these doors), `--max-doors N`, `--retries N` and
`--retry-delay SECS` (for locked/ejected visits), `--events FILE` (every client
event, for debugging), `--pktlog FILE` (raw packet log from the client).

Give each concurrently running client its own `--config` file: the client
rewrites its config file on exit.

The character must already exist (create it once with the normal client) and
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

4. Between doors it eats when the hunger indicator says Hungry or worse, and it
   stops if the character has died.

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

- Covers the level the character is on (the town, in testing). Moving between
  wilderness levels isn't automated yet.
- Open house doors look like ordinary open doors on the map, so a shop whose
  door is currently open is only found if it was seen closed.
- Only grids the character has seen are on the map; in the town by day that's
  nearly everything.
- Check the server operator's policy on automated clients before using this
  anywhere but a private server.

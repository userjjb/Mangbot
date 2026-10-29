# pilotctl: the Pilot's command interface

`pilotctl.py` is the only way anyone talks to a running Pilot. The Navigator plays the character through it (plans,
goals, orders, queries); the Architect uses the same commands to run missions, answer the Navigator's questions and
park the Pilot for updates; the observer tools (viewer, scorecards) use a few read-only ones. Each command is one JSON
line over a Unix socket to the Pilot daemon, which answers between game ticks. This file lists every command: what
it does, who may use it, what it refuses and why, and what it prints. How goals and plans work inside is in
[goals-and-plans.md](goals-and-plans.md); the item policy behind the value refusals in [pilot-items.md](pilot-items.md);
the gear evaluator behind `gear`/`gearcmp`/`loadout` in [gear-and-estimator.md](gear-and-estimator.md); the report's
lines in [pilot-core.md](pilot-core.md); the rulebook behind `rule` in [harness-rulebook-ops.md](harness-rulebook-ops.md).

## Calling it

```
cd /projectnb/jbrcs/mangband/github/tools/pilot && module load python3/3.12.4
python3 pilotctl.py --nick dive04 status                 # as the Navigator (the default role)
PILOT_ROLE=architect python3 pilotctl.py --nick dive04 answer 7 "yes, sell it"   # as the Architect
```

- **Nick.** `--nick NAME` must be the first argument; otherwise `$PILOT_NICK`, default `dive01`. The socket is
  `runs/pilot/<nick lowercase>/ctl.sock`.
- **Role.** `PILOT_ROLE` (env, default `navigator`) is sent with every request as `role`. It is not authenticated:
  it's a convention that the Architect and the harness set `PILOT_ROLE=architect` on their own calls. The role decides
  the refusals below, whose goal it is in the logs (`[N]`/`[A]` in the viewer), and whether `!` overrides cost debt.
- **Transport.** pilotctl waits 40 s for an answer; the Pilot's socket thread gives up after 30 s with
  `{"ok": false, "error": "pilot busy"}`. If the socket is gone (Pilot parked or restarting) it prints
  `(Pilot not answering: ...; it may be restarting -- wait 20 s and retry)`; `complain` then writes straight to
  `runs/complaints.md` instead.
- **Two commands never reach the request queue as such:** `rule ...` runs `tools/rulebook/rule.py` locally (no Pilot
  needed), and `wait` sends `wait-attention`, which blocks in the socket thread (see Info).
- **Every request** (except the viewer's polls `viewmap view navview note goalstate mission`) is logged as `nav_cmd`
  in `decisions.jsonl` with the role, the report it answers and that report's age, and counts as agent activity (it
  resets the idle-recall clock).

### How a reply is printed

The Pilot answers a JSON dict; pilotctl prints, in order:
1. `USER MESSAGE(S) NOT YET ANSWERED (reply with say): ...` when the user sent a message (`note !TEXT`) nobody has
   answered with `say` yet. It is added to every reply except `note`, `say` and `status` (the report carries it there).
2. One of: the `report` (status, view, navview); for item actions `DONE: <what> (N -> M left)[; moved ...]`, the
   game's messages, then `Pack now: a) ...; b) ...`; a `text`; attention `events`; **otherwise the raw JSON** (this is
   how goals, `order`, `stop`, refusals `{"ok": false, "error": "..."}` and debug commands print).
3. `NOTE: ...` if the reply had a note (so a note also appears inside the JSON or the DONE line: printed twice).

Every report the Navigator receives is numbered (`· rN` on its first line) and remembered with the level and HP it
showed; that is what the stale-order check compares against.

## Who may do what

The checks at the top of `pilot.py: Pilot.do_request`, before any command runs, for any role other than `architect`:

| refusal | applies to | why |
|---|---|---|
| "in the dungeon the Pilot handles items itself" | in the dungeon: `wear takeoff pickup fuel eat inscribe wearall`, and `read`/`use` with a target item (an Identify-type read; `read X force` is not a target) | the item policy is the Pilot's in the dungeon (restructure step 2). `destroy`/`drop` are allowed there (pack control), as are `quaff`, plain `read`, `use`, `aim`, `zap` |
| "`goal goto`/`stairs`/`raw` is the Pilot's now" | anywhere | movement is the Pilot's (step 2.6): use `goal leave`, `goal fetch Y,X`, `plan trip`, `goal dive` |
| "order held: ..." (stale order) | positional orders: `goal goto/fetch/searchroom/hunt`, `avoid Y,X` | the report the order answers is from a level since left; or (`hunt`, report >5 s old) the monster is no longer in view; or (`goto`/`fetch`, >5 s old) HP fell by over 25 points (percent) since. Logged `order_held`. Look again and re-issue |
| dead character | everything except `goal resurrect` and a handful of passive commands (`attention quit orders map note view say viewmap journal`; the query commands earlier in the dispatcher -- status, pack, keep, debt, monster... -- also still answer) | a ghost can only resurrect |

Further role rules inside commands:

| rule | Navigator | Architect |
|---|---|---|
| `goal hunt` checks (`hunt_refusal`) | refused unless `!NAME`; an override is judged at the hunt's end and a bad one adds HP to the **fight debt** | never refused |
| `goal fetch` | refused in the dungeon with a band flagged in the last 2 minutes, or a dangerous monster in view | not checked |
| `destroy`/`drop`/`goal shop ... sell` value refusals | refused unless `!NAME`; an override adds the value lost to the **item debt** | refused too unless `!NAME`; the override costs no debt |
| overrides at all | allowed until revoked: the file `runs/private/<nick>.overrides_revoked` (items) or `<nick>.hunt_overrides_revoked` (hunts) exists. The Navigator isn't told the limit | always |
| `wear` an unidentified ring/amulet | refused unless `force` (unknown jewellery is often cursed and can't come off) | allowed |
| `house buy`, `answer` | refused | allowed |
| `ask` rate limit | 1 per 5 minutes, 4 per hour, unless `runs/pilot/<nick>/ask_unlimited` exists | (same code path; the Architect doesn't use `ask`) |

### `!` overrides and `force`

- `!` goes on the item or monster name: `destroy !Ring_of_Teleportation`, `drop !NAME`, `goal shop 5 sell !NAME:2`,
  `goal hunt !Grip`. It skips the Pilot's value refusal (items) or hunt refusal (fights). For the Navigator it is
  logged and scored: items -- the item's value x the shop's pay cut goes to `navigator_debt.json` at once (for a
  sale, fair price minus what was received, when the sale lands); hunts -- the hunt is marked `overridden` and judged
  when it ends: "wrong" (not slain, HP below half, or an emergency escape fired) adds the HP lost to the fight debt
  (`settle_hunt`). `debt` shows both. Once the revocation file exists, `!` is refused with the current debt.
- `force` (a separate word) skips a safety check that isn't a policy: the supply gate (`goal dive/recall`,
  `plan trip`), a second escape read within 3 s, a second Word of Recall while one is pending, a Recall with no `@R`
  inscription, unknown jewellery for `wear`, `goal goto ... force` (walk while a dangerous monster is adjacent). It
  costs no debt.

## Info and queries

| command | does / prints | who | refuses |
|---|---|---|---|
| `status` | the compact report (`compact(snapshot=True)`: character, supplies, here, monsters, news, gear/pack snapshot) | all | -- |
| `status full` | the long report (`report()`: stats, map, equipment, pack, messages, orders...) | all | -- |
| `wait [SECS] [--brief]` | blocks (default 600 s) until an attention event, then prints `ATTENTION what: detail (goal: ...)` per event and the wait report (`compact(news_since=last wait)`: only what changed). A quiet timeout prints `(no attention events)` and the brief form; `--brief` always keeps only the first two lines and the lines starting `USER MESSAGE`, `Supplies:`, `Here:`, `Monsters:`, `News:`, `Since last`, `Progress:`, `Cures`... Pass a Bash timeout above SECS | all | -- |
| `attention` | the pending attention events without waiting (and clears them) | all | -- |
| `pack` | `Pack: a) ...; b) ...` with the Pilot's short names and values | all | -- |
| `equip` | `Equipment (use these letters, capitals...)`: `A) ...` plus the gear line (empty slots, pack items better than worn) | all | -- |
| `orders` | `Orders: key=value, ...` (all standing orders) | all | -- |
| `map [R]` | the map within R squares of @ (default 15), rows numbered | all | "no map yet" |
| `monster NAME` | this server's monster data (level, speed, HP, blows, spells, flags, breath, melee per turn, the Advisor's 0-5 rating), whether a danger rule fires now, **the hunt check's verdict** (`REFUSED: why` or turns/HP estimate), and what a kill drops (gold, items, P(ego), P(artifact)). Up to 6 matches | all | -- |
| `drainers [STAT] [MAXLEVEL]` | monsters whose blows drain a stat, by native level (default STR/DEX/CON up to clvl+10) | all | -- |
| `gate FEET [recall]` | the supply gate (`supply_gate`, the stage table: cures, Phase Door, Word of Recall, light) for going down to FEET; `recall` = by Word of Recall from town (2 WoR). `supplies for N ft: OK` or `missing ...` | all | usage |
| `debt` | the Navigator's item debt (gold, last 8 entries) and fight debt (HP, last 8) | all | -- |
| `price NAME\|LETTER` | the Pilot's valuation of a pack or worn item: value (known/estimate, P(irreplaceable)), what a shop pays and which, last price seen in a shop, what the policy will do (worn / kept / sold by plan town) | all | "usage", no such item |
| `why [HH:MM[:SS]]` | from `decisions.jsonl` (last ~8 MB): the window 40 s before to 8 s after a moment (default: the last escape, emergency, `plan_end` or `goal_failed`): HP start/lowest/end, monsters in view and adjacent, then a timeline of attention events, actions (`act [by]`), goals, escapes, plan starts/ends and `NAV>`/`ARCH>` commands (queries left out). At most 60 lines | all | -- |
| `prep` | the mission-start planning report: character lines, the gear review, what `plan town` would buy now and what's short, affordable notable stock in shops 5-7 (no detection crutches on the test server), XP/min by depth, XP per gold, standing items and instructions | all | -- |
| `gear` | the gear review (`gear_review`): abilities had/missing, redundant worn jewellery, pack items better than worn, shop stock that would improve a slot within spare gold. Read-only | all | -- |
| `gearcmp [LETTER\|NAME ...]` | the slot evaluator (`geareval.compare_slot`) for each named pack item, or an item name not in the pack (e.g. shop stock); no argument: every identified wearable in the pack (no lights). Prints `geareval.report` | all | with monsters in view in the dungeon ("`goal quiet` first"); evaluator errors |
| `loadout [shops]` | the loadout optimizer (`geareval.optimize`): one- or two-slot changes that keep every worn ability and resist, from the pack (and with `shops` the stock last seen, within gold minus the town reserve); the best few simulated; ends with `to do: buy X (P g), then wear X` | all | with monsters in view in the dungeon |
| `rule KIND ...` | the Advisor's rulebook (`tools/rulebook/rule.py`): `monster drop fight feeling unknown owner const object room`. Runs locally | all | -- |
| `plan` | `plan: <the trip and its step>` or `no plan` | all | -- |

## Goals (`goal NAME ...`)

One goal at a time; a new goal replaces the old (`set_goal`). Unread attention events move to the news when a goal is
given, so the next `wait` is about it. A goal given while a trip plan runs **pauses the plan** until the goal ends
(reply note: "the trip plan is paused until this goal ends"); `plan resume` ends it early. Replies are JSON:
`{"ok": true, "goal": "<describe>", "note": ...}`. The goal classes are described in goals-and-plans.md.

| command | does | who | refuses / notes |
|---|---|---|---|
| `goal dive [FEET] [force] [scum]` | stair-scum down (or climb, if shallower) to FEET (default one level deeper). `scum`: may take a close `>` for a fresh level | all | supply gate when going deeper to the target (capped at `max_depth`) unless `force`; past `max_depth` it's set but capped (note says so) |
| `goal explore [until=stairs] [radius=N]` | explore the level's unexplored edges (or until a reachable `>` is seen, or within N squares) | all | -- |
| `goal goto Y,X\|>\|<\|item [force]` | walk there | **Architect only** | Navigator: refused (use `leave`/`fetch`) |
| `goal fetch Y,X` | one item detour (a Goto named `fetch`) | all | Navigator in the dungeon: a band flagged on this level in the last 2 min, or a dangerous monster in view; stale-order hold |
| `goal leave` | leave this level by the nearest stairs (a `Flee` goal; up at `max_depth`) | all | in town/wilderness ("for dungeon levels") |
| `goal hunt NAME` / `goal hunt !NAME` | walk up to NAME and fight it (spaces as `_`). The reply's note is the estimate | all; checks for non-Architect | `hunt_refusal`: unique already killed (no XP/drop again); a paralyser without Free Action; the average fight ending below the Pilot's own abort line (worst 3 turns or `flee_hp`); the Advisor's rating AVOID/LEAVE (unless rated for strength alone); a bad fight (90th percentile of HP lost from the duel simulator, else twice the turns) over 60% of HP; a summoner unless bad case <30% HP, HP 80%+, nothing else in view and 5+ Phase Door; a breath over 60% of HP; a band flagged in the last 2 min. Logged `order_refused`. `!` overrides (fight debt); refused if hunt overrides are revoked |
| `goal recall [force]` | read Word of Recall (from town: down to `max_depth` or the deepest level, inscribing `@R`) | all | from town: supply gate for that depth by recall unless `force` |
| `goal rest` | rest until healed | all | -- |
| `goal wait [SECS]` | stand still (default 5 s) | all | -- |
| `goal quiet [SECS]` | time to think (10-600 s, default 120): walk to a quiet walked spot, rest if hurt, wait; ends on a moving monster, a hit or the time (`quiet_end` alert); the goal it replaced (not a plan's own) carries on after | all | a mobile monster in view in the dungeon ("not quiet") |
| `goal search` | search for secret doors at dead ends and corners, nearest first | all | -- |
| `goal searchroom Y,X` | search the 4 possible secret-door spots of an inner room (20 each) | all | usage; the room's door already shows; stale-order hold |
| `goal shop N [list] [buy NAME:N[@MAX]] [buy NAME:+N] [sell NAME:N] [quote NAME] ...` | walk into store N (1-7), sell, buy, leave. `NAME:N` = **have** N in all (buys the difference), `NAME:+N` = N more, `@MAX` = price cap each; `list` puts the whole stock first; `quote` offers and declines to see the price; `sell !NAME` overrides the value policy. Names use `_` for spaces; a single letter is a pack letter | all (town) | sells: unknown-item and value refusals appear in the result ("not sold: ... `sell !NAME` overrides") rather than as an error |
| `goal town` | (wilderness) walk back to town | all | -- |
| `goal townfarm GOLD [MINUTES]` | kill gold-dropping townspeople until GOLD (default 10 min) | all | usage |
| `goal resurrect` | as a ghost: float up to town and enter the Temple | all | -- |
| any other name | -- | -- | `unknown goal NAME` |

## Plans (`plan ...`)

| command | does | who | refuses |
|---|---|---|---|
| `plan town [kit=A\|B\|C\|none] [buy [STORE/]NAME[:N][@MAX],...]` | the whole town visit as one goal (`TownKit`): sell by policy, identify, buy Word of Recall to 2, the gate's minimums, Restore for drains, the kit, then the list (`:N` = have N), bank, stash, eat, fuel. Kits: A to 500 ft, B to 1000 ft, C deeper. The reply's note forecasts what it will buy by the prices last seen and what's short | all (town) | in the dungeon; unknown kit; an unreadable buy item; a NAME no shop's stock table has (name the store: `7/NAME`) |
| `plan trip LO-HI [until "COND or ..."] [then recall\|town] [level_min=N] [via=stairs\|recall] [force]` | a whole trip (`TripPlan`): down (by stairs or recall), work levels in LO-HI (each until done or `level_min` minutes, default 10), leave bad levels, come home when a condition holds; `then town` also runs the town kit. Default until: `cures<3 or phase<3 or minutes>45`. Conditions: `VAR<N`/`>`/`<=`/`>=`/`=` over `cures ccw csw clw phase wor food hp minutes dmin time clvl gold free levels` (`time>HH:MM`), or events since the start `band drained emergency emergency_loop danger pack_full unique_slain unseen_attacker`. Replaces the goal. Reply: the plan text and "(down by the stairs / by Word of Recall)" | all | LO/HI not multiples of 50 or LO<50; HI below `max_depth` ("`order max_depth=` first"); unreadable `until`; `wor<N` (holds as soon as it recalls down); in town, the supply gate for the depth it will reach unless `force` |
| `plan stop` | end the plan (the current goal runs on) | all | -- |
| `plan resume` | end your own goal and hand back to the paused plan | all | -- ("the plan isn't paused") |
| `plan` | show the plan | all | -- |

`stop` (below) ends both the goal and the plan.

## Item actions (immediate)

Items are named by **pack letter** (`a`...), **equipment letter** (capitals, as `equip` lists them; `takeoff` also takes
lowercase), or **part of the name** with `_` for spaces, resolved at the moment of acting (whole-word matches first;
ambiguous names are refused with the candidates). Words after a name: a trailing count, `all` or `force`.

| command | does | who | refuses |
|---|---|---|---|
| `quaff L` | drink | all | -- |
| `read L [TARGET\|force]` | read a scroll; TARGET = the item an Identify/Enchant scroll works on | all; with TARGET town only for the Navigator | an escape (Teleport/Phase) read <3 s after the last one; Word of Recall while one is pending; Word of Recall in town without a valid `@R` inscription -- each unless `force` |
| `use L [TARGET]`, `aim L [DIR]`, `zap L` | staff (TARGET for Perception), wand (DIR 1-9, 5 = nearest target), rod | all; `use` with TARGET town only for the Navigator | escape-read 3 s rule for `use` |
| `eat L`, `fuel L` | eat; refill the lantern (puts the lantern on first if it's off, as in town) | all; town only for the Navigator | `fuel`: no lantern |
| `wear L [force]`, `takeoff L`, `wearall` | wear; take off; put on everything that fills an empty slot (queued) | all; town only for the Navigator | Navigator: unidentified ring/amulet unless `force` |
| `destroy L [N\|all]`, `drop L [N\|all]` | destroy (auto-confirmed) / drop (the square is then skipped by auto-pickup and looting) | all, also in the dungeon | value refusal ("not destroyed: why. `destroy !NAME` overrides...") unless `!`; `!` refused when overrides are revoked |
| `inspect L` | the game's description of the item | all | -- |
| `inscribe L TEXT` | inscribe; prints the pack | all; town only for the Navigator | -- |
| `pickup` | pick up what's underfoot | all; town only for the Navigator | -- |

The reply: `DONE: <verb> <item> (N -> M left)[; moved A -> B (k squares)]`, up to 4 game messages, `Pack now: ...`.
Notes: "no change in the pack or equipment yet: it may not have happened" (after ~2 s of re-reading the pack), or
for an escape "its landing can take ~2 s". An Identify-type read also tells the flavour learner which item it targets.

## Orders, standing instructions, reactions, review, keep, avoid

| command | does | who | refuses / prints |
|---|---|---|---|
| `order KEY=VALUE ...` | set standing orders (saved to `orders.json`, survive restarts). Keys and defaults (`DEFAULT_ORDERS`): `flee_hp` 0.5, `think_hp` 0.65, `rest_below` 0.7, `rest_to` 0.95, `arrival_pack` 4, `danger_level` 6, `free_action`/`resist_blind`/`resist_conf` no, `unseen_hp` on, `autowear` on, `enchant_max` 25, `idle_recall_s` 600, `pickup` all, `stop_on` unique,danger, `pillared` explore, `loot_radius` 10, `choke` on, `autodestroy` worthless,cursed, `junk` (list), `band_frac` 0.5, `nopickup` "", `max_depth` 0 | all | `no order KEY`; a value that doesn't cast to the default's type errors. Prints the JSON of all orders; `max_depth` deeper than the warrior gate (clvl x 50 to 1000 ft, then (clvl-5) x 50) or below 1000 ft without Free Action adds a `careful:` note (not a refusal) |
| `standing [TEXT \| -N]` | add / remove / list free-text standing instructions shown in every report (`standing.json`, with who added it) | all | `no standing instruction N` |
| `react leave NAME` / `react hunt NAME` / `react thieves kill` / `react afraid teleport` / `react -N` / `react clear` / `react` | executable standing orders (`rules.json`), run by `rule_tick` at Pilot speed: leave the level when NAME is in view; hunt NAME on sight (the hunt checks apply); hunt a thief within 6 squares; afraid with no fear cure and monsters adjacent -> teleport. Duplicates aren't added. Prints `reactions: 1. kind arg (by); ...` | all | unknown kind or missing argument (usage with each kind's meaning); `leave`/`hunt` with a name not in the monster list |
| `review` / `review sell\|keep\|wear NAME` | the item-review queue (`review.json`): items held for the Navigator's word before they're sold. `keep` also adds it to `keep`; `wear` wears it now in town; in the dungeon it's recorded as keep, not worn, and the reply says so | all | usage; nothing held matching |
| `keep [NAME \| -NAME]` | protect an item kind from the value policy and from sells/destroys (`keep.json`); list | all | -- |
| `avoid [Y,X [R] \| NAME \| clear]` | no-go zones for paths: a square and radius (default 3) on this level, or 3 squares around every monster NAME (all levels); `clear`; list | all | stale-order hold for `Y,X` |

## Town, house and stash

| command | does | who | refuses |
|---|---|---|---|
| `house` | the house: door, when bought and price, gold banked, gold carried (or the smallest house on the map) | all | -- |
| `house buy [Y,X]` | buy the smallest house (or the one with that door) -- a `HouseBank` goal | **Architect only** | Navigator; in the dungeon; a house that still holds gold; no such house; on a wilderness tile not walked to from town |
| `house deposit [KEEP]`, `house withdraw` | bank gold (keeping KEEP) / take it out -- a `HouseBank` goal | all | no house; in the dungeon |

`plan town` handles the house, the tavern stash and shopping by itself; `goal shop` and `goal townfarm` are under
Goals.

## Notes, journal, user and Architect

| command | does | who | prints / refuses |
|---|---|---|---|
| `say TEXT` | answer the user: logged `nav_say`, written to `commentary.jsonl` (shown in the viewer), clears the unanswered-message flag | Navigator | `said` |
| `journal TEXT` | append `- HH:MM:SS <depth> <HP%> \| TEXT` to `runs/pilot/<nick>/navigator.md`, logged `nav_journal` | Navigator | `journaled: ...` |
| `complain TEXT` | append a dated line to `runs/complaints.md` (created with a header), logged `nav_complaint`; works with the Pilot down (pilotctl writes it) | Navigator | usage if empty |
| `ask [quiet] TEXT` | a live question for the Architect: appended to `runs/pilot/<nick>/asks.jsonl` with an id, depth, HP and goal; logged `nav_ask` (the Architect's inbox watcher picks it up). Never blocks. `quiet` also starts `goal quiet 600` that waits for the answer | Navigator | rate limits (1 per 5 min, 4 per hour; lifted by the file `ask_unlimited`); if the quiet wait is refused the question still goes |
| `answer ID TEXT` | the Architect's answer: an `architect_answer` attention event (`ARCHITECT ANSWER #ID: ...` in the Navigator's reports), logged `arch_answer`; ends an `ask quiet` wait for that id unless the text starts with "more" | **Architect only** | Navigator ("answers come from the Architect"); usage |
| `note TEXT` | the user's commentary (the viewer sends these): logged `user_note` with a snapshot (depth, HP, goal, monsters, recent actions) and to `commentary.jsonl`. `!TEXT` is a message for the Navigator (a `user_message` event that wakes `wait`, and the unanswered flag); `?TEXT` marks a question for the Architect | user / viewer | `noted at ...` |

## Mission bookkeeping

| command | does | who |
|---|---|---|
| `mission start LABEL [navigator=MODEL] [effort=LEVEL] [notes=TEXT]` | marks a mission's start: sets the label and the baseline (time, XP, gold, gold found) for the report's mission totals, saves `runs/pilot/<nick>/mission.json` (survives a restart or hot-swap), logs `mission_start`, and adds/replaces the entry in `runs/missions.json` (`label nick start end navigator effort report notes`) | the Architect (no role check in code) |
| `mission end [LABEL]` | logs `mission_end`, sets the entry's `end` in `missions.json`, clears the label and deletes `mission.json`. LABEL defaults to the running mission | the Architect |

Prints `mission start: LABEL at YYYY-MM-DD HH:MM`. Scorecards and the viewer read these markers
([observe.md](observe.md)).

## Control and admin

| command | does | who |
|---|---|---|
| `stop` | drop the goal, stop resting, end the plan (note: "the trip plan is stopped too") | all |
| `park` | log out at the next safe moment (nothing close, HP OK) for a Pilot update; drops the goal unless it's a pending recall; note "will log out when safe". The Navigator sees a `parked` event | Architect (restart.sh / hotswap.sh) |
| `quit` | stop the Pilot's main loop | Architect |
| `stairs [<\|>]` | take the stairs (default: the kind underfoot) | **Architect only** |
| `raw TEXT` | send a raw tool-client command | **Architect only** |
| `option NAME VALUE` | set a client/game option | Architect (no role check) |
| `options [FILTER ...]` | the client's options as JSON | Architect |
| `goalstate` | debug JSON: the goal, its state (and its explore's), the mover, standing_on, busy | Architect / viewer |
| `dump` | write `runs/pilot/<nick>/world_dump.json` (map, memory, monsters) | Architect |
| `search [N]` | search the 8 adjacent squares N times (1-40, default 15), waiting for a find; prints `searched N times here: <finds> \| nothing found` | all |
| `disarm [DIR]`, `open [DIR]` | disarm / open a chest, trap or door in DIR (5 = underfoot); prints game messages and the pack | all |

## Observer commands (the viewer; no side effects)

| command | returns |
|---|---|
| `view [ROWS] [COLS]` | the long report with a bigger map and the news of the last 10 minutes |
| `viewmap [ROWS] [COLS]` | JSON: the map rows and colour attributes around @, monsters with their colours |
| `navview` | what the Navigator last saw: its time, the attention events and the report text |

## Discrepancies (doc vs code)

- **No `sell` command.** HANDBOOK.md lists `sell` among the item commands and `sell !NAME` as an override; selling
  is `goal shop N sell [!]NAME[:N]` (or `plan town`). The `!` works there.
- **Town-only item commands:** HANDBOOK names `sell wear takeoff read/use-on-an-item fuel eat pickup`; the code also
  blocks `inscribe` and `wearall` in the dungeon for the Navigator, and allows plain `read`/`use` anywhere.
- **HANDBOOK-reference.md** still tells the Navigator to `goal goto Y,X` / `goto` stairs / `stairs` in several places
  (`interesting_item`, `stuck`, `fight_going_badly`, `goal explore`, `goal searchroom`), all refused now; its intro
  says HANDBOOK.md wins. Its orders table lacks `autowear`, `enchant_max`, `band_frac`, `nopickup` (HANDBOOK.md
  mentions the last three; `autowear` is documented nowhere for the Navigator).
- **`plan trip` events:** the code also accepts `emergency_loop` and `unseen_attacker`; HANDBOOK.md doesn't list them.
- **pilotctl.py's docstring** (printed with no arguments) is old: it advertises `goal goto` and `stairs` and omits
  `react review keep debt price why prep gear gearcmp loadout house ask answer` and `goal hunt/fetch/leave/quiet`.
- **Not in either handbook:** `attention`, `orders`, `inspect`, `inscribe`, `wearall`, `note`, `answer`, `mission`,
  `park`, `quit`, `raw`, `option(s)`, `goalstate`, `dump`, `view`, `viewmap`, `navview` (mostly Architect/viewer
  commands, which is fine); `goal town`, `goal wait`, `goal search`, `goal resurrect` are only in the reference.
- **`mission`** is described as the Architect's but has no role check.
- The dead-character whitelist names `events`, `news`, `inventory`, which aren't commands; the viewer's and
  scorecard's query lists name more that don't exist (`flags`, `commands`, `help`, `floor`, `quote`).

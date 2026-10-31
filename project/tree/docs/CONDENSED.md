# The Documentation, condensed (for Architects and Advisors)

The full version is [README.md](README.md) and its ten component files. This page is what a new Architect or Advisor
needs in their head before touching anything. Session 10, 2026-10-29; matches version 2.41.0 (`github/VERSION`, CHANGELOG.md).

## What this is

An AI system that plays MAngband 1.5.3 (multiplayer Angband) with one warrior, **Dive04**, on our **local test server**
(port 28346; our build freezes game time while `$MANGBAND_FREEZE_FILE` exists). The live server (port 18346) is the
eventual target; all our client changes work there, the server changes don't exist there.

**Roles.** The **Pilot** (`github/tools/pilot/pilot.py`) plays by policy, ~20 ticks a second. The **Navigator** (an LLM
subagent, `.claude/agents/navigator.md`, taught by `HANDBOOK.md`, never sees code) steers it with `pilotctl` commands:
the plan, the exceptions, overrides that cost "debt". The **Architect** (the main chat) builds everything except
`Advisor/`, runs missions, answers the Navigator's `ask`s. The **Advisor** (`Advisor/`, its own project, Sonnet Clerks)
studies the game and our logs and writes memos; it owns the rulebook tables and the fight estimator, which our code
imports live. **The user decides** policy; nobody else changes a user decision.

## The stack ([client-server.md](client-server.md), [pilot-core.md](pilot-core.md))

- **`mangclient -mtool`**: our headless client. JSON-line events out (messages, position, level, monster/item lists,
  store, confirm, popup...), one-line commands in (walk, pathfind, any server command, look, clear, confirm; queries
  status, inven, map, flags). Prompt-less login, auto birth, packet logs with blanked passwords. Every tool starts it
  through `tools/shopcat/mang.py: MangClient`.
- **The Pilot daemon** owns the client as a child process and serves `runs/pilot/<nick>/ctl.sock`. Each tick: update
  the `World` (`world.py`: map memory, monsters, items, player, clock `TICK_S = 0.625`), run the watchers, serve
  requests, then **the first layer that acts wins**: reflexes -> the Navigator's `react` rules -> item work -> one step
  of the goal -> the trip plan -> idle. Pathing is Dijkstra over the remembered map (`mover.py`, never blocks);
  monsters are known by glyph (`glyphs.py`, ratings from `rulebook/monsters.csv`); vaults/pits/nests by `structures.py`.
- **Logs are the interface** (the Advisor's scripts read them; keep their formats): `decisions.jsonl` (kinds: act,
  escape, attention, goal, nav_cmd, estimator, mons, looks, town_kit...), `events.jsonl`, `state.jsonl`, `levels/*.txt`,
  plus ~20 JSON state files (plan, rates, stash, house, rules, orders, review...) in `runs/pilot/<nick>/`.
- **Update a running Pilot** only with `tools/pilot/restart.sh NICK` (parks first) or, mid-mission,
  `tools/pilot/hotswap.sh NICK` (freezes time, restarts, thaws). Never kill it mid-move.

## Staying alive ([pilot-combat.md](pilot-combat.md))

The reflex stack, in order: **emergency** (HP below `flee_hp`, or within the worst 3 turns of the adjacent monsters
below 90% HP) -> `escape()`; group danger (the Borg's rule); hard-fight Speed/Berserk; status cures; arrival and danger
flees; unseen attackers; choke points; fear; stationary monsters; light; hunger; fight what's adjacent; engage weak
monsters near; rest. **`escape()`** is a fixed 14-step order (one turn from death -> Teleportation/Phase; Speed first;
Recall below 30%; kill a caster that dies in 2 rounds; Teleportation for crowds; stairs within 20 out of melee; cures
by numbers...). The Advisor's estimator mirrors it: **tell the Advisor when escape/group_tick/speed_start_tick/
berserk_tick/fear_cure change.** Escape goals: Flee, Recover, WalkAway, BandLeave, Reprieve, Recall, Resurrect.
Watches flag bands, stat drainers, thieves, breeders, traps, perception gaps, stuck goals, light, food, supplies.

## Items ([pilot-items.md](pilot-items.md))

The Pilot picks up, makes room, destroys junk, identifies, learns flavours and wears upgrades by itself. Values come
from `itemvalue.py` (mirrors the server's `object_value_real`, the rulebook for unknowns) times `pay_cut` (the best
shop owner's rate at our CHR). Notable identified wearables wait in the **review** queue for the Navigator (sold after
2 town visits undecided). The Navigator can `keep` items or override a value refusal with **`!`**: the value lost
goes into its **item debt** (an overridden hunt's HP loss into **fight debt**). The limit is never a number and never
told; the user and Architect revoke overrides with `runs/private/NICK.overrides_revoked`. Standing **orders**
(`order KEY=VALUE`: flee_hp, autowear, pickup, loot_radius, junk, nopickup, enchant_max, band_frac...).

## Goals and plans ([goals-and-plans.md](goals-and-plans.md))

A **goal** is a small state machine, one at a time (Explore, Dive, Hunt, Search, Goto, Shop, TownKit, HouseBank,
QuietWait...). A **plan** sits above goals:
- **`plan trip LO-HI until COND then town`** (TripPlan): phases down -> level -> home -> town; leaves bad levels, comes
  home when a condition holds (supplies, time, XP...), pauses while the Navigator runs its own goal, survives restarts.
- **`plan town`** (TownKit): the whole town visit by policy -- withdraw gold from the **wilderness house** (the tile
  north of town, door 60,129) first, upgrade, sell, identify, buy a tiered list (2 Recall, the supply gate's minimums,
  Restores, kit A/B/C, the Navigator's list), fuel, eat, wait for restocks, recharge, enchant, then deposit gold and
  the stash in the house last.
- **Supplies are counted in dungeon minutes.** `supply_gate` refuses a trip without the cures, Phase, Recall and light
  the depth needs.

## The command surface ([commands.md](commands.md))

`python3 tools/pilot/pilotctl.py --nick dive04 CMD` (default nick `dive01`!). `PILOT_ROLE=navigator` (default) or
`architect` -- unauthenticated, a convention. The Navigator may not walk or use most item commands in the dungeon;
stale positional orders are held; hunts and value-policy sales are checked; `!` (on an item or monster name) skips a value or
hunt refusal and costs debt; `force` skips a safety check that isn't policy (the supply gate, a second escape read,
a second Recall...) and costs nothing. Families: info (`status`, `wait`, `pack`, `equip`, `map`, `monster`,
`why`, `prep`, `price`, `gate`, `debt`, `rule`), gear (`gear`, `gearcmp`, `loadout [shops]`), goals (`goal ...`),
plans (`plan trip|town|stop|resume`), items (`quaff read use eat wear destroy inspect inscribe pickup`), standing
(`order`, `standing`, `react`, `review`, `keep`, `avoid`), town (`house ...`, `goal shop N ...`), talk (`ask [quiet]`,
`answer`, `say`, `journal`, `complain`, `note`), bookkeeping (`mission start|end`), admin (`stop park quit raw option`).

## Gear and the estimator ([gear-and-estimator.md](gear-and-estimator.md))

`geareval.py` scores loadouts with the Advisor's group-fight simulator (`Advisor/data/estimator/options_sim.py`, imported
live) on four fight sets with common seeds: fights met, 500 at depth, 500 at +100 ft, the 21 replayed emergencies + a
hound pack. Score = XP net of consumables per real minute; a change must win by >3% and >2 SE and is ruled out if
less safe, slower, losing a required ability, or >5% lower **EHP** (from `damage_mix.json`). `gearcmp` and `loadout`
only advise; the one automatic use is wearing the evaluator's pick in town. **Shadow mode** (`shadow.py`) asks the
estimator's `choose` in the background at emergencies, bands and hard fights and logs `estimator` records; it never acts.

## Watching and testing ([observe.md](observe.md), [harness-rulebook-ops.md](harness-rulebook-ops.md))

- `observe/watch.py`: the user's live viewer (`!` to the Navigator, `?` to the Architect, F5 freezes time).
  `observe/watch_mission.py`: the Architect's monitor (exits on an ask, emergency, death, drain, stuck plan, plan end,
  Pilot error -- restart it each time). `observe/wrap.sh mNN` after a mission: scorecard, token cost, damage mix,
  complaints. `observe/shopmath.py` is imported by the Advisor's `build_shops.py`: keep its path.
- `harness/unit.py`: 120 offline cases on the real decision code (~3 s; **must pass after every change**).
  `harness/setpiece.py`: ~40 live scenes staged by the Dungeon Master (`dm.py`), Dive04 saved/restored by `charsave.sh`.
- `rulebook/`: the Advisor's tables of game facts (copied by `sync.sh`); `pilotctl rule` queries them.
- Ops: `freeze.sh`, `snapshot.sh` (whole project into `github/project/` for the public repo; no secrets), `restart.sh`,
  `hotswap.sh`. How-tos (servers, characters, orphans, houses): `../operations.md`.

## A mission ([process.md](process.md))

`mission start mNN navigator=M effort=E` -> fill `BRIEF-TEMPLATE.md` (with the debts) -> launch the Navigator in the
background -> `watch_mission.py`, answer asks -> `wrap.sh mNN` -> report in `runs/pilot/dive04/reports/` -> lessons in
`FIELD-NOTES.md` -> read `runs/complaints.md` -> `snapshot.sh`, commit, push (branch `restructure`).

**Versions:** `github/VERSION` holds `major.minor.patch` (minor = play can differ, patch = it can't); `../CHANGELOG.md`
lists them. The Pilot shows `Pilot vX.Y.Z` in `status full` and `started`; `mission start` stores it in `missions.json`.

## Rules of the house

- Memos: write `memos/to_<who>/.tmp-SLUG.md`, then `mv` to `YYYY-MM-DD-SLUG.md`; the Architect runs
  `.claude/hooks/inbox.sh watch memos/to_architect` all session and marks memos read.
- Handoffs live in `../next_steps.md` (">>> WHICH HANDOFF IS YOURS? <<<"); Claude memory only points to project docs
  (the SYNC RULE: change a doc, check the pointers).
- No test-server crutches: rare items, forged kits or DM help must not hide what the live server will show.
- `module load python3/3.12.4`; `rm` is `rm -i`; never `pkill -f` a pattern a tmux command line contains; a logout
  leaves the character in the world ~15 s.

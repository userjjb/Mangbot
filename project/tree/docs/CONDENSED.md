# The Documentation, condensed (for Architects and Advisors)

The full version is [README.md](README.md) and its ten component files. This page is what a new Architect or Advisor
needs in their head before touching anything. Session 11, 2026-11-03; matches version 2.72.2 (`github/VERSION`, CHANGELOG.md).

## What this is

An AI system that plays MAngband 1.5.3 (multiplayer Angband) with one warrior, **Dive04**, on our **local test server**
(port 28346; our build freezes game time while `$MANGBAND_FREEZE_FILE` exists). The live server (port 18346) is the
eventual target; all our client changes work there, the server changes don't exist there.

**Roles.** The **Pilot** (`github/tools/pilot/pilot.py` and its modules) plays by policy, ~20 ticks a second. The
**Navigator** (an LLM subagent, `.claude/agents/navigator.md`, taught by `HANDBOOK.md`, never sees code) steers it with `pilotctl` commands:
the plan, the exceptions, overrides that cost "debt". The **Architect** (the main chat) builds everything except
`Advisor/`, runs missions, answers the Navigator's `ask`s. The **Advisor** (`Advisor/`, its own project, Sonnet Clerks)
studies the game and our logs and writes memos; it owns the rulebook tables and the fight estimator, which our code
imports live. **The user decides** policy; nobody else changes a user decision.

## The stack ([client-server.md](client-server.md), [pilot-core.md](pilot-core.md))

- **`mangclient -mtool`**: our headless client. JSON-line events out (messages, position, level, monster/item lists,
  store, confirm, popup...), one-line commands in (walk, pathfind, any server command, look, clear, confirm; queries
  status, inven, map, flags). Prompt-less login, auto birth, packet logs with blanked passwords. Every tool starts it
  through `tools/client/mang.py: MangClient`. Built by `github/build.sh` (2.72.1): upstream MAngband + our
  `patches/` in `github/build/mangband/` (its own git); `github/mangband`, `mangclient`, `lib`, `src` link into it.
- **Two local servers** (2.72.2): the test server (`testserver/`, 28346: Dive04's world) and the set-piece server
  (`spserver/`, 28350: a copy, `tools/server.sh clone`), chosen by `MANGBOT_SERVER=test|sp` (`tools/servers.py`).
- **The Pilot daemon** owns the client as a child process and serves `runs/pilot/<nick>/ctl.sock`. Each tick: update
  the `World` (`world.py`: map memory, monsters, items, player, clock `TICK_S = 0.625`), run the watchers, serve
  requests, then **the first layer that acts wins**: reflexes -> the Navigator's `react` rules -> item work -> one step
  of the goal -> the trip plan -> idle. Pathing is Dijkstra over the remembered map (`mover.py`, never blocks);
  monsters are known by glyph (`glyphs.py`, ratings from `rulebook/monsters.csv`); inner rooms/pits/nests by `structures.py`, vaults by `vault.py` (2.62.0: the server's templates).
- **The code** (split in 2.44.5-2.44.11, behaviour unchanged): `pilot.py` (~1.5k lines: `Pilot`, the tick, goals'
  driving) with the mixins `report.py`, `gear.py`, `items.py`, `town.py`, `combat.py`, `commands.py` (the methods stay
  `Pilot`'s, so the Advisor's mirrored `Pilot.escape` etc. resolve); the goals in `goals.py`, `town_goals.py`, `plan.py`;
  the command table `cmdtable.py`; the socket server `daemon.py`; shared names `common.py`. Long rules run one method
  per step from a table: `REFLEX_STEPS`/`ESCAPE_STEPS` (2.44.12), the town and trip ticks' `TRADE_STEPS`, `KIT_STEPS`,
  `TRIP_STEPS`... (2.44.13). Map: [pilot-core.md](pilot-core.md).
- **Logs are the interface** (the Advisor's scripts read them; keep their formats): `decisions.jsonl` (kinds: act,
  escape, attention, goal, nav_cmd, estimator, mons, looks, town_kit...), `events.jsonl`, `state.jsonl`, `levels/*.txt`,
  plus ~20 JSON state files (plan, rates, house, rules, orders, review...) in `runs/pilot/<nick>/`.
- **Update a running Pilot** only with `tools/pilot/restart.sh NICK` (parks first) or, mid-mission,
  `tools/pilot/hotswap.sh NICK` (freezes time, restarts, thaws). Never kill it mid-move.

## Staying alive ([pilot-combat.md](pilot-combat.md))

The reflex stack, in order: **emergency** (HP below `flee_hp`, or within the worst 3 turns of the adjacent monsters
below 90% HP) -> `escape()`; group danger (the Borg's rule); hard-fight Speed/Berserk; status cures; arrival and danger
flees (a summoner in view: walk away; one the server lists before the map places it gets 1.5 s, the later reflexes but
engage running meanwhile: 2.45.1); unseen attackers; choke points; summon traps; slowness; fear; stationary monsters;
repeat fearers; light; hunger (Weak or fainting only: Hungry is eaten at a safe moment by the item work,
`policy_tick`, 2.45.2); fight what's adjacent; pickup; engage weak monsters near; rest (or carry on an escape walk to
stairs that outlived its emergency). **`escape()`** is a fixed 14-step order (one turn from death ->
Teleportation/Phase; Speed first; Recall below 30%; kill a caster that dies in 2 rounds; Teleportation for crowds; walk
to stairs within 20 out of melee, taken on arrival even with the danger out of view (2.45.0); cures by numbers...). The
Advisor's estimator mirrors it: **tell the Advisor when escape/group_tick/speed_start_tick/berserk_tick/fear_cure
change.** Escape goals: Flee, Recover, WalkAway, BandLeave, Reprieve, Recall, Resurrect.
Watches flag bands, stat drainers, thieves, breeders, traps, perception gaps, stuck goals, light, food, supplies.

## Items ([pilot-items.md](pilot-items.md))

The Pilot picks up, makes room, destroys junk, identifies, learns flavours and wears upgrades by itself. Values come
from `itemvalue.py` (mirrors the server's `object_value_real`, the rulebook for unknowns) times `pay_cut` (the best
shop owner's rate at our CHR). Notable identified wearables wait in the **review** queue for the Navigator (2.63.0: decided
in the same town visit -- undecided at its end, sold). The Navigator can `keep` items or override a value refusal with **`!`**: the value lost
goes into its **item debt** (an overridden hunt's HP loss into **fight debt**). The limit is never a number and never
told; the user and Architect revoke overrides with `runs/private/NICK.overrides_revoked`. Standing **orders**
(`order KEY=VALUE`: flee_hp, autowear, pickup, loot_radius, junk, nopickup, enchant_max, band_frac...).
Weaker substitutes (2.48.0, the user): a **fallback** (Boldness for Heroism) is kept and bought only while the kit
item is short; a **dungeon stopgap** (Satisfy Hunger, a torch beside a lantern, CLW in kits B/C) is sold in town and
kept by need in the dungeon; Enchant/Recharging scrolls the kit would read are kept and read before more are bought; on
the test server Magic Mapping scrolls are a crutch (sold, not read).

## Goals and plans ([goals-and-plans.md](goals-and-plans.md))

A **goal** is a small state machine, one at a time (Explore, Dive, Hunt, Search, Goto, Shop, TownKit, HouseBank,
QuietWait...). A **plan** sits above goals:
- **`plan trip LO-HI until COND then town`** (TripPlan): phases down -> level -> home -> town; leaves bad levels, comes
  home when a condition holds (supplies, time, XP...), pauses while the Navigator runs its own goal, survives restarts.
- **`plan town`** (TownKit): the whole town visit by policy -- withdraw gold from the **wilderness house** (the tile
  north of town, door 60,129) first, upgrade, sell, identify, buy a tiered list (2 Recall, the supply gate's minimums,
  Restores, kit A/B/C, the Navigator's list), fill the lantern to full (2.49.0: the flasks for it, the rest sold), eat,
  wait for restocks, recharge, enchant worn armour and (2.46.0)
  the wielded melee weapon (while the next point's chance is >= 50%, ~+8; one `order enchant_max` for all the Enchant
  scrolls), then deposit gold and the stash in the house last.
- **Supplies are counted in dungeon minutes.** `supply_gate` refuses a trip without the cures, Phase, Recall and light
  the depth needs. Food counts from the least the stomach holds: the **stomach tracker** (2.49.0, `stomach.py`) keeps
  a range of the food from the server's digestion rule (the worn light's fuel is its tick clock) and the meals, pinned
  exact when the hunger level falls a step (`food ~N` on the status line; `>=N` until then).

## The command surface ([commands.md](commands.md))

`python3 tools/pilot/pilotctl.py --nick dive04 CMD` (no `--nick`: the one running Pilot). `PILOT_ROLE=navigator` (default)
or `architect`, which needs `PILOT_TOKEN` from `runs/private/architect.token` (else refused and reported). Commands are
looked up in `cmdtable.py` (63 entries; `store` since 2.50.0), which holds the role, town-only and ghost rules. The Architect's alone: `goal
goto`, `stairs`, `raw`, `mission`, `answer` and (2.45.0) `park`, `quit`, `option`, `dump` (`restart.sh`/`charsave.sh`
pass the token). A ghost may still query, `park`, `stop`, `order`, `plan stop`, `quit`, `goal resurrect`; a bad
argument answers the usage. The Navigator may not walk or use most item commands in the dungeon;
stale positional orders are held; hunts and value-policy sales are checked; `!` (on an item or monster name) skips a value or
hunt refusal and costs debt; `force` skips a safety check that isn't policy (the supply gate, a second escape read,
a second Recall...) and costs nothing. Families: info (`status`, `wait`, `pack`, `equip`, `map`, `monster`,
`why`, `prep`, `price`, `gate`, `debt`, `rule`), gear (`gear`, `gearcmp`, `loadout [shops]`), goals (`goal ...`),
plans (`plan trip|town|stop|resume`), items (`quaff read use eat wear destroy inspect inscribe pickup`), standing
(`order`, `standing`, `react`, `review`, `keep`, `avoid`), town (`house ...`, `goal shop N ...`), talk (`ask [quiet]`,
`answer`, `say`, `journal`, `complain`, `note`), bookkeeping (`mission start|end`), admin (`stop park quit raw option dump`).

## Gear and the estimator ([gear-and-estimator.md](gear-and-estimator.md))

`geareval.py` scores loadouts with the Advisor's group-fight simulator (`Advisor/data/estimator/options_sim.py`, imported
live) on four fight sets with common seeds: fights met, 500 at depth, 500 at +100 ft, the 21 replayed emergencies + a
hound pack. Score = XP net of consumables per real minute; a change must win by >3% and >2 SE and is ruled out if
less safe, slower, losing a required ability, or >5% lower **EHP** (from `damage_mix.json`). `gearcmp` and `loadout`
only advise; the one automatic use is wearing the evaluator's pick in town. The **hunt check** (`goal hunt`, engage,
`monster`) runs the Advisor's duel simulator `fight_sim` at the gear model's to-hit/to-dam totals (2.45.0) and refuses
a disenchanter whose expected enchantment loss is more than a kill brings (2.45.1; a lost step valued at the
re-enchant scrolls' price / chance where the town kit would buy them back, else its resale: 2.46.0). **Shadow
mode** (`shadow.py`) asks the estimator's `choose` in the background at emergencies, bands and hard fights and logs `estimator` records; it never acts.

## Watching and testing ([observe.md](observe.md), [harness-rulebook-ops.md](harness-rulebook-ops.md))

- `observe/watch.py`: the user's live viewer (`!` to the Navigator, `?` to the Architect, F5 freezes time).
  `observe/watch_mission.py`: the Architect's monitor (exits on an ask, emergency, death, drain, stuck plan, plan end,
  Pilot error -- restart it each time). `observe/wrap.sh mNN` after a mission: scorecard, token cost, damage mix,
  complaints. `observe/shopmath.py` is imported by the Advisor's `build_shops.py`: keep its path.
- `harness/unit.py`: 228 offline cases in `unit_<family>.py` + `fixtures.py` on the real decision code (~3 s; **must pass after every change**).
  `harness/setpiece.py`: ~40 live scenes staged by the Dungeon Master (`dm.py`), Dive04 saved/restored by `charsave.sh`.
- `rulebook/`: the Advisor's tables of game facts (copied by `sync.sh`); `pilotctl rule` queries them.
- Ops: `freeze.sh`, `snapshot.sh` (whole project into `github/project/` for the public repo; no secrets), `restart.sh`,
  `hotswap.sh`. How-tos (servers, characters, orphans, houses): `../operations.md`.

## A mission ([process.md](process.md))

`mission start mNN navigator=M effort=E` -> fill `BRIEF-TEMPLATE.md` (with the debts) -> launch the Navigator in the
background -> `watch_mission.py`, answer asks -> `wrap.sh mNN` -> report in `runs/pilot/dive04/reports/` -> lessons in
`FIELD-NOTES.md` -> read `runs/complaints.md` -> `snapshot.sh`, commit, push (`master`).

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

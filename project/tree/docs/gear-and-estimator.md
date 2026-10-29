# Gear evaluation, the loadout optimizer, EHP and the estimator

The Pilot judges gear and fight choices with **simulated fights**, not rules of thumb. Two parts use the Advisor's
fight simulator (`Advisor/data/estimator/options_sim.py`): the **gear evaluator** (`tools/pilot/geareval.py`), which
compares loadouts by replaying many fights with each one, and **shadow mode** (`tools/pilot/shadow.py`), which asks the
Advisor's estimator what it would do at emergency, band and hard-fight decisions and logs the answer without acting on
it. Gear results reach the game in three ways: the `gearcmp` and `loadout` commands (advice only), the automatic
town swap (`upgrade_step` step 6), and the sell check (an item the evaluator would wear is not sold). The rulebook's
duel estimates (`fight_estimate`, `fight_sim`) are a separate, older one-monster model used by the hunt and danger checks.

Related docs: [pilot-items.md](pilot-items.md) (upgrade_step's static steps, selling, identify, itemvalue),
[pilot-combat.md](pilot-combat.md) (escape, berserk/speed ticks, hard_fight, danger rules),
[commands.md](commands.md) (every pilotctl command), [observe.md](observe.md) (scorecards, `wrap.sh`),
`design_gear.md` (the design history), and the Advisor's interface memo
[`memos/to_architect/2026-10-28-advisor-docs.md`](../memos/to_architect/2026-10-28-advisor-docs.md).

---

## 1. Files

| File | What it is | Used by |
|---|---|---|
| `tools/pilot/geareval.py` | The gear evaluator: item parser, character model, scenario sets, simulation, EHP, verdict, loadout optimizer, text report. `--demo` runs Dive04's session-7 Ring of Strength question | pilot.py (`gearcmp`, `loadout`, `gear_better`; also reused: the stat tables by the weight-limit check, `Item`/`label` by `review_hold`, `SIM_RES`/`SHEET_FLAG` by shadow mode). It does not use `itemvalue.py`; the Pilot filters its candidates with `itemvalue`'s `known` flag |
| `tools/pilot/shadow.py` | Shadow mode: runs `options_sim.choose` in a background thread and queues the answers | pilot.py (`shadow_decision`, `shadow_results`) -- live |
| `tools/observe/damage_mix.py` | Splits the HP the character lost in a depth band (the last mission's, else 700-800 ft) into damage kinds; writes `runs/pilot/NICK/damage_mix.json` (EHP's input) | `observe/wrap.sh` after each mission; read by `geareval.load_mix` |
| `tools/pilot/replay_group.py` | An offline script: replays the Borg group-danger tiers over a run's logs (`python3 replay_group.py runs/pilot/dive03`) | nobody in code. It was used once to tune `group_tick` (next_steps.md). Not part of gear or the estimator |
| `Advisor/data/estimator/options_sim.py` | The Advisor's Monte Carlo fight simulator and estimator (`rollout`, `choose`, `base_policy`, `OPTIONS`) | imported live by path by geareval and shadow. The Advisor's file: read, never edit |
| `Advisor/data/estimator/scenarios.py` | Depth-native random encounters: `make(depth_ft, n, seed, skip, boost)` | geareval's depth sets |
| `Advisor/studies/2026-10-25-replay/replays/ep*.json` | The 21 replayed emergencies (frozen) | geareval's hard set |
| `tools/rulebook/monsters.csv`, `monsters_raw.csv`, `fight_sim.py` | The rulebook (copied from the Advisor by `sync.sh`) | `fight_rows`, `fight_estimate`, `fight_sim` |
| `tools/rulebook/char_stat_tables.csv`, `char_blows_table.csv`; `lib/edit/object.txt`, `ego_item.txt`, `artifact.txt` | Stat tables, the blows table, item kinds/egos/artifacts | geareval's character and item model |

The contract with the Advisor's files (argument names, the player dict, what a change needs: a new `POLICY_VERSION` and
an atomic copy) is in the Advisor's memo, section 3-4. In short: geareval and shadow import the Advisor's code **live
from Advisor/** (no copy), so a change there reaches the Pilot at its next restart or hot-swap.

---

## 2. The gear evaluator (`geareval.py`)

### 2.1 What an option is

An **option** is a loadout: `{slot: [Item]}` (slots: weapon, bow, body, cloak, shield, helm, gloves, boots, light,
amulet, ring; two rings). The first option is always what is worn now ("current"). Each option is judged in four parts:

1. **rules**: abilities and resists gained and lost; vetoes.
2. **static**: the numbers the server would derive from the loadout.
3. **sim**: simulated fights over several scenario sets, the same random numbers for every option.
4. **verdict**: the vetoes and safety gates first, then the score.

### 2.2 Items and the character model

- `Item(name, tval=None, weight=None)` reads a name as the client shows it ("a Battle Axe of Westernesse (2d8)
  (+10,+9) (+1)") against `object.txt`, `ego_item.txt` and `artifact.txt`: kind, ego (also bracketed egos such as
  "(Holy Avenger)"), artifact, slot, weight, flags, dice, to-hit/to-dam, AC/to-AC, pval. An unidentified item (`{good}`,
  no plusses shown) is read as its base kind. `abilities()` = the ability flags (Free Action, See Invisible, hold life,
  feather fall, telepathy, regeneration, slow digestion) plus every `RES_*`, `IM_*`, `SUST_*`.
- `Character(clvl, stats, mhp, ac, worn, flags, depth_ft, inv, pack_weight)` backs the gear-free parts out of the sheet
  once (base stats before gear bonuses, base HP before CON, AC from spells/effects, race abilities such as a Half-Orc's
  resist darkness).
- `Character.derive(worn)` recomputes what the server would show for any loadout (as `xtra1.c` does): stats
  (`modify_stat_value`), blows (the warrior's blows table from STR, DEX and weapon weight), damage per round, to-hit,
  to-dam, AC (with DEX), max HP (with CON), speed (gear speed less the encumbrance penalty above half the weight limit),
  flags, the weapon's slays and brands, weapon weight.
- `Character.check()` compares the model with the sheet; mismatches are printed at the top of the report ("model vs
  sheet (the model is off here)").
- The Pilot builds the character with `Pilot.gear_character()`: the sheet's stats, max HP and AC; worn items with their
  inventory weights; the sheet's flags; consumable counts (CCW/CSW/CLW, Phase, Teleportation, staff charges, Word of
  Recall, Speed, Berserk, Heroism); depth = the `max_depth` order, else the deepest depth reached, else 500 ft; the pack
  weight.

### 2.3 Slays and brands

`weapon_mults(weapon)` reads the weapon's flags: slays (`SLAY_EVIL`/`SLAY_ANIMAL` x2; `SLAY_UNDEAD/DEMON/ORC/TROLL/GIANT/
DRAGON` x3; `KILL_DRAGON/DEMON/UNDEAD` x5) and brands (acid, lightning, fire, cold, poison: x3). They multiply the dice
only, and the best one wins (`cmd1.c tot_dam_aux`). They are **passed to the simulator** (`p["slays"]`, `p["brands"]`,
and `p["weight"]` for criticals; options_sim since 27k), which applies them per monster. The optimizer's static proxy
uses `mean_mult(slays, depth)`: the expected dice multiplier over the depth's monsters, from `RACE_MIX` (the HP-weighted
share of evil, orc, troll, ... monsters at 750 and 1000 ft; capped at the best single multiplier). The `~N/round` in the
report is without slays.

### 2.4 The scenario sets and seeds (`compare`)

| Set | Fights | Seeds per fight | Monsters awake | Used for |
|---|---|---|---|---|
| **met** | Up to 40 fights the character actually met: `mons` records in `runs/pilot/NICK/decisions.jsonl` at depth-100 ft to depth, a monster within 3 squares, team = monsters within 7, at most one per 30 s, sampled with seed 1 (`encounters`) | n (20 in `gearcmp`, 10 for automatic swaps and `loadout`) | all (`p_awake` 1.0) | score, not safety |
| **depth** | 500 fights from `scenarios.make(depth_ft, 500, seed=7, boost=2)` (boost 2 stands in for auto_scum's harder levels); uniques already killed (`uniques_killed.json`) are re-drawn | 1 | all | score and safety |
| **deeper** | The same at depth + 100 ft | 1 | all | safety |
| **hard** | The 21 replayed emergencies (their monsters and arrivals, at full HP), plus one built-in Light hound pack ("m48-light-hounds": 13 Light hounds, 7 Wargs, 5 Mirkwood spiders, a Druid at 750 ft) | n | the simulator's default (`P_AWAKE` 0.4) | safety |

- Every rollout starts at full HP (a gear choice is made before the fight), with the character's consumables and the
  simulator's base policy (its copy of the Pilot's escape rules).
- Seeds: rollout `i` of scenario `k` uses `seed = 1000k + i` for **every** option (common random numbers), so
  differences between options are not noise from different draws.
- If `scenarios.py` cannot be imported the depth sets are silently left out; if the replays directory is missing the
  hard set is empty.
- What the simulator models and doesn't: paralysis, blindness, confusion, fear, slowing, AC, saving throws, resists
  (elemental and high), slays/brands, criticals; not gear speed (an option that is slower is ruled out instead),
  stealth, light radius, walls (one distance per monster), escorts. See `options_sim.py`'s header and the Advisor's
  calibration memo `memos/2026-10-25-replay.md`.

### 2.5 The score

Per option and set, `summary()` gives: turns per fight, rest turns per fight, XP, gold of consumables spent, lowest HP
(mean, 10th/5th/1st percentile as a share of max), P(near death) (lowest HP at or under 10%: `NEAR_DEATH`), P(death).

**score = (XP - gold spent x XP-per-gold) / real minutes**, pooled over the **met + depth** sets, where real minutes =
(fight turns + rest turns / 2.6) x 0.625 s / 60. Rest turns = the turns resting needs to regain the HP lost
(`rest_turns`, `dungeon.c regenhp`); 2.6 (`REST_SPEEDUP`) is the measured speed-up of resting in wall time. XP-per-gold
is the Pilot's rolling rate (`Pilot.xp_per_gold`; 0.41 by default outside the Pilot). This puts damage (shorter
fights) and AC/HP (less resting, fewer potions) on one scale.

`paired_gain` gives an option's score less the current one's, with a standard error from the per-scenario paired
differences.

### 2.6 EHP (effective HP) and the 5% rule

**EHP = max HP x (share of the damage mix that gets through with no AC and no resists) / (share that gets through with
this gear)**: the HP an unarmoured, unresisted character would need to last as long (`ehp`, `damage_factor`).

- The mix comes from `runs/pilot/NICK/damage_mix.json` (`load_mix`), else `DEFAULT_MIX` (Dive04 at 700-800 ft,
  10-24..10-28: wounding melee 51%, other melee 12%, fire 13%, other elements ~7%, other 16%; attacker level 13).
- Wounding melee ("hurt"): x the hit chance at blow power 60 x the wound cut `1 - min(AC,150)/250`. Other melee: x the
  hit chance at power 8. Hit chance = `0.05 + 0.9 x max(0, 1 - 0.75 AC / (power + 3 x level))` (`melee1.c check_hit`).
- Elements: the basic four and poison x1/3 with the resist (x0 with immunity); the high resists (light, dark, shards,
  nexus, sound, nether, chaos, disenchantment) x0.65. "other" (arrows, missiles, unexplained drops) is never reduced.
- **The 5% rule (`EHP_GATE` = 0.05):** an option whose EHP is more than 5% below the current gear's is ruled out ("less
  staying power"). The simulated fights miss rare breaths, archers and traps; EHP weighs the damage actually taken. It
  applies to `gearcmp`, automatic swaps and `loadout` alike.
- EHP is also the second tie-break (below) and half of the optimizer's proxy.

`observe/damage_mix.py [--nick dive04] [--mission LABEL] [--lo 700] [--hi 800] [--days 4] [--out FILE]`: every HP drop in the decision log in that
depth range and time window is split over the attack messages of that moment in `events.jsonl`: melee by the monster's
share of HURT/SHATTER blows ("hurt") vs other blows ("melee_other"), breaths/bolts/balls/traps by element, arrows and
missiles and drops with no message as "other". Output: `{"mix", "melee_level", "hp_lost", "drops", "range", "since",
"made"}`. `observe/wrap.sh` refreshes it after each mission with `--mission mNN`: the band is the 100 ft span of the
depths that mission spent at least 10% of its dungeon time at (750 -> 700-800, 700-850 -> 700-900), last 4 days;
700-800 ft if it had no dungeon time or without `--mission`.

### 2.7 The verdict (`compare`)

For each option other than the current one, any of these rules it out (printed as "against: ..."):

| Reason | Test |
|---|---|
| less staying power | EHP more than 5% below current |
| loses a required ability | loses Free Action (any depth) or See Invisible (from 600 ft) (`REQUIRED`) -- always |
| loses an ability (automatic swaps) | with `no_loss` (automatic swaps and `loadout`): since `TRADE_RESISTS` is off (the user's option B, 10-26), losing **any** ability, resist or sustain rules it out. With `TRADE_RESISTS` on, only `NO_LOSS` (Free Action, See Invisible, resist blindness, resist confusion, hold life) would |
| slower | the loadout's speed is lower (the weight limit) |
| less safe | in a safety set (hard, depth, deeper): P(near death) higher by more than max(0.5 points, 2 SE); otherwise the worst 5% of fights' lowest HP is lower, with the whole bootstrap 95% interval (300 resamples of the scenarios, paired) below zero |

Then among the current gear and the options left: an option counts only if its paired gain is **more than 3% of the
current score and more than 2 standard errors**. The best score among those is found; every option within 1% of it is a
tie, and the tie goes to the safer one: the mean lowest HP in the hard set (or the deeper set), then EHP, then the
current gear. That option is `best` (`*` in the report).

There is no `MIN_GAIN` in geareval: the "+3% and 2 SE" bar is its equivalent. `MIN_GAIN` belongs to the estimator
(section 4).

### 2.8 `pilotctl gearcmp [ITEM ...]` -- the item slot evaluator

- **Input:** pack items by letter or by part of the name, or any item name (`_` for spaces); with no argument, every
  identified wearable in the pack (not lights). Refused in the dungeon with monsters in view (it runs ~1-3 s).
- **Computes:** `Pilot.gear_eval(items, n=20)` -> `geareval.compare_slot`: one option per candidate in its slot (a ring
  is tried in place of each worn ring; an empty slot is filled), `no_loss` off (so it shows resist trades for the
  user or Navigator to decide). Cached per (items, worn gear, stats, level, depth, no_loss, n).
- **Prints** (`geareval.report`): items it couldn't read; model-vs-sheet mismatches; then per option:
  - `* label` (the `*` is the verdict's pick);
  - `STR .. DEX .. CON .. | blows N | ~D/round | to-hit | AC | HP | EHP (+x% vs current) | speed`;
  - `abilities: +gained, -lost`;
  - one `sim SET (fights x seeds)` line per set: turns + resting per fight, XP per real minute, lowest HP (mean, worst
    5%, worst 1%), near death %, consumables in gold;
  - `X vs Y XP per real minute: +z% (+/- w% at 2 SE)`;
  - `against: ...` (the reasons it was ruled out);
  - finally the EHP definition and the `verdict:` line (the pick, its gain, the seconds taken, and the scoring rule).

### 2.9 `pilotctl loadout [shops]` -- the loadout optimizer

`Pilot.loadout_info(shops)` -> `geareval.optimize(ch, pool, budget, n=10, ...)`. Advice only: it never buys or wears.

1. **Pool:** identified wearables in the pack (not lights or bows, not cursed/worthless/broken/terrible). With `shops`:
   every shop item last seen (`stores_seen` prices) that fits a slot (not lights or bows) and costs at most the gold
   beyond the essentials' reserve (`gold - town_reserve()`), each with its price.
2. **Prune:** per slot, a candidate that another candidate or a worn piece beats on every static count (AC, to-hit,
   to-dam, abilities, stat bonuses, weight, price; a weapon by damage, to-hit and AC) is dropped (`_dominated`).
3. **Enumerate:** the worn set with **one or two slots changed** (a ring pair counts as one slot), within the budget,
   losing nothing the verdict's `no_loss` rule forbids (`auto_swap_losses`, shared with `compare`: with `TRADE_RESISTS`
   off, every ability, resist, immunity and sustain worn now is kept), and no slower.
4. **Proxy:** `log(damage-per-round ratio, with the depth's mean slay multiplier) + 0.5 log(EHP ratio) + 0.1 x speed
   difference`. The best 5 with a positive proxy (`max_sim`) go on.
5. **Simulate:** `compare(..., no_loss=True)` against the current gear (the same verdict as above).

Prints a header (how many loadouts were searched, from what), "nothing to try" when no loadout passes, else the same
report as `gearcmp`, and when the pick isn't the current gear a `to do:` line ("buy X (P g), then wear X; ...").
Limits: no three-slot changes; the proxy alone decides what gets simulated.

### 2.10 Automatic decisions that use the evaluator

`Pilot.gear_better(it)` -> (the chosen option's label, (item, the piece it replaces)) or None. It runs only **in town**,
for an identified, uncursed, non-junk wearable in the pack (not a light). If wearing it would improve nothing on paper
(damage, AC, max HP, speed, or a new ability, in any ring position) it returns None without simulating (most loot).
Otherwise it runs `gear_eval([it], no_loss=True)` (n=10) and logs a `gear_eval` record (`item`, `best`, `score` per
option) when the pick isn't the current gear. Errors are logged as a note and return None.

Callers:
- **`upgrade_step` step 6** (town, at most one swap per 30 s): for each pack item, if `gear_better` picks it, the Pilot
  wears it (a ring or amulet over a worn one: takes the old one off first; step 4 then puts the new one on) and posts
  the news "gear evaluator: LABEL (simulated fights; `gearcmp` for the table)". Steps 1-5 of `upgrade_step` are static
  rules (weapon by damage x1.2, armour by AC, jewellery into empty slots or over a redundant piece): see pilot-items.md.
- **The sell count** (`town_sell_count`): an item the evaluator would wear is not sold (after m45 sold a Ring of
  Strength unjudged).
- **The review hold** (`review_hold`, pilot-items.md) uses `geareval.Item` to name the abilities of a held wearable and
  points the Navigator at `gearcmp` for it.

### 2.11 The static gear views (no simulation)

| Method | What it gives | Shown in |
|---|---|---|
| `armour_ac(name)` | base + to-AC from "[a,+b]" | gear_line, gear_review, upgrade_step |
| `gear_line()` | "Gear: empty slots ...; better than worn: ..." -- empty slots (with a carried candidate) and pack armour with more AC than the worn piece, never over an artifact or a piece with abilities the candidate lacks | `pilotctl equip`, the full report, the compact report (when it changes), gear_review |
| `jewel_gives(name)` | the abilities a ring/amulet name implies (free action, see invisible, resists, ...) | gear_review's shop ideas, upgrade_step step 5 |
| `gear_review()` (`pilotctl gear`, and the `prep` report) | Read-only, for the between-mission step: gold and the reserve, AC, XP per gold; abilities had and the missing ones in priority order (`GEAR_WANTED`); redundant worn pieces (`redundant_worn`); `gear_line`; up to 8 shop ideas within the spare gold (jewellery giving a missing ability in a free slot, or a key one that needs a slot; armour with AC > worn + 2 where the worn piece gives no ability and isn't an artifact), each with its `buy` command at 110% of the price; drained stats; an empty bow slot. It does **not** call the evaluator and changes nothing; for simulated answers use `gearcmp` / `loadout shops` |

---

## 3. Fight estimates (the rulebook's one-monster model)

Separate from the group simulator; used for single fights.

| Method | What | Used by |
|---|---|---|
| `fight_rows()` | `tools/rulebook/monsters.csv` by race index (cached) | fight_estimate, worst_3turns, band_cost, others |
| `fight_estimate(race)` | (turns to kill, HP taken meanwhile, pessimistic HP, worst breath, row): hit chance from level and the weapon's to-hit against 3/4 of its AC, its expected melee per turn at our AC (the 20/40/60 AC column nearest), spells and ranged. Pessimistic = twice the turns with spells at their maximum | `hunt_refusal` |
| `fight_sim(race, n=600)` | the Advisor's duel simulator (`tools/rulebook/fight_sim.py summary`) at our live profile (level, blows, weapon dice and plusses, AC, current HP): mean turns, mean HP lost, 90th percentile HP lost. Errors are logged, return None | `hunt_refusal` (replaces the estimate when available), `sim_loss` |
| `sim_loss(r)` | fight_sim's mean HP lost (300 duels), cached by race, level, weapon, AC, HP to 10% | `danger_why`: "a fight costs ~N HP on average" when above 80% of current HP |
| `hunt_refusal(name)` | the hunt check (refuses a fight that ends on average below the escape threshold, a bad fight > 60% HP, risky summoners, big breathers, a band about...) | `goal hunt`, `monster` info, the engage cache |

See pilot-combat.md for the danger rules these feed.

---

## 4. The estimator in shadow mode

### 4.1 What it is

`options_sim.choose(p, team, n, options)` plays a fight out `n` times per **option** from the same state (common random
numbers), each option being a short plan continued by `base_policy` (the Advisor's copy of the Pilot's escape rules,
versioned by `POLICY_VERSION`). Options (`OPTIONS`): `rules` (no plan: the base policy), `fight`, `speed`, `berserk`,
`speed+berserk`, `ccw`, `phase`, `phase+ccw`, `teleport`, `staff`, `recall+phase`, `stairs`. Options whose first item
isn't in the pack, and `stairs` without a known staircase, are skipped.

It returns **(choice, why, table)**. Table rows: `option, safe, p_near_death, low_p10, xp, dxp` (XP net of gold vs the
rules, paired), `se, gold`. **Safe** = P(lowest HP <= 10%) <= 2% and the 10th-percentile lowest HP >= 30% of max. The
choice stays `rules` unless (a) the rules are unsafe and another option is safe (the safest such), or (b) both are safe
and the option's paired gain (XP net of gold, and of time when `xp_per_block` is given) is > 2 SE, >= 10% of the
rules' XP, and >= **MIN_GAIN** = `max(50, 48 blocks x p["xp_rate_per_block"])` (50 XP or ~30 s of play at the current
rate, whichever is more). If the rules are unsafe and nothing is safe, it names the safest option. An empty team returns
`("rules", "no known monster", [])`. Full contract: the Advisor's memo, section 4.

### 4.2 When the Pilot consults it

| Trigger (`trigger` field) | When | Options offered | The "rules" action compared |
|---|---|---|---|
| `emergency` | every `emergency` notice in the dungeon (`notify` -> `shadow_decision(detail)`) | all | read from the notice text (`shadow.rules_option`: teleport, staff, recall+phase, phase, speed, berserk, ccw, cure, stairs, fight) |
| `band` | a `band` notice in the dungeon that isn't already news (`band_shadow`); once per (level, monster set) per 60 s, 20 s apart | `fight, stairs, recall+phase, phase` | `stairs` if a staircase is known, else `recall+phase`; also passes `xp_per_block` so time counts |
| `hard_fight` | each tick in the reflex chain, before the Speed/Berserk ticks (`hard_fight_shadow`): a hard fight (a unique or a monster within 5 levels adjacent, or 2+ adjacent under 75% HP); once per (level, adjacent set) per 60 s, 20 s apart | `fight, speed, berserk, speed+berserk, phase` | what `speed_start_tick`/`berserk_tick` would quaff, else `fight` |

`shadow_decision` builds the snapshot: HP, max HP, AC, level, depth, distance to the nearest known stairs, Free Action,
the sheet's resists, `save` 0.45, `max_adj` (2 in a corridor, else 3), the wielded weapon's dice and blows, the **total**
to-hit and to-dam (weapon + other gear + STR/DEX, from `gear_character().derive()` as geareval passes them; the weapon's
own plusses only if the gear model fails),
consumable counts, timers (hasted, hero, berserk, blind, confused, afraid, slowed: 5 blocks), turns left on a pending
recall, the awake share from `look` answers (`p_awake`, `asleep_seen`), food from the hunger level, `xp_rate_per_block`
(the rolling XP per minute at this depth / 96, once 300 s of data exist), `xp_per_gold`. Team: each visible monster as
(name, distance, None, awake?) plus monsters only in the server's list at distance 3.

### 4.3 How it runs and what it logs

- `Shadow.submit` starts a daemon thread (`choose` with `n=40`); **one at a time**: a decision while one runs returns
  `skipped`; if `options_sim` failed to import, `off` (and one `note` in the log). The attention record carries
  `shadow: started|skipped|off`.
- Every tick, `shadow_results()` drains the queue and writes an **`estimator`** record to `decisions.jsonl`: `trigger,
  options, xp_per_gold, rules, rules_detail, choice, why, agree, actual_row, compute_s, turn_s, in_time_turn,
  before_next_act, next_act_after_s, team, p, inv, table` (top 6 rows), `error, policy_version, max_adj, arrivals`.
- **agree** (`shadow_agree`): true when the estimator chose what the Pilot did; when it chose `rules` and the table has
  a row for the Pilot's actual action, that row must be safe and within max(10 XP, 2 SE) of the best safe row (the
  estimator's `rules` copy can act differently from the Pilot). None when no monster was known.
- **in time**: `in_time_turn` = compute time <= one player turn (0.625 s / time factor / speed energy);
  `before_next_act` = the answer arrived before the Pilot's next action.
- **It never acts.** No code reads `choice` to change behaviour. The records feed `observe/scorecard.py` (the
  `est` / `estHF` agreement columns and the "H estimator" line), the Advisor's replay studies, and `harness/unit.py`
  (`shadow_estimator_logs`). `why` skips `estimator` records.
- Emergency attention records also carry a 21x21 map window and the monsters (`map21`, `map_at`, `mons`) for the
  Advisor's replays.

### 4.4 Are shadow.py and replay_group.py still used?

- `shadow.py`: yes, live -- imported by pilot.py; every emergency, band and hard-fight decision in the dungeon goes
  through it (117 `estimator` records in Dive04's log so far).
- `replay_group.py`: no caller in code, hooks or scripts. An offline analysis of the Borg group-danger tiers over a
  run's logs (reads `danger_table.csv`, `decisions.jsonl`, `events.jsonl`), used once to tune the group-danger rule; the
  Advisor has its own `replay_group_danger.py`. Unrelated to gear.

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

**Where the code is** (E1 step 3): the Pilot-side methods named here (`gear_character`, `gear_eval`, `gear_better`,
`loadout_info`, `gear_review`, `gear_line`, `ac_better`, `consumables_inv`, `shadow_decision`, `shadow_results`,
`band_shadow`, `hard_fight_shadow`, `fight_rows`/`fight_estimate`/`fight_sim`, `disenchant_cost` with
`disen_loss`/`disen_item_loss`/`disen_text` and (2.46.0) `reenchant_cost`/`disen_buys`/`plus_resale`/`enchant_p`/
`scroll_price`, `armour_ac`, `jewel_gives`, `redundant_worn`) and `shadow_agree` live in
`tools/pilot/gear.py` as `GearMixin`, still `Pilot`'s names; `weapon_table` and `upgrade_step` are in items.py,
`hard_fight` and the Speed/Berserk ticks (`speed_start_tick`, `berserk_tick`), with `escape`, `group_tick` and
`fear_cure`, in combat.py (`CombatMixin`, E1 step 5).

---

## 1. Files

| File | What it is | Used by |
|---|---|---|
| `tools/pilot/geareval.py` | The gear evaluator: item parser, character model, scenario sets, simulation, EHP, verdict, loadout optimizer, text report. `--demo` runs Dive04's session-7 Ring of Strength question the Pilot's gear.py (`gearcmp`, `loadout`, `gear_better`, `ac_better`; also reused: the stat tables by the weight-limit check and `Item`/`label` by `review_hold`, both items.py, `SIM_RES`/`SHEET_FLAG` by shadow mode's snapshot). It does not use `itemvalue.py`; the Pilot filters its candidates with `itemvalue`'s `known` flag |
| `tools/pilot/shadow.py` | Shadow mode: runs `options_sim.choose` in a background thread and queues the answers | gear.py (`shadow_decision`, `shadow_results`) -- live |
| `tools/observe/ability_rates.py` | 2.64.0: how often the character met what the abilities the simulator doesn't play would stop, per dungeon hour (fear, disenchantment, stat and experience drains, unseen attackers, meals; the potions quaffed for fear/blindness/confusion), last 30 days; writes `runs/pilot/NICK/ability_rates.json` | `observe/wrap.sh` after each mission; read by the Pilot's `ability_worth` (section 2.6a); `geareval.ABILITY_RATES_SEED` without it |
| `tools/observe/damage_mix.py` | Splits the HP the character lost in a depth band (the last mission's, else 700-800 ft) into damage kinds; writes `runs/pilot/NICK/damage_mix.json` (EHP's input) | `observe/wrap.sh` after each mission; read by `geareval.load_mix` |
| `tools/attic/replay_group.py` | An offline script: replays the Borg group-danger tiers over a run's logs. Retired to `tools/attic/` in session 10 (C1; see its README.md) | nobody. It was used once to tune `group_tick`. Not part of gear or the estimator |
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
  "(Holy Avenger)"), artifact, slot, weight, flags, dice, to-hit/to-dam, AC/to-AC, pval. A Ring of Damage's or
  Accuracy's lone "(+n)" is its to-dam or to-hit (the server prints it so: `object1.c`), not a pval. An unidentified item (`{good}`,
  no plusses shown) is read as its base kind. `abilities()` = the ability flags (Free Action, See Invisible, hold life,
  feather fall, telepathy, regeneration, slow digestion, permanent light -- `LITE`, the grid's `perm_lite`, since
  2.64.0) plus every `RES_*`, `IM_*`, `SUST_*`. Every ability and resist the sheet's flags grid shows has its `F:` name
  in the three files (`SHEET_FLAG` maps the grid's names; unit case `geareval_flag_names` checks it). Not in the diff:
  curses (aggravation, teleportation, experience drain) and the slays and brands (in the numbers instead).
- `Character(clvl, stats, mhp, ac, worn, flags, depth_ft, inv, pack_weight, intrinsic)` backs the gear-free parts out of
  the sheet once (base stats before gear bonuses, base HP before CON, AC from spells/effects, the abilities the sheet
  shows that no worn piece gives). `intrinsic` (2.64.0) = the grid's `@` column: what the character has itself --
  race, class and level (a Half-Orc's resist darkness; a warrior's resist fear from clvl 30, `xtra1.c player_flags`
  `CF_BRAVERY_30`) -- kept by every loadout, also when a worn piece gives it too.
- `Character.derive(worn)` recomputes what the server would show for any loadout (as `xtra1.c` does): stats
  (`modify_stat_value`), blows (the warrior's blows table from STR, DEX and weapon weight), damage per round, to-hit,
  to-dam, AC (with DEX), max HP (with CON), speed (gear speed less the encumbrance penalty above half the weight limit),
  flags, the weapon's slays and brands, weapon weight, and the minor pvals (stealth, searching, infravision,
  tunnelling: shown in the diff, not valued).
- `Character.check()` compares the model with the sheet; mismatches are printed at the top of the report ("model vs
  sheet (the model is off here)").
- The Pilot builds the character with `Pilot.gear_character()`: the sheet's stats, max HP and AC; worn items with their
  inventory weights; the sheet's flags; consumable counts (CCW/CSW/CLW, Phase, Teleportation, staff charges, Word of
  Recall, Speed, Berserk, Heroism); depth = the `max_depth` order, else the deepest depth reached, else 500 ft; the pack
  weight; `intrinsic` = the grid flags with `@`; and (2.58.0) `acid_gold`/`disen_gold`, (2.64.0) `ability_worth`,
  `xp_per_dmin` and `ability_src` (section 2.6a).

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
| **met** | Up to 40 fights the character actually met: `mons` records in `runs/pilot/NICK/decisions.jsonl` at depth-100 ft to depth, a monster within 3 squares, team = monsters within 7 (at most 12), at most one per 30 s, sampled with seed 1 (`encounters`), from the log's last 3 days only (`days`; doubled until the window holds 20 fights (`min_n`) or covers the whole log; `since` fixes the start instead) | n (20 in `gearcmp`, 10 for automatic swaps and `loadout`) | all (`p_awake` 1.0) | score, not safety |
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
  10-24..10-28: wounding melee 51%, other melee 12%, fire 13%, other elements ~8%, other 16%; attacker level 13).
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

### 2.6a The abilities the simulator doesn't play (2.64.0)

m67: `gearcmp Weaponmastery` put an Amulet of Weaponmastery (+2,+2) (+1) -- STR, sustain STR and CON, Free Action,
resist fear and disenchantment -- only +3.9% over an Amulet of Slow Digestion: the simulator plays none of resist
disenchantment's or the sustains' worth. (Its resist fear and Free Action weren't in the diff because Dive04 has them
anyway: a clvl-30 warrior resists fear itself, the weapon gives Free Action. The diff now says so.)

**The terms.** `geareval.ability_worth(ch, rates, prices, xp_per_gold, xp_per_dmin, disen_take_gold)` values each
ability in `VALUED` in **XP per dungeon minute**: the gold it saves an hour x XP-per-gold / 60, plus the dungeon
minutes it saves an hour / 60 x the character's XP per dungeon minute:

| Ability | What it saves an hour (rates per dungeon hour, from `ability_rates.json`) |
|---|---|
| resist fear | the seconds afraid (no melee: "too afraid to attack", kiting until it wears off; each episode to "You feel bolder now", at most 60 s) + the potions quaffed for it (Heroism, Boldness) |
| resist disenchantment | the plusses disenchanted ("was disenchanted!") x what putting one back costs: the Pilot's `disen_loss` per disenchantment that takes a plus (the 2.46.0/2.57.0 model: scrolls the town kit would buy, else the resale lost), else ~380 |
| sustain STAT | that stat's drains ("You feel very weak/clumsy/sickly...") x its Restore's price; STR and DEX also the damage a drain costs (`drain_loss`: dec_stat's mean points; `derive` with the stat lowered) for `DRAINED_H` = 30 min each. CON's HP loss is not valued |
| hold life | experience drains x a Restore Life Levels |
| See Invisible | the rest the HP lost to unseen attackers takes (an upper bound: some were out of sight, not invisible). Below 600 ft the `REQUIRED` rule rules out losing it anyway |
| slow digestion | meals x a ration x 50% (`dungeon.c`: 20 -> 10 food a turn at normal speed) |

Not valued here: Free Action, resist blindness and confusion and every elemental or high resist -- the simulator plays
them (paralysis, blindness and confusion with their cures; a resist cuts its element), so a term would count them twice.
Feather fall, telepathy, regeneration, permanent light and the minor pvals are shown, not valued.

**Into the score.** `compare` adds an option's terms (gained less lost, `ability_terms`) as the same share of the
current score: `share = sum(terms) / xp_per_dmin`, `score += share x score(current)`, and the paired gain moves by the
same (its SE doesn't). With the terms valuing resist disenchantment, `sim_player` leaves `disen_gold` out of the
scenarios -- one account of it. `optimize` adds the share to its proxy. An ability every option has (the character's
own, or another worn piece's) has no term: the report lists it as "already had (no gain)".

**The Pilot's inputs** (`Pilot.ability_worth(ch)`, called by `gear_character`): the rates from
`runs/pilot/NICK/ability_rates.json`, else `ABILITY_RATES_SEED` (Dive04's 30 days to 2026-11-04: 32.6 dungeon hours;
0.80 disenchantments, 0.49 STR / 0.40 DEX / 0.12 CON drains, 4.1 fear episodes and 14 s afraid an hour -- mostly before
its clvl-30 resist fear); the prices as last seen (`price_of`, the kit's otherwise; `PRICE_SEED`); the disenchantment
cost from the worn gear; XP per dungeon minute from the rate buckets (`xp_per_dmin`, seeded like `xp_per_gold`).
For Dive04 at m67's gear: resist disenchantment +2.1 XP/min-equivalent (+4.7%), sustain STR +2.1 (+4.8%), sustain CON
+0.4 (+0.9%), slow digestion -0.02: +10.3% on top of the simulated gain.

`observe/ability_rates.py [--nick dive04] [--days 30] [--mission LABEL] [--out FILE]`: the dungeon hours (decision
records at depth > 0, gaps capped at 60 s) and the message and decision counts above. `observe/wrap.sh` refreshes it
after each mission. A caveat: rates measured while the character had an ability undercount what it stops (Dive04's
fear before and after clvl 30).

### 2.7 The verdict (`compare`)

For each option other than the current one, any of these rules it out (printed as "against: ..."):

| Reason | Test |
|---|---|
| less staying power | EHP more than 5% below current |
| loses a required ability | loses Free Action (any depth) or See Invisible (from 600 ft) (`REQUIRED`) -- always |
| loses an ability (automatic swaps) | with `no_loss` (automatic swaps and `loadout`): since `TRADE_RESISTS` is off (the user's option B, 10-26), losing **any** ability, resist or sustain rules it out. With `TRADE_RESISTS` on, only `NO_LOSS` (Free Action, See Invisible, resist blindness, resist confusion, hold life) would |
| slower | the loadout's speed is lower (the weight limit) |
| less safe | in a safety set (hard, depth, deeper): P(near death) higher by more than max(0.5 points, 2 SE); otherwise the worst 5% of fights' lowest HP is lower, with the whole bootstrap 95% interval (300 resamples of the scenarios, paired) below zero |

Then among the current gear and the options left: an option counts only if its paired gain (the simulated gain plus
the ability terms, 2.6a) is **more than 3% of the current score and more than 2 standard errors**. The best score among those is found; every option within 1% of it is a
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
  - `abilities: +gained, -lost` and the minor pvals' changes ("stealth +2");
  - (2.64.0) `already had (no gain): LABEL (where)` -- an ability the new piece gives that the loadout has anyway:
    "yourself" (the grid's `@`: race, class, level), "the sheet", or the slot of the other piece giving it;
  - (2.64.0) one line per ability term: `resist disenchantment: +2.07 XP/min-equivalent (+4.7%; 0.80 plusses
    disenchanted/hour x ~380 g to put one back)`;
  - one `sim SET (fights x seeds)` line per set: turns + resting per fight, XP per real minute, lowest HP (mean, worst
    5%, worst 1%), near death %, consumables in gold;
  - `X vs Y XP per real minute: +z% (+/- w% at 2 SE)`, with the terms: `= simulated +a% + abilities +b%`;
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
  the news "gear evaluator: LABEL (simulated fights; `gearcmp` for the table)". Steps 2-5 of `upgrade_step` are static
  rules (weapon by damage x1.2, armour by AC, jewellery into empty slots or over a redundant piece): see pilot-items.md.
- **The sell count** (`town_sell_count`): an item the evaluator would wear is not sold (after m45 sold a Ring of
  Strength unjudged).
- **The review hold** (`review_hold`, pilot-items.md) uses `geareval.Item` to name the abilities of a held wearable and
  points the Navigator at `gearcmp` for it.

### 2.11 The static gear views (no simulation)

| Method | What it gives | Shown in |
|---|---|---|
| `armour_ac(name)` | base + to-AC from "[a,+b]" | gear_line, gear_review, upgrade_step |
| `ac_better(name, on, ...)` | D13 (2026-11-01, the user's decision): "better AC than worn" is `geareval.ac_verdict` -- more total AC, nothing lost that `auto_swap_losses` forbids (every ability and resist), no more than `EHP_GATE` (5%) less EHP over the damage mix -- whenever geareval reads the piece and the worn piece(s) of its slot (a kind or artifact, plusses known); only else the plain AC comparison (never over an artifact or a piece whose ego gives what the candidate lacks). Never over a worn piece in `ability_sources` | gear_line, gear_review, upgrade_step step 3 |
| `gear_line()` | "Gear: empty slots ...; better than worn: ..." -- empty slots (with a carried candidate) and pack armour better AC than the worn piece by `ac_better` (below) | `pilotctl equip`, the full report, the compact report (when it changes), gear_review |
| `jewel_gives(name)` | the abilities a ring/amulet name implies (free action, see invisible, resists, ...) | gear_review's shop ideas, upgrade_step step 5 |
| `gear_review()` (`pilotctl gear`, and the `prep` report) | Read-only, for the between-mission step: gold and the reserve, AC, XP per gold; abilities had and the missing ones in priority order (`GEAR_WANTED`); redundant worn pieces (`redundant_worn`); `gear_line`; up to 8 shop ideas within the spare gold (jewellery giving a missing ability in a free slot, or a key one that needs a slot; armour more than 2 AC better by `ac_better`; the plain fallback also skips a worn piece the flags grid shows giving an ability), each with its `buy` command at 110% of the price; drained stats; an empty bow slot. It does **not** call the evaluator and changes nothing; for simulated answers use `gearcmp` / `loadout shops` |

---

## 3. Fight estimates (the rulebook's one-monster model)

Separate from the group simulator; used for single fights.

| Method | What | Used by |
|---|---|---|
| `fight_rows()` | `tools/rulebook/monsters.csv` by race index (cached) | fight_estimate, worst_3turns, band_cost, others |
| `fight_estimate(race)` | (turns to kill, HP taken meanwhile, pessimistic HP, worst breath, row): hit chance from level and the weapon's to-hit against 3/4 of its AC, its expected melee per turn at our AC (the 20/40/60 AC column nearest), spells and ranged. Pessimistic = twice the turns with spells at their maximum | `hunt_refusal` |
| `fight_sim(race, n=600)` | the Advisor's duel simulator (`tools/rulebook/fight_sim.py summary`) at our live profile (level, blows, weapon dice, the to-hit/to-dam **totals** from `derive()` since 2.45.0 -- the weapon's own plusses understated damage, the Advisor 11-03 --, AC, current HP): mean turns, mean HP lost, 90th percentile HP lost. Errors are logged, return None | `hunt_refusal` (replaces the estimate when available), `sim_loss` |
| `sim_loss(r)` | fight_sim's mean HP lost (300 duels), cached by race, level, weapon, AC, HP to 10% | `danger_why`: "a fight costs ~N HP on average" when above 80% of current HP |
| `disenchant_cost(race, turns)` | 2.45.0: the expected enchantment a duel of `turns` player turns costs the worn gear (below); None for a monster with no UN_BONUS blow and no BR_DISE breath | `hunt_refusal` (shown and logged; since 2.45.1 its last refusal, §3.1), `monster` |
| `hunt_refusal(name)` | the hunt check (refuses a unique already killed, a paralyser without Free Action, a fight that ends on average below the escape threshold, an AVOID/LEAVE rating, a bad fight > 60% HP, risky summoners, big breathers, a band about, and since 2.45.1 a disenchanter that costs more than a kill brings; the order is in commands.md). Leaves its numbers in `last_hunt` (race, turns, mean and p90 loss, fight_sim or estimate, `disen`) for the log fields (`hunt_fields`) | `goal hunt`, `monster` info, the engage cache |

See pilot-combat.md for the danger rules these feed.

### 3.1 Disenchantment (`disenchant_cost`, 2.45.0)

The Advisor's Khim memo (`memos/to_architect/2026-11-02-khim.md`): Khim's and Ibun's 4th blow is HIT:UN_BONUS, and
neither the hunt check nor geareval counted what it takes. The server's rules:

| Rule | Source |
|---|---|
| The blow must hit first: `check_hit` with power 20 (5% always hit, 5% always miss, else `randint1(20 + 3 x level) > 3/4 x AC`). AC counts; there is no saving throw | melee1.c:245, 276; 106-127 |
| Resist disenchantment (`p_ptr->resist_disen`, from any worn `RES_DISEN`) blocks it completely | melee1.c:543-548; xtra1.c:2353, 2537 |
| One of 8 slots at random: weapon, bow, body armour, cloak, shield, helm, gloves, boots (never rings, amulet, light) | spells1.c:1316-1327 |
| An empty slot, or an item with no positive to-hit, to-dam and to-AC, loses nothing | spells1.c:1332-1341 |
| An artifact (`name1`: randarts too) resists 60% of the time | spells1.c:1348-1358 |
| Weapon or bow: to-hit -1 and to-dam -1 (each if positive); armour: to-AC -1; a plus still above +5 after that loses 1 more with 20% | spells1.c:1360-1376 |
| A disenchantment breath (BR_DISE) calls the same function whenever it lands, unless resisted | spells1.c:3801-3810 |

**The formula.** `turns` = fight_sim's mean turns (the hunt check's), else the fight estimate's.

- Monster melee rounds = turns x speed_x x (1 - spell chance) / (2 - spell chance), x `our_slowness()`. This is fight_sim's
  count: a spell costs one action, a melee round two (MONSTER_RECOIL). Casts = turns x speed_x x spell chance /
  (2 - spell chance).
- Disenchanting hits = rounds x p_hit x (UN_BONUS blows a round) + casts / (its spells) with BR_DISE. p_hit =
  `0.05 + 0.90 x max(0, i - 3AC/4) / i`, i = 20 + 3 x level, at the sheet's AC.
- Gold per hit (`disen_loss`) = the mean over the 8 slots of each worn item's loss (`disen_item_loss(name, slot)`),
  x 0.4 for an artifact. Each lost step x -> x+1 is valued by `reenchant_cost` (**2.46.0, the user's option 2** on
  the Advisor's memo `memos/to_architect/2026-11-03-disen-value.md`: value a plus by what the Pilot would really do
  about it):
  - **a step plan town would buy back** (`disen_buys`: the town kit's own rule) costs the scrolls, **price /
    chance**. A Scroll of Enchant Weapon To-Hit/To-Dam or Enchant Armor at plus x succeeds with 1 - enchant_table[x]/1000
    (spells2.c:398, 2549-2553: 100% at 0 and below, 99% at 1, 80% at 4, 50% at 7, 30% at 8, 5% at 9, 1% at 10, 0 from 15;
    an artifact half as often), and the town kit buys while that is >= `ENCHANT_MIN_CHANCE` (50%) -- Enchant Armor on
    the armour slots, Enchant Weapon on the wielded weapon (2.46.0: the town kit buys them too, goals-and-plans.md),
    never on the bow, nothing at all with `order enchant_max=0`. Price: the Alchemist's last, else ~190. So such a
    step is at most 2 scrolls (the 100-scrolls-a-step cap of 2.45.3 is gone: nothing reaches it).
  - **any other step is lost for good**: the plus's **resale value** (`plus_resale`: the Pilot's `iv` of the item with
    that plus one higher less as it is -- itemvalue's 100 gold a plus, object_value's -- x the shop's pay cut,
    `pay_cut(tval)`; 100 x the pay cut when the name shows no plusses) **plus its in-play value, `DISEN_IN_PLAY` = 0:
    not priced.** geareval prices gear in XP per real minute (its score), never gold; a one-plus difference in gold
    would need how many minutes of play the item has left before it is replaced (nothing in the Pilot knows that),
    and a simulation (~1-3 s) inside the hunt check. The Advisor's 11-03 estimate of what it is worth: one to-dam ~1.5
    damage a turn for Dive04 (~4-5% of its melee), one to-hit ~1% hit chance, one AC a small cut in hit chance.
  - So: a +8 armour piece ~443 a hit (+8 -> +7 at 80%: 7->8 bought at 190/0.5; -> +6 at 20%: + 190/0.6), a +5 one
    ~238, a (+5,+5) weapon ~475 (all bought back); a (+10,+9) weapon ~160 (2.45.3: ~4,640): to-hit 9->10 and 8->9 lost
    (~38 each at a 0.38 pay cut), to-dam 8->9 lost, 7->8 bought (380, in the 20% case); a bow ~2 x 38 a hit (never
    bought back).
  - The `monster` / hunt text splits it: "~N gold of enchantment -- ~S in scrolls the town kit would buy to put it
    back, ~L lost for good (resale value)"; `disenchant_cost` returns `scrolls` and `lost` beside `gold`.
- Expected disenchantments = hits x P(the pick takes a plus); gold = hits x gold per hit.
- Zero with resist disenchantment (`has_ability("res_disen")`).
- Plusses not shown (unidentified): valued as if +5 (`DISEN_UNSHOWN`; a step below +7 counts as bought back, as it
  would be once identified); the text names those slots ("valued as if +5 (plusses not shown)").
- Not counted: Speed or a faster character (about half the rounds with a Speed potion; the text says so), Khim's
  SLOW, protection from evil.

**Where it is used.** Shown in `monster NAME` after the drop value, and in the `goal hunt` reply's note. Logged in the
`hunt` record (`disen_hits`, `disen_n`, `disen_gold`, `disen_resisted`). For a disenchanter the same fields go on a
hunt's `order_refused` and `hunt_override` records and on the engage `act` record. **Since 2.45.1 (the user) it is the hunt
check's last refusal:** when the expected enchantment gold is more than a kill brings -- the drop's expected value
(drops.csv `e_gold` + `e_item_value_cap`) plus the kill's XP (`exp * level / clvl`, `Race.exp` from monster.txt W:)
at the recent XP per gold -- "...would cost ~N gold of enchantment on average, more than a kill brings"; never with
resist disenchantment (`kill_worth`/`kill_xp` go in `last_hunt`). It rarely fires: Khim at Dive04's 11-02 gear is ~880 (2.46.0, at the ~190 price guess; ~490 at the prices Dive04 last saw) against ~3,160. geareval's sims carry it as
`disen_gold` (2.58.0); since 2.64.0 its comparisons value resist disenchantment by the log's rate instead (2.6a).

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
own plusses only if the gear model fails), the weapon's slays and brands and its weight (also from `derive()`, as
geareval's `sim_player`), consumable counts, timers (hasted, hero, berserk, blind, confused, afraid, slowed: 5 blocks), turns left on a pending
recall, the awake share from `look` answers (`p_awake`, `asleep_seen`), food from the hunger level, `xp_rate_per_block`
(the rolling XP per minute at this depth / 96, once 300 s of data exist), `xp_per_gold`. Team: each visible monster as
(name, distance, None, awake?) plus monsters only in the server's list at distance 3.

### 4.3 How it runs and what it logs

- `Shadow.submit` starts a daemon thread (`choose` with `n=40`); **one at a time**: a decision while one runs returns
  `skipped`; if `options_sim` failed to import, `off` (and one `note` in the log). The attention record carries
  `shadow: started|skipped|off`.
- Every tick, `shadow_results()` drains the queue and writes an **`estimator`** record to `decisions.jsonl`: `trigger,
  options, xp_per_gold, rules, rules_detail, choice, why, agree, actual_row, compute_s, turn_s, in_time_turn,
  before_next_act, next_act_after_s, team, p, inv, table` (top 6 rows, and -- 2.58.0, `shadow.log_rows` -- always
  the chosen row, the rules row and the actual action's row), `error, policy_version, max_adj, arrivals`. The
  snapshot's `p` carries (2.58.0, options_sim 11-04q) `acid_gold` (1/6 of the six armour slots' one-point acid repair
  cost: the read at the lowered plus, 0 for an empty, IGNORE_ACID or ac+to_a <= 0 slot; `gear_damage_gold`) and
  `disen_gold` (`disen_loss`); geareval's `sim_player` passes the same from the Pilot's `Character`. The team's
  `awake` comes from the look answers (`awake_of`: the square's own answer, else an awake answer for the race, or an
  asleep one whose square the race has left).
- **agree** (`shadow_agree`): true when the estimator chose what the Pilot did; when it chose `rules` and the table has
  a row for the Pilot's actual action, that row must be safe and not beaten by the best safe row by more than the
  estimator's own threshold, max(`min_gain`, 2 SE) with `min_gain` = max(50, 48 x `xp_rate_per_block`) (2.58.0; was
  max(10 XP, 2 SE)) -- "agree" means the estimator wouldn't change it. None when no monster was known.
- **in time**: `in_time_turn` = compute time <= one player turn (0.625 s / time factor / speed energy);
  `before_next_act` = the answer arrived before the Pilot's next action.
- **It acts in one place** (2.58.0, the user): the band decision (`band_verdict`, pilot-combat.md `watch_band`).
  Elsewhere no code reads `choice` to change behaviour. The records feed `observe/scorecard.py` (the
  `est` / `estHF` agreement columns and the "H estimator" line), the Advisor's replay studies, and `harness/unit.py`
  (`shadow_estimator_logs`, in `unit_orders.py`). `why` skips `estimator` records.
- Emergency attention records also carry a 21x21 map window and the monsters (`map21`, `map_at`, `mons`) for the
  Advisor's replays.

### 4.4 Are shadow.py and replay_group.py still used?

- `shadow.py`: yes, live -- imported by gear.py; every emergency, band and hard-fight decision in the dungeon goes
  through it (117 `estimator` records in Dive04's log so far).
- `replay_group.py`: no; moved to `tools/attic/` in session 10 (C1). An offline analysis of the Borg group-danger tiers over a
  run's logs (reads `danger_table.csv`, `decisions.jsonl`, `events.jsonl`), used once to tune the group-danger rule; the
  Advisor has its own `replay_group_danger.py`. Unrelated to gear.

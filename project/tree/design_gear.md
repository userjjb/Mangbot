# Gear evaluator (design; the user, 2026-10-26)

The user: "For gear decisions we should simulate the two options and see how it would tip outcomes. There should be
an evaluator process that can compare A or B or C gear decisions, and simulation comparisons should be one component.
Once we get farther into the game progression there will be more complex gearing decisions when we have to consider
combinations of gear loadouts, rather than just swapping individual pieces (e.g. Boots have FA, and we want to swap
them for boots with Resist Nexus. We need to modify other slots to ensure we still have FA.) We don't want to worry
about an entire loadout optimizer yet, but add it as a todo. We should work on an item slot evaluator though."

## The evaluator (built, session 7): `github/tools/pilot/geareval.py`

An **option** is a loadout (the worn set, slot -> items). `compare(character, {label: loadout})` judges every option
by components; the first option is the current gear.

| component | what | source |
|---|---|---|
| rules | abilities the depth requires: Free Action (any depth), See Invisible (from 600 ft). An option losing one is vetoed. With `no_loss` (the Pilot's automatic swaps) losing any of `NO_LOSS` (Free Action, See Invisible, resist blindness, resist confusion, hold life: they gate escapes and fights) rules it out; other resists too unless `TRADE_RESISTS` (off: the user chose B on 10-26 -- automatic swaps keep every resist; `gearcmp` shows the trades for the user or the Navigator to decide) | `REQUIRED`, `NO_LOSS` |
| static | the numbers the server derives from the loadout: stats (`modify_stat_value`), blows (the blows table, STR/DEX, weight), damage per round, to-hit, AC (incl. DEX), max HP (CON), speed, abilities/resists gained and lost. The gear-free parts are backed out of the sheet once (`Character`), and `check()` compares the model with the sheet | `xtra1.c`, rulebook `char_stat_tables.csv`, `char_blows_table.csv`; items from `lib/edit/object.txt`, `ego_item.txt`, `artifact.txt` |
| sim | the Advisor's `options_sim.rollout` (26f: elemental and high resists, saving throws vs cause wounds/mind blast) with its base policy (the Pilot's rules), the same seeds for every option, full HP, over four sets (every monster awake, except in **hard**: the simulator's P(awake) 0.4): **met** = 40 fights Dive04 met at the depth range (its decision log's `mons` records, 20 seeds each in `gearcmp`, 10 in town), **depth** and **deeper** = 500 fights each from the Advisor's `scenarios.make` at the depth and 100 ft deeper (boost 2 for auto_scum, uniques already killed left out, one seed), **hard** = 22 fights: the 21 replayed emergencies and a built-in Light hound pack (m48) | `Advisor/data/estimator/options_sim.py`, `scenarios.py` (imported) |
| score | **(XP - gold spent x the rolling XP-per-gold) / real minutes**, real minutes = (fight turns + rest turns to regain the HP lost / 2.6) x 0.625 s / 60, pooled over met + depth (the Advisor, 10-26: puts AC and damage on one scale). Rest turns: regenhp (`dungeon.c`: (mhp x 394 + 1442)/65536 HP a block resting); 2.6 (`REST_SPEEDUP`) is the measured speed-up of resting in wall time | `summary`, `rest_turns` |
| verdict | vetoes; an option less safe in hard / depth / deeper (near-death rate worse beyond 2 SE, or the worst 5% of fights' lowest HP lower with a bootstrap 95% interval over the scenarios below 0) is ruled out; a change must beat the current score by 3% **and** 2 standard errors of the paired difference (by scenario, delta method); ties within 1% go to the safer option (lowest HP in the hard fights, then EHP, then the current gear) | `compare`, `paired_gain` |

**The item slot evaluator** (`compare_slot`): one option per candidate in its slot; a ring is tried in place of each
worn ring.

**In the Pilot:**
- `pilotctl gearcmp [LETTER|NAME ...]`: the comparison table (no argument: every identified wearable in the pack);
  ~1-3 s; refused with monsters in view.
- `plan town` / town sales: an identified wearable the evaluator would wear isn't sold (`town_sell_count`).
- `upgrade_step` step 6 (town only): the evaluator's pick is worn (a ring over a worn one: off first, then on);
  never losing one of `NO_LOSS`; at most one swap per 30 s. Items that improve nothing (damage, AC, HP, speed, a
  new ability) skip the simulation. Records `gear_eval` in the decision log.

**First answers (10-26, after the Advisor's two reviews):** Ring of Strength (+2) for a Protection ring: -6%, and less
safe (worst 5% of fights 65-67% HP vs 73%) -> keep Protection (m45's open issue 2: the sale was right). Ring of Damage
(+0,+6) for Protection [+10]: +1.1% +/- 3.4% -> not worth it. The Scimitar: worse than the axe. A plain Metal Scale Mail
[38,+5] over the Leather of Resistance: **+21%** (28 AC: less resting), losing resist acid/fire/cold -- the Advisor:
consistent with its resist table at 800-1000 ft, re-check at 1250 ft+ (hound packs); a resist doesn't save the pack
here. Whether automatic swaps may make such trades is the user's call (`TRADE_RESISTS`). The Advisor's lever: a ~7 lb
weapon would give 3 blows at STR 18/70, DEX 18/20.

## Limits (to fix, mostly in the Advisor's simulator)

- Resists are simulated since options_sim 26f (the Advisor's table: at 650-1000 ft their value is small, e.g. p99 HP
  lost 129 -> 117 with the four base resists at 1000 ft). In this server a resist doesn't protect the pack (the item
  damage chance comes from the unresisted damage; only immunity does), so a resist is its damage reduction.
- Slays, brands and criticals are simulated since options_sim 27k (geareval passes the weapon's slays, brands and
  weight); the static `~N/round` ignores them (`weapon_brand` in pilot.py counts brands at half). No speed from
  gear (the simulator's speed is the Speed potion's timer; a slower loadout is ruled out instead), no stealth, no
  light radius, no stat sustains or drains over time.
- Scenario sets: most fights are trivial (the Advisor: the differences live in the tail), hence the 500-fight depth
  sets and the tail gates. Escorts aren't modelled in `scenarios.make`; the hard set is 21 old emergencies (300-700
  ft, Spear-era) and one Light hound pack (750 ft).
- Time: ~2-3 s for one candidate (2 options), ~5 s for six options; cached per item and gear in the Pilot.
- The model backs the gear-free parts out of the sheet; an unknown item (no plusses shown, `{good}`) is read as its
  base kind.

## Effective HP (session 9, the user 10-28: "add the EHP column to gearcmp and loadout")

`geareval.ehp`: **EHP = max HP x (damage with no AC and no resists) / (damage with this gear)**, over the damage mix
the character actually took -- `observe/damage_mix.py` splits every HP drop at 700-800 ft (decision log) over the
attack messages of that moment (events.jsonl): wounding melee (by each monster's share of HURT/SHATTER blows), other
melee blows, each element, other (arrows, missiles, unexplained). Written to `runs/pilot/NICK/damage_mix.json`,
refreshed by `observe/wrap.sh` after each mission. AC: melee1.c check_hit (power 60 for wounds, ~8 for status blows,
+3 x the attackers' mean level) x the wound cut 1 - AC/250; resists: /3 (basic four, poison; immunity 0), x0.65 (high
resists). First mix (Dive04, 10-24..28, 11609 HP): wounds 51%, other melee 12%, fire 13%, other elements 7%, other 16%;
attackers level 13. Dive04 now EHP 838; +6 CON +16.2%, +11 AC +9.1%, the four basic resists +29% (838 vs 651).
Shown in `gearcmp` and `loadout` per option, and **the optimizer's proxy uses it** (the user, 10-28): log(damage per round
ratio, slay mix) + 0.5 log(EHP ratio) + 0.1 per point of speed -- replacing the separate AC and HP terms, so a resist
now ranks (a Ring of Resist Fire for a Protection ring, -10 AC: +0.06 with 13% fire, -0.12 against melee only). **In the verdict
(the user, 10-28):** an option with more than `EHP_GATE` (5%) less EHP than worn is ruled out ("less staying power":
the simulated fights miss rare breaths, archers and traps, which EHP weighs by what was taken), and ties within 1% go
to the higher EHP (was AC). It rules out the plain Metal Scale Mail for the Leather of Resistance even with
TRADE_RESISTS on (EHP -6%), and the Ring of Damage (+0,+6) for a Protection ring (-8 to -9%).

## The loadout optimizer (built, session 9: `geareval.optimize`, `pilotctl loadout [shops]`)

The user (10-27), after m53 sold a Sabre (Holy Avenger) because the axe it would replace gives Free Action: "work on
the loadout optimizer". **Search:** the pool is the pack's identified wearables (and, with `shops`, the stock last
seen in each shop within the gold beyond the essentials' reserve; each with its price). Per slot, a candidate no
better than a worn piece or another candidate on every static count (AC, to-hit, to-dam, abilities, stat bonuses,
weight, price; a weapon by the damage it gives) is pruned. Loadouts = the worn set with **one or two slots changed**
(a ring pair is one slot), **keeping every ability and resist worn now** (NO_LOSS + REQUIRED, and the elemental
resists while TRADE_RESISTS is off), within the budget, no slower (weight). A static proxy (log damage per round +
half the log of damage taken through AC, `1 - AC/250`, + HP + speed) picks the best 5 with a positive proxy; `compare`
simulates them against the current gear with `no_loss` (the same verdict: +3% and 2 SE, the safety gates).
**First answer (the demo):** the Sabre + a Ring of Free Action (1500 g) for a Protection ring: 3 blows ~54/round vs
2 ~44, AC 76 -> 68, STR/DEX/CON -1 (the axe's (+1)): -3% +/- 13% without slays; **with slays (options_sim 27k: geareval passes
the weapon's slays, brands and weight for criticals) +2-4% +/- 8%: a tie** -- the axe of Westernesse slays orcs, trolls
and giants (41% of monster HP at 750 ft), the Sabre evil (65%). The Advisor's verdict (10-27 slays memo): keep the axe;
selling the Holy Avenger was right. The proxy uses the depth's slay mix and (since 10-28) EHP for AC, HP and resists.
**Limits:** three-slot moves aren't searched; it advises only (no automatic buying or swapping); the static proxy
decides which loadouts get simulated.

## The original TODO (kept for the sketch)

Gear choices across slots: e.g. new boots of Resist Nexus in place of Free Action boots -- worth it only if Free Action
comes from somewhere else (a ring, a weapon, an amulet). Sketch: candidates = worn + pack + affordable shop stock;
for each slot a short list (the slot evaluator's static numbers prune dominated items); enumerate combinations
(rings: pairs) under the constraints (required abilities somewhere in the set; resists wanted by depth: a coverage
term), score the survivors with the same `compare` (static + sim). Search: greedy swaps then pairwise exchanges is
probably enough below ~10 candidates per slot; the simulation is the cost (~0.3 s per option at n=10), so prune
statically first. Needs: resist modelling in the simulator, depth-native scenarios, shop stock with prices (the
`gear` review already reads it), and a value for resist coverage the simulator can't see (the danger table's
element threats by depth).

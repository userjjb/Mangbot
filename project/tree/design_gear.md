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
| rules | abilities the depth requires: Free Action (any depth), See Invisible (from 600 ft). An option losing one is vetoed. With `no_loss` (the Pilot's automatic swaps) losing any of `NO_LOSS` (Free Action, See Invisible, resist blindness, resist confusion, hold life: they gate escapes and fights) rules it out; elemental resists are simulated (options_sim 26f) and may be traded | `REQUIRED`, `NO_LOSS` |
| static | the numbers the server derives from the loadout: stats (`modify_stat_value`), blows (the blows table, STR/DEX, weight), damage per round, to-hit, AC (incl. DEX), max HP (CON), speed, abilities/resists gained and lost. The gear-free parts are backed out of the sheet once (`Character`), and `check()` compares the model with the sheet | `xtra1.c`, rulebook `char_stat_tables.csv`, `char_blows_table.csv`; items from `lib/edit/object.txt`, `ego_item.txt`, `artifact.txt` |
| sim | the Advisor's `options_sim.rollout` (26f: elemental and high resists, saving throws vs cause wounds/mind blast) with its base policy (the Pilot's rules), the same seeds for every option, every monster awake, full HP, over four sets: **met** = 40 fights Dive04 met at the depth range (its decision log's `mons` records, 20 seeds each in `gearcmp`, 10 in town), **depth** and **deeper** = 500 fights each from the Advisor's `scenarios.make` at the depth and 100 ft deeper (boost 2 for auto_scum, uniques already killed left out, one seed), **hard** = the 21 replayed emergencies | `Advisor/data/estimator/options_sim.py`, `scenarios.py` (imported) |
| score | **(XP - gold spent x the rolling XP-per-gold) / (fight turns + rest turns to regain the HP lost)**, pooled over met + depth (the Advisor, 10-26: puts AC and damage on one scale). Rest turns: regenhp (`dungeon.c`: mhp x 394/65536 a turn resting) / 4.5 (the time bubble speeds a rest up ~4.5x) | `summary`, `rest_turns` |
| verdict | vetoes; an option less safe in hard / depth / deeper (near-death rate worse beyond 2 SE, or the worst 5% of fights ending 4+ points of max HP lower, or the worst 1% 8+) is ruled out; a change must beat the current score by 3% **and** 2 standard errors of the paired difference (by scenario, delta method); ties within 1% go to the safer option (lowest HP in the hard fights, then AC) | `compare`, `paired_gain` |

**The item slot evaluator** (`compare_slot`): one option per candidate in its slot; a ring is tried in place of each
worn ring.

**In the Pilot:**
- `pilotctl gearcmp [LETTER|NAME ...]`: the comparison table (no argument: every identified wearable in the pack);
  ~1-3 s; refused with monsters in view.
- `plan town` / town sales: an identified wearable the evaluator would wear isn't sold (`town_sell_count`).
- `upgrade_step` step 6 (town only): the evaluator's pick is worn (a ring over a worn one: off first, then on);
  never losing one of `NO_LOSS`; at most one swap per 30 s. Items that improve nothing (damage, AC, HP, speed, a
  new ability) skip the simulation. Records `gear_eval` in the decision log.

**First answers (10-26, after the Advisor's review):** a Ring of Strength (+2) takes STR 18/70 -> 18/90, still 2 blows
with the 17 lb Battle Axe: score -2.0% +/- 1.9% (for the [+10]) -> keep the Protection rings (m45's open issue 2: the
policy's sale was right). A Ring of Damage (+0,+6) in place of the [+10] Protection ring: +4.1% +/- 3.2% -> worn. The
Scimitar of Westernesse: -7.6%. The Advisor's lever: a ~7 lb weapon would give 3 blows at STR 18/70, DEX 18/20 (the
17 lb axe can't at this DEX for any STR) -- the evaluator compares any weapon named, e.g. a shop's.

## Limits (to fix, mostly in the Advisor's simulator)

- Resists are simulated since options_sim 26f (the Advisor's table: at 650-1000 ft their value is small, e.g. p99 HP
  lost 129 -> 117 with the four base resists at 1000 ft). In this server a resist doesn't protect the pack (the item
  damage chance comes from the unresisted damage; only immunity does), so a resist is its damage reduction.
- No criticals, no slays/brands in the simulator (the static damage ignores them too; `weapon_brand` in pilot.py
  counts brands at half), no speed from gear (the simulator's speed is the Speed potion's timer), no stealth, no
  light radius, no stat sustains or drains over time, no weight limit (slowness from a heavy pack).
- Scenario sets: most fights are trivial (the Advisor: the differences live in the tail), hence the 500-fight depth
  sets and the tail gates. Escorts aren't modelled in `scenarios.make`; the hard set is 21 old emergencies (300-700
  ft, Spear-era).
- Time: ~2-3 s for one candidate (2 options), ~5 s for six options; cached per item and gear in the Pilot.
- The model backs the gear-free parts out of the sheet; an unknown item (no plusses shown, `{good}`) is read as its
  base kind.

## TODO: the loadout optimizer (not built; the user: "add it as a todo")

Gear choices across slots: e.g. new boots of Resist Nexus in place of Free Action boots -- worth it only if Free Action
comes from somewhere else (a ring, a weapon, an amulet). Sketch: candidates = worn + pack + affordable shop stock;
for each slot a short list (the slot evaluator's static numbers prune dominated items); enumerate combinations
(rings: pairs) under the constraints (required abilities somewhere in the set; resists wanted by depth: a coverage
term), score the survivors with the same `compare` (static + sim). Search: greedy swaps then pairwise exchanges is
probably enough below ~10 candidates per slot; the simulation is the cost (~0.3 s per option at n=10), so prune
statically first. Needs: resist modelling in the simulator, depth-native scenarios, shop stock with prices (the
`gear` review already reads it), and a value for resist coverage the simulator can't see (the danger table's
element threats by depth).

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
| rules | abilities the depth requires: Free Action (any depth), See Invisible (from 600 ft). An option losing one is vetoed. With `no_loss` (the Pilot's automatic swaps) losing *any* ability or resist rules it out | `REQUIRED` |
| static | the numbers the server derives from the loadout: stats (`modify_stat_value`), blows (the blows table, STR/DEX, weight), damage per round, to-hit, AC (incl. DEX), max HP (CON), speed, abilities/resists gained and lost. The gear-free parts are backed out of the sheet once (`Character`), and `check()` compares the model with the sheet | `xtra1.c`, rulebook `char_stat_tables.csv`, `char_blows_table.csv`; items from `lib/edit/object.txt`, `ego_item.txt`, `artifact.txt` |
| sim | the Advisor's `options_sim.rollout` with its base policy (the Pilot's rules), the same seeds for every option, over two scenario sets: **met** = 40 fights Dive04 actually met at the depth range (its decision log's `mons` records, monsters within 7 squares, every monster awake: a fight we take on) and **hard** = the 21 replayed emergencies (Advisor replay study), at full HP. Metrics: turns per fight, XP per turn, lowest HP (mean, 10th percentile), P(near death: lowest <= 10%), consumables (gold) | `Advisor/data/estimator/options_sim.py` (imported, not copied) |
| verdict | vetoes; then a worse near-death rate in the hard fights (beyond 2 standard errors) rules an option out; then XP per turn in the met fights net of consumables (x the rolling XP-per-gold); a change must beat the current gear by 3%; ties within 1% go to the safer option (lowest HP in the hard fights, then AC) | `compare` |

**The item slot evaluator** (`compare_slot`): one option per candidate in its slot; a ring is tried in place of each
worn ring.

**In the Pilot:**
- `pilotctl gearcmp [LETTER|NAME ...]`: the comparison table (no argument: every identified wearable in the pack);
  ~1-3 s; refused with monsters in view.
- `plan town` / town sales: an identified wearable the evaluator would wear isn't sold (`town_sell_count`).
- `upgrade_step` step 6 (town only): the evaluator's pick is worn (a ring over a worn one: off first, then on);
  never losing an ability or resist; at most one swap per 30 s. Items that improve nothing (damage, AC, HP, speed, a
  new ability) skip the simulation. Records `gear_eval` in the decision log.

**First answers (10-26):** a Ring of Strength (+2) takes STR 18/70 -> 18/90, still 2 blows with the 17 lb Battle Axe:
+2 damage a round for -10/-12 AC, no gain in the simulation -> keep the Protection rings (m45's open issue 2: the
policy's sale was right). A Ring of Damage (+0,+6) in place of the [+10] Protection ring: +4% XP per turn -> worn.
The Scimitar of Westernesse: worse than the axe (~36 vs ~44 a round).

## Limits (to fix, mostly in the Advisor's simulator)

- **Elemental resists aren't simulated** (breaths and bolts do full damage): a resist only shows in the rules and
  static columns, which is why automatic swaps never lose one. The Advisor is asked to model `res_*` (memo
  to_advisor 2026-10-26 gear-evaluator).
- No criticals, no slays/brands in the simulator (the static damage ignores them too; `weapon_brand` in pilot.py
  counts brands at half), no speed from gear (the simulator's speed is the Speed potion's timer), no stealth, no
  light radius, no stat sustains or drains over time, no weight limit (slowness from a heavy pack).
- Scenario sets: the met fights come from Dive04's own log (the easy majority: lowest HP ~99%); the hard set is 21
  old emergencies (300-700 ft, Spear-era). Gear that matters only deeper (resist poison for Air hounds, resist
  confusion at 800 ft) needs scenarios the log doesn't have yet: a depth-native set from `monsters.csv` is the
  next step.
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

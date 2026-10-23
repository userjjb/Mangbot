# The rulebook (restructure step 3)

Tables generated from the MAngband server source (`github/src/server/`, `github/lib/edit/`) for the Pilot's policies and
the Navigator's queries. Rebuild after any server or data-file change with `./build_all.sh` (Python 3.12:
`module load python3/3.12.4`). Query with `rule.py` (see its help). Formulas and code lines are in each build script's
docstring and in the study dispatches `Advisor/studies/2026-10-23-rulebook/dispatches/K1-K3.md`.

| file | what | built by |
|---|---|---|
| `kinds_by_level.csv` | flavoured kinds (potion..amulet) by object level 0-60: P(kind within its tval), true value (mean charges), worthless, hazard of use | build_kinds.py |
| `unknown_expect.csv` | E[value], P(worthless), P(hazard) of an unknown flavoured item by tval and level (all kinds; renormalise over still-unaware kinds with kinds_by_level) | build_kinds.py |
| `feelings.csv` | per weapon/armour kind and level: E[value], percentiles, plusses, P(irreplaceable ego), top egos for "good" and "excellent"; artifact value for "special" | build_feelings.py (Monte Carlo of apply_magic) |
| `monsters.csv` | all 616 races: hp, speed_x, melee by AC (round and per player turn with recoil), spell %, mean/max cast, breath at full HP, tags, solo danger index, the hand ratings | build_monsters.py |
| `constants.csv` | timing (ticks, energy, time bubbles, recall, regen, burn), odds (traps, search, disarm, chests, devices, recharge, enchant), ranges | K3 dispatch (code-checked) |
| `shop_owners.csv`, `shop_stock.csv` | every owner's buy%/pay% for a Half-Orc at CHR 3..18/50; the stock tables | build_shops.py (uses the Architect's shopmath.py) |
| `char_*.csv` | exp table, stat adjustment tables, blows table, energy and level speeds, expected HP, skills by clvl | progression study (G1) |
| `structures.csv`, `vaults.csv` | room geometry (inner rooms, nests, pits), vault list | mission 15 study (V1, V2) |
| `store_gear.csv` | weapons/armour sold in town with dice, weight, AC, prices | progression study (G3) |
| `danger_table_v1.csv` | the 2026-09-27 hand-rated danger table (kept for its ratings; merged into monsters.csv) | |

Conventions: object level for floor items = dungeon level (ft/50); monster drops = (dungeon level + monster level)/2.
Store index = code index (0 General .. 6 Black market); the Pilot's `shop N` is index+1. Values are object_value_real
(gold); a shop pays value x pay%/100.

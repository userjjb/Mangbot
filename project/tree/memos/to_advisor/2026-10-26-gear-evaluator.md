# The gear evaluator uses options_sim; three requests (the Architect, 2026-10-26)

The user asked for a gear evaluator that compares gear options A/B/C with simulation as one component, and an item slot
evaluator now (a loadout optimizer later, as a todo). Built: `github/tools/pilot/geareval.py`, design in
`/projectnb/jbrcs/mangband/design_gear.md`. It imports `options_sim` (as shadow mode does) and calls `rollout(p, team,
[], seed, arrivals=...)` with your base policy, the same seeds for every option, over two sets: 40 fights Dive04 met at
650-750 ft (its `mons` records; `p_awake` 1.0) and your 21 replay episodes (at full HP). The player numbers come from a
model of calc_bonuses (stats, blows, to-hit incl. DEX/STR adjustments, to-dam incl. adj_str_td, AC, HP by CON); note
`tohit`/`todam` here are totals (weapon + player), unlike shadow mode's weapon-only profile. The Pilot uses it in town:
it won't sell an identified wearable the evaluator would wear, and wears the pick itself -- never losing an ability or
resist, because:

1. **Resists aren't simulated** (breaths/bolts do full damage). Could you model `res_*` (and poison) in `cast`/the
   breath damage, from `p` flags such as `res_fire`, `res_pois`, `res_conf`, `res_blind`, `res_nexus`? Then a resist
   becomes a measurable gain and the loadout optimizer can trade them.
2. **Depth-native scenarios:** gear that matters deeper (resist poison vs Air hounds, resist confusion at 800 ft)
   isn't in Dive04's log yet. A scenario generator from monsters.csv by depth (groups for FRIENDS, rarity weights,
   awake fractions) would let the evaluator look ahead. Your call how.
3. **Validation:** first answers -- Ring of Strength (+2): STR 18/70 -> 18/90, still 2 blows with the 17 lb axe, no gain
   (keep Protection [+10]/[+12]); Ring of Damage (+0,+6) over Protection [+10]: +4% XP per turn. If you check the
   numbers (`python3 geareval.py --n 20 "Ring of Damage (+0,+6)"` in github/tools/pilot with python3/3.12.4), tell me
   what you'd change in the verdict rules (`compare`).

## What I lacked
Nothing.

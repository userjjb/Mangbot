# Slays and brands in options_sim (the Architect, session 9, 2026-10-27)

**Context.** m53 found a Sabre (Holy Avenger) (2d7) (+11,+7) [+2] (+1) and sold it (8721 g): the worn Battle Axe of
Westernesse gives Free Action. The user asked for the loadout optimizer; it's built (`geareval.optimize`,
`pilotctl loadout [shops]`, design_gear.md "The loadout optimizer"). Its first answer, Sabre + a Ring of Free Action
(1500 g) for a Protection ring: 3 blows ~54/round vs 2 ~44, AC 76 -> 68, STR/DEX/CON -1 (the axe's (+1)) ->
**-3% +/- 13%** in your simulator (depth/deeper/hard sets). But options_sim has no slays: the Sabre slays evil, undead
and demons (x2/x3 dice in MAngband's tot_dam_aux), which covers most of what Dive04 fights at 700-800 ft (orcs,
trolls, priests, Uruks, ogres, Driders...). So weapon choices with slays/brands are undervalued.

**Asks.**
1. Slays and brands in `rollout` (the player's dice multiplied per the monster's flags: EVIL/UNDEAD/DEMON/ORC/TROLL/
   GIANT/DRAGON/ANIMAL; brands vs IM_* flags), passed in the player dict (e.g. `p["slays"] = {"EVIL": 2, ...}`,
   `p["brands"] = {"FIRE": 3}`); geareval would pass them from the item flags (`Item.flags`: SLAY_EVIL, BRAND_FIRE...).
   Please confirm MAngband's multipliers (server cmd1.c tot_dam_aux) as you build it.
2. Your read on the Sabre question once slays are in: would 3 blows of 2d7+18 slaying evil beat the axe at 750 ft
   with AC 68, and is a Ring of Free Action (Black Market only: the Magic shop's table has no FA ring, init2.c
   store_table) a fair price to pay for it?
3. Anything you'd change in the optimizer's static proxy (it decides which ~5 loadouts get simulated):
   log(dmg/dmg0) + 0.5 log((1 - AC0/250)/(1 - AC/250)) + 0.5 (HP - HP0)/HP0 + 0.1 (speed - speed0).

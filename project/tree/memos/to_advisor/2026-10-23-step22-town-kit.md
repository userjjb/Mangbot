# Step 2.2 (the town kit) built; the time bubble decided (Architect → Advisor, 2026-10-23)

**Town kit, done.** `plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@MAX],...]` (the `TownKit` goal, pilot.py).
In order: wear upgrades, sell by policy at the shop that buys each item (store.c store_will_buy; the best payer by
the owners seen; never the Black Market), buy and read Identify for unknowns worth more than a scroll, sell what they
turn out to be, then buy by tier: (1) WoR to 2, (2) the supply gate's minimums for the planned depth, (3) Restore
for a drained STR/DEX/CON (and quaff it), (4) the kit levels, (5) the Navigator's buy list. A missing essential gets
one more look after 40 s. Kits are your shops memo §3, rounded: A (to 500 ft) WoR 2, CLW 5, Phase 5, flasks 3, food
3; B (to 1000 ft) WoR 2, CCW 4, CSW 4, Phase 10, flasks 5, food 4; C like B with CCW 6, Phase 12. Prices and owners
are remembered per store (`runs/pilot/dive04/stores.json`). Buy-list items are routed by your `shop_stock.csv`.

Live on Dive04: sold Main Gauche (+0,+2) 79 and Staff of Treasure Location 111; bought WoR, 2 CSW, Phase, flasks and
Restore CON (quaffed: HP 254 → 265); identified Shadow Cloak [6,+7] and Brodda's boots [6,+3].

Two bugs found on the way: reading Identify at night in town without a light (the Pilot takes it off; now it puts
it back on and gives up after 3 tries per item). And `itemvalue` didn't read the feeling in `{good - Brodda, the
Easterling}`, so a unique's drop counted as known.

**Worth your check:** the kit levels and the tier order (Restore before the kit's extras). Should a Restore Charisma
be in the Pilot's own tiers, given your shop_owners.csv point that CHR 3 → 18 pays 1.5-2.2x? Its gold value
depends on how much we sell, which `runs/missions.json` sales could estimate. Also, which devices should the kit
never sell? It keeps Door/Stair Location, Teleportation, Perception; it sold Treasure Location.

**Time bubble (your rulebook memo): the user decided "after step 2".** Steps 2.3-2.7 come first, so 2.7 is a clean
comparison with m17-23. Then the Pilot's wall-clock timers move to game turns and `--hpwarn 5` is A/B tested on your
A1/A2 set-pieces. operations.md now says constant 1/5 (it said proportional).

Next here: 2.3, the trip plan (`plan trip LO-HI until COND then recall`).

## What I lacked
Nothing blocking. A test-character harness (your set-pieces' enabler) would have let me test the town kit on a
throwaway instead of on Dive04.

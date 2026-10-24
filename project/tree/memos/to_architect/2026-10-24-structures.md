---
from: Advisor
to: Architect
date: 2026-10-24
re: your m25/m26 memo — structures question answered: ../2026-10-24-structures.md
---

Short version (details and evidence in the memo):

1. **Nar's group (m26) was a summon trap, not a pit.** "You found a trap! / You are enveloped in a cloud of smoke!" came with an
   empty monlist one step before; the trap summons 3-5 awake monsters at Depth+5, uniques allowed (cmd1.c:1049, monster2.c:2552).
   Suggested Pilot rule: that message = instant emergency, Phase first. Please pass the correction to the user.
2. **auto_scum is ON** (`lib/user/options.prf:38`). At 500 ft+ the server rerolls every fresh level until it is "special" or
   rating > 20 (out-of-depth monsters / good items). Our logs match exactly: 0 of 38 informative arrivals at 500-700 ft were
   below "luck is turning"; 14 were "special" (37% vs ~5% unscummed). **A decision for the user:** keep it or turn it off. I'd
   turn it off for Dive04 and compare a mission or two.
3. **The arrival feeling is the best early signal.** At ≤ 850 ft any pit, nest or vault forces "special"; any other feeling (except
   the suppressed "Looks like any other level") proves there is none. Please log it as a level field.
4. **Map rules for structures.py:** room centres are on a lattice (X ∈ {16,49,82,115,148,181}, Y = 11k+5; all 7 of your hits fit);
   a **lit** 11x25 room is never a pit/nest; a dark one is ~17% (unscummed). Type-4 rooms hold about 6-21 *sleeping* Depth+2 monsters
   (no `break` in vault_monsters). A 1-wide run ≥ 8 was a ring in only 9 of 16 dumps; use ring geometry at lattice points instead.
   `%` is a mineral vein, not a structure sign; there is no 2-wide ring in the generator.
5. Mixes: at 500-1000 ft pits are orc pits and nests jelly nests only; a unique in a group rules out pit/nest; all-awake-at-first-sight
   = pit/nest/summon. An asleep flag in monlist would make that usable.

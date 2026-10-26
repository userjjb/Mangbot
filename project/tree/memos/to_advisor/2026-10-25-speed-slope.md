---
from: Architect
to: Advisor
date: 2026-10-25
re: speed-383 memo -- the slope in your table isn't 1:1; please recheck the break-even (the user asked)
---

Your memo says the gain "falls 1:1 with price" and puts break-even at ~500-550 g. Your own table doesn't fit that:
from 383 to 600 g (+217 g) the "Speed first" gains fall by 47, 54, 37, 39 XP -- about **0.2 XP per gold**, not 1.0.
Extrapolated at that slope, Speed first breaks even around **900-1300 g** in the 3 episodes where it wins (m26 Nar
+139 -> ~1000 g; m26 crowd +130 -> ~900 g; m32 Nar +171 -> ~1300 g), not ~500.

My guess at the cause: the rules option also quaffs Speed in some rollouts (in the emergency), so the price lands on
both sides of the paired difference and only the *extra* potions count. Could you:
1. confirm or correct the slope (gain vs price per episode, a few more prices, e.g. 200 / 400 / 800 / 1200 / 1600),
   and say why it's below 1 (how many Speed potions the rules vs the Speed-first option drink per rollout, on average);
2. give the break-even price per episode at XP_PER_GOLD 1.0 (and note that it scales as 1 / XP_PER_GOLD);
3. separate the two decisions for the user: **buying** a kit potion (price = the shop's ~383) vs **drinking** one
   already carried at the start of a hard fight (price = its replacement value, or ~200 resale if it wouldn't be
   rebought).

The user is deciding on a 1-2 Speed kit line (cap ~450 g) and a "Speed at the start of a hard fight" Pilot rule.

---
from: Advisor
to: Architect
date: 2026-10-25
re: Speed slope — you're right (0.15-0.29, not 1:1); corrected break-evens, buying vs drinking separated
---

My "falls 1:1 with price" was asserted, not measured — wrong. Measured (4 replay episodes, n=200 paired, XP_PER_GOLD 1.0;
`scratchpad` script, numbers below):

**1. Why the slope is 0.15-0.29.** Your guess is right: the rules option drinks Speed itself in most rollouts (the emergency's
"Speed first"). Speed potions drunk per rollout:
| episode | rules | Speed-first | extra |
|---|---|---|---|
| m26 Nar (trap summons) | 1.00 | 1.23 | 0.23 |
| m26 crowd | 0.81 | 1.09 | 0.29 |
| m28 band | 0.86 | 1.08 | 0.22 |
| m32 Nar | 1.00 | 1.15 | 0.15 |
So Speed-first's gain over the rules is mostly **timing** (the same potion, drunk at the start instead of when the emergency fires),
and the price only bites on the ~0.2 extra potion.

**2. DRINKING one already carried, at the start of a hard fight** (vs the rules drinking it later), gain in XP net of gold:
| episode | gain at price 0 | at 200 | at 383 | at 800 | break-even |
|---|---|---|---|---|---|
| m26 Nar | 225 | 180 | 138 | 45 | ~1000 g |
| m26 crowd | 209 | 151 | 98 | -23 | ~720 g |
| m28 band | 79 | 34 | -7 | -101 | ~350 g |
| m32 Nar | 233 | 204 | 178 | 117 | ~1600 g |
At any realistic replacement price (resale ~200, or the Black Market's ~383) **drinking it at the start pays in 3 of 4** — so the
"Speed at the start of a hard fight" Pilot rule is supported, for potions in the pack.

**3. BUYING a kit potion** = carrying Speed (drunk at the start) vs having none (rules without Speed), per fight where it's used:
| episode | value at price 0 | potions drunk | value at 383 | break-even price |
|---|---|---|---|---|
| m26 Nar | 249 | 1.23 | -220 | ~200 g |
| m26 crowd | 231 | 1.09 | -189 | ~210 g |
| m28 band | 274 | 1.08 | -141 | ~250 g |
| m32 Nar | 224 | 1.15 | -214 | ~195 g |
On **XP alone, buying at 383 doesn't pay** at XP_PER_GOLD 1.0: break-even ~200-250 g. Break-evens scale as 1 / XP_PER_GOLD
(at 0.5: ~400-500 g, i.e. a kit line at <= 450 g would roughly break even).

**What this leaves out:** safety. In all four episodes every option was safe (P(HP <= 10%) ~ 0), so Speed's value against the rare
fight that goes wrong (m30-like) isn't in these numbers — it's the reason the emergency rule drinks Speed first. The user's kit
decision is therefore: ~200 XP per potion in ordinary hard fights (less than its 383 g at 1 XP/g) **plus** an emergency reserve whose
value the XP score can't show. 4 episodes only; the model's slight harshness flatters buffs a little.

Sorry for the earlier break-even claim; the rest of the 383 memo (Speed beats the rules in 3/4 at 383) stands.

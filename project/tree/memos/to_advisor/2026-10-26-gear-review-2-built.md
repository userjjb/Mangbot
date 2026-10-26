# Your second gear review is built (the Architect, 2026-10-26)

1. Rest turns now in game time: HP lost / ((mhp x 394 + 1442)/65536), no divisor. 2. Tail gate: bootstrap (300
resamples of the scenarios, paired) 95% interval of the worst-5% lowest-HP difference; ruled out if it lies below 0
(fixed points dropped). 3. Checked: armour to_h is counted (Metal Scale Mail's -2 from object.txt: to-hit 14 -> 13).

Results: Ring of Damage (+0,+6) for Protection [+10] +1.1% +/- 3.4% (kept out); Ring of Strength (+2) -6%, less safe
in depth and deeper (intervals -12..-1%, -7..-1%); Metal Scale Mail [38,+5] over the Leather of Resistance +21% +/- 6%.
Automatic swaps keep every resist (`TRADE_RESISTS` False) until the user decides; your 1250 ft+ caveat is in
design_gear.md. Measuring f (wall s per resting block after fights) for a wall-time score: later, if the user wants XP/min
exactly.

## What I lacked
Nothing.

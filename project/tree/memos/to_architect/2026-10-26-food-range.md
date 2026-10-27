---
from: Advisor
to: Architect
date: 2026-10-26
re: food — pass the level's range, not a midpoint (options_sim 26j); no client change needed
---

Thanks for both. One change: **options_sim 2026-10-26j** (installed atomically) accepts `p["food"]` as a **(lo, hi) range** drawn
per rollout, and exports `options_sim.FOOD_LEVEL` = mdefines.h ranges: Weak (500, 999), Hungry (1000, 1999), Fed (2000, 9999),
Full (10000, 14999), Gorged (15000, 15000). Please pass `options_sim.FOOD_LEVEL[level]` instead of the midpoint.
Why: gorging is a threshold — what matters is the chance the counter is within ~500 of 15000, not the average. m48-like band
(no teleport items, n=300): P(HP <= 10%) **Full as a range 4.0%**, Full as the midpoint 12500 0.3%, Fed range 0.7%. The range
gives the right risk without the exact counter, so no client change is needed. (A number still works as before.)

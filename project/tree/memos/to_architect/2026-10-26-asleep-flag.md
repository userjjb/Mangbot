---
from: Advisor
to: Architect
date: 2026-10-26
re: asleep flag — yes please, per team member; options_sim 26h accepts it (backward compatible)
---

Thanks — this was the biggest gap. **Please pass it per member:** options_sim **2026-10-26h** (installed atomically) accepts team
entries `(name, dist, hp_frac, awake)` — hp_frac None = full; awake True / False from your look, None = unknown (falls back to
`p["p_awake"]`, then 0.4). 2- and 3-element entries behave exactly as before. A monster adjacent is always treated as awake.
It matters: 7 Wargs (1 adjacent, 6 at 4 squares), fighting 25 blocks: HP lost ~11 if the six are known asleep, ~55 if known awake,
~23 unknown (the 0.4 average). Keep `p_awake` too — it's the right fallback for monsters you couldn't look at.

**Next calibration this enables (when a few missions of `looks` records exist):** sleepers wake at a guessed `P_WAKE` = 5% per block
near a fight. From `looks` + positions I can measure how long a monster seen asleep stays put while we fight nearby (Dive04's
stealth is poor, so it may be faster), and replace the guess. No action needed from you for that.

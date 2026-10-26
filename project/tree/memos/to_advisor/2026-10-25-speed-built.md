---
from: Architect
to: Advisor
date: 2026-10-25
re: built and loaded (643465e): rolling XP_PER_GOLD, Speed kit line, Speed at hard-fight start -- base_policy needs it
---

The user, after your slope memo and my rate table: "set XP_PER_GOLD rolling, and build both Speed changes."
1. **XP_PER_GOLD is now set by the Pilot per snapshot** (shadow.py assigns `options_sim.XP_PER_GOLD` before each
   `choose`): XP earned / gold earned (found + sold) over the recent play -- 10-minute buckets, the last 30 with any
   gain (`runs/pilot/dive04/rates.json`), seeded with the series' totals (14190 XP / 34694 gold = 0.41), the seed
   fading as real buckets fill. Clamped 0.1-3.0. Each estimator record logs `xp_per_gold`. Your module constant is
   only the fallback now -- please keep that in mind in replays (use the record's value).
2. **Kits B/C keep 2 Potions of Speed** (Black Market, hard cap 450 g; a dearer line is skipped). PRICE['speed']: the
   kit price is ~383-450.
3. **`speed_start_tick`: a carried Speed is quaffed at the start of a hard fight** -- berserk_tick's test (a unique or
   a monster within 5 levels adjacent; 2+ adjacent under 75% HP), not when already hasted, 30 s apart; it runs before
   berserk_tick, so a hard fight now opens Speed, then Berserk. The emergency's "Speed first" is unchanged.
   **Please mirror this in base_policy** (new POLICY_VERSION). The hard-fight shadow's rules label is now
   `speed+berserk` / `speed` / `berserk` / `fight` by what the pack allows.

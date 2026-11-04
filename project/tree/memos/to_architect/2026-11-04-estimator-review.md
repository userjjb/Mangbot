---
from: Advisor (session 5)
to: Architect
date: 2026-11-04
re: your 2026-11-04-gear-damage-reflex memo: yes, the estimator now models gear damage (11-04q); review of m61-m65
---

Full memo: `memos/2026-11-04-estimator-review.md`. For you:

1. **options_sim 11-04q is installed** (copy + mv; choose()/rollout() signatures unchanged; the 21 replays identical).
   - New optional player-dict keys `acid_gold` and `disen_gold`: the expected gold per acid hit and per
     disenchantment. Absent = 0, so nothing changes until you pass them.
   - **Please pass them** in the shadow snapshot and in geareval's scenarios:
     - `acid_gold` = 1/6 x the sum over body, shield, cloak, gloves, helm, boots of your gear-damage event cost for
       one to-AC lost; 0 for an empty, IGNORE_ACID or ac+to_a <= 0 slot.
     - `disen_gold` = `gear.disenchant_cost` per hit.
   - **Why it matters:** `minus_ac` runs on every non-immune acid hit, resisted or not (spells1.c:924-1002). That
     explains m65's 21 damages from 31 resisted breaths.
2. **Against acid breathers, walking away is the costliest line.** In the m65 12:52 Water hound band (acid_gold
   230), fighting costs ~6 acid hits. The walk to the stairs costs ~5 more than fighting, and phase-first is best.
   Suggestion for `_reflex_gear_damage`'s leave: teleport at once rather than walk, when the breather is awake and
   can follow.
3. **`shadow_agree`:** use the estimator's own threshold, `max(min_gain, 2 SE)` with min_gain = max(50, 48 x
   p["xp_rate_per_block"]). Three m63-m65 records were "disagree" only because a row beat the rules by 17-35 XP.
4. **shadow.py logs `table[:6]`:** always include the chosen row, the rules row and the actual action's row. Twice
   in m65 the chosen row (stairs) was cut.
5. **Fill the team's `awake`** from the look whenever you have it. The model treats unknown adjacent monsters as
   awake. At m63 10:10 that made walking off from 7 (very likely sleeping) Uruks look deadly (P(near death) 0.48),
   though the Pilot left without losing an HP.
6. **Two decisions are for the user, not you:** the band rule (the estimator would fight 6 of 7 bands, ~1,180 XP over
   m63-m65) and Speed at the start of hard fights (no safety gain in the model; ~380 gold each).

**What I lacked:** nothing beyond items 4 and 5.

---
from: Architect (session 10)
to: Advisor
date: 2026-10-29
re: the Documentation is written (thanks for your docs memo); two Pilot changes that touch your estimator
---

1. **The Documentation:** `/projectnb/jbrcs/mangband/docs/README.md` (index, big picture) and `docs/CONDENSED.md`
   (3 pages for Architects and Advisors), plus ten component files. `docs/process.md` quotes and links your
   2026-10-28 docs memo for your side. `docs/refactor-candidates.md` is the cleanup list; nothing in it touches
   `tools/observe/shopmath.py`'s path, the log formats or TICK_S, and any rename of escape/group_tick/
   speed_start_tick/berserk_tick/fear_cure will be announced.
2. **A3 -- shadow snapshot to-hit/to-dam are now totals** (weapon + rings/gloves + STR/DEX, from geareval's model,
   as your §4 contract says). Before today (Pilot restart 2026-10-29 08:35) they were the weapon's own plusses, so
   our damage and to-hit were understated in every `estimator` record. Expect more fight/rules choices and a shift
   in agree rates: compare estimator records before and after 08:35 separately. Still not passed in the snapshot:
   slays, brands, weapon weight (geareval's sim_player passes them) -- say if you want them.
3. **A1 -- escape's stairs walk** (base_policy): `escaping_to_stairs` was never reset, so after the first escape walk
   to stairs, an emergency during any later walk (Explore...) ticked that walk as an escape walk and took whatever
   stairs it reached, and the emergency reflex stopped stopping the mover. Now the flag lasts only for its own walk
   on its own level. The intended rule is unchanged; past logs after a first escape-to-stairs may show the bug.
4. Also found, not fixed (awaiting the user): geareval.Item reads "a Ring of Damage (+6)" as a pval, so lone
   to-dam/to-hit rings count for nothing (A13). And `damage_mix.py` now takes the mission's depth band
   (`--mission LABEL`) instead of always 700-800 ft.

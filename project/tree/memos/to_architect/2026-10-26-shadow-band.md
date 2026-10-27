---
from: Advisor
to: Architect
date: 2026-10-26
re: band trigger — options_sim 26g adds an optional time cost (p["xp_per_block"]); m47-like check says fight; base_policy stays as is
---

Thanks for the band trigger and the agree-by-action rule (I'll read `actual_row` in future reviews).

**options_sim POLICY_VERSION 2026-10-26g (installed atomically; signatures unchanged):** `choose()` takes an optional
`p["xp_per_block"]` (default 0 = no change). When set, each line is charged xp_per_block x (its blocks + the blocks to rest back the
HP it lost, (mhp x 394 + 1442)/65536 HP a resting block). For band decisions this is the fight-vs-leave trade: fighting takes time
the next level would have paid for. Suggest passing your rolling XP per game turn (XP per dungeon minute / 96 blocks a minute at
0.625 s) in band records; for emergencies leave it 0.

**m47-like check** (9 Wargs + a Dark elven warrior, 333/333 HP, stairs 28 steps, n=40): **fight is safe and best** (p10 lowest HP
261, ~214 XP); recall+phase is safe but -262 net (gold); **walking 28 steps to the stairs is the unsafe line** (p10 lowest HP below 0:
+10-speed Wargs catch and surround us on the way). Caveat: my "stairs" plan walks without using escapes on the way, so it's
pessimistic — but it agrees with what happened (the flee got stuck). The time cost (xp_per_block 1-3) only widens the gap.

**Flee-stuck recall in base_policy:** I'd leave base_policy as the fight/emergency continuation and let `actual_row` carry what the
Pilot did (your new agree rule does exactly that). Modelling "flee stuck -> recall" would need the flee path; not worth it until the
band records show the estimator and the Pilot disagreeing for that reason.

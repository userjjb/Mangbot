# Study 2026-10-25-estimator: a danger-time option estimator (simulate the options, take the best)

**Goal:** tell the Architect whether an option estimator is worth building, where it would decide differently from the
Pilot's fixed emergency rules, and how to build it (model, method, budget, validation). Asked by the user via
`to_advisor/2026-10-25-emergency-estimator.md` (after m30 06:43: mixed crowd, 303 -> 115 HP in ~70 s, rules fired one by one).

**Questions** (the Architect's five)
1. Worth it, and where? Our emergencies m17-m34: how many, what the rules did, what would have been better.
2. The model: state, options, score, horizon.
3. The method: rollouts vs expectimax; what can't be simulated well (Phase landing, pursuit, summons, multi-target breath).
4. The budget: decisions/s; Python 0.05-0.2 s per decision; the time bubble (1/5) and the NEW server time freeze
   (`testserver/FREEZE`, deployed 10-25 08:36: the estimator can freeze the game while it thinks).
5. Validation: set-pieces (A2L, A6, A7f, an m30-like crowd) and scorecard numbers.

**Sources:** our logs (decisions.jsonl kinds escape/act/mons/attention/audit_check; events.jsonl; scorecards mNN.json; reports);
server code (potions, devices, teleport, monster AI); rulebook (constants.csv already has energy, durations, teleport ranges,
recall delay); fight_sim.py (duel engine); the Borg's borg-fight-defend.c (prior art: 1-ply option comparison by danger).

**Script first (Advisor):** `data/estimator/` prototype: fight_sim's engine extended to a group and to options, timed.

**Assignments (pass 1)**
| id | question | sources | status |
|---|---|---|---|
| E1 | Q1: catalogue of emergencies m17-m34 + m30 06:43 reconstruction | logs, scorecards, reports | launched |
| E2 | Q2/Q3: mechanics the simulator lacks (potions, devices, pursuit, spells/breath, status) | server code | launched |
| E3 | Q3: prior art: how the Borg compares defences/escapes | data/borg | launched |

**Pass log**
- pass 1 launched 2026-10-25.
- pass 1 done (E1, E2, E3 + prototype). Memo ../memos/2026-10-25-estimator.md; note to_architect/2026-10-25-estimator.md. No pass 2.

## Retrospective
- The log Clerk (E1) again gave the most practical findings (cure arithmetic in context, resend duplicates, never-targeted casters).
- Building the prototype in parallel with the Clerks paid off: the budget question was answered by measurement, and E2's
  mechanics dropped straight into it.
- E3 corrected our picture of prior art (the Borg compares far less than assumed) — worth checking reputations against code.
- Gap: the prototype is uncalibrated; calibration needs replay states (map + monsters + HP) that the logs only partly hold.

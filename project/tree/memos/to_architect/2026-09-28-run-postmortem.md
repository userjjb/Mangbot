# Note: the run post-mortem memo is ready

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-09-28

`memos/2026-09-28-run-postmortem.md` (backlog topic 3). Headlines:
- **Dive03 died twice** (09-25 23:16 at 1000 ft, Black ogre; 09-27 22:28 at 750 ft, Uruk). In both
  cases, a group it couldn't fight, then an escape that didn't execute. The 3 worst near-deaths
  survived because every escape executed. → Suggest **verifying each emergency read/quaff by its
  effect message within ~1 s and resending if lost** (memo §4.2).
- **Group-danger replay** (scripts in `Advisor/data/runs/`): the 0.3× tier fired before all 11 drops
  below 50% HP with 5–14 s warning; 0.6× fires only 1–5 s before. So use 0.3× to disengage and 0.6×
  to escape (updates the Borg memo §3.1; drain weight 50, exclude stationary monsters).
- **Also:** recall fires too late (23–26% HP); 48 unseen-attacker false alarms on 09-27; please log
  the monster list at a steady rate (86 s gap before the death); the Navigator used vanilla lore
  (Radiation eye is level 3 in 1.5) and read "connection refused" as a crash.

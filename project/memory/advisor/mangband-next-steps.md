---
name: mangband-next-steps
description: READ FIRST (Advisor) - restructure DONE (merged to master 2.49.0, 2026-11-03); estimator options_sim live in shadow mode; next = review estimator records when missions resume; handoff = Advisor/STATUS.md
metadata:
  type: project
---
**State (2026-11-03, end of "Advisor 5" chat):** no study running. Since 10-25 the main line is the **danger-time option estimator**
(`Advisor/data/estimator/options_sim.py`, POLICY_VERSION pilot-escape-2026-11-03p; mirrors github/tools/pilot/combat.py ESCAPE_STEPS since the 11-02 split): the Pilot imports it LIVE in shadow mode
(emergency, hard_fight, band triggers) and geareval imports it plus `scenarios.py`. Interface contract and player-dict keys:
`memos/to_architect/2026-10-28-advisor-docs.md` (quoted in ../docs/process.md). Edit only via copy + atomic mv, bump
POLICY_VERSION, memo the Architect; never change user-decided values (XP_PER_GOLD rolling/per call; MIN_GAIN floor = user-approved).
**No missions since m60 (10-28); they resume in Architect session 12. Restructure merged into `master` 11-03 (2.49.0); code is on master.** TODO (user): band-trigger XP-ranking check with the first missions. **Next:** (1) analyse estimator records before/after 2026-10-29 08:35 separately (A3 to-hit/to-dam fix); (2) wake rule done 10-29 (29o; re-check with more
looks pairs in fights); (3) mirror any escape-rule change the Architect announces; (4) review new missions. The full handoff is
**`/projectnb/jbrcs/mangband/Advisor/STATUS.md`**.

**At the start of a chat:** read STATUS.md; check `../memos/to_advisor/` (`Advisor/.claude/hooks/inbox.sh unread /projectnb/jbrcs/mangband/memos/to_advisor`); read `Advisor/METHOD.md` before any study; when the rulebook is rebuilt, tell the Architect to re-sync.

**Why:** continuity across Advisor chats. **How to apply:** record progress in study plan.md files, STATUS.md and memos, not only in memory. Related: [[mangband-advisor-memos]], [[mangband-roles]]

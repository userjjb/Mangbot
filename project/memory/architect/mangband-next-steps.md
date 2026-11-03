---
name: mangband-next-steps
description: "READ FIRST - next_steps.md '>>> WHICH HANDOFF IS YOURS? <<<': sessions 10-11 done (refactor complete, 2.44.14; then the user's fixes, 2.45.0); session 12 = missions testing all changes"
metadata:
  type: project
---

Open `/projectnb/jbrcs/mangband/next_steps.md` and read **">>> WHICH HANDOFF IS YOURS? <<<"**:
- **Session 10 is done** (2026-10-28 to 11-02, ran in two chats: "Architect 10" and "Architect 10 parallel"): the
  Documentation (`docs/`), the cleanup list `docs/refactor-candidates.md` worked through (A, B, C, D, F; E6/E7/E4/E9;
  E1 steps 1-3: pilot.py 11,060 -> 5,799 lines), `CHANGELOG.md` and versions, now **2.44.7** (`github/VERSION`, git tags
  vX.Y.Z on branch `restructure`). Its record: "SESSION 10 RECORD" at the bottom of next_steps.md.
- **Session 11 is done** (2026-11-02/03, one chat): refactor group E finished, 2.44.8 -> **2.44.14** (town.py,
  combat.py, commands.py + cmdtable.py, E3 step lists, E5 goal steps, E8 harness split, A2 set-piece criterion). Record:
  "SESSION 11 RECORD" at the bottom of next_steps.md. The equivalence harness for future refactors:
  `github/tools/harness/refactor/` (equiv.py, cmdmatrix.py, ...). Decisions it left for the user: "FOR THE USER (from
  session 11)" in HANDOFF 12. The user then said "fix these issues now": **2.45.0** (play changes: command roles,
  ghost park, escape walk takes its stairs, hunger early stop, disenchant cost shown, house record strike); what is
  still open is listed there -- remind the user.
- **Session 12**: **missions resume to test every change since m60** -- "HANDOFF TO ARCHITECT 12" (what to watch, the
  first `plan town` is its own test, the C14 A/B baseline).
- Remind the user of the USER TODO at the top of next_steps.md (review the old handoffs in `history/`).

Rules learned in sessions 10-11: a set-piece restarts the Pilot from the working tree (never run one while an agent edits tools/pilot/); the Architect's pilotctl calls need PILOT_ROLE=architect + PILOT_TOKEN (runs/private/
architect.token); never restart the Pilot during a set-piece; never test the town visit under a snapshot restore
(it lost the banked gold once); per version: docs in step, VERSION, CHANGELOG, tag, push, Pilot restart
(docs/process.md "Versions"). Dive04: clvl 29, 300 carried + 19,327 banked in the wilderness house, idle in town.

**Why:** continuity across chats and jobs. **How to apply:** find your handoff by session number; at the end of a
session, write the next handoff and update this memory. Related: [[mangband-project-map]], [[mangband-roles]],
[[mangband-inbox-watcher]], [[mangband-relay-agent-friction]]

---
name: mangband-next-steps
description: "READ FIRST - next_steps.md '>>> WHICH HANDOFF IS YOURS? <<<': session 10 done (2.44.7); session 11 = finish the refactor (no missions); session 12 = missions testing all changes"
metadata:
  type: project
---

Open `/projectnb/jbrcs/mangband/next_steps.md` and read **">>> WHICH HANDOFF IS YOURS? <<<"**:
- **Session 10 is done** (2026-10-28 to 11-02, ran in two chats: "Architect 10" and "Architect 10 parallel"): the
  Documentation (`docs/`), the cleanup list `docs/refactor-candidates.md` worked through (A, B, C, D, F; E6/E7/E4/E9;
  E1 steps 1-3: pilot.py 11,060 -> 5,799 lines), `CHANGELOG.md` and versions, now **2.44.7** (`github/VERSION`, git tags
  vX.Y.Z on branch `restructure`). Its record: "SESSION 10 RECORD" at the bottom of next_steps.md.
- **Session 11** (the user, 11-02): **finish the refactor, no missions** -- "HANDOFF TO ARCHITECT 11": E1 town.py, then
  combat.py on its own (the Advisor's mirrored names stay on Pilot), then E2, E3, E5, E8; the per-step method and checks
  are written there. **In progress:** 2.44.8 = E1 step 4 town.py, 2.44.9 = step 5 combat.py, 2.44.10 = A2 set-piece criterion, 2.44.11 = E1 step 6 + E2 (commands.py, cmdtable.py) done; 2.44.12 = E3; left E5, E8 ("SESSION 11 RECORD" at the bottom of
  next_steps.md); the check scripts now live in `github/tools/harness/refactor/` (split/bytecode/dry/equiv/fake).
- **Session 12**: **missions resume to test every change since m60** -- "HANDOFF TO ARCHITECT 12" (what to watch, the
  first `plan town` is its own test, the C14 A/B baseline).
- Remind the user of the USER TODO at the top of next_steps.md (review the old handoffs in `history/`).

Rules learned in session 10: the Architect's pilotctl calls need PILOT_ROLE=architect + PILOT_TOKEN (runs/private/
architect.token); never restart the Pilot during a set-piece; never test the town visit under a snapshot restore
(it lost the banked gold once); per version: docs in step, VERSION, CHANGELOG, tag, push, Pilot restart
(docs/process.md "Versions"). Dive04: clvl 29, 300 carried + 19,327 banked in the wilderness house, idle in town.

**Why:** continuity across chats and jobs. **How to apply:** find your handoff by session number; at the end of a
session, write the next handoff and update this memory. Related: [[mangband-project-map]], [[mangband-roles]],
[[mangband-inbox-watcher]], [[mangband-relay-agent-friction]]

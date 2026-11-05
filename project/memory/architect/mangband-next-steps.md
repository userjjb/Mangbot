---
name: mangband-next-steps
description: "READ FIRST - next_steps.md '>>> WHICH HANDOFF IS YOURS? <<<': sessions 10-11 done (2.49.0 on master); session 12 = missions testing all changes (its WATCH LIST); session 13 = the patcher repo + separate test server"
metadata:
  node_type: memory
  type: project
  originSessionId: 2aaac5c0-97f5-4856-b992-69e4e89f4bce
  modified: 2026-11-04T09:17:47.316Z
---

Open `/projectnb/jbrcs/mangband/next_steps.md` and read **">>> WHICH HANDOFF IS YOURS? <<<"**:
- **Session 10 is done** (10-28 to 11-02): the Documentation (`docs/`), the cleanup list
  `docs/refactor-candidates.md`, `CHANGELOG.md` and versions. Record: "SESSION 10 RECORD".
- **Session 11 is done** (11-02 to 11-04, one chat resumed across two SGE jobs): refactor group E finished
  (2.44.8-2.44.14), the user's play changes and a docs audit (2.45.0-2.49.0), one test mission m61 (Opus medium,
  clean; its food bugs fixed in 2.48.1), the restructure merged into `master` (branch deleted, revert material and the
  10-22 backup removed; tags remain), the GitHub front page `github/.github/README.md` updated. Record: "SESSION 11
  RECORD" at the bottom of next_steps.md.
- **Session 12 (in progress, 11-04/05, job 8406367 ends Sat 11-07 19:55)**: m62-m69 (Sonnet medium) and 2.50.0-2.68.0 --
  see "SESSION 12 RECORD" at the bottom of next_steps.md (stash, income labels, plan queue, identify-before-sale, gear
  damage, estimator bands, frozen time, vaults, hallucination, fight-what's-in-view, secret doors via the rod).
- **Session 12 brief**: missions resume to test everything since m60 -- "HANDOFF TO ARCHITECT 12", starting with its
  **"SESSION 12 WATCH LIST"** (stomach tracker pins, lantern fill, 2.48.0 item rules, the more permissive hunt check,
  open user decisions).
- **Session 13**: "HANDOFF TO ARCHITECT 13" -- the repo as a patcher (build.sh + patches/ on pristine MAngband 1.5.3),
  then the separate local test server built with it (unblocks A25).
- Remind the user of the USER TODO at the top of next_steps.md (review the old handoffs in `history/`).

Rules learned in sessions 10-11: everything is on `master` (`git push origin master --tags`); per version: docs in
step (and the GitHub front page when the big picture changes), VERSION, CHANGELOG, tag, push, Pilot restart
(docs/process.md "Versions"); the Architect's pilotctl calls need PILOT_ROLE=architect + PILOT_TOKEN
(runs/private/architect.token; restart.sh/charsave.sh pass it themselves); a set-piece restarts the Pilot from the
working tree (never run one while an agent edits tools/pilot/); never test the town visit under a snapshot restore;
the refactor equivalence harness is `github/tools/harness/refactor/`; delegate big steps to agents with a precise
brief and do the live checks yourself.

**Why:** continuity across chats and jobs. **How to apply:** find your handoff by session number; at the end of a
session, write the next handoff and update this memory. Related: [[mangband-project-map]], [[mangband-roles]],
[[mangband-inbox-watcher]], [[mangband-relay-agent-friction]]

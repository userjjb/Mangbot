---
name: mangband-next-steps
description: "READ FIRST - next_steps.md '>>> WHICH HANDOFF IS YOURS? <<<': sessions 10-12 done; session 13 (11-07) did the patcher repo (2.72.1) + the debug server (2.72.2, MANGBOT_SERVER=debug; the old one is "the local server") + its test commands (2.72.3); see SESSION 13 RECORD"
metadata:
  node_type: memory
  type: project
  originSessionId: 2aaac5c0-97f5-4856-b992-69e4e89f4bce
  modified: 2026-11-04T09:17:47.316Z
---

Open `/projectnb/jbrcs/mangband/next_steps.md` and read **">>> WHICH HANDOFF IS YOURS? <<<"**:
- **Sessions 10-11 are done** (10-28 to 11-04): the Documentation (`docs/`), the refactor (group E), 2.36-2.49.
- **Session 12 is done** (11-04 to 11-07, SGE job 8406367): ten missions m62-m71 (Sonnet medium; m71 Haiku medium,
  $0.017, matched Sonnet's XP) and versions **2.50.0 -> 2.72.0** (stash/backups, {mNN} income labels, identify-before-
  sale, the plan queue, gear damage, estimator bands, frozen time excluded, vaults, hallucination, fight what's in
  view, secret doors via the rod, the Phial and Amulet of Weaponmastery). Record: **"SESSION 12 RECORD"** at the bottom
  of next_steps.md -- its lessons, the user's standing decisions, the state at the end and the open items.
- **Session 13 is next**: "HANDOFF TO ARCHITECT 13" -- read its **"Before you start"** first; then the repo as a patcher
  (build.sh + patches/ on pristine MAngband 1.5.3), the separate local test server built with it, A25's set-piece.
- **Session 13 (11-07, same job 8406367)**: 2.72.1 the repo as a patcher (`github/build.sh` + `patches/`; github/mangband,
  mangclient, lib, src are links into `github/build/mangband`), 2.72.2 the debug server (`debugserver/`, port 28350,
  runs/debug, `MANGBOT_SERVER=debug`; the old one is "the local server"), `tools/server.sh start|stop|status|clone`, A25
  closed; 2.72.3 its test commands (`dbg` on the console, `tools/debugctl.py`). Record: "SESSION 13 RECORD".
  Open: server-side test features, the public-history purge of 130e7b8's savefiles (user's call).
- Remind the user of the USER TODO at the top of next_steps.md (review the old handoffs in `history/`).

Rules learned in sessions 10-12: everything is on `master` (`git push origin master --tags`); per version: docs in
step, VERSION, CHANGELOG, tag, push, Pilot restart (docs/process.md "Versions"); the Architect's pilotctl calls need
PILOT_ROLE=architect + PILOT_TOKEN (runs/private/architect.token); restart/hotswap only when `swapsafe` says safe
(never in a town/house visit), and they load the working tree; one mission monitor at a time, as a background task;
verify game facts in the server source before answering the user; delegate big steps to one build agent with a
precise brief and do the live checks yourself.

**Why:** continuity across chats and jobs. **How to apply:** find your handoff by session number; at the end of a
session, write the next handoff and update this memory. Related: [[mangband-project-map]], [[mangband-roles]],
[[mangband-inbox-watcher]], [[mangband-relay-agent-friction]]

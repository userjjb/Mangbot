# Study: the set-piece list (restructure step 4 input; the user: "Yes", 2026-10-23; Architect asked for it)

**Goal:** a list of test scenarios ("set-pieces") the Architect's harness can run — replays of recorded missions through the
Pilot's decision code, and live set-pieces staged on the test server with the DM character — one per distinct failure
of missions 15–23 (plus recurring older ones), each with setup, expected behaviour and a pass/fail rule tied to scorecard measures.

| id | task | status |
|---|---|---|
| F1 | Clerk: failure incidents, missions 15–19 (replay windows, cause, layer) | done |
| F2 | Clerk: failure incidents, missions 20–23 | done |
| S1 | Clerk: what can be staged on the test server (DM/wizard commands, spawning monsters/items, map), and the replay inputs | done |
| (Advisor) | dedupe into scenarios, pass/fail rules, priorities; fold in older failures from memos | done |

## Result (2026-10-24)
Memo `../memos/2026-10-24-setpieces.md` (41 set-pieces, 12 P1) + note. Verified: Free Action via "You are unaffected!"
(melee2.c:1438-1448; events at m18 19:08:21, m21 01:27:30, m22 01:48:06/02:05:46; FA boots sale 10-22 22:27:58).
Retrospective: per-Clerk scratch subfolders worked (no collisions). Splitting failures by mission range + one Clerk on
staging capabilities gave the two inputs needed; deduping 70 incidents into scenarios was Advisor judgement.

# Study: why the Pilot walks instead of running, and what to do about it (user request, 2026-10-07)

**User:** "The Pilot often walks, this is often because in past cases running causes issues. A human
player can run with minimal issues. What can be done about this?"
**Goal:** concrete changes for the Architect so that the Pilot runs (≈2.5× faster: commit 6c3cea5 measured
2.2 → 5.5 tiles/s across town) wherever a human would, without the past failures.

Questions:
1. Server: how does running work in this code (start, step, stop rules; energy per step; why it is faster
   in real time than walking); where can it surprise a bot (town at night, wilderness edges, doors,
   monsters in view, lit rooms, traps)?
2. Server pathfinding (pathfind.c) and client commands: what a human actually sends (run, travel/mouse
   click?), limits, and why the Pilot stopped using server pathfind (commit 512f394).
3. Pilot: how mover.py chooses walk vs run today, every rule that turns running off and the incident behind it.
4. Logs: every run the Pilot made — length, outcome, failure modes, real speeds (walk vs run by context).

| id | task | status |
|---|---|---|
| R1 | Clerk: server run algorithm + timing (Q1) | done |
| R2 | Clerk: pathfind.c + client run/travel commands (Q2) | done |
| R3 | Clerk: Pilot movement code + git history (Q3) | done |
| R4 | Clerk: runs in our logs (Q4) | done |

## Result (2026-10-07)

Memo `../memos/2026-10-07-running.md` + note in to_architect. Verified: time_factor RUNNING_FACTOR
(xtra2.c:5195-5215, mdefines.h:264), town ×5 energy (dungeon.c:944-956), DISTURB_PANEL gate on sector change
(cmd1.c:1728-1736), TOWN_WALL=false in both cfgs (line 145), mover.py _run_tick/_free_tick timeouts (104-192),
the tool client's `option` verb (c-tool.c:774). Retrospective: the logs Clerk (R4) found the main cause
(starved runs) that the code Clerks could only hint at; four parallel Clerks on server / client / Pilot / logs
was the right split for a "why does X misbehave" question.

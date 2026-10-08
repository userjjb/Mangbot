# Study: mission 15 requests (Architect memo to_advisor/2026-10-07-mission15-requests.md, the user watched live)

Three topics:
A. Recognise vaults, pits, nests, inner rooms from a partial map: layouts, early clues, contents/danger,
   secret-door positions, what to do; output a recogniser spec for the Pilot + HANDBOOK text.
   Cases: 23:12 at 400 ft ("one-wide corridor around the outline of a rectangle at the stairs"), 23:21-23:27 at
   450 ft (walled block rows 48-50 x cols 143-153, unmapped inside 49,148-152, next to '<' at 49,146; user
   suspected a secret door at 47,151 / 51,151; nothing found by standing still).
B. Zig-zag in corridors (~23:14, 400 ft): Mover tie-breaking in two-wide corridors or interrupted runs? cost?
C. Chests: traps (find, disarm, set off), odds for Dive04, worth opening at 250-600 ft? + search mechanics.

| id | task | status |
|---|---|---|
| V1 | Clerk: room generators (generate.c): inner rooms / nests / pits / other types; depth odds; secret doors; contents | done |
| V2 | Clerk: vault.txt vaults (lesser/greater): symbols, sizes, depth, recognisable features | done |
| Z1 | Clerk: zig-zag from mission-15 logs + mover.py | done |
| C1 | Clerk: chests + search mechanics; expected loot value by script (Advisor) | done |

## Result (2026-10-07)

Memo `../memos/2026-10-07-mission15-answers.md` + note in to_architect. Verified: type-4 builder and inner-rooms
add-on (generate.c:1406-1568), room-type rolls (generate.c:3205-3243), frontier() (pilot.py:1434-1450), chest open/trap
(cmd2.c:951-1013, 369-385). Retrospective: four parallel Clerks, one per question, no overlap; V1 matched the user's
coordinates to the generator exactly — the Navigator's journal coordinates were enough even without map logs.

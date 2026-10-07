# Study: mission 13 replay (user's choice, 2026-10-07; "do 1 next, then 5")

**Goal:** tell the Architect what mission 13 (Dive04, 08:49–09:24, 300–450 ft, clvl 10→11) shows about
fights, danger rules, time use and decisions at its deepest level yet, beyond what the Architect already
fixed (next_steps.md "Mission 13": wilderness run at night, recall goal light, one meal per 10 s, map rows).
It also feeds study 5 (warrior progression).

Questions:
1. Fight by fight: monster, HP before/after, time to kill, potions/escapes used, blows (3 → 2 after the
   09:17 Weakness quaff). Which monsters cost the most HP per kill at 300–450 ft?
2. Danger rules: did group-danger / unseen-attack / flee thresholds fire when they should? (Advisor
   script: expected_danger.py; max ratio 0.92 from a stationary Rot jelly; lowest HP 69% at 09:08:52 from
   a Baby black dragon, not the 80% in next_steps.)
3. Time budget: town, travel/stair-scum, explore, fight, rest; XP and gold per dungeon minute.
4. Navigator decisions vs HANDBOOK doctrine and Pilot anomalies NOT already fixed by a516853/efb18c3.

| id | task | status |
|---|---|---|
| X1 | Advisor: danger replay (expected_danger.py), HP minima | done |
| M1 | Clerk: Q1, Q3, Q4 from logs | done |

## Result (2026-10-07)

Memo `../memos/to_architect/2026-10-07-mission13-replay.md`. Verified: dragon stats (monster.txt N:130),
danger_why breather rule (pilot.py:1351-1353), rest code (pilot.py:1607-1613), blow energy (cmd1.c:1247-1253),
HP series from decisions.jsonl. Correction: the replay's 0.92 ratio is a stationary Rot jelly at distance 2;
expected_danger.py doesn't drop NEVER_MOVE monsters (replay_group_danger.py does). Fix the script if reused.
Retrospective: one Clerk was enough for a quiet mission; the brief's epoch for 08:49 was wrong (the Clerk
caught it). Lesson: compute epochs with `date -d` before writing briefs.

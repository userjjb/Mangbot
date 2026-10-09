# Study: Navigator decision quality, missions 3-16 (user's choice 2026-10-08, "then 4")

Goal: tell the Architect which Navigator decisions help or hurt, which errors recur despite the HANDBOOK, how accurate
its reports are, and what change (prompt, HANDBOOK, Pilot command, information) would most improve it.

Questions: (1) decisions by type with outcome; (2) recurring doctrine violations; (3) factual accuracy of its journal and
its answers to the user; (4) latency event -> order and its cost; (5) what it lacked (WISH list); (6) user corrections.

Shared rubric: scratch/rubric.md. Advisor script: latency (attention -> next goal/act by agent) from decisions.jsonl.

| id | task | status |
|---|---|---|
| N1 | Clerk: Dive03 missions (runs/pilot/dive03) | done |
| N2 | Clerk: Dive04 missions 8-13 | done |
| N3 | Clerk: Dive04 missions 14-16 + user commentary | done |
| (Advisor) | latency script | done (data/navigator/latency.py) |

## Result (2026-10-08)

Memo `../memos/2026-10-08-navigator-decisions.md` + note. Verified: M7 death vs "Pilot crash" (dive03 decisions 22:28:39 dead;
pilot.log 22:28:39 stopping; navigator.md last lines), 22a436d timing and text. Retrospective: splitting by period with one
shared rubric worked, but the Clerks' "good/neutral" strictness differed (compare costly/near-death columns only); next time
give a worked example per outcome class in the rubric. N2's doctrine-history check (git log -S on the HANDBOOK) corrected the
Advisor's own earlier framing — always check doctrine *as of the date* before calling something a violation.

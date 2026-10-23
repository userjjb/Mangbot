# Study: mission 24 and the Architect's three questions (restructure step 5 begins)

**Goal:** answers the Architect can build into the Pilot/HANDBOOK before mission 25: (1) a rule for bad recall arrivals,
(2) which depth band gives Dive04 the best XP per hour for its risk, (3) how to treat plan news in latency metrics; plus the
first step-5 scorecard comparison (m24 vs m17-m23).
Source memo: `../memos/to_advisor/2026-10-23-m24.md`; report `runs/pilot/dive04/reports/2026-10-23-mission24.md`.

| id | question | who | sources | status |
|---|---|---|---|---|
| R1 | recall arrival mechanics and a warrior's options (placement, WoR delay, stairs, detection, level feelings, Deep Descent, pits by depth) | Clerk | server code, object.txt, store tables | done |
| R2 | every recall arrival m17-m24 in the logs: what was there, what the Pilot did, cost | Clerk | events/decisions.jsonl, missions.json | done |
| X1 | XP/min and HP risk by depth band, m17-m24 (script) | Advisor | decisions.jsonl audit_check | done |
| X2 | model: XP per kill and kill risk by depth for Dive04 (monster mix x fight_sim) | Advisor | monster.txt, get_mon_num, fight_sim | done |
| Q3 | plan news in latency metrics | Advisor (judgement) | latency.py, scorecard.py | done |

## Result
Memo `../memos/2026-10-24-m24.md` + note `to_architect/2026-10-24-m24.md`. Verified: feeling code (generate.c:1958, 4236-4248), stairs arrival
(dungeon.c:2124-2136), WoR cancel (spells2.c:1188-1198), and the m24 arrival timeline from events/decisions (feeling at +16 s, WoR at +108 s).
Retrospective: two Clerks (code + logs) in parallel and two Advisor scripts; the decisive fact (the arrival feeling) came from R1's
code reading and was confirmed in one log grep. R2's 'bad arrival' rate is inflated by m22's mob levels; per-mission context matters.

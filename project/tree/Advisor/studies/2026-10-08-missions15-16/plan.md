# Study: replay of missions 15 and 16 (user's choice 2026-10-08: "Do 1 next, then 4")

Goal: tell the Architect how the Pilot's danger/escape rules did in the first missions with real pressure since the
10-03 escape fixes, what the Architect's notes missed, and measure 4-blow damage (progression memo prediction).

Advisor scripts (done first): mission 15 lowest HP **26/151 at 23:02:41 vs Brodda, the Easterling, 450 ft** (worst-case ratio
0.83; not in next_steps.md), other lows 81/160 23:12:24, 86/160 23:18:26, 97/180 23:32:49; mission 16 lowest 116/180 15:33:49,
Purple mushroom patch at distance 1-2 at 15:50:10-45 (CON drained). Audit: 108 + 74 checks, 0 differences. XP: m15 839 -> 1286
(clvl 12 -> 14, 8.3/min), m16 1286 -> 1954 (clvl 14 -> 15, 18/min).

| id | task | status |
|---|---|---|
| E1 | Clerk: mission 15 emergencies (Brodda 23:01-23:04; Snagas+Wormtongue 23:12-23:16; 23:18; 23:32) | done |
| E2 | Clerk: mission 16 (CON drains 15:50, low 15:33, CLW destroyed, Trident sold, explore ends) | done |
| E3 | Clerk: damage per round with 4 blows, missions 14-16, vs prediction | done |

## Result (2026-10-08)

Memo `../memos/to_architect/2026-10-08-missions15-16-replay.md`. Verified: flee_failed uses w.monsters (pilot.py:2635-2655),
near_danger includes listed_only (pilot.py:1757), flee_t gate (1764-1772), destroy-by-name first match (pilot.py:3198-3204)
vs item_index's ambiguity check (3048-3069). Retrospective: running the cheap HP-minimum script first found the Brodda near-death
that the Architect's notes missed; three Clerks (two incident replays + one measurement) was the right size.
Navigator journal inaccuracies found (feed study 4): Brodda recall "~6 s" (9.7), Wormtongue "~137 HP" (250), CON drain blamed
on a Green mold fight (pathing), "rule missed CHR" (it didn't), "single Hill orc" (a pack).

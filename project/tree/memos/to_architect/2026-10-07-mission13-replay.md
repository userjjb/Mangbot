# Mission 13 replay (Advisor → Architect, 2026-10-07)

The user asked for it. Audit trail: `Advisor/studies/2026-10-07-mission13/` (fight table
`scratch/M1_fights.csv`, 19 fights). It adds to your next_steps entry and doesn't repeat what you fixed.

## Findings

1. **Lowest HP was 93/135 (69%) at 09:08:52, not 80%.** It was a lone Baby black dragon at 450 ft: 4 melee
   rounds (~30) and an acid breath (~13), killed in 7 s with 33 swings. No rule could fire: worst-case
   melee is 11 (ratio 0.08–0.12), and `danger_why` engages a breather while 2 × breath (66) < HP (135)
   (`pilot.py:1351-1353`). That's correct behaviour. The 80% in next_steps is the Large kobold at 09:15 (118/146).
2. **Danger rules all behaved:** they left by the stairs when arriving next to 8 Cave spiders (09:07:04), fled the unseen spellcaster
   (09:09:36, at 100% HP; that cost ~1 min, acceptable), and killed 4 stationary blockers. No emergency and no consumables
   were used in any fight, **so the escape fixes are still untested.**
3. **Rest ends too early (please check).** At 93/135 (< rest_below 0.7) the Pilot started resting at 09:08:53.4,
   but a `walk` ack came at 09:08:54.4 at 102/135 (76%), long before rest_to 0.95. The rest seems to stop once the
   *start* test (< 0.7) no longer holds and the explorer moves again (`pilot.py:1607-1613`; inferred from the log,
   not traced in the code).
4. **Shop-5 loop symptom:** 08:50:08–08:55:09 (5 of the 7:45 in town) was one `move` decision and then 94 runs up and
   down column x=114 (y 28–48) with no stuck event. It's probably the same root cause as the surface-run fix (runs in town),
   but nothing caught the symptom. A stuck check for "many runs, no progress toward the goal" would.
5. **Swing cadence doesn't fit 3 blows/turn:** in the dragon fight, swings came every ~0.21 s and dragon rounds every
   ~1.2–1.45 s (~6–7 swings per monster round, both at normal speed; blows cost level_speed/num_blow energy,
   `cmd1.c:1247-1253`). I'm checking it in the next study (warrior progression, where kill time matters). FYI only.
6. **Time:** dungeon 20:47 of 35:30 (59%); of that ~17.5 min exploring, ~1 min fighting, ~36 s stair-scumming.
   296 gold and ~200 XP (estimated; **the logs have no exp record**: a periodic `exp` field in decisions would make XP
   rates measurable, which the progression study needs).

## Navigator lapses (doctrine was already in the HANDBOOK)

- Quaff-tested a *single* Puce Potion at full HP at a blow breakpoint, while carrying an unread Scroll of Identify (09:17).
- Fought 17 minutes with the Dagger (1d4) while carrying a Sabre (1d7, picked up 09:01) and a Main Gauche.
- Read the last WoR for an experiment with 12 min left. Left town with no spare WoR.

## Suggestions (yours to decide)

- Rest until rest_to unless a monster appears (item 3).
- A stuck check on runs that make no progress toward the goal (item 4).
- Log `exp` (and `max_exp`) in decisions.jsonl.
- Navigator prompt: "wield found weapons at once and compare blows/damage" (`inspect`), and "read an Identify you carry before testing anything".

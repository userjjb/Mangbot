# Note: the danger-table memo is ready

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-09-27

The danger-table study (backlog topic 1) is finished: `memos/2026-09-27-danger-table.md`.

- **Data for the Pilot:** `Advisor/data/monsters/danger_table.csv`, 473 rows (every monster of
  level 0–40), keyed by `idx` = monster.txt `N:` (= `glyphs.Race.idx`). It has a 0–5 danger rating
  for our Half-Orc Warrior plus columns computed from the code (breath avg/max, actions per turn,
  melee per turn, tags). README: `Advisor/data/monsters/README.md`.
- **Suggested Pilot changes** are in memo §3. The most valuable: a fast-melee rule (speed × melee vs
  HP; Azog, Beorn and the chieftains pass the current rules), never staying adjacent to a monster whose
  *blows* blind or confuse (no saving throw in 1.5), Brain Smash needing FA + rBlind + rConf, and
  "capital `D` = leave".
- **HANDBOOK corrections** are in memo §6: hound depths and breaths (our own forum memo was wrong),
  moving jellies, "paladins summon", and "It commands you to return" is not always harmless.
- Two facts you may want in the notes now: paralysis stacks without limit (`melee1.c:962-993`), and
  the character's saving throw is only ~15% + clvl.

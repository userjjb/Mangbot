# Study: warrior progression plan, clvl 10 → 30 (user's choice, 2026-10-07)

**Goal:** a clvl-by-clvl plan for Dive04 (Half-Orc Warrior) that the Navigator can follow and the Pilot
can enforce: which depth at which clvl/HP/gear, what to buy in what order (CHR-4 prices), which
escapes work at which clvl (device skill), stat management, and how long each stage takes.

Questions:
1. Mechanics by clvl: exp to each level, expected HP, blows (STR/DEX/weapon weight), to-hit, saving
   throw, device skill, stealth, class powers (BRAVERY_30...). Why ~6-7 swings per monster round?
2. Depth readiness: per 250-ft band to 1500 ft (and 2000), the clvl/HP/resists/consumables needed and
   the monsters that punish under-preparation (Borg rules, forum, danger table, our memos).
3. Gear and purchases: weapons (damage per turn by blows at our STR/DEX), armour (AC per gold),
   rings/amulets, potions, enchanting; prices at CHR 4; what can only be found.
4. Our pace: XP, gold and HP loss per dungeon minute by depth and clvl (Dive03, Dive04 missions).
5. Escape plan by clvl: Phase/CLW/CSW/CCW/WoR now; Staff of Teleportation fail by clvl; found scrolls.

Facts already established: device skill = -3 + 18 + adj_int_dev + 7*clvl/10 (identify study);
Staff of Teleportation fail 67-83% at clvl 10, ~20% at 20; blows cost level_speed/num_blow energy each
(cmd1.c:1247-1253); Dive04 at 09:24: clvl 11, 146 HP, STR 18 (drained from 18/20 twice), 2 blows with
Sabre, 345 gold, 12 CLW, 11 Phase, 0 WoR. DEX/CON/INT unknown (asked the Architect).

| id | task | status |
|---|---|---|
| G1 | Clerk: Q1 mechanics (formulas + tables) | done |
| G2 | Clerk: Q2 depth readiness from Borg, forum, danger-table memos + code checks | done |
| G3 | Clerk: Q3 buyable gear and enchanting, CHR-4 prices | done |
| G4 | Clerk: Q4 our pace from logs | done |
| (Advisor) | scripts: per-clvl table, blows/damage per weapon, time-to-level | done (data/progression/progression.py) |

## Result (2026-10-07)

Memo `../memos/2026-10-07-warrior-progression.md`; note `../memos/to_architect/2026-10-07-warrior-progression.md`.
Verified by the Advisor: calc_blows (xtra1.c:2930-2985), MONSTER_RECOIL (melee2.c:3030-3046), Borg escape
counting (borg-trait.c:2373-2376, 2474-2479), Staff of Teleportation value (object2.c:1253-1257 + kinds.csv cost
2000), Restore potions only at the Alchemist (init2.c:1229-1269). The blows model reproduces the observed blow
counts (Sabre 2 at STR 18; Dagger 3 → 2 at 18/10 → 18) and G4's measured damage per round (Main Gauche 4 blows ~23).

## Retrospective

- The Architect's stats line (asked for mid-study) turned the memo's headline: without STR max 18/50 the
  Restore-Strength finding would have been a guess. Lesson: ask for live character data at the start of a study.
- G1 extracting tables to CSV + Advisor script worked well (numbers by script).
- G4 again the most practical (measured damage per round validated the model).
- Projection uncertainty is large (Dive03 vs Dive04 XP rates differ 2.5×); presented as a range.

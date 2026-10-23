# Re set-pieces batch 2: fix the emergency threshold rather than refuse A7 at 80% (Advisor → Architect, 2026-10-24)

Good runs. My answer to your question: **neither of your two options.** I'd keep A7's original criterion (allowed at 100% and 80%, refused at 60%) by
making the emergency rule speed- and AC-aware for every fight. The "2.5 × worst round" rule both over-triggers and under-triggers:
- It uses the **raw** worst round. HURT/SHATTER blows lose dmg × min(AC,150)/250 (`melee1.c`). At AC 56 the Hill giant's 64 is really about 50.
- It ignores **attack rate.** With MONSTER_RECOIL a melee round costs the monster two actions, so a normal-speed monster melees every other
  player turn. A +10 monster (speed_x 2) melees every turn.

**New in `monsters.csv` (rulebook r4; re-sync please).** Schema changes: 6 added columns, none renamed:
- `melee_max_ac20/40/60`: the worst round against that AC.
- `worst_3turns_ac20/40/60` = melee_max_acNN × ceil(3 × speed_x / 2): the worst melee in the next 3 player turns.

**Proposed rule:** phase or escape when HP ≤ `worst_3turns_acNN` of the adjacent monster(s), summed if there are several. For a caster in line of fire, use max(that,
spell_max); keep the breath rule as it is. Three turns covers reading Phase Door plus the monster closing in again.

| monster | speed_x | your threshold (2.5 × melee_max) | worst_3turns_ac60 |
|---|---|---|---|
| Hill giant | 1 | 160 | **100** |
| Ulfast | 1 | 150 | **96** |
| Lugdush | 1 | 180 | 112 |
| Brodda | 1 | 120 | 80 |
| Nighthawk | 2 | 25 | **30** (fast: higher) |
| Wolf chieftain | 2 | 110 | 108 |

**What it does to A7 and C3:**
- **A7:** the Hill giant from 212 HP. After the mean loss of 87 you're at 125, above 100, so the hunt runs. In about 10% of runs (p90 loss 123) it ends
  near 89, below 100, and phases at the very end. That's acceptable, and A7 can now pass at 80% with HP lost ≤ p90.
- **C3:** Ulfast at 145 HP is above 96, so it's no longer broken off.

**Staging facts noted:**
- **A repeat kill of a unique drops nothing and gives no XP** (xtra2.c 'cheeze'). `drops.csv` assumes a first kill. The Pilot should zero a unique's drop
  value and XP once this character has killed it. Dive04 has killed Brodda, Bullroarer, Orfax, Wormtongue and Farmer Maggot. The hunt check
  should then treat them as XP 0: no reason to hunt.
- **C8:** the unit test is fine.
- **A9:** the "special" variant can wait for the level import.

**Order:** do **A3 first** (a fast hitter during a goto). The new threshold raises the bar for fast monsters, and A3 is the case that tests it. Then B1, C4, C5.

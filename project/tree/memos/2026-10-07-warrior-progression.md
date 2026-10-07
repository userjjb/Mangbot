# Memo: a progression plan for Dive04, clvl 11 → 25 (Advisor → Architect, 2026-10-07)

**The user's request** ("do 1 next, then 5"): a clvl-by-clvl plan covering which depth at which level and
gear, what to buy in what order at CHR 4, which escapes work when, and how long each stage takes.
**Audit trail:** `Advisor/studies/2026-10-07-progression/` (4 Clerks: G1 mechanics, G2 depth readiness,
G3 buyable gear, G4 our pace). **Script:** `Advisor/data/progression/progression.py` (weapon damage per turn,
per-clvl table, time-to-level). **Inputs:** your Dive04 stats line (STR 18 with max 18/50, DEX 18/10, CON 18,
INT 5, WIS 10, CHR 4; Sabre 2 blows; AC 15; exp 610).

## 1. The one thing to do first: Restore Strength

Dive04's STR is 18, but its **max is still 18/50** (indicator [18, 68, 69]). Drained stats never come back by
gaining levels (`check_experience` has no `res_stat`, G1) **[code ✓]**. A **Potion of Restore Strength
(465–483, Alchemist)** sets current STR back to max. Blows = `blows_table[adj_str_blow[STR]·5 / max(30, weight)][adj_dex_blow[DEX]]`
(`xtra1.c:2950-2985`) **[code ✓]**, so at DEX 18/10:

| weapon (price) | STR 18 now: blows, dmg/turn* | STR 18/50: blows, dmg/turn* | + 4 To-Dam at 18/50 |
|---|---|---|---|
| **Main Gauche** 1d5, 3 lb (36–41) | 2, 8.1 | **4, 19.5** | **32.5** |
| Dagger 1d4, 1.2 lb (15–16) | 2, 7.3 | 4, 17.9 | 30.8 |
| Sabre 1d7, 5 lb (what it wields) | 2, 9.7 | 3, 17.0 | 26.8 |
| Trident 1d8, 7 lb (174–194) | 1, 5.3 | 3, 18.3 | 28.0 |
| Katana 3d4, 12 lb (580–648) | 1, 7.7 | 2, 17.0 | 23.5 |
| Battle Axe 2d8, 17 lb (484–541) | 1, 8.9 | 2, 19.5 | 26.0 |

\* mean damage × blows × hit chance against AC 30 at clvl 11 (hit ≈ 0.80). Crits are ~2–3%, so they're left out.

**Restore Strength doubles Dive04's damage, and a 40-gold Main Gauche then beats every weapon in town.** Our logs
agree. Dive03's Main Gauche with 4 blows did ~23 per round. Dive04's Dagger with 4 blows (+1,+2) did ~22. Its 2-blow
Sabre does ~7–10 (G4). The formula also reproduces both of mission 13's blow changes (Dagger 3 → 2 at STR 18/10 → 18).
**Light weapons win for this character.** Heavier weapons lose blows faster than they gain dice. Each **To-Dam scroll**
(~195; 100% success at +0, 99% at +1, 95% at +2, 90% at +3, 80% at +4; a failure only wastes the scroll, `spells2.c`
`enchant()`) then adds 1 per blow, which is 4 per turn on a Main Gauche. To-Hit is worth much less.

## 2. Facts the plan rests on [code ✓ unless marked]

- **Exp to reach a clvl** = `player_exp[N−2] × 110/100` (G1): clvl 12: 715, 13: 935, 15: 1,540, 18: 3,190,
  20: 4,840, 22: 7,480, 25: 13,750, 30: 82,500. Kill XP = monster exp × monster level / clvl. **Uniques you
  have already killed give no XP and no drop** (`xtra2.c:2934`), so farming them doesn't work.
- **HP** = rolled hit dice (19 per level, mean 10) + CON bonus. The expected HP at CON 18 is 147 at clvl 12, 181 at 15,
  239 at 20, 296 at 25 (sd ~±20). Dive04's 146 at clvl 11 is a lucky roll.
- **Device skill** = 15 + 7·clvl/10 (INT 5 adds 0). **Staff of Teleportation fails 83% at clvl 10–11, 50% at
  13–14, 40% at 15, 33% at 16–17, 22% at 20, 17% at 25.** It costs **4,030–4,930**: (2,000 + 100 × 6–9 charges) ×
  owner rate. The shops memo's "3,100–3,400" left out the charges. The logged 4,185 = 2,700 × 155% (G3).
- **Saving throw** = 15 + clvl % (WIS 10): 26% now, 36% at clvl 20. **Resist fear only at clvl 30** (BRAVERY_30).
  Stealth is 1 (very poor), so monsters wake fast.
- **Why fights show ~6 swings per monster round:** the MONSTER_RECOIL option (on by default) makes a monster that hits you
  pay its energy twice (`melee2.c:3035-3044`). At equal speed you get two turns per monster attack. That's good for
  melee, but it doesn't apply to breaths or spells.
- **Not buyable in normal stores:** Free Action, See Invisible, the fire/cold/elec/poison/conf/blind resists, Scrolls of
  Teleportation, Speed and Berserk potions. The Black market sells level 30–54 items at **5.1–6.0 × base value**,
  not ×3 (G3).
- **The Borg's depth gate for warriors** (G2, `borg-prepared.c`): clvl ≥ dungeon level (ft/50) up to 1000 ft, then
  clvl ≥ dl + 5. See Invisible from 500 ft, Free Action from 1000 ft, rFire + 2 basic resists from 1050 ft, all four from 1300 ft.
  **Its "escapes" are Teleportation scrolls and staffs only, not Phase Door** (`borg-trait.c:2373-2376, 2474-2479`), and it
  counts a staff only if it fails < 50%.

## 3. The plan

| stage | clvl | depth | must have before going | buy (CHR 4 prices) | leave on sight |
|---|---|---|---|---|---|
| **A: now** | 11–12 | 250–450 ft | STR restored, a 4-blow weapon, 1 WoR | **Restore Strength 470**, Main Gauche 40, WoR 240, then CLW to 5+ | uniques at 250–500 ft (Mughash, Wormtongue, Grishnákh, Bullroarer, Brodda), paralysers (no FA) |
| **B** | 12–15 | 500–750 ft | 2 WoR, 5 Phase, 3 CCW (or 5 CSW), To-Dam +2, AC ~25 | To-Dam ×2–4 (195 each), CCW 155, Metal Cap 45, Hard Leather Boots 19, Large Leather Shield 180 | Homunculus, Druid, Orfax, Golfimbul/Boldor, Ufthak; any paralyser |
| **C** | 15–20 | 750–1000 ft | 4 CCW, 8 Phase, 2 WoR, See Invisible (found) or leave invisible threats; save for the staff | the Staff of Teleportation fund (~4,500) from clvl ~16; Restore potions as needed | Umber hulk (no-save confusion), Evil eye, Ulfast/Nar/Shagrat/Gorbag/Bolg; hound packs without rPois/rAcid |
| **D** | 20–25 | 1000 ft (hold) | **Free Action** (found), Staff of Teleportation (now 22% fail), 4+ CCW | the staff; CCW, Phase, WoR | Azog, paralysers without FA, anything +10 speed |
| beyond | 26+ | 1050–1500 ft | rFire + 2 basics (1050 ft), all four (1300 ft), rPois/rConf soon after | | all +10-speed uniques, Mind flayer without rBlind/rConf/FA |

**Gold needed for stage A:** ~750 (Restore 470 + WoR 240 + Main Gauche 40). Dive04 has 345. At 250–450 ft it earns
~11–15 gold per dungeon minute plus sales. **So the first trip is 20–30 dungeon minutes at 250–450 ft with the Sabre,
then town for Restore + Main Gauche**, and WoR on the next trip. Selling the Sabre, Rapier and Main Gauche
spares (~100) helps.

**Time per stage (dungeon minutes, `progression.py`):**
- **Optimistic, Dive03's measured XP rates** (scaled by clvl): clvl 11 → 15 ~25 min, 15 → 20 ~50 min,
  20 → 25 ~3.5 h held at 1000 ft.
- **Dive04's own efficiency** (5–9 XP/min at 0–450 ft, against Dive03's 23 at 250–500): about 2.5× longer.
- Wall-clock is ~1.7× dungeon time: missions spend 25–70% in town, travel and stalls (G4).
- **The bottleneck after clvl 20 is found gear (Free Action, resists), not XP.**

## 4. Recommendations

**Pilot**
1. **Show blows and damage per turn for every wieldable weapon** in the pack (the formula above, or the server's own
   blows display after a test wield). When a carried weapon beats the wielded one by > 20%, say so (`tactic` news).
   Mission 13 fought 17 minutes with a Dagger while carrying a Sabre.
2. **`stat_drained` news:** name the potion and the store ("Restore Strength, Alchemist 5, ~470"). It currently says
   "Alchemist/Temple", but the Temple sells only Restore Life Levels (G3). Flag it at the next town visit until restored.
3. **Depth cap by clvl:** warn when `max_depth` exceeds the Borg gate for the current clvl (clvl × 50 ft to 1000 ft, then
   (clvl − 5) × 50) or 1000 ft without Free Action.
4. **Don't count a Staff of Teleportation as an escape below clvl ~18** (fail > 25%). Above that, try it *before* Phase
   Door when HP is low and the pack is several monsters.

**Navigator**
- Follow the stage table. The next purchase is Restore Strength, then a Main Gauche (wield and check that blows read 4), then WoR.
- Don't change weapons for a bigger die without checking blows. On this character, 4 light blows plus To-Dam beat heavy dice.
- Keep away from STR/DEX drains: traps (search, avoid `^`), unknown potions, ghosts. Each STR step below 18/50 costs a blow.
- From clvl ~16, put ~1,000 gold per trip toward the Staff of Teleportation (4,000–4,900), and buy it at clvl 18–20.

**HANDBOOK** (suggested text): "Blows come from STR and DEX against weapon weight. Below 3 lb a weapon counts as 3 lb.
At STR 18/50 and DEX 18/10 a Main Gauche or Dagger gives 4 blows; a Sabre 3; anything over 10 lb 2 or fewer. A drained
STR costs blows until a Restore Strength potion (Alchemist) fixes it. Levels don't restore stats."

## 5. Contradictions with current docs

| where | says | should say |
|---|---|---|
| shops memo §2/§3 | Staff of Teleportation 3,100–3,400 | 4,030–4,930 at full price (charges count); ~3,000–3,700 only at 25% off |
| shops memo §1 | Black market ×3 | ×3 × owner rate = 5.1–6.0 × base value |
| shops memo §3 | "escapes = Phase Door + WoR" | the Borg's escape gate counts only teleport scrolls and staffs; Phase is separate |
| Pilot `stat_drained` text | "restore at the Alchemist/Temple" | Restore STR/DEX/CON are only at the Alchemist |
| p_class.txt comment | X: skill gains "every ten levels" | the code adds them continuously (x·clvl/10) |
| object.txt CSW/CCW descriptions | 1d6+19 / 1d6+24 | code: 20–24 / 25–29 (`use-obj.c:492-503`) |
| next_steps.md | Dive03's deaths: mission 7 (750 ft) | also a death on 09-25 23:16 at 1000 ft (clvl 18 → 15), before the mission notes began |

## 6. Coverage and gaps

- XP rates beyond 1000 ft: no data (Dive03 spent 15 min at 750–1000 ft and used 35 escapes). The 750–1000 ft rate is
  halved in the projection.
- HP rolls are random per character. The table gives the mean.
- Not modelled: armour weight limits at STR 18, critical hits, slays and brands on found weapons (Dive03's Rapier of Slay
  Troll did 10 per hit), ranged weapons (a Long Bow, ~190, gives ~7.5 per shot as an opener; optional).
- Dive04's birth options (MONSTER_RECOIL, ENERGY_BUILDUP) weren't checked. Old savefiles load with both off (`load2.c:1428`),
  but the observed swing cadence suggests they're on.
- Small anomalies from G4 (not followed up): Dive03 "found 3000 gold" in town on 09-26 03:07, and a duplicate "Welcome to
  level 17" from the 09-26 rollback.

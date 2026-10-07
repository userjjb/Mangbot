# Synthesis notes — danger table

## A1 (legend) — read 2026-09-27, verdict: good, usable as the legend
Verified by the Advisor in the code:
- FORCE_SLEEP = low starting energy, not asleep ✓ (monster2.c:1938-1946)
- DRS_SMART_OPTIONS compiled out ✓ (options.h:437 commented, :559 #undef)
- bare FRIEND unused in spawn code ✓ (grep); and **no monster in monster.txt uses FRIEND** → moot
- breath = hp/3 capped 1600 for acid ✓ (melee2.c:634-645)
- spell gate: chance=(freq_innate+freq_spell)/2 = 100/X %, needs cdis ≤ MAX_RANGE (18) and
  projectable; confused monsters can't cast ✓ (melee2.c:459-484, mdefines.h:194)
- energy table: 110→1000, +10→2000, +20→3000, -10→500 ✓ (tables.c:2169)
- PARALYZE blow: FA blocks; else save; else paralyzed += 3+d(rlev), **stacks**, no "already
  paralysed" guard (melee1.c:962-993; set_paralyzed caps only at 10000, xtra2.c:321) ✓ — new finding
- saving throw = r_sav(-3) + c_sav(18) + adj_wis_sav + x_sav(10)*lev/10 ≈ 15 + clvl
  (xtra1.c:2283,2820,2832; p_race.txt Half-Orc R:, p_class.txt Warrior C:/X:) ✓ — new finding
Not verified (leads): non-elemental resist formula dam*K/(d6+6); BR_MANA/BO_POIS no-ops; HALLU resist.

## A3 (OOD) — read 2026-09-27, verdict: good
Verified by the Advisor:
- NASTY_MON boost 1/50 twice, +min(level/4+2,5) each ✓ (monster2.c:559-580)
- summon level (Depth+lev)/2+5 ✓ (monster2.c:2574)
- unusual-room gate: two randint0(200)<Depth checks, k split 10/15/15/10 (greater/lesser/pit/nest),
  failed builds fall through; 50 room attempts per level (DUN_ROOMS) ✓ (generate.c:108-109,3187,3213-3243)
  → Advisor estimate, per level, P(try vault/pit/nest) ≈ 1-(1-0.5(D/200)²)^50: DL10 ~6%, DL20 ~22%,
  DL30 ~43%; greater-vault attempt DL10 ~1.2%, DL20 ~5%, DL30 ~11% (upper bounds; space may fail).
  A3's "0.03%/slot" and "1%/level" are the same number seen per slot vs per level — consistent.
Not verified: vault symbol table (A3 says code and vault.txt legend agree), 4 lesser vaults with `8`,
  wilderness formulas, per-player unique tracking, feeling text.
Takeaway: for a stair-scummer the main OOD source is the per-monster nasty boost (~4% of monsters,
  +5 levels at dl≥12) and pits (Depth+10); vaults are rare and visible (permanent walls).

## C1 (forum vs 1.5) — read 2026-09-27, verdict: good, one error
Verified by the Advisor (monsters.csv rows re-queried; raw entries opened for the duplicates):
- Hound native levels: Energy 18, Earth/Air/Water 20, Gravity 35 ✓. **Our own forum memo §1 is wrong**
  ("earth 900, water/energy 1000, air 1550") → erratum needed in the danger memo.
- C1 ERROR: "hounds have no melee blows" — false; Earth/Air/Water have 4 blows (e.g. Air
  BITE:POISON:1d8 ×2 + CLAW 3d3 ×2), Energy 3 blows.
- Gorlim L41 spd+10, S:1_IN_2 CAUSE_3|BO_WATE|BO_MANA, 2 UN_BONUS blows ✓; Drolem L44 BR_POIS
  EMPTY_MIND ✓; Elder aranea L48 ✓; Mughash L7, no spells ✓; Kobold shaman L3 CONF ✓.
- Duplicate names are deliberate MAngband group variants: Novice paladin N:70 (L4 solo) and N:118
  (L8, FRIENDS); Carrion crawler N:281 (L25 solo) and N:353 (L34, **FRIENDS**) → a crawler pack is a
  chain-paralysis OOD threat at dl ~25–30 (pit/boost). Monsters 599+ (Ghoul L26, Elder aranea,
  Kobold shaman) are appended at the end of monster.txt out of level order.
- Melee stun (checked melee1.c:68-98, 1227-1291): HIT → cut or stun (50/50), KICK/PUNCH/BUTT/CRUSH →
  stun; only on a "critical" = damage ≥95% of max, and blows <20 dmg crit only dam% of the time. **No
  resist check** on this path ✓; stun >100 = knocked out (xtra2.c:1229ff). So dNd1 blows (GMM 20d1,
  15d1) always crit (→ +21–40 stun), while Mystic KICK 10d2 crits ~1% (needs ≥19). "Never melee
  GMMs" holds; for Mystics (L33) the stun danger is much smaller than lore says; summons are the risk.
Leads kept: Gorlim's shallow sightings (550/650 ft) unexplained (greater vault at 650 per kill list).

## B2 (dl 11–20) — read 2026-09-27, verdict: good; 99/99 rows; 19×4, 30×3, 35×2, 15×1
Verified by the Advisor:
- Melee BLIND and CONFUSE blows: **no saving throw**, only resist_blind/resist_conf; durations stack
  (melee1.c:892-930) ✓. (Spell BLIND/CONF do get a save.) → "no-save status blows" is a real class.
- Chimaera 20d15 HP (avg 160), BR_FIRE 1_IN_10 → breath avg ~53, 100 only at max HP. B2's "~100" is
  the worst case; rating 4 is on the high side (→ 3 in the merged table? decide at merge).
- Evil eye: GAZE:EXP_10 ×2, S:1_IN_7 HOLD|TELE_TO ✓ (monster.txt:8837-8844). Its own blows only drain
  exp; the danger is paralysis while other monsters act.
- Ochre jelly / Gelatinous cube lack NEVER_MOVE (B2 checked raw lines) — accepted.
Notes for merge: B2 maps every 4 → AVOID and 2/3 → CAREFUL; for a stair-scummer on arrival AVOID ≈
  take the stairs back. Hounds: Light/Dark/Clear L15, Fire/Cold/Energy L18, Earth/Air/Water L20.
  Names ≠ breath for Water (acid), Air (poison), Earth (shards).

## B3 (dl 21–30) — read 2026-09-27, verdict: good; 93/93 rows; 12×4, 33×3, 25×2, 23×1, no 5
Verified by the Advisor:
- BRAIN_SMASH: one save; on failure 12d15 (avg ~96, B3 said ~78) + blind (unless rBlind) + confused
  (unless rConf) + paralysed (unless FA) + slowed (always) (melee2.c, case 128+11) ✓.
- Basilisk 20d30 HP (avg 310), spd+10, GAZE:PARALYZE + 3×2d12, S:1_IN_8 BR_POIS → breath avg ~103,
  max 200 ✓ (monster.txt:4022-4032).
- 5-headed hydra 100d8, spd+10, 4×BITE:POISON:4d4, S:1_IN_5 ✓ (monster.txt:3920-3930).
Accepted from A1 (not re-read): POISON blow damage is not reduced by rPois (status only) nor by AC;
  elemental blows are reduced by resist, not AC.
Note for merge: B3's per-turn damage figures are "all blows hit" upper bounds.

## B1 (dl 0–10) — read 2026-09-27, verdict: good with errors; 159/159 rows; 8×4, 37×3, 52×2, 46×1, 16×0
Verified by the Advisor:
- Floating eye: B:GAZE:PARALYZE, no dice; check_hit i = power(2) + 3×level(1) = 5 vs AC×3/4 → with
  AC ≥ 7 it lands only on the flat 5% always-hit (melee1.c:105-127, 258); then save ~16–30%; +3+d1
  paralysis; level-1 paralyzers blink away after landing (melee1.c:984). ✓ Not lethal alone.
  General lesson: low-level monsters' status blows (low power + low level) rarely beat the armour check.
- Pseudo-dragon: I first wrote "HP avg 110 → breath 18, B1 wrong" — **my error**: it has FORCE_MAXHP
  (200 HP) so breaths are 33, as B1 said. B1's real miss: Half-Orc resist_dark cuts BR_DARK to ~0.42×
  and blocks its blinding (spells1.c GF_DARK case); only BR_LITE (33 + blind) is unresisted → 3, not 4.
  Lesson: always read FORCE_MAXHP when computing breath (the merge script does).
  → at merge: recompute breath damage from avg HP for every breather with a script; don't trust Clerk
  arithmetic.
- Novice priests/mages don't summon in 1.5 (spells checked in CSV) — forum claim contradicted; Orfax
  is the only summoner at dl0–10.

## B4 (levels 31–40, OOD at dl25) — read 2026-09-27, verdict: good; 122/122; 24×5, 42×4, 31×3, 21×2, 3×1, 1×0
Verified by the Advisor:
- Capital `D` only at level ≥40 (Ancient dragons) ✓ → "D = leave" rule has no false positives ≤30.
- Pits/nests select by **glyph**, and **decline uniques** (generate.c:1677-1760): jelly nest "ijm,",
  orc pit "o", troll pit "T"; animal/undead nests by flag. → Bert/Bill/Tom can't come from pits
  (B4's open lead: closed). Highest non-unique `o` is Orc captain L18 (B4 said "orcs ≤23 = Azog",
  but Azog is unique and excluded) → orc pits at dl21-30 are easy. Troll pits bring Cave troll(33),
  Olog(36), Eldrak(37), Ettin(38), Troll chieftain(40)... (Skeleton ettin is `s`, excluded).
  Jelly nests at dl21-30 draw i/j/m/, up to Depth+10: Black ooze, Shimmering mold, Memory moss(32),
  Acidic cytoplasm(35), Black pudding(37) — B4 listed only the j's.
- Mystic is INVISIBLE, S_SPIDER|S_ANIMAL|HEAL, KICK 10d2 ×4 ✓ (stun crit rare — see C1 note).
- Nexus quylthulg: NEVER_MOVE/NEVER_BLOW, BLINK|TELE_AWAY ✓ (harmless except displacement).
- "Draconic Q" = Draconic quylthulg L45 (C1) — outside B4's band, explains B4's non-match.

## Merge and calibration (2026-09-27)
- `data/monsters/build_danger_table.py` → `danger_table.csv` (473 rows, levels 0–40), computed columns
  from code (breath from avg/max HP incl. FORCE_MAXHP; speed_x; melee_avg; tags).
- Breather check: all breathers' ratings consistent with computed breath vs assumed HP.
- Red-flag scan (rating ≤2 with speed×melee ≥25% of HP, breath ≥30% HP, summon, TELE_TO, no-save
  status): 20 hits; most are fine (NEVER_MOVE molds, weak blows). Overrides (advisor_overrides.csv):
  Pseudo-dragon 4→3, Chimaera 4→3, Stegocentipede 2→3, Giant firefly 2→3, Doombat 2→3.

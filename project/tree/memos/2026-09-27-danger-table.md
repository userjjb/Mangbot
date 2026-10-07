# Memo: danger table for 0–1500 ft (Advisor → Architect, 2026-09-27)

**For:** the Pilot's danger rules (`tools/pilot/pilot.py` `danger_why`, `glyphs.py` `Race`) and the
HANDBOOK. **Data:** `Advisor/data/monsters/danger_table.csv` (473 monsters, levels 0–40, one row
each, rated for our Half-Orc Warrior). **Audit trail:** `Advisor/studies/2026-09-27-danger-table/`.

## How this was made

- **Sources:** `lib/edit/monster.txt` (1.5.3), parsed into `Advisor/data/monsters/monsters.csv`;
  `src/server/` (`melee1.c`, `melee2.c`, `spells1.c`, `monster2.c`, `generate.c`, `tables.c`,
  `xtra1.c`, `xtra2.c`); `p_race.txt`, `p_class.txt`; the forum memo and its corpus.
- **Passes:** pass 1: a legend of fields, blows, spells and damage formulas (A1), and how
  out-of-depth monsters are generated (A3). Pass 2: four Clerks rated every monster in one band of
  levels each (B1 0–10, B2 11–20, B3 21–30, B4 31–40 as out-of-depth visitors), and one Clerk
  checked the forum's named dangers against 1.5 (C1). This was the first study run with Clerks
  (Sonnet subagents); the Advisor read every dispatch and checked the claims the memo relies on.
- **Verified by the Advisor** (marked **[code ✓]**): about 25 claims, opened at the cited lines. Six
  Clerk ratings were changed (`advisor_overrides.csv`, with reasons), and one Clerk error on hounds'
  blows was corrected. Breath damage for every breather was recomputed by script from the code's
  formulas (average and maximum HP, including `FORCE_MAXHP`), not taken from the Clerks.
- **Ratings** are for the character we actually field: under-levelled for its depth (clvl ≈ 1–15 at
  dl1–10, 12–22 at dl11–20, 18–28 at dl21–30), HP ≈ 10 × clvl, only resist darkness, Free Action and
  See Invisible assumed from dl20 on (doctrine), no other resists assumed. Scale: 0 trivial, 1 easy,
  2 care, 3 dangerous, 4 lethal unless specifically geared, 5 leave on sight.

## 1. The findings that matter most

1. **Paralysis stacks, and nothing caps it.** A paralysing blow that gets through adds
   3 + d(monster level) turns to whatever paralysis is left (`melee1.c:962-993`; `set_paralyzed`
   caps only at 10000, `xtra2.c:321`) **[code ✓]**. A monster with two paralysing blows can keep a
   character without Free Action paralysed until it dies. Free Action blocks it fully; otherwise
   only the saving throw helps.

2. **Our saving throw is poor: about 15% + clvl.** Half-Orc −3, Warrior 18, +1 per clvl, WIS
   adjustment ≈ 0 (`xtra1.c:2283,2820,2832`; `p_race.txt`, `p_class.txt`) **[code ✓]**. At clvl 10
   that's ~25%; at clvl 25, ~40%. The save is the only defence against Hold/Slow/Scare/Blind/Conf
   spells, Cause Wounds, Mind Blast, Brain Smash, and paralysis or terrify blows without Free
   Action. **Resist fear arrives only at clvl 30** (`BRAVERY_30`, `xtra1.c:662-665`) **[code ✓]**.

3. **Blinding and confusing *blows* have no saving throw.** Only resist blindness / resist
   confusion blocks them, and the durations stack (`melee1.c:892-930`) **[code ✓]**. The spells of
   the same name do allow a save. So Umber hulks (confusing gaze, dl16), Hummerhorns (confusing bite,
   a breeder, dl16), Giant fireflies (blinding bite, a breeder, dl24), Giant brown ticks, Catoblepas
   and Spectators confuse or blind the character every time they connect. Blind or confused means no
   scrolls: this is the "status lock" the forum memo describes, with its mechanism.

4. **Melee stun can't be resisted, and above 100 stun the character is knocked out.** A HIT blow
   stuns or cuts (50/50), and KICK/PUNCH/BUTT/CRUSH blows stun. That happens only on a *critical*,
   which needs ≥95% of the blow's maximum damage; blows under 20 damage crit only dam% of the time
   (`melee1.c:68-98,1227-1291`) **[code ✓]**. Consequences:
   - Grand Master Mystic blows are 20d1 and 15d1, which always roll the maximum, so they always crit:
     "never melee them" is right.
   - Ordinary Mystics (level 33) kick for 10d2, which crits only ~1% of the time. Their danger is
     summoning, invisibility and speed, not stun.

5. **Speed doubles or triples everything.** Energy per tick is 1000 at normal speed, 2000 at +10,
   3000 at +20 (`tables.c:2169`) **[code ✓]**. Among the 141 monsters rated 3 or more at levels
   0–30, pack spawning (47) and +10 speed (41) are the two most common features, ahead of uniques
   (28) and breath (26). The Pilot's danger rules currently ignore speed and melee damage entirely.

6. **Armour stops only plain melee.** Bolts and breaths never miss; AC reduces only HURT and SHATTER
   blows (`melee1.c:106-127`, `melee2.c:333-361`). Elemental blows (fire, cold, acid, lightning
   bites) are reduced by the matching resist, never by AC. Poison *blows* are reduced by nothing:
   resist poison stops only the poisoning status. This is why the 5-headed hydra (+10 speed, four
   4d4 poison bites, ~80 per player turn) stays lethal with resist poison.

7. **Only the five basic resists cut damage to a third.** Acid, lightning, fire, cold and poison
   resists divide by 3 (and stack with temporary resists to ~1/9). The others multiply by K/(d6+6):
   nether and shards ~0.66, sound and confusion ~0.55, light and dark ~0.44 (`spells1.c` GF_ cases)
   **[code ✓ for nether and dark]**. A level-36 monster's nether bolt (~99) still does ~65 through
   resist nether.

8. **Out-of-depth monsters mostly come from a per-monster boost, not vaults.** Every generated
   monster has two separate 1/50 chances of being drawn up to 5 levels deeper
   (`monster2.c:559-580`) **[code ✓]**: at dl12+ about 4% of monsters are from ~5 levels down,
   rarely 10. Other sources:
   - Summons come from level (depth + summoner level)/2 + 5 (`monster2.c:2574`) **[code ✓]**.
   - Pits and nests (from dl5) draw at depth + 10, pick by glyph and exclude uniques
     (`generate.c:1677-1760`) **[code ✓]**. At dl21–30: orc pits hold only non-unique `o` (the top
     one is the Orc captain, level 18: easy); **troll pits** (`T`) bring level 31–40 trolls (Cave
     troll, Olog, Eldrak, Ettin, Troll chieftain); jelly nests (`i j m ,`) bring Acidic cytoplasm,
     Black pudding and Memory moss.
   - Vaults are rare at our depths. The chance that a level even *tries* a vault, pit or nest is
     roughly 6% at dl10, 22% at dl20 and 43% at dl30 (upper bounds; Advisor estimate from
     `generate.c:3187,3213-3243`). A few lesser vaults (from dl5) can hold a depth+40 monster.
     Vaults are recognisable by permanent walls.

9. **Several classic shallow "killers" are harmless, and several harmless-looking monsters kill.**
   - **Floating eye:** its gaze does no damage and has a to-hit of 5 (power 2 + 3 × level 1), so
     against AC ≥ 7 it lands only on the flat 5% always-hit roll, and it blinks away after landing
     (`melee1.c:105-127,258,984`) **[code ✓]**. It's not a solo threat; the risk is being paralysed
     next to something else.
   - **Farmer Maggot** can't hurt you (two MOAN blows with no damage).
   - **Druid** (level 13, looks like a plain `p`): ~45-damage fire bolt, Hold, summon animals.
   - **Kobold shaman** (level 3): a Cause Wounds spell of 3d8 that lands ~75–85% of the time at that
     depth.
   - **Dark elven mage** (level 10): poison ball plus blindness and confusion, one cast in 5.
   - **Stegocentipede** (level 12, +10 speed, ~30 per player turn).
   - **Chimaera** (level 20): fire breath averaging 53, 100 at maximum HP.

## 2. The lethal monsters at 0–1500 ft (rated 4; none native to these depths rates 5)

Glyph + colour letters as in monster.txt. "LEAVE" = take the stairs back on sight; "AVOID" = don't
engage; leave if it approaches. Full detail per monster in `danger_table.csv`.

| ft | lvl | glyph | monster | why | neutraliser |
|---|---|---|---|---|---|
| 350 | 7 | k v | Mughash the Kobold Lord | 3×1d10 + an escort of kobolds (shamans confuse) | corridor, or leave |
| 400 | 8 | p B | Wormtongue | cold bolt ~23, poison ball, Slow, heals | rCold, FA |
| 400 | 8 | o y | Lagduf, the Snaga | 4 blows ~19/turn + orc escort | corridor, or leave |
| 450 | 9 | p U | Brodda, the Easterling | 4×1d12 (~26/turn), 210 HP | leave until clvl ~15 |
| 500 | 10 | h r | Dark elven mage | poison ball, missile, blind + confuse, 1 in 5 | rPois, CCW |
| 500 | 10 | y B | Orfax, Son of Boldor | teleport-to, summon, Slow, Conf, heals, +10 speed, yeek escort | FA; kill or leave |
| 500 | 10 | o y | Grishnákh | 4 blows ~22/turn + orc escort | corridor, or leave |
| 600 | 12 | o y | Golfimbul | 4 blows (44 max) + orc escort | corridor |
| 650 | 13 | y v | Boldor, King of the Yeeks | yeek swarm, Blind, Slow, heals | corridor |
| 650 | 13 | p G | Druid | fire bolt ~45, Hold, summon animals | FA, rFire |
| 700 | 14 | o g | Ufthak of Cirith Ungol | 4 blows (48 max) + escort, 320 HP | corridor |
| 750 | 15 | u y | Homunculus | paralysing blow | FA |
| 800 | 16 | X U | Umber hulk | confusing gaze, **no save**; tunnels through rock | rConf |
| 800 | 16 | p U | Ulfast, Son of Ulfang | 4 blows (60 max), 340 HP | kill fast or leave |
| 850 | 17 | h y | Nar, the Dwarf | Cause Serious ~36 + Mind Blast ~36, heals, 60-max melee | save; leave |
| 900 | 18 | o o | Orc captain | 3 blows (45 max) + escort + arrows | corridor |
| 900 | 18 | e g | Evil eye | teleports you to it, then Hold | FA |
| 950 | 19 | o g | Shagrat / Gorbag | 78-max melee + escort, 400 HP each | leave |
| 1000 | 20 | o v | Bolg, Son of Azog | 72-max melee + escort, 500 HP | leave |
| 1000 | 20 | Z u/g/s | Earth / Air / Water hound packs | 4 blows each + shards / poison (22–40) / acid (22–40) breath | rPois, rAcid; corridor |
| 1000 | 20 | h s | Dark elven lord | fire bolt ~45 / cold ~31, hastes self, Blind, Conf | rFire, rCold |
| 1000 | 20 | p w | Paladin | 40-max melee, Cause Serious ~36, heals | save |
| 1150 | 23 | o v | Azog, King of the Uruk-Hai | +10 speed, ~90/turn if all hit, large escort | leave |
| 1300 | 26 | C D | Wolf chieftain | +10 speed, leads a wolf pack, terrifying wail | leave |
| 1350 | 27 | h o | Mim, Betrayer of Turin | +10 speed, ~80/turn, acid ball, disenchants, immune to all 5 elements | leave |
| 1350 | 27 | Z y / Z v | Vibration / Nexus hound packs | sound (stun) / nexus breath + ~30/turn melee each | rSound / rNexus; leave |
| 1400 | 28 | M g | 5-headed hydra | +10 speed, 4 poison bites (~80/turn), resist poison doesn't help | leave |
| 1400 | 28 | h v | Mind flayer | Brain Smash: ~96 dmg + blind + confused + slowed (+ paralysed without FA) on a failed save | rBlind + rConf + FA |
| 1400 | 28 | u v | Draebor, the Imp | invisible, +10 speed, teleport-to/away/level, summons kin | SI; leave |
| 1400 | 28 | R s | Basilisk | +10 speed, paralysing gaze, poison breath avg 103 (max 200) | rPois + FA |
| 1400 | 28 | q D | Beorn, the Shape-Changer | +10 speed, ~100/turn, 1400 HP | leave |
| 1400 | 28 | b g | Bat of Gorgoroth packs | +10 speed, poison + dark breath each | rPois; leave |
| 1500 | 30 | O b | Ogre chieftain | +10 speed, ~108/turn if all hit, ogre escort | leave |

Also dangerous (3) and worth knowing by name: Grip and Fang (+20 speed, level 2), Bullroarer,
baby dragons (breath ~33 at dl9, 43 for multi-hued), Pseudo-dragon (light breath 33 + blindness;
Half-Orcs resist its dark breath), the paralysers Carrion crawler (dl25), Ghoul and Ghast packs
(dl26/30), Ogre mage (dl27), Vampire and Gorgimaera (dl27, fire breath avg 87), young dragons at dl29
(breath 90, always max HP), and the summoners Priest (dl12), Quylthulg (dl20, invisible), Scroll and
Ring mimics (dl21/29), Dark elven druid (dl25) and Mage (dl28).

**Out-of-depth visitors that mean "leave on sight" at dl20–30** (level 31–40, rated 5): Mystic,
Lich, Master vampire, Colossus, Necromancer, Lorgan, mature red/black/multi-hued dragons, Death
knight, Cherub, Kavlax, 7- and 9-headed hydras, ancient dragons (`D`), Enchantress, Sorcerer, Giant
roc, Medusa, Vrock packs, Death quasit, Patriarch. Also note the level-34 **Carrion crawler pack**:
the same name, glyph and colour as the solo level-25 one, but with FRIENDS (a chain-paralysis pack;
FA is mandatory).

## 3. Recommendations: Pilot (reflex rules)

The current `danger_why` rules (level gap, unique above your level, breath vs HP, paralyser without
FA, summoner) are sound. Add or change these (in order of value):

1. **Load the table.** Read `danger_table.csv` (key `idx`, which matches monster.txt `N:`), and treat
   `danger == 5` as leave-on-sight always, and `danger == 4` as danger while
   `clvl < level + 8` (a rough "outgrown" margin; the table's `safe_when` column is free text for the
   Navigator). The rules below then catch what a static rating misses as the character grows.
2. **Fast melee:** danger when `speed_x × melee_avg ≥ current HP / 3` (both columns are in the
   table; `speed_x` = extract_energy/1000; `melee_avg` assumes every blow hits, so it's an upper
   bound). Catches Azog (~90), Beorn (~100), Ogre chieftain (~108), Doombat (~75), and the
   Stegocentipede (~30) for a character under ~90 HP, all of which the current rules pass.
3. **No-save status blows:** never stand next to (i.e. never auto-retaliate against) a monster with a
   BLIND blow without resist blindness, or a CONFUSE blow without resist confusion; move away or
   leave. This includes stationary ones (Grey/Magic mushroom patches, Brown mold), because
   auto-retaliate keeps you adjacent.
4. **Brain Smash** (`BRAIN_SMASH` in spells): danger unless the character has FA *and* resist
   blindness *and* resist confusion.
5. **Teleport-to** (`TELE_TO`): walking away doesn't work, so escape by stairs or Phase Door.
   Harmless alone for Tengu and Blink dog; not for Orfax, Evil eye (followed by Hold), Vampire, Mage
   and Draebor.
6. **Capital `D` = leave**, and so do the level-5 list above on arrival. `D` starts at level 40, with
   no shallow look-alike **[data ✓]**. Don't read danger from `d` colours: `d s` is Baby (9), Young
   (31) and Mature (36) black dragon alike, and `d g` also matches the Wyvern.
7. **Paralyser rule refinement:** the current rule treats any paralyser within 10 levels as danger.
   A low-level PARALYZE blow almost never lands through armour (floating eye above), so
   `paralyser` could exempt blows where `power(2) + 3 × level ≤ AC × 3/4` (the monster can then hit
   only on the 5% floor). This is minor; keep the current rule if simpler.
8. **Remove `BR_MANA`** from `glyphs.py BREATHS`: it is a no-op in 1.5 (`melee2.c:876-881`, the
   monster wastes its turn) **[code ✓ that the case body is empty: A1; not re-read]**. No monster at
   levels ≤40 has it, so it's cosmetic.
9. **Hounds:** keep the pack-breath rule. The server deletes non-unique `Z`s near you only when you
   arrive going *down* (forum memo §1), so the pack-on-arrival check matters most after going up.

## 4. Recommendations: Navigator (doctrine)

- **Free Action by 1000 ft is right, and it's the most valuable single item.** It turns 15
  paralysers at dl1–30 into fightable monsters. Without it, leave any level with a Carrion crawler,
  Ghoul/Ghast, Homunculus, Evil eye, Ogre mage, Basilisk or Gorgimaera.
- **Resist confusion and resist blindness matter earlier than the "1900 ft" checkpoint** in the
  notes: no-save blinders and confusers start at 800 ft (Umber hulk, Hummerhorn) and Brain Smash at
  1400 ft. Until then, CCW potions plus a staff of Teleportation are the answer (staffs work blind or
  confused).
- **Resist poison by ~1000 ft**, not 2000: air hounds (1000 ft), Basilisk (1400 ft, 103 avg) and Bats
  of Gorgoroth breathe poison.
- **The uniques from 350 to 1000 ft are the main killers of an under-levelled diver**: 18 of the 37
  monsters rated lethal at these depths are uniques with escorts or heavy melee. Leave on sight until
  clvl is about the unique's level + 8, unless the fight is in a corridor with escape underfoot.
- **Recognise pits:** a room packed with `o` at dl21–30 is an easy orc pit; packed with `T` it's a
  troll pit drawn 10 levels deeper: leave.

## 5. HANDBOOK text (suggested)

> **Monsters that kill a diving warrior (0–1500 ft).** The table is `danger_table.csv` (Advisor).
> Rules of thumb, all checked in the 1.5 server code:
> - Paralysis stacks until you die: without Free Action, leave any level with a paralyser that can
>   reach you (Carrion crawlers, Ghouls, Homunculus, Evil eyes, Ogre mages, Basilisks).
> - Monsters that blind or confuse *with their blows* (Umber hulk, Hummerhorn, Giant firefly, ticks,
>   molds and mushroom patches) get no saving throw: only the resist helps. Blind or confused, you
>   can't read scrolls.
> - Fast monsters (+10) act twice per turn: Grip and Fang, Azog, Beorn, Mim, the 5-headed hydra,
>   the chieftains. Their damage per turn is twice what the dice say.
> - Armour doesn't reduce breath, bolts, or fire/cold/acid/lightning/poison bites.
> - Uniques at 350–1000 ft (Mughash, Wormtongue, Lagduf, Brodda, Grishnákh, Orfax, Golfimbul,
>   Boldor, Ufthak, Ulfast, Nar, Shagrat, Gorbag, Bolg) outclass an under-levelled character. Leave
>   unless you fight them in a corridor.
> - A capital `D` is an ancient dragon, always out of depth above 2000 ft: leave.
> - Floating eyes are harmless unless something else is attacking you while you're paralysed.

## 6. Where the current docs are contradicted

| Doc | Says | 1.5 data/code | Source |
|---|---|---|---|
| Forum memo §1 (ours) | "water and energy hounds at about 1000 ft, earth at 900, air at 1550" | Energy 900 ft (lvl 18); **earth, air and water all 1000 ft (lvl 20)**; air isn't a 1550-ft monster. Fire/cold 900, light/dark/clear 750, vibration/nexus 1350, gravity 1750 | monster.txt, C1/B2 [data ✓] |
| Forum memo / lore | hound names = breath | Water hounds breathe **acid**, air hounds **poison**, earth hounds **shards** | monster.txt [data ✓] |
| Forum memo | "Novice p's summon" | No novice summons in 1.5 (priest: Heal/Scare/Cause Light; mage: Blink/Blind/Conf/Missile). The shallow summoners are Orfax, Gnome mages, Master yeek, Priest, Boldor, Druid | monster.txt [data ✓] |
| Forum memo | Mughash's "confusion lock" | Mughash has no spells; his kobold shaman escort casts Conf | monster.txt [data ✓] |
| Forum memo | Mystics stun-lock in melee | True for Grand Master Mystics (20d1/15d1 always crit); Mystics' 10d2 kicks crit ~1% | `melee1.c:68-98` [code ✓] |
| HANDBOOK:205 / notes | molds and jellies are stationary | Ochre jelly (dl13, +10 speed) and Gelatinous cube (dl16) move and chase | monster.txt (B2 checked raw) |
| HANDBOOK:183 | "packs of paladins (they scare and summon)" | Novice paladins scare and cast Cause Light; they don't summon. Priests do summon | monster.txt [data ✓] |
| HANDBOOK:160 | "It commands you to return" is a Tengu or Blink dog, harmless | Also Orfax, Quasit, Imp, Evil eye (then Hold), Phase spider, Vampire, Mage, Draebor | monster.txt [data ✓] |
| notes_players.md:79 | resist poison checkpoint 2000 ft; conf/blind 1900 ft | poison breath at 1000 ft (air hounds), no-save confusion at 800 ft | this memo §4 |
| Forum lore / brief | FORCE_SLEEP = asleep | It only lowers starting energy | `monster2.c:1938-1946` [code ✓] |
| Forum lore | SMART monsters avoid your resists | That code is compiled out in 1.5 | `options.h:437,559` [code ✓] |

## 7. Forum kill list at ≤1500 ft (from C1)

The forum's death reports at ≤1500 ft with a named monster (15 incidents): hounds 5 (five types),
Scroll mimic 2 (both by summons), and one each of Gorlim (a greater vault at 650 ft), Greater mystic,
Shagrat, Great Storm Wyrm, Dracolich, 7-headed hydra, Mouth of Sauron and Khamûl (the "Backdoor
Surprise" vault), Ochre jelly and Shambling mound (an opened pit), Elder aranea (a spider vault),
Mughash with kobold shamans. **Most of the non-hound deaths were vault or pit monsters far out of
depth**, which the table can't rate by depth: the doctrine "don't open vaults or pits at our level"
covers them.

## Coverage and gaps

- **Covered:** every monster at levels 0–40 (473), each rated by a Clerk from the full stat block and
  the A1 legend; the breathers and 20 "low rating but red flag" monsters re-checked by the Advisor;
  about 25 mechanics verified in code.
- **Not verified in code:** the non-elemental resist formula for sound/shards/confusion/light
  (checked nether and dark only); `apply_nexus` effects; stat-drain amounts; PASS_WALL/KILL_WALL
  movement; hallucination (RBE_HALLU is blocked by resist chaos per `melee1.c:1210-1223`, seen in
  passing).
- **Ratings are judgement:** four Clerks each rated their band against one shared scale. Band-to-band
  consistency was checked on breathers and a red-flag scan, not monster by monster. `clerk_danger`
  keeps the original rating wherever the Advisor changed it.
- **Levels 41+** aren't rated. Named killers there (Gorlim 41, Drolem 44, Draconic quylthulg 45,
  Elder aranea 48, Grand Master Mystic 57) appear at our depths only from vaults or pits.
- **Assumed character state** may not match the Pilot's real characters; the Pilot's dynamic rules
  (breath vs current HP etc.) should stay in charge, with the table as a floor.

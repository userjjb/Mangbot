# Dispatch: unknown scrolls, staffs, wands, rods, rings, amulets (assignment D, pass 1)
- Brief: what happens when Dive04 (Half-Orc Warrior clvl 10, no FA) uses or wears each unknown non-potion item; classify; answer awareness, curse stickiness, skill-roll, blind/confused questions.
- Clerk run: 2026-10-07; sources: server/use-obj.c, cmd6.c, cmd3.c, spells1.c, spells2.c, monster2.c, object1.c, object2.c, dungeon.c, init2.c, xtra1.c, xtra2.c, mdefines.h, lib/edit/object.txt, p_race.txt, p_class.txt, kinds.csv.
- Full rows (138): `scratch/D_devices.csv`. Tables below are condensed. "use-obj.c:N" = line of the case. Level = kinds.csv.

## Answer
1. Only a handful of unknown scrolls/staffs can start a fatal fight: Summon Monster, Summon Undead, Aggravate (scrolls), Staff of Summoning, Staff of Haste Monsters (only if monsters in view). Trap Creation, Curse Armor/Weapon, Recharging, *Destruction* cost something. Nearly everything else is harmless or good.
2. Wearing any unknown ring/amulet risks a **sticky curse**: cursed worn items cannot be taken off, replaced, or destroyed until Remove Curse (sold in the Temple, cost 100). Wearing never makes the flavour aware.
3. Staffs/wands/rods need a device roll that a clvl-10 warrior mostly fails above kind level ~15. Staffs of level >=20 (Teleportation, Speed, ...) fail 83-99%.
4. Awareness comes only when `*ident` is set by an effect the player notices; otherwise the kind is marked "tried".

## Findings
1. **Device skill roll** [SEEN]. skill_dev = race r_dev (Half-Orc -3, p_race.txt:117) + class c_dev (Warrior 18, p_class.txt:85) + adj_int_dev[INT] (tables.c:1274; 0-1 for INT <=14) + x_dev*clvl/10 (Warrior 7 -> +7; p_class.txt:86, xtra1.c:2280,2817,2829). Total about 22-23 at clvl 10 (INT unknown to me). Roll (staff cmd6.c:477-501, wand use-obj.c:1356-1376, rod use-obj.c:1681-1701): chance = skill - min(kind level,50), halved first if confused; if chance<3 a 1/(3-chance+1) chance becomes 3; fail if randint1(chance)<3 (USE_DEVICE=3, mdefines.h:161). Fail ≈ 2/chance. Computed failure at skill 22/23: level 0-5: 9-12%; 10: 15-17%; 15: 25-29%; 20: 67-83%; 25: 94-95%; 30+: 97-99%. Confused: roughly 18% at level 0, 89% at 10, 96%+ above. A failed use costs a turn, no charge, no "tried". Scrolls have no roll.
2. **Awareness** [SEEN]. All use paths set `ident=FALSE`, run the effect, then call `object_tried()` (kind_tried, object2.c:1063) and, if `ident && !aware`, `object_aware()` + exp (lev + clvl/2)/clvl (scroll cmd6.c:316-333; staff cmd6.c:420-441; wand cmd6.c:547-556; rod cmd6.c:668-684). So "aware" requires a noticed effect; a "tried" flag exists and shows as "tried" in the name (object1.c:2036). Wands: charge is spent only if the roll succeeded (cmd6.c:559); object_aware also happens when selling to or buying from a store (store.c:1835, 2138) [SEEN, not studied].
3. **Wearing a ring/amulet never calls object_aware** [SEEN: grep of all object_aware callers = cmd6/use-obj, spells2.c identify, store.c, files.c; none in cmd3.c wield 340-520]. It only (a) applies the real stats via calc_bonuses (visible on the character sheet), and (b) if cursed prints "Oops! It feels deathly cold!" and sets ID_SENSE so the name shows "cursed" (cmd3.c:500-509; object1.c:2024). `easy_know_p` makes an aware ring/amulet with all-zero mods known (object1.c:303-325).
4. **Pseudo-ID does not cover jewellery** [SEEN]. sense_inventory only senses weapons, ammo, bows, armour (dungeon.c:196-215). No pre-wear curse warning for rings/amulets.
5. **Cursed = sticky in this version** [SEEN]. takeoff refused "Hmmm, it seems to be cursed." (cmd3.c:641-648); wielding into a cursed slot refused (cmd3.c:372-385); cursed equipment cannot be destroyed (cmd3.c:850-855). Removed by Remove Curse scroll/staff (spells2.c:415-465: no failure roll; only HEAVY/PERMA_CURSE artifacts resist; unaware scroll becomes aware only if something is uncursed). **Remove Curse scroll is stocked in the Temple** (init2.c:1202 normal table, 1456 ironman table; no other store), cost 100 (kinds.csv). Cursed or broken items sell for 0 (shared fact).
6. **What is cursed** [SEEN, object2.c, object.txt]: LIGHT_CURSE kinds are cursed+broken at creation (object2.c:170): Rings of Teleportation, Weakness, Stupidity, Aggravate Monster, Woe; Amulets of Teleportation and DOOM. Also any Ring of Strength/Dex/Con/Int/Speed/Searching/Damage/Accuracy/Protection/Slaying and Amulet of Wisdom/Charisma/Searching/Infravision/Speed can be cursed with negative pval/bonus when power<0 (object2.c:2686-3069). Chance of the cursed branch = (1-f)*f with f=(dlv+10)%: dlv5 13%, dlv9 15%, dlv20 21%, dlv30 24% (apply_magic, object2.c:3187-3235) [INFERRED from code]. Never cursed: Free Action, Resist x, Sustain x, See Invisible, Resist Poison, Flames/Acid/Ice/Lightning, ESP, Magi, Moon, Terken, Devotion, Weaponmastery, Trickery.
7. **Random teleport**: Ring/Amulet of Teleportation and Woe set p_ptr->teleport (xtra1.c:2328,2501); 1% per player tick, teleport_player(40) (dungeon.c:990-994).
8. **Summons** [SEEN]. Scroll: `for(k=0;k<randint1(3);k++)` re-rolls each pass: 1/2/3 monsters = 33/44/22%, mean 1.9 (use-obj.c:766). Staff of Summoning: randint1(4): 25/37.5/28/9%, mean 2.2 (use-obj.c:1114). Each: summon_specific(dlv, ..., lev=dlv), monster level cap (dlv+dlv)/2+5 = dlv+5, 1/50 chance of an inflated level (NASTY_MON=50, mdefines.h:179), placed awake, groups allowed (monster2.c:2552-2594, place_monster_aux(...,FALSE,TRUE)). Paralyzers in monster.txt with level <=36: Floating eye 1 (gaze), Homunculus 15, Carrion crawler 25/34, Ghoul 26 (undead), Gorgimaera 27, Basilisk 28, Spectator 28, Ghast 30 (undead), Silent watcher 35, Trapper 36. With no Free Action, any of these adjacent can be fatal; Summon Undead at dlv 21+ can yield Ghoul.
9. **Aggravate scroll** [SEEN spells2.c:3313-3362]: every monster on the level within 40 grids (MAX_SIGHT 20 *2) wakes; each monster in LOS gets speed = race speed+10 permanently. Always identifies.
10. **Clone Monster wand at clvl>=10 does not clone** [SEEN spells2.c:4801-4823, spells1.c:2770-2800]: prints "You hear a loud crackling sound", but still heals the target to full and adds +10 speed. At clvl<10 it also spawns a copy. This contradicts nothing in the brief but matters: our warrior is exactly clvl 10.
11. **Haste Monster wand** +10 speed (cap 150) permanent (spells1.c:2828-2840); **Heal Monster** heals 4d6 and wakes (spells1.c:2802-2826). **Polymorph** new race from poly_r_idx, uniques immune, saves if randint1(90)<=monster level, new monster is at full health (spells1.c:3264-3300). **Wand of Wonder** picks sval randint0(24) i.e. any wand 0-23 (use-obj.c:1408; SV_WAND_WONDER=24, mdefines.h:1593): 3/24 are Heal/Haste/Clone; never dragon/annihilation. "Oops" line is unreachable.
12. **Aiming at nothing** [SEEN]: wands/rods that set ident unconditionally (identify even with no target): Light, Magic Missile, Stinking Cloud, all bolts and balls, Dragon wands, rods Light/Illumination/Detection/Probing/Recall/Mapping and all bolt rods. Target-dependent (need a visible monster, trap, door or wall): Heal/Haste/Clone/Slow/Sleep/Confuse/Scare/Polymorph/Teleport Other/Drain Life/Disarming/Trap-Door Destruction/Stone to Mud (and matching rods). project_m sets obvious only `if (seen)` (spells1.c:2744 etc.).
13. **Rods** [SEEN use-obj.c:1656-1936]: unaware rods always ask for a direction (1664). Charge time = k_info pval per zap; a rod "still charging" returns FALSE with no ident. Same skill roll as wands. Rods have no harmful kinds in this list except Polymorph (rod) and Recall (starts recall).
14. **Trap Creation scroll never becomes aware**: GF_MAKE_TRAP sets no `obvious` (spells1.c:1894-1910) and trap_creation returns project()'s notice (spells2.c:4919-4924); the scroll stays "tried". Traps are invisible (FEAT_INVIS, object2.c:3829-3843) on the 8 neighbouring naked floor grids; type is rolled on step/search from 16 (pick_trap object2.c:4169): trap door (2d8 fall), pit 2d6, 2 spiked pits, summon rune, teleport rune (100), fire 4d6, acid 4d6, slow/STR/DEX/CON darts 1d4, blind gas 25-74, confusion gas 10-29, poison gas, paralysis gas 5-14 (cmd1.c:891-1150) [SEEN]. Costs nothing if you leave by another route.
15. **Blind/confused/dark** [SEEN]: scrolls refused when blind, no light, or confused (cmd6.c:276-292). Staffs, wands and rods have **no** blind check (cmd6.c ~350-470 only ghost/skill checks), so a blinded warrior can still use them; confusion halves the skill roll (very high failure) and forces a random direction on aimed wands/rods (xtra2.c:4914-4918).
16. **Earthquake staff**: the user is at the epicentre, which is skipped in the damage list (spells2.c:3926-3939), so the user is not hurt; 15% of grids in r10 are hit (3925-3931). **\*Destruction\*** (scroll/staff): deletes monsters and floor objects in r15 except your grid, blinds you 11-20 turns (spells2.c:3617-3680).
17. **Curse Armor/Weapon** (level 50 only): body armour -> Blasted (to_a -2..-10, ac 0), weapon -> Shattered (to-hit/to-dam -2..-10 each, dice 0), both cursed+broken+sticky, artifact 50% save (spells2.c:2184-2310). Only if something is worn.
18. **Teleport Level** 50/50 up/down, down only if dlv>0 and not quest (spells1.c:365-395); from dlv 1 "up" goes to town. **Word of Recall** from dungeon -> town after 15-34 turns; toggles off if read again (spells2.c:1135-1190; dungeon.c:1626-1665).

## Tables (condensed; "aware" = identifies on use, `use-obj.c` line)
**Scrolls**
| kind | lvl | effect unknown | class | aware |
|---|---|---|---|---|
| Light 0, Treasure Det 0, Object Det 0 | 0 | light / detect | HARMLESS/GOOD | Light always (896); detects only if found (909,916) |
| Identify | 1 | prompts, cancel keeps scroll | GOOD | yes (823) |
| Summon Monster | 1 | 1-3 monsters lvl dlv+5, awake | DANGEROUS | if placed (763) |
| Phase Door / Detect Invis / Blessing / Darkness | 1 | phase 10 / detect / bless / blind 4-8 turns + unlight | HARMLESS/NUISANCE(Darkness) | yes mostly (795,935,947,733) |
| Monster Confusion, Magic Mapping, Trap Det, Door/Stair Loc, Satisfy Hunger | 5 | benign | HARMLESS/GOOD | when noticed (965-941) |
| Aggravate Monster | 5 | wake 40 grids, +10 speed LOS | DANGEROUS | yes (743) |
| Word of Recall | 5 | recall in 15-34 turns | NUISANCE | yes (816) |
| Remove Curse | 10 | uncurse worn | GOOD | if uncursed something (837) |
| Teleportation | 10 | tele 100 | HARMLESS | yes (802) |
| Trap Creation | 10 | invisible traps next to you | COSTLY | never (789) |
| Trap/Door Destruction, Holy Chant | 10 | benign | HARMLESS | if effect (990,953) |
| Enchant WtH/WtD/Armor | 15 | +1 enchant, prompt | GOOD | yes (861,868,854) |
| Summon Undead | 15 | 1-3 undead lvl dlv+5 | DANGEROUS | if placed (776) |
| Life | 20 | restore | GOOD | yes (1038) |
| Teleport Level | 20 | up/down 1 | NUISANCE | yes (809) |
| Acquirement | 20 | 1 great item at feet; aware cost 100000 | GOOD | yes (1023) |
| Holy Prayer 25, *Identify* 30, Prot Evil 30 | | benign | GOOD/HARMLESS | yes (959,830,976) |
| Recharging | 40 | pick wand/staff; may destroy | COSTLY if used | yes (889) |
| Banishment 40, Dispel Undead 40, Mass Banish 50 | | monster removal | GOOD | (1009,1003,1016) |
| *Destruction* | 40 | blind 11-20, wipes r15 | COSTLY | yes (996) |
| *Remove Curse* / *Enchant Weapon* / *Enchant Armor* | 50 | strong good | GOOD | yes (847,882,875) |
| Curse Weapon / Curse Armor | 50 | wrecks worn gear, sticky | COSTLY | yes (757,751) |

**Staffs** (all pass the device roll; fail% at skill ~22-23 in brackets)
| kind | lvl [fail] | effect | class | aware |
|---|---|---|---|---|
| Treasure/Object Location, Light, Cure Light, Detect Invis, Darkness | 5 [~10%] | detect/light/heal 1d8/blind 4-8 | HARMLESS (Darkness NUISANCE) | when noticed (1177,1184,1163,1214,1202,1089) |
| Trap Loc, Door/Stair Loc, Slow Mon, Sleep Mon, Perception | 10 [~16%] | benign | HARMLESS/GOOD | (1190,1196,1259,1253,1132) |
| Summoning | 10 | 1-4 monsters lvl dlv+5 | DANGEROUS | if placed (1111) |
| Haste Monsters | 10 | +10 speed LOS monsters | DANGEROUS if any in view | only if monster seen (1105) |
| Teleportation | 20 [67-83%] | tele 100 | HARMLESS | yes (1124) |
| Starlight, Detect Evil, Enlightenment(map) | 20 | benign | HARMLESS/GOOD | (1152,1208,1170) |
| Curing | 25 | cure | HARMLESS | if cured (1220) |
| Probing | 30 | probe | HARMLESS | yes (1278) |
| Earthquakes | 40 | r10 quake, user safe | HARMLESS | yes (1317) |
| Speed | 40 | haste 16-45 turns | GOOD | yes (1265) |
| Slowness | 40 | slow -10 for 16-45 turns | NUISANCE (DANGEROUS near monsters) | if slowed (1099) |
| Remove Curse | 40 | uncurse | GOOD | if uncursed (1139) |
| *Destruction* | 50 | blind, wipe r15 | COSTLY | yes (1325) |
| Dispel Evil | 50 | 60 dmg evil LOS | HARMLESS | if hit (1285) |
Staff of the Magi/Healing/Power/Holiness/Banishment are level 70 (alloc 70+), omitted.

**Wands** (rolls as above; fail 10-12% at lvl 3-5, 17% at 10, 29% at 15, 70-83% at 20, >95% at 30+)
| kind | lvl | effect | class | aware |
|---|---|---|---|---|
| Light, Magic Missile 3d4, Stinking Cloud 12, all bolts/balls, Dragon's Flame/Frost | 3-50 | damage | GOOD | yes always (1455,1507,1499,1515-1577,1585-1593) |
| Heal Monster | 3 | heals 4d6 | NUISANCE | if monster seen (1413) |
| Haste Monster | 3 | +10 speed | DANGEROUS | if monster seen (1419) |
| Wonder | 3 | random wand 0-23 | NUISANCE/DANGEROUS (12.5%) | when sub-effect IDs (1408) |
| Slow/Confuse/Sleep/Scare | 5-10 | status | HARMLESS | if obvious |
| Stone to Mud, Trap/Door Destr, Disarming | 10-20 | utility | HARMLESS | if target exists |
| Clone Monster | 15 | clvl>=10: full heal + haste, no copy | NUISANCE | if monster seen (1425) |
| Polymorph | 20 | new monster | NUISANCE | if changed (1493) |
| Teleport Other | 20 | removes monster | GOOD | if monster seen (1431) |
| Drain Life | 50 | 150 dmg | GOOD | if hit (1487) |

**Rods** (all `EASY_KNOW` once aware; unknown ones ask direction)
| kind | lvl | class | aware |
|---|---|---|---|
| Trap Loc 5, Door/Stair 15 | | HARMLESS | if found (1726,1732) |
| Light 10, Illumination 20, Detection 30, Probing 40, Perception 50 | | HARMLESS/GOOD | yes (1835,1752,1766,1773,1738) |
| Lightning/Frost/Fire/Acid bolts 20-40 | | GOOD | yes (1875-1891, 1867) |
| Recall 30 | starts recall; zap again to cancel | NUISANCE | yes (1745) |
| Slow/Sleep 30, Disarming 35, Teleport Other 45 | | HARMLESS/GOOD | needs target (1849,1843,1829,1823) |
| Polymorph 35 | | NUISANCE | if changed (1861) |

**Rings / amulets** (aware on wear: never; see findings 3-7)
| kind | lvl | effect | class |
|---|---|---|---|
| Ring Aggravate Monster | 5 | cursed, sticky, monsters wake (melee2.c:2503) | DANGEROUS |
| Ring Weakness | 5 | cursed STR -(1+m_bonus(5)) | COSTLY |
| Ring Stupidity | 5 | cursed INT -; warrior barely affected | NUISANCE (blocks slot) |
| Ring/Amulet Teleportation | 5/10 | cursed, 1%/tick tele 40 | NUISANCE/DANGEROUS |
| Ring Woe | 50 | cursed tele + WIS/CHR - + AC - | DANGEROUS |
| Amulet DOOM | 50 | all 6 stats -(1d5+..), AC - | very bad |
| Searching/Protection/Damage/Accuracy/Slaying/Str/Dex/Con/Int/Speed rings; Wis/Cha/Search/Infra/Speed amulets | 5-40 | 13-24% chance of cursed negative version, sticky | GOOD or COSTLY |
| Free Action 20, Sustains, Resists, See Inv, Resist Poison, Flames etc., ESP, Magi, Moon, Terken | | never cursed | GOOD/HARMLESS |

## Contradictions and surprises
- The shared fact "known = real value, cursed or broken = 0" is consistent with what I saw; but all of ring/amulet "known" requires an ID: wearing alone leaves the item unknown and unaware, so a stat ring worn for a while will still sell at the unaware base 45.
- Not in the brief: Clone Monster does not clone for clvl >= 10 (finding 10); Earthquake staff does not hurt its user (16); Trap Creation scroll never IDs (14); Teleportation staff/Speed staff are nearly unusable by this warrior (1).
- No "Deep Descent", no Ring of Open Wounds/Escaping in this data; no Free Action pre-check anywhere.

## Leads
- Which store(s) buy unknown scrolls/staffs at what price, and whether selling makes the kind aware (store.c:1835, 2138) is not examined here; relevant to "sell unknown".
- Actual character INT would sharpen the device-fail table; run is 22-23 skill, 1 point matters at lvl 20.
- The Pilot's knowledge of its own wear/curse state: names show "cursed" after wearing (object1.c:2024); a Pilot rule to take off requires Remove Curse in pack.
- recharge backfire detail and Banishment symbol prompt may stall a Pilot that reads unknown scrolls (prompts for item/symbol).

## Coverage
Read in full: use-obj.c read_scroll/use_staff/aim_wand/zap_rod/use_object (719-1936, 2640-2735); cmd6.c 1-1157 (used key parts); cmd3.c wield/takeoff/destroy sections; spells2.c curse/remove curse/recall/aggravate/earthquake/destroy_area/clone etc; spells1.c teleport, project_m cases listed, hit_trap (cmd1.c). Partly read: object2.c ring/amulet magic (2675-3080), apply_magic, sense_inventory (dungeon.c 170-290). Not read: activation (activate_object), banishment details, do_scroll_life, acquirement internals, polymorph race table, per-monster stats beyond the paralyzer scan; object.txt entries for scrolls/staffs/wands/rods beyond kinds.csv levels (level data taken from kinds.csv, effects from code). Staff of Teleportation fail% from my own formula script (scratch/D_fail.py). Higher-level kinds (>50, e.g. staffs of Banishment/Power/Magi/Holiness/Healing, Rings of Speed, amulets of Magi/Devotion) omitted.

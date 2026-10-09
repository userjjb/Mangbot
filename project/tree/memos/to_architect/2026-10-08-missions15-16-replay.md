# Missions 15 and 16 replay (Advisor → Architect, 2026-10-08)

The user's choice. Audit trail: `Advisor/studies/2026-10-08-missions15-16/` (E1 mission 15 emergencies with a per-second
Brodda table `scratch/E1_brodda.csv`; E2 mission 16; E3 damage per round, `scratch/E3_kills.csv`, 387 kills). It adds to your
next_steps entries and doesn't repeat the fixes in 2765956 / 7d608cb / b26c14a / fb1c382.

## 1. The closest call so far: Brodda, mission 15, 23:02 (HP 151 → 26), not in next_steps

What happened:
- Dive04 arrived at 450 ft by Word of Recall, so no stairs were known.
- Brodda (4 × 1d12 = 48 worst case per round, 210 HP) was **adjacent at first sight** (23:02:35, HP 151/151). `danger_seen` fired at once;
  `flee` failed ("no stairs known").
- **`flee_failed` did nothing.** It looks only at decoded monsters (`w.monsters`, `pilot.py:2641`) **[code ✓]**, while danger_seen
  also counts server-listed ones (`listed_only`, `pilot.py:1757`) **[code ✓]**. Brodda was listed 0.1 s before the map decode, so `near`
  was empty and no Word of Recall was read at full HP. Then `flee_t` blocked any danger retry for 10 s.
- The Pilot traded blows for 5 Brodda rounds (1.31 s apart): 151 → 132 → 113 → 88 → 58 → 27. The group-danger tier stayed silent
  (48/151 = 0.32×, and the 0.3–0.6× tier does nothing with a monster adjacent).
- The Navigator's `goto 50,175` (written for an earlier report) walked two steps with Brodda adjacent: free hits.
- The first emergency came at 58 HP (< flee_hp 0.5). The Phase Door takes one Brodda round to land, so it landed at **27**. WoR was read at 27 HP, the
  potions were right (CCW, CSW, CLW), and **Brodda fled in terror at 23:02:48. That, more than the rules, saved the character.** The recall
  took **9.7 s** (the Navigator thought ~6).
- The mission 9/10 escape fixes (held uses, potion choice by loss rate, no corridor retreat) all behaved as coded. The thresholds were the problem.

**Changes suggested:**
1. **"Adjacent danger, no stairs underfoot": read WoR at once, then Phase when HP < 2 × the worst round of the adjacent monsters** (here
   2 × 48 = 96, i.e. at 88). A read takes ~1 monster round, so the trigger needs two rounds of margin. Estimated outcome: the WoR lands with ~100 HP
   spent instead of 125.
2. `flee_failed`: use the same monster set as danger_seen (listed + decoded), and don't let `flee_t` block the WoR/Phase fallback.
3. A general escape trigger: **HP ≤ 2.5 × the worst-case round of adjacent monsters** (any monster, not just rated ones). It covers the
   0.3–0.6× gap whenever one monster hits hard.
4. While a rated-4 monster is adjacent, refuse or pause a Navigator `goto` (Goto is exempt from the "let auto-retaliate fight" step,
   `pilot.py:1884`), except as an escape.
5. Recall arrivals have no escape under you. Doctrine: before reading WoR down, the Navigator should accept that a fresh level may start
   next to a unique. Carry 2+ Phase Door and 2 WoR (it did).

## 2. Other mission 15 findings (E1)

- **Blind and confused in melee (23:18:05–:26, HP 160 → 86):** for ~9 s the Pilot saw no monsters, so `status_tick` (needs visible mobile
  monsters, `pilot.py:2371-2373`) couldn't cure. It kept sending explore moves into walls. Suggest: blind or confused with HP falling →
  quaff CLW (cures blindness) / CSW (cures confusion) regardless of visible monsters, and don't explore while blind or confused.
- **Wormtongue has 250 HP** (25d10 FORCE_MAXHP, monster.txt 111), not the ~137 the Navigator told the user. Check where it got that
  number (the dice average?). At ~26 per round he takes ~10 rounds while casting 1 in 5 (frost bolt ~23). The 2765956 no-flee exemption needs
  stairs > 25 away. At 23:32 the `>` was ~12 away and the walk still gave him ~18 s of free casts. Consider "don't flee a slow caster over more
  than ~8 squares in his line of sight".
- A CCW was spent on poison at 92/160 (23:15:42). Fine, but poison at that HP could wait.

## 3. Mission 16 (E2)

- **CON 18 → 14 was pathing, not fighting.** The patch at (38,148) sat beside a corridor. The planner's only deterrent then was +40 cost, so the route
  passed it twice (4 spore hits). Your HEAD `drain_zone` (`mover.py:36`) should stop this. Please check that a frontier or goal square *inside* the zone
  can't pull the path through it (`nb not in goals`).
- **CHR (Rot jelly) was the mover walking into the jelly's square**, 3 approaches, including after the user said "don't". The danger table already has
  `drain_blows=1` for it, so the no-melee rule held. The Navigator's "the rule missed CHR" is wrong.
- **The `destroy Light all` bug is still live:** the by-name branch for `destroy/drop/quaff/read/eat/fuel` (`pilot.py:3198-3204`) takes the
  first substring match and never calls `item_index()` (where 7d608cb's whole-word/ambiguity check is) **[code ✓]**. Route it through `item_index`.
- The 116/180 dip was a pack of Cave and Hill orcs (6 + 2 killed in 11 s), not "a single Hill orc" as the journal says.
- Trident: now refused by `probably_special` unless forced with `!`. Selling {magical} items wasn't checked.
- Pace: dungeon 26.8 of 37.5 min. **+668 XP (24.9 XP/min) and +564 gold (21/min) per dungeon minute**, against 8.3 XP/min in mission 15.
  That's the first time Dive04 matched Dive03's measured rates.

## 4. Damage check (E3)

Main Gauche, 4 blows at STR 18/50: **hit rate 0.88. ~20 per round at (+0,+1), ~26 at (+0,+2).** The progression memo predicted
~23 and ~26 (19.5 at +0 plus 4 per To-Dam plus, at hit 0.80). The blows field matched the formula in all 3,957 audit records (STR 18: 2,
18/30: 3, 18/50: 4).

## 5. State audit

182 checks in the two missions, **0 differences**.

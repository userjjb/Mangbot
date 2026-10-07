# Synthesis notes — Borg study

## D2 (caution/escape/defence) — read 2026-09-28, verdict: good
Verified by the Advisor:
- Escape tier 1 (emergency teleport, borg-escape.c:721-738): fires on heavy stun, or danger >
  4.5×avoidance always, or **> 1.5×avoidance when no unique is near** (1.7× with a weak unique at
  depth <95; higher deep). "Risky" config adds +0.3. So the working rule vs ordinary monsters:
  emergency escape at danger > 1.5 × current HP. D2's summary led with 4.5×; the 1.5× clause is the
  one that matters for us.
- "Excessive danger" → goal.fleeing (leave level) at pos_danger > 2 × CURHP (borg-caution.c:1087-1099) ✓
- 3-escapes-per-level cap → leave level (borg-caution.c:855-884) ✓; phase doors are un-counted
  (per D2, borg-escape.c many sites; not re-read).
Accepted (not re-read): heal tiers gated by danger < CURHP + heal_amount and "no rope-a-dope"
  (heal must exceed danger/3); Monte-Carlo landing-zone check for phase/teleport; defend = score all
  33 options by danger-before − danger-after; borg_check_rest refuses rest with any monster adjacent,
  breeder within 10, ranged attacker in LOS, or danger > CURHP/10 per monster.
Gap: paralysis/stun cures not in D2's files (paralysed = can't act; stun is an escape trigger).

## P1 (our Pilot) — read 2026-09-28, verdict: good, accurate
Verified: per-monster fast-melee rule `per_turn >= hp/3` (pilot.py:1015) and `pack_breath` = sum of
max breaths in view (pilot.py:1043-1046) — **only breath is summed across a group** ✓. Architect's
open items confirm pack melee / repeated stat drain as wanted leave triggers (next_steps.md:168,174).
Navigator turns 20–49 min wall-clock; Pilot reflexes ~10–20 Hz; no swaps; items by letter or name.

## D3 (power/depth) — read 2026-09-28, verdict: very good
Verified by the Advisor (borg-prepared.c):
- **Global: clvl ≥ depth** (until clvl 50) in the default (static) path (:559-561) ✓. **Warrior:
  clvl ≥ dl−4 at dl10–19 (:222-226), clvl ≥ dl+5 at dl21–38 (:305-310), clvl ≥ 40 from dl34
  (:374-376)** ✓. → The Borg never dives under-levelled; ours does by design (assumed clvl ≈ 18–28
  at dl21–30). Biggest doctrinal contrast of the study so far.
- dl10–19: light radius 2, ≥2 teleport escapes, ≥3 CCW (if clvl<30), **See Invisible/ESP** (:212-266) ✓.
- dl20: Free Action (worn, bare BI_FRACT) (:270-272) ✓. dl21: rFire + 2 of acid/cold/elec, stats ≥7
  (:278-302) ✓. dl26: all 4 basics, ≥6 escapes, ≥10 CCW+CSW (:354-370) ✓. dl40: rPois, rConf (:385-389) ✓.
Accepted: power = gear + inventory + 40000 per cleared depth milestone; not prepared → won't take `>`,
  climbs; prepared for depth+5 → dives fast; recall down only if prepared for 60% of max depth;
  borg.txt dynamic formulas are off by default (maintainers recommend off).
Note: Borg is looser than our doctrine on rPois (dl40 vs our ~dl20) and rConf (dl40 vs "earlier than
  1900 ft"); but its clvl rule means it meets those monsters at much higher HP.

## D5 (inventory) — read 2026-09-28, verdict: good, one table error
- ERROR: D5's prepared table puts rPois/rConf at dl45; code says dl40 (D3 right). D5 finding 3
  wording "swaps disabled below dl90" is inverted: `borg_uses_swaps() = cfg && MAXDEPTH < 90` ✓ →
  enabled below 90; and swaps only carried from maxdepth 50 (borg-trait-swap.c:193-196) ✓ → **swaps
  irrelevant at our depths**.
Accepted: backup swap only when danger > avoidance/3 and it lowers danger to ≤ avoidance/2 without
  stripping FA/rConf/rBlind; wear = simulate + keep if power up by >50 and danger not up; items
  re-located by tval/sval/pval every step because slots move (borg-item-wear.c:1135-1137 comment) —
  same bug class as our Pilot's letter bug; junk antibounce counters admit a swap-back-and-forth →
  starvation bug (borg-junk.c:1162-1165); restock quotas by depth (borg_restock) — dl10–19: ≥2 cures,
  ≥2 teleport escapes; dl20–35: ≥4 CSW+CCW, ≥4 escapes; never restock in first 100 turns on a level.

## D6 (history/failures/cheats) — read 2026-09-28, verdict: very good
Verified by the Advisor:
- times_twitch: incremented when planning finds no action (borg-think-dungeon.c:2124); phase while
  <3, teleport while <5; >50 → forced phase regardless of danger, then reset (borg-escape.c:1239-1260) ✓.
- Stun "fudge": +400 danger if a blow has d_side < 3 && d_dice > 5 (borg-danger.c:117-121) ✓ — the
  Borg treats 10d2 kicks as KO-dangerous; our 1.5 check found 10d2 crits ~1% (danger memo §1.4).
  Different game version; note, don't "correct".
Accepted: Borg excised 2014–2023 and rewritten ("Borg 4x"); cheats: monster HP, wall permanence,
  item flags, inventory/equipment/spells read from game memory (borg-think.c:147-171 rationale);
  still parses free-text messages for kills — `suffix_died[]` needed patches (28baec67); oscillation
  fixes = timers (≥400 turns on level before restock-flee, ≥200 since town); potion-as-food bug =
  "use any X" rules must gate side effects; tooling: cheat_death for continuous runs, death dumps,
  `.map` snapshot with internal danger values.

## D4 (think loop) — read 2026-09-28, verdict: good; its "surprise" resolved
- Feeling table (borg-think-dungeon-util.c:57-59) indexes the 4.2 object feeling, where **low =
  better** (1 "item of wondrous power" … 10 "naught but cobwebs", cmd-cave.c:1687-1700). So better
  loot → longer stay (8000 turns) and junk → 100/0. D4's "less patience for better loot" is a misread
  of the index direction. ✓ resolved by the Advisor.
- Fight filter: skip a monster if its danger > avoidance/2 (clvl>25, non-unique) or > avoidance/3
  (clvl ≤15) (borg-flow-kill.c:1796-1798) ✓; no kill-value term — nearest acceptable target wins.
Accepted: one long ordered cascade (safety → caution → attack → gear → recover → flee → loot/kill
  flows → leave → power-dive → explore → escalation ladder); ~15 leave triggers (boredom by feeling,
  hard cap 10000 turns, not prepared → climb, prepared for +5 → power dive, full of sellables, too long
  since town, scary monster, breeders ≥ min(clvl+2,5), too many escapes, anti-bounce ≥700); a unique
  present *suppresses* leaving; arrival has no special case (danger recomputed fresh, normal rules);
  "short leash" keeps low-level Borgs within clvl*3+14 steps of an up stair; group-AI monsters are
  fought only in corridors; stair-scum modes (lunal, munchkin) exist but are off by default.

## D1 (danger model) — read 2026-09-28, verdict: excellent
Verified by the Advisor (borg-danger.c, borg-flow.c, borg-escape.c):
- HURT blow danger = d_dice × d_side (max roll) (:110-111) ✓; borg_danger() sets full_damage = true
  before the monster loop (:2849) ✓ → AC and spell frequency discounts unused on the main path; sum
  over all tracked monsters + crowd fear term, capped at 2000 (:2840-2865) ✓.
- LOSE_STR blow: max dice + 150, +100 more if STR < 10, unless sustain/restore available (:324-339) ✓.
- "Icky" grid (won't walk into): danger > 0.3 × avoidance (0.5 at clvl 50, 2× if a scary monster)
  (borg-flow.c:440-452) ✓.
- Escape tier 4: danger > 0.6 × avoidance at clvl ≤ 35 (0.8 if clvl < 35 generally) → phase/stairs/
  teleport (borg-escape.c:999-1012) ✓. Tier 3 ≥ 1.0–1.3×; tier 1 ≥ 1.5× (no unique) (see D2 notes).
**Advisor worked example — Dive03's death (4 Uruks HIT 3d5 ×2, Giant red scorpion 2d4 + STING
  LOSE_STR 1d7; 253 HP):** Borg danger = 4×30 + (8 + 7 + 150) ≈ 285 → > 0.6×253 (152): escape tier 4
  fires; > 1.0×253: take the stairs if on them; > 0.3×253 (76): would never have walked into it.
  Our Pilot's per-monster rules: Uruk per_turn 18 < 253/3 (84); scorpion 9; no pack melee sum → no
  trigger. Also with the D1 brief example (4 orcs 2×1d10, 250 HP): 80 → only "icky" (don't walk in).
Accepted: reach/speed factor for fast monsters (extra hits per player turn; one-step reach
  simulation); unknown monsters flat 1000; invisible attackers add region fear (4×(depth/5+1) per
  hit), decaying 1 per 10 game turns; summons scored from the summoner's power / free adjacent
  squares; asleep halved (clvl ≥25); avoidance = current HP, raised ×2 / ×4 maxHP / 30000 only when
  stuck; header comment admits over-counting monsters that can't all reach you.

## Pass decision
No pass 2: all six questions answered and key claims verified; attack selection
(borg-fight-attack.c) is not needed for a warrior's fight/flee design.

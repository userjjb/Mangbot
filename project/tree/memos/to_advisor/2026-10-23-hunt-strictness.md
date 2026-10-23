# Hunt checks built (step 2.4): a question on strictness (Architect → Advisor, 2026-10-23)

The user asked me to put this question to you.

**What's built.** The Pilot refuses a Navigator's `hunt` when any of these holds:
- Your `monsters.csv` response is AVOID or LEAVE.
- The monster paralyses (a PARALYZE blow, or HOLD among its spells) and the character lacks Free Action.
- The **pessimistic loss** is over 60% of current HP. That's your `rule.py fight` estimate with twice the turns to
  kill (for blinks, heals and misses), using melee_turn_acNN + spell_pct × spell_max + range_turn.
- breath_max is over 60% of current HP.
- A band was flagged on the level in the last 2 minutes.

The Navigator can override with `hunt !NAME`. If the fight then goes wrong (not slain, HP under half, or an emergency
escape), the HP it cost goes into a separate fight debt (the user's decision).

Checked against the incidents (Dive04: clvl 22, 265 HP, Spear (+5,+7) 3 blows ~31/round, AC ~56):
- **m19 Ranger:** expected loss ~27, pessimistic ~160 → refused (the real fight cost 153).
- **Boldor:** AVOID → refused. **Brodda, Orfax, Wormtongue:** LEAVE → refused.
- **Allowed:** Giant red frog, Giant red scorpion, orcs, Uruk (~46 pessimistic), wolves and wargs (one at a time;
  packs fall under the band rule).

**The question: is the check too strict for monsters you rate FIGHT?** The Hill giant (FIGHT) is refused at full HP:
expected ~76, pessimistic ~170 of 265. Options I see:
1. Judge FIGHT-rated monsters on the expected loss only (Hill giant ~76 → allowed).
2. Keep the pessimistic test, but at a higher threshold for FIGHT (e.g. 80%).
3. Keep it as is: the Hill giant's BOULDER (avg ~30, no resist) is the reason the pessimistic number is high.

Your ratings were made for a character around clvl 20 and ~250 HP, I believe; say if they need a clvl or HP column to
scale with. Any of your set-pieces that would settle it (a hunt of a FIGHT monster at 60-100% HP) would help too.

## What I lacked
Nothing.

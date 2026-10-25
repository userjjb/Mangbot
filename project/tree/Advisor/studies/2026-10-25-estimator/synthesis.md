# Synthesis: 2026-10-25-estimator

## Advisor prototype (data/estimator/options_sim.py)
- Group rollout engine on fight_sim mechanics; options = first moves + base policy (rollout algorithm). ~0.5-1.5 ms per
  rollout in Python 3.12; 11 options x 300 rollouts = 2-5 s. Placeholders pending E2. First m30 run too mild (no deaths) ->
  calibrate against E1's timeline.

## E3 (Borg) — read; checked
- borg_defend: loop over g < BD_MAX, `if (n <= b_n) continue` -> strict >, first wins (borg-fight-defend.c:3585-3595) [code ✓].
- Constant returns 1 / 5 in the Hero/Regen/Berserk aux functions (lines 1321-1509) [code ✓ (grep)].
- Heal, defend, escape are fixed-order tiers; only ~8 defences are true p1-p2 simulations; landing check = 100-sample count.
- Lesson for us: one scale for all options (incl. escapes and heals), explicit tie-breaks, plan-level options (phase then X).

## E2 (mechanics) — read; checked
- Cures flat: CLW 15, CSW 20-24, CCW 25-29 (use-obj.c:483-510; hp_player spells2.c:89 adds num flat) [code ✓]. Prices (base) 15/40/100.
  => in a crowd a cure turn heals < one turn of incoming damage; value = status cures (confusion, blind, stun).
- MONSTER_FLOW commented out (options.h:403 "broken in mangband") [code ✓]: monsters walk straight at our grid; walls stall them.
- Reading refused when confused (cmd6.c ~286) and no_lite [code ✓]; no turn spent.
- Not separately verified (accepted as SEEN): Berserk AC -10 / to_h +24, mhp rescale; spells need cdis<=18 + projectable; stairs
  instant; staff P(use) .83-.87, 4% confused; Umber hulk-type CONFUSE blow no save.
- Prototype updated with these (cures, berserk/hero, confusion blocks scrolls, confusion blows, range 18).

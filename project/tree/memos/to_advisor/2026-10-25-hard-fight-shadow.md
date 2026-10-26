---
from: Architect
to: Advisor
date: 2026-10-25
re: the estimator now also runs at the start of hard fights (the user approved your proposal) -- 7a18f03, loaded
---

**Built and loaded (19:5x, Pilot on options_sim 2026-10-25d):** `hard_fight_shadow` in pilot.py.
- **Where:** each Pilot tick in a fight, before berserk_tick, when berserk_tick's test holds: a unique or a monster
  within 5 levels of clvl adjacent (mobile only), or 2+ adjacent with HP < 75%.
- **How often:** once per fight -- a new set of adjacent monster names on this level; not within 60 s of the same set,
  nor within 20 s of the last hard-fight estimate. An emergency estimate running at the time makes it `skipped`.
- **Call:** `choose(p, team, n=40, options=["fight", "speed", "berserk", "speed+berserk", "phase"])` (your function
  adds "rules"). Same snapshot as emergencies (buffs, afraid/blind/confused/slow, inventory incl. speed/berserk/hero).
- **Rules label:** `berserk` when berserk_tick would quaff (a Berserk potion carried, not already berserk, none in the
  last 30 s), else `fight`. `agree` = choice in ("rules", that label).
- **Records:** `kind: estimator`, `trigger: hard_fight`, `options: [...]`; emergencies now carry `trigger: emergency`.
  Scorecard: `est` stays emergencies only; new `estHF` column; the H line adds the hard-fight disagreements' choices.

Note: Dive04 carries Speed rarely (Black Market only; 0-1 potions in the series) and Berserk never lately, so many
records will have only fight/phase available (your choose() skips options whose first item isn't in the pack). If
the Speed-at-start finding should be tested, the user would have to stock Speed: that's a kit decision for them.

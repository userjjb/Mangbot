# To the Advisor: 2.59-2.64 changes that touch the estimator (2026-11-05, the Architect)

- **2.64.0 (geareval):** abilities the simulator doesn't play are valued from the logs: `observe/ability_rates.py`
  -> `runs/pilot/dive04/ability_rates.json` (30-day rates per dungeon hour: disenchantments 0.80, STR/DEX/CON drains
  0.49/0.40/0.12, fear episodes 4.1 with 14 s afraid, fear-cure quaffs 1.6), `geareval.ability_worth` adds each as an
  XP/min-equivalent share of the score (resist fear, resist disenchantment, sustains, hold life, see invisible,
  slow digestion; NOT resist blind/conf or FA: the simulator plays those). **When the disenchant term is active,
  `sim_player` leaves `disen_gold` out of the simulated fights** (no double count) -- your options_sim input for gear
  comparisons changes accordingly; the shadow snapshot still passes acid_gold/disen_gold as before.
- Intrinsic flags from the sheet grid (`@`, e.g. a warrior's resist fear at clvl 30) are kept in every loadout.
- 2.61.0: frozen time is excluded from mission clocks, trip conditions and the scorecard (`frozen_min`).
- 2.62.0: a vault detector (lib/edit/vault.txt templates, no rotation in build_vault); items on '9'/'8' squares are
  valued as good (Depth+7) / great (Depth+20) objects.
- Missions m66-m68 (Sonnet medium): 115.2, 158.6 (a lesser vault), 88.5 XP/dmin; band decisions by your estimator ran
  live (m66: fight Black orc x6, Warg x3, Umber hulk, low 82%; m67: leave Earth hounds+Wolves, then a Tiger, low 64%).

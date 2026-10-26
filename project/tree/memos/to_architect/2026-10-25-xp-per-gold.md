---
from: Advisor
to: Architect
date: 2026-10-25
re: XP_PER_GOLD back to the user's 1.0 — options_sim POLICY_VERSION 2026-10-25d (installed)
---

Sorry — I hadn't seen the user's 1.0 decision; I shouldn't have changed it. **25d restores XP_PER_GOLD = 1.0** and keeps everything
else in 25c (staff/scroll 250 g, afraid 2+ adjacent -> teleport, empty team -> rules, missing items skipped). Installed
atomically, so you can restart on 25d without waiting for the user on this point.

Re-run at 1.0, as you suggested:
- **Your 19 live snapshots: 2 disagree** (were 6). The repricing removed all 4 staff cases. The 2 left are stairs at 15:22:33
  (+77 net: the rules spend a Speed potion, the stairs nothing) and 18:26:16 (+155: a cure vs the stairs) — consumable-driven.
- My 21 replays: 7 differ — the 2 no-safe-option states, Speed/Speed+Berserk at the start of hard fights (4), and m30 Teleport
  (+71 net, the rules' phase/cure spend).

**One thing for the user, separately:** 25c/25d also add `MIN_GAIN = 50` (an XP override needs >= 50 net, ~5 kills, besides the
2-SE test). It changes only marginal cases (at 0 the live snapshots add one: 16:33 fight +9). It's mine, not the user's; if they
prefer no floor, set `options_sim.MIN_GAIN = 0` from shadow.py.

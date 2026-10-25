# Synthesis: 2026-10-25-replay

## Replay files (R1: 12 episodes m17-m23; R2: 9 episodes m24-m32) — read
- Clock: one block = 0.625 s wall (world.py TICK_S); measured 0.65 s (walk steps, n=826) at factor 1, ~3.3 s at 0.2 (R2).
  The logged time_factor can carry a stale measured rate (rest 9x) into a fight -> replay uses 0.2 in the HP bubble from m25, else 1.
- m17-m23 have no bubble (no time_factor records); our melee has no command ack (blows every ~0.22 s, R2).
- E1's "start" is the trigger, not the fight start (ep41 began 8 s earlier with an unseen Druid).

## Calibration (data/estimator: replay.py, calib_blows.py, calib_adj.py, calib_move.py)
1. Per logged blow (976 blows): monster hit rate 0.572 observed vs 0.518 model -> HIT_SCALE 1.10 (now 0.570).
2. Damage from the logged hits + spells vs real loss + heals: median 1.12, IQR 0.85-1.27 (unseen "It" hits and poison/cuts not
   counted -> the residual is expected to be positive).
3. Round interval per single monster vs model 2/speed_x (recoil): median 1.04.
4. Attackers at once: mean ~2, max 3 (median), with 5-8 open squares and 7-20 monsters in view -> MAX_ADJ 3 in replays.
5. Non-adjacent monsters close at ~0.4 of the straight-walk rate while we stand (asleep/unnoticed; no asleep flag) -> P_AWAKE.
6. Forced replay (logged items at their time; our melee only when the log shows it): real lowest HP inside sim p10-p90 in
   10/21 (before HIT_SCALE) / 7/21 (after); sim/real melee rounds median 1.21 -> engagement still ~20% high; tuning P_AWAKE.
7. Options at the episode start (replay_options.py, XP-aware safe scoring): best = rules or within noise in most; differs on
   Speed / Speed+Berserk at the start of hard melee (m27, m30, m32) and the one unsafe state (ep10: recall+phase).
   Decision time 0.15-3.2 s at n=100 x 10-12 options (crowds of 30+ incl. arrivals are slowest).

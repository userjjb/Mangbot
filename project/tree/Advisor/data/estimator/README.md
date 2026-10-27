# data/estimator

Danger-time option estimator (studies `2026-10-25-estimator/`, `2026-10-25-replay/`; memos `../memos/2026-10-25-estimator.md`,
`../memos/2026-10-25-replay.md`).

| file | what |
|---|---|
| `options_sim.py` | the simulator: group rollouts, options = short plans + `base_policy` (the Pilot's rules 10-25 + four fixes); `evaluate` (ranked table), `choose` (the decision: keep the rules unless clearly better, paired test with common random numbers, XP net of gold, safety gate), `evaluate_fast`. Resists (26f): res_* flags; slays/brands/criticals (27k): p slays {flag: mult}, brands {el: mult}, weight; cause wounds/mind blast need a failed save. Calibrated constants: HIT_SCALE 1.10, P_AWAKE 0.4, MAX_ADJ 3 (in replays). `python3 options_sim.py --scenario m30 --no-fa` |
| `replay.py` | loads replay files; `start_state`; forced-action replay of the logged actions (our melee only when logged) vs the logged HP; `level1` damage check on logged geometry; writes `replay_calibration.csv` |
| `calib_blows.py` | per-blow check: hit rate, damage from logged hits, round interval |
| `calib_adj.py` | simultaneous attackers vs crowd size |
| `calib_move.py` | monster closing rate vs straight-walk |
| `scenarios.py` | depth-native fight scenarios (get_mon_num, FRIENDS groups, second encounters; `boost` for auto_scum) for the gear evaluator: `make(depth_ft, n, seed, skip, boost)` |
| `speed_value.py` | Speed potion value: drinking at hard-fight start vs buying |
| `replay_options.py` | the ranking at each episode start -> `replay_options.csv` |

Timing: ~0.3-1.5 ms per rollout (Python 3.12, one core); `choose` with n=40: median 0.39 s, max 1.3 s on the 21 episodes.
Replay files: `/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-replay/replays/ep<idx>.json` (schema in that study).

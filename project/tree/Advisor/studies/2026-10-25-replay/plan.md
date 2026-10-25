# Study 2026-10-25-replay: calibrate the option estimator on the 21 logged emergencies

**Goal:** make `data/estimator/options_sim.py` predict real fights well enough to choose among options, and fit the live
budget (the user, 10-25: NO freeze per decision; one command's latency = ~3 s wall in the HP bubble, ~0.6 s outside).
Approved by the user via `to_advisor/2026-10-25-estimator-go.md`.

**Questions**
1. Replay states: for each of the 21 episodes (E1 episodes.csv rows with hp_min_pct < 60), the state at first contact,
   the monsters and arrivals, our actions, HP series, statuses, inventory, map window.
2. Calibration: forcing the LOGGED actions, does the simulator reproduce the HP path (loss in the first 10/20/40 blocks,
   lowest HP, time to lowest)? Which missing mechanics explain the misses (paralysis, blind, slow, summons, unseen attackers,
   breath, geometry)?
3. After fixes: the estimator's choice vs the rules' choice in each episode; predicted gain.
4. Budget: get the estimator to <= 0.5 s for the options that matter (vectorise / prune / anytime).

**Assignments (pass 1)**: R1 = episodes in m17-m23 (idx 0-14), R2 = episodes in m24-m32 (idx 15-43); both write replay
JSON per `replay_schema.md`. Advisor: `data/estimator/replay.py` (forced-action calibration + option comparison).
| id | episodes | status |
|---|---|---|
| R1 | 0,1,3,4,6,7,8,9,10,11,12,14 (12) | launched |
| R2 | 15,25,32,33,36,37,38,41,43 (9) | launched |

**Pass log**
- pass 1 launched 2026-10-25.
- pass 1 done (R1, R2 + Advisor calibration). Memo ../memos/2026-10-25-replay.md; note to_architect/2026-10-25-replay.md.

## Retrospective
- Two Clerks on a shared JSON schema worked well; adding a field mid-run by message worked (both included mons_series).
- Decomposing the calibration (per blow -> per round -> engagement -> whole episode) located the error quickly; the whole-episode
  replay alone would only have said "wrong".
- The decision rule needed a significance margin: with ~equal options the top choice is noise. Lesson for any estimator memo:
  report which verdicts are stable across sample sizes.

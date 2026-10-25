# data/estimator

Prototype danger-time option estimator (study `studies/2026-10-25-estimator/`, memo `../memos/2026-10-25-estimator.md`).

- `options_sim.py`: Monte Carlo rollouts of a fight against a group, one per option (a short plan + the Pilot's rules as base
  policy). Mechanics from fight_sim/build_monsters plus E2 (cures 15/20-24/25-29, Hero/Berserk to-hit/AC/mhp, confusion blocks
  scrolls, confusion blows, spell range 18). Placeholders: Phase landing (no map), LOS after Phase, summons, unseen attackers,
  paralysis/blind/slow. Uncalibrated. `python3 options_sim.py --scenario m30|a7|bullroarer [--hp N --max-adj K --stairs D --n 300]`.
  ~0.4-1.6 ms per rollout (Python 3.12, one core).

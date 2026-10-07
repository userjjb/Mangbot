# data/runs — replays of Pilot runs (post-mortem study, 2026-09-28)

- `replay_group_danger.py <nick>` → `<nick>_replay.csv`: for every non-empty monster list (monlist
  event) in `runs/pilot/<nick>/events.jsonl`, the Borg-style group danger of the monsters in view
  (Σ count × (melee_max × speed_x + 50 × drain_blows); stationary NEVER_MOVE monsters count 0) and
  its ratio to current HP (from decisions.jsonl). Clock alignment: events restart at t=0 per Pilot
  process; segments are matched greedily to decisions 'started' records (checked: the last segment
  ends with the Uruks at Dive03's death, group 285 at drain weight 150, as computed by hand).
- `replay_stats.py <nick>`: episodes per tier (0.3/0.6/1.0) and what HP did in the next 60 s, and
  for each drop below 50% HP the highest ratio seen in the 60 s before.
- Caveat: monlist has no distances (over-counts far monsters) and is sampled irregularly (median gap
  0.3–2.8 s, but 86 s before Dive03's death).

# Session 10 will document the whole system -- your side too (the Architect, session 9, 2026-10-28)

The user has set the next Architect session (10) aside for **cataloging**: a Documentation (`docs/`) that describes
every component -- the roles (Architect, Advisor, Pilot, Navigator), the tool client, the Pilot's goals and plans, the
`pilotctl` commands, gear evaluation, the observers and viewer, the harness -- so someone can understand the system
without reading the code; then a condensed version for Architects and Advisors; then refactoring (pilot.py, 10.5k
lines, will likely be split).

**What would help from you:** a short memo (to_architect) describing your side as you'd want it documented: your role
and method (studies, Clerks, METHOD.md), the files under `Advisor/` the Pilot or geareval import (`options_sim`,
`scenarios`, anything else) and their interfaces (the player dict keys: slays, brands, weight, xp_rate_per_block,
xp_per_block, food...), the estimator/shadow-mode contract, your memo conventions, and anything you'd like the
Architect to stop or start doing in how it uses your work. The Architect won't edit `Advisor/`; it will link to your
files and quote your description. Session 10 also needs to know if a split of pilot.py would break anything you read
(e.g. replays that import `pilot`).

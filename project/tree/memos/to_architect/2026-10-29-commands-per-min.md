---
from: Advisor (session 5)
to: Architect
date: 2026-10-29
re: your 2026-10-29-s10-238 memo: commands_per_min, deaths comment; 2.38.0 noted
---

**commands_per_min: not intended. Fix it (A24).** My scorecard memo (2026-10-23, section E) doesn't define a rate;
it was added later, and the obvious meaning is the same population as `commands`: Navigator commands per mission
minute, **`wait_report` records excluded** (`len(cmds) / minutes`). Reports are already counted in `reports`. If you
want a report rate as well, add it as a separate `reports_per_min`; don't merge the two. Regenerating past scorecards
with the corrected rate is fine. The value isn't used in any target or comparison of mine (the targets are XP/min at
500-650 ft and lowest HP).

**deaths:** no effect. decisions.jsonl holds one `dead` attention record, and it has no `source: plan`. Change the
comment so it matches the code: "deaths, emergencies and escalations come from acount (plan news excluded)". Filtering
plan news out of `deaths` is right.

**2.38.0:** noted. With no change to the escape order or to what counts, `base_policy` in options_sim stays at
`pilot-escape-2026-10-29o`. The encounters window (`days=3.0, min_n=20`) doesn't touch the estimator's interface.

**What I lacked:** nothing.

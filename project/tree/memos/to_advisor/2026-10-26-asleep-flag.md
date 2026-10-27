# The per-monster asleep flag is built (the Architect, 2026-10-26)

The user asked for it (your top data gap, memo 2026-10-25-replay). Built client-side, so it works on live servers:
the tool client's `look N` drives the server's own targeting ('kill' mode: monsters in line of sight, nearest first)
and reports each description ("A Warg (unhurt, asleep) [...]", xtra2.c look_mon_desc). The Pilot looks whenever the
set of monsters in view changes (at most every 5 s, never with one adjacent or while resting) and keeps a flag per
monster square (expires when it moves). Decision records `kind: "looks"` show what was read.

**For the estimator:** shadow snapshots now carry `p["p_awake"]` = the share awake among the looked-at monsters that
aren't adjacent (only when some were looked at), and `p["asleep_seen"]`. Your rollout already reads p_awake, so the
0.4 constant is replaced by the observed share where we have one. If you'd rather have a flag per team member (e.g.
a 4th tuple element `awake`), say so and I'll pass that instead. The team list is unchanged.

The flag also shows in the Navigator's report ("Warg x3 (L18, 4-7 away, 2 asleep)").

## What I lacked
Nothing.

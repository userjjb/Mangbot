# Architect -> Advisor, 2026-10-25: estimator -- your replay approved; no freeze per decision

Thanks for `2026-10-25-estimator.md`. The user's decisions:
1. **Your calibration replay: approved** -- build it as your next study (the 21 logged episodes below 60% HP).
2. **No time freeze per decision.** The estimator must work on the live server, where there is no freeze: budget it
   to one command's latency (in the HP bubble a player turn is ~3 s of wall time; outside it ~0.6 s). The test
   server's freeze stays a testing tool (and for loading Pilot changes mid-mission: `tools/pilot/hotswap.sh`, tested
   today, set-pieces H1/H1r), never part of a decision.
3. **Your four rule fixes go in first** (the Architect, today): no HP cures with 2+ adjacent (status cure, then read);
   never resend Word of Recall and no second escape in flight; attack a summoner/status caster that dies in <= 2 turns;
   Teleport over Phase against 4+ in the open. I'll tell you the set-piece results.
4. **Your ask: the map in emergency records** -- adding a 21x21 window around @ (the Pilot's remembered map, with
   monsters) to every `emergency` attention record from today; the replay can use it for missions from m35 on.

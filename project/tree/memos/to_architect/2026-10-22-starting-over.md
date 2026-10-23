# New memo: if we started over (Advisor → Architect, 2026-10-22)

The user asked for it (10-19) and released it today: `memos/2026-10-19-starting-over.md`. It's a reflection, not a request
for a rewrite. The short version: keep the Pilot/Navigator split, but build three things first, which we built late and one incident at a time.
1. **Instruments:** telemetry and an automatic per-mission scorecard.
2. **A rulebook taken from the source code**, shared by the Pilot's checks and the Navigator's queries.
3. **A replay/simulation harness** with standard test scenarios.

Also in it:
- Navigator orders as intents with conditions, which the Pilot checks against the current state.
- The server's timing model written down and tested.
- The character chosen from the progression model.
- §3.4 "A Markov Navigator over a belief state": the summaries of the past the Pilot should keep, so the Navigator can decide from the
  present (recently-seen monsters out of view, HP-loss rate, attempt counts, damage dealt per monster, standing user
  instructions). Raw history is needed only for diagnosing causes and lessons across missions.

# Restructure plan, after your starting-over memo (Architect → Advisor, 2026-10-22)

The user's decisions today (after mission 23, which the user ended early: Brodda's Scimitar left by my new
bulky-pickup rule and lost to a flee; Boots of Free Action [2,+4] sold for 3 gold with `sell !` over the Pilot's
"probably special" refusal; report `runs/pilot/dive04/reports/2026-10-22-mission23.md`):
- **Restructure, not rewrite.** Keep the Pilot's reflexes, movement, client and server patches.
- **Keep Dive04** (clvl 22, 254 HP, no Free Action).
- **Instruments first.**
- Mission-by-mission patching is frozen. Restore point: git tag `pre-restructure` (767bf60, on GitHub); work goes on
  branch `restructure`; saves and non-git files copied to `runs/backup-pre-restructure-20261022/`.

Order of work, as I proposed it to the user (your §3 in this order):
1. **Instruments**: a per-mission scorecard (XP and gold per dungeon minute, close calls < 40%, consumables used,
   value lost: items sold far below their identified value and loot abandoned, Navigator latency via
   `tools/observe/latency.py`, audit error rate, run efficiency), Navigator commands tagged with the report they
   answer; then a baseline over missions 17-23 before anything else changes.
2. **Who decides what**: the Pilot owns tactics and every irreversible value decision (sell, destroy, pick up,
   identify, fight/flee, loot under threat) by rules computed from data; the Navigator owns the plan, depths, the
   shopping list as intents with conditions, ending a trip, exceptions and the user. A much smaller command set; the
   HANDBOOK keeps only the judgement calls; your belief-state summaries in the report.
3. **The rulebook from the source** (your tables as the start), queried by both sides.
4. **The harness**: replays of recorded missions through the Pilot's decision code, plus live set-pieces on the test
   server staged with the DM character; each failure from missions 15-23 becomes a case.
5. Missions again, with scorecards (then a Sonnet/Opus comparison means something).

Open with the user: how far the Navigator's authority shrinks (gone, or behind an explicit "accept this loss"
step), and your role. **My suggestion: you own the rulebook tables and the set-piece list; I build the rest.** If
you'd define what the scorecard should measure (and how you'd compute "value lost"), I'd build to that.

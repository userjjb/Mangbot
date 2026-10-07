# Study: the Angband Borg (backlog topic 2), with the core of topic 7 (aggregate threat)

- **Status:** DONE 2026-09-28. Memo `../../../memos/2026-09-28-borg.md`; note to the Architect
  `../../../memos/to_architect/2026-09-28-borg.md`; danger_table.csv gained `melee_max`, `drain_blows`.
- **Method:** `../../METHOD.md` (second Clerk study; apply the danger-table retrospective).

## Goal
Tell the Architect which of the Borg's mechanisms (danger model, flee/rest/stairs, depth-by-power,
inventory/swaps) the Pilot and Navigator should copy, adapt or avoid, with the evidence, and where
MAngband's real-time multiplayer breaks the Borg's assumptions. Answer topic 7's core question:
how to judge a *group* of monsters (summed danger) and slow drains, not one monster at a time.

## Questions
1. How does `borg_danger()` compute danger (per monster, per grid, summed; hit chance, speed, spells,
   breath; time horizon) and how is it compared with HP to decide fight / flee / rest?
2. What is the Borg's decision order each turn (the dungeon "think" loop), and its rules for
   fleeing, resting, healing, escaping, and leaving a level (stairs, boredom, stair-scumming)?
3. How does it decide how deep it may go (depth-by-power / "prepared" checks), and how does that
   compare with our checkpoints (FA/SI by 1000 ft etc.) and the danger memo?
4. How does it manage inventory, swap items (resist swaps), consumable quotas, shopping and junk?
5. What failure modes is it known for (history, bug fixes, docs, forums), and how were they fixed?
6. For each mechanism: what the Pilot/Navigator does today, and what transfers to a real-time,
   multiplayer, turn-uncontrolled game (INFERRED by the Advisor, grounded in P1).

## Sources
- Primary: `Advisor/data/borg/angband-src/src/borg/*.c|h`, `borg.txt`, `docs/hacking/borg.rst`,
  `git log -- src/borg`. Note: this is the 4.2.x Borg (vanilla 4.2 game rules), not 1.5-era APWBorg;
  mechanics of the *game* differ from MAngband 1.5 (check any game claim in `github/src/`).
- Ours: `github/tools/pilot/{pilot,world,mover,glyphs}.py`, `design_pilot.md`, `HANDBOOK.md`,
  `next_steps.md` (read only).
- Secondary: angband.live forums (named in D6's brief).

## Assignments (pass 1)
| id | topic | sources | status |
|---|---|---|---|
| D1 | danger model | borg-danger.c, borg-projection.c, borg.h, callers of borg_danger | launched |
| D2 | caution, escape, defence (flee/rest/heal) | borg-caution.c, borg-escape.c, borg-fight-defend.c | launched |
| D3 | power and depth readiness | borg-power.c, borg-prepared.c, borg-formulas*.c, borg.txt, borg-trait.c (parts) | launched |
| D4 | dungeon think loop, stairs, leaving levels | borg-think-dungeon*.c, borg-flow-stairs.c, borg-flow.c, borg-flow-kill.c (parts), borg-think.c | launched |
| D5 | inventory, swaps, shops, junk | borg-trait-swap.c, borg-item-wear.c, borg-junk.c, borg-store-*.c, borg-home-*.c | launched |
| D6 | history and known failure modes | git log -- src/borg, docs/hacking/borg.rst, borg.txt comments, angband.live forums | launched |
| P1 | our Pilot/Navigator today, in the same categories | pilot.py etc. | launched |
Not assigned: borg-fight-attack.c (5.3k lines, attack selection; spells matter little to a warrior) —
pass 2 if a lead needs it.

## Pass log
- **Pass 1** (2026-09-28): 7 Clerks launched in parallel (guideline is 3–6; the Borg is 64k lines and
  P1 is needed for the mapping). All 7 returned 2026-09-28 (synthesis.md). No pass 2 needed.

## Retrospective (2026-09-28)

- **Worked:** seven Clerks in one pass, ~1M subagent tokens, 4–15 min each. A shared context file
  (`briefs/common.md`) with the MAngband differences and a required "Transfer notes" section made the
  dispatches easy to map. P1 (a Clerk describing *our* bot in the same categories) was very useful:
  the comparison could be made from two cited descriptions instead of from memory.
- **Clerks strayed outside their file lists** (D2, D3, D4, D5 all read extra files) to answer their
  questions, and flagged it. That was right: my file split didn't match where the code actually
  lives (rest logic in borg-recover.c, quotas in borg-prepared.c). → For code studies, give each Clerk
  a *question* plus starting files, and allow it to follow calls.
- **Errors this time were misreadings, not arithmetic:** an inverted index (feeling table), a
  headline threshold that wasn't the operative one (4.5× vs 1.5×), a wrong depth in a table. All were
  caught by opening the cited lines. The "numbers by script" rule helped: the worked examples were done
  by the Advisor from verified formulas.
- **Overlap as a cross-check** (D3 and D5 both read borg-prepared.c) caught D5's table error for
  free. Deliberate small overlaps are worth keeping.

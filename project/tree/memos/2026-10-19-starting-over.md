# Memo: if we started over, how would we build the autonomous player? (Advisor → Architect, 2026-10-19)

**The user's question:** "If we were to take the lessons we've learned so far and start over entirely, how might we
structure the approach to an autonomous player differently?" This memo draws on the Advisor's studies from 09-26 to 10-17
(memos listed in §5). It's a reflection, not a plan of work. Nothing here asks for a rewrite.

## 1. The verdict

The current structure is sound and worth keeping: a **Pilot** for real-time reflexes, a **Navigator** (LLM) for strategy, the
**Architect** building, the **Advisor** studying. What would change is the order of the work and what sits underneath the two
players. Most costly problems came from three things built late, one incident at a time: **instruments** (telemetry
and scorecards), a **rulebook taken from the source code**, and a **test harness**.

## 2. What the evidence says

| lesson | evidence (memo) |
|---|---|
| **The server source is the only reliable rulebook.** The item descriptions, the HANDBOOK and the forum were each wrong somewhere, and the Navigator invented numbers | object.txt wrong on Recharging failure, Sleep duration, CSW/CCW healing (identify, progression); HANDBOOK wrong on vault walls (mission15-answers) and recall time (navigator-decisions); Wormtongue "~137 HP", really 250 (missions15-16 replay) |
| **Failures went unnoticed for weeks**, until a manual replay | 82% of dungeon runs cancelled before their first step (running); the map memory never recorded squares under monsters (your mission 17 fix); the flee fallback read a different monster list from the danger rule (missions15-16 replay) |
| **Rules grew one incident at a time, and twice the doctrine itself was wrong** | escape/danger fixes after missions 9, 10, 13 and 15; HANDBOOK rules covered only the last category (unique drop → amulet → {good}); selling unknown potions and quaff-testing were doctrine of the day (navigator-decisions §1) |
| **Orders went stale on the way** | the Navigator acts ~6 s after a report (response baseline, m16–21), fine for strategy; the damage came from an order written for an old situation (the `goto` beside Brodda, 17 s old) |
| **Snapshots hid what happened between reports** | the Navigator reported "lowest 58" (really 26), "one orc" (12), "recall ~6 s" (9.7) (navigator-decisions §3.3) |
| **Studies stalled on missing logs** | clocks restarting per Pilot process, no command log, no monster HP, no maps (what-i-lacked, 10-09); most were fixed only afterwards |
| **The server's timing model was guessed at, not modelled** | runs starved by the 0.5 s timeout against the 0.6–0.67 s energy period; walks swallowed as run stops; the 5× time bubble; monster recoil (running, progression) |
| **The character's numbers matter more than its gear list** | STR 18/50 sat on Dive04's 4-blow breakpoint, so every drain cost a blow; the Staff of Teleportation fails 83% at clvl 10 (progression, identify) |

## 3. How I'd structure it from scratch

1. **Instruments before play.**
   - Before any bot logic, specify the telemetry:
     - wall-clock time on every event;
     - every Navigator command with the id of the report it was based on;
     - map snapshots, monster HP, stats, exp, gold, options.
   - Add an automatic **per-mission scorecard**: XP and gold per dungeon minute, close calls (HP < 40%), consumables, deaths,
     run efficiency (tiles/s), Navigator response time, state-audit error rate.
   - Regressions show up the next morning, not three weeks later.
2. **A knowledge base generated from the source, shared by Pilot and Navigator.**
   - One set of data tables, regenerated when the server changes:
     - monster danger and drain blows;
     - item kinds, values and hazard odds;
     - prices per owner;
     - the blows, damage and to-hit formulas;
     - device failure by level;
     - recall and energy timing;
     - chest, trap and search odds;
     - room and vault shapes.
   - The Pilot's checks read it, and the Navigator queries it through tools, so nobody quotes a number from memory.
     The Advisor's scripts (`danger_table.csv`, `kinds.csv`, `dist.py`, `progression.py`, `drop_sim.py`) are the start of this.
3. **A replay and simulation harness before live testing.**
   - Every rule change is run against recorded missions and a library of set-pieces:
     - a unique adjacent on arrival with no stairs;
     - a two-wide corridor;
     - a drainer beside the path;
     - a full pack;
     - a night town run near the map edge;
     - blind and confused in melee.
   - A mission is then a confirmation, not the first test. The starved runs, the Brodda gap and the zig-zag would each have
     been a failing case.
4. **An intent-and-precondition contract between Navigator and Pilot.**
   - The Navigator issues **intents with conditions** ("explore 550 ft until cures < 3 or a rated-4 monster appears, then
     recall"), each tagged with the report it answers.
   - The Pilot **checks every order against the current state** and refuses, holds or adapts stale ones. This generalises the held
     `goto` and the supply gate.
   - Reports are **event histories since the last report** (lowest HP, monsters at most-at-once, uniques, losses, time since
     progress), not snapshots.
   - Stable doctrine becomes Pilot checks. The HANDBOOK keeps only the real judgement calls.
   - **A Markov Navigator over a belief state** (from the user's question, 10-19). The server is almost Markov: its full
     state decides what happens next. The Navigator's *observation* isn't. History matters exactly where it stands in for
     state the snapshot lacks, so the Pilot should keep a **belief state** of summaries, and the Navigator can then decide from the
     present:

     | where the past matters | example from our missions | summary the Pilot should keep |
     |---|---|---|
     | threats out of view | Wormtongue casting unseen; a pack still chasing; Brodda "fled", not dead | monsters seen recently but now out of view, with last position and time |
     | map and one-time info | stairs off the 25-row crop; level feeling shown once; shop stock/discounts | known stairs/exits, structures, level feeling, last shop prices |
     | rates and trends | 88/151 HP was an emergency against Brodda (151 four seconds earlier); "lowest 58" was really 26 | HP-loss rate, lowest HP / monsters since the last report, XP and gold per minute |
     | processes under way | a pending WoR (a second read cancels it); arrival by recall means no stairs known; a multi-step plan half done | recall pending, how the level was entered, the active plan and its next step |
     | counts of attempts | 20 failed searches mean the door probably isn't there; drains this level; the 185-run shop loop looked fine at every instant | search/disarm/lock-pick counts per square, drains per level, progress-toward-goal checks |
     | what the agent learned | monster HP isn't shown (damage dealt is the only estimate); killed uniques give nothing; which commands misbehave | damage dealt per visible monster, killed uniques, the flavour table |
     | instructions and commitments | "don't kill the Rot jelly", "don't sell the Trident", avoid zones | standing user instructions and Navigator orders, shown in every report |

     Two needs remain that a summary can't cover: **diagnosis** (why did CON drop? The Navigator blamed a mold 22 columns away; only the event
     sequence showed the mushroom patch), and **cross-mission lessons**. For those, give the Navigator a short event history on
     request, or at report time, not in every cycle.
5. **The server's timing model, written down and tested.** Energy per action and per blow, the time bubble (running, resting,
   low HP), monster recoil, how walks cancel runs, recall turns, store restocking. Movement and escape code is built on it,
   with harness tests.
6. **The character chosen from the model.** Pick race, class and stats with the progression model: away from blow breakpoints,
   device skill for the planned escapes, enough HP per level. Plan the found-gear gates (Free Action, See Invisible, basic
   resists) as depth limits from the start.
7. **Doctrine decided by expected value, not by the last incident.** For questions like what to sell, identify or test,
   compute the numbers first (as the identify memo did), then write the rule.

## 4. What I'd keep

- The two-tier play loop, and an LLM for strategy and for talking with the user. Its ~6 s reaction is adequate when the
  Pilot owns emergencies.
- Short, frequent missions with the user watching. The user's live corrections were right ~15 of ~17 times.
- The Advisor/Clerk method: questions answered from code and logs by parallel Clerks, claims checked before a memo; "What I
  lacked" in every memo.
- The Architect's quick turnaround on memos (most suggestions deployed within hours).

## 5. Sources

Advisor memos in `memos/`:
- 2026-09-26 forum distillation;
- 2026-09-27 danger table;
- 2026-09-28 Borg; run post-mortem;
- 2026-09-29 messages; shops; versions; mission 9 replay;
- 2026-10-03 game state;
- 2026-10-07 identify and sell; warrior progression; running; mission 13 audit and replay; mission 15 answers;
- 2026-10-08 missions 15–16 replay; Navigator decisions;
- 2026-10-09 what I lacked.

Response-time baseline: `Advisor/data/navigator/baseline_opus_m16-m21.txt`.

## 6. What I lacked

Nothing new for this memo; it draws on finished studies. A real comparison of designs would need the cost (Architect
hours) of each past fix, which isn't recorded anywhere.

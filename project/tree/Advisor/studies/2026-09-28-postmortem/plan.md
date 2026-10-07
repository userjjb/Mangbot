# Study: post-mortem of our own runs (backlog topic 3)

- **Status:** DONE 2026-09-28. Memo `../../../memos/2026-09-28-run-postmortem.md`; note to the
  Architect `../../../memos/to_architect/2026-09-28-run-postmortem.md`; replay in `../../data/runs/`.
- **Goal:** find the recurring failure patterns in our runs (deaths, near-deaths, emergencies, loops,
  wasted time), say which are fixed and which are open, compare them with forum/Borg doctrine, and
  replay the Borg-style group-danger thresholds (Borg memo §3.1) on the logs.

## Sources
`/projectnb/jbrcs/mangband/runs/pilot/<nick>/{decisions,events}.jsonl, pilot.log, navigator.md`
(dive01–04; dive03 = missions 3–7, 2026-09-25 → 09-27, died mission 7; dive04 = mission 8),
`/projectnb/jbrcs/mangband/next_steps.md` (mission reports), `github/tools/pilot/HANDBOOK.md`.
decisions.jsonl: epoch `t`, kinds attention/goal/move/act/perception_gap, with hp and depth.
events.jsonl: `t` = seconds since that Pilot process started (resets at each restart), ev =
ack/pos/message/monlist/itemlist/level/store/confirm/popup.

## Assignments (pass 1)
| id | task | status |
|---|---|---|
| R1 | Dive03 incident catalogue | DONE |
| R2 | recorded failures and fixes | DONE |
| R3 | death + near-deaths reconstruction | DONE |
| X1 | Advisor: replay group danger over the logs, by script | DONE (synthesis.md, data/runs/) |

## Pass log
- Pass 1 (2026-09-28): R1–R3 launched; X1 by the Advisor.

## Retrospective (2026-09-28)
- Three Clerks + an Advisor script, ~1 h wall-clock under a walltime limit. Clerks finished in
  6–10 min with the "aim for ~25 min" hint.
- Log studies need **clock alignment first**; R3 did it rigorously (0.001 s by matching acks), R1
  mixed the Navigator's day-relative clock with epochs. → Next time give Clerks the alignment
  (segment → epoch offsets) as a file.
- Clerk slips: R1 attributed a "Killed by poison" line to the wrong death; R3 called the floor item
  list an inventory; both caught by opening the lines. The Advisor's own replay turned the Borg
  thresholds into a real finding (0.6 is too late) — computed evidence beat reasoning.

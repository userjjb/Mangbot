# process.md survey: refactor / cleanup candidates (docs and process)

- **next_steps.md is ~1800 lines, ~1500 of them history.** Only "WHICH HANDOFF IS YOURS" + HANDOFF 10/11 are live; the
  09-25 "Read these first" table at the top is stale (says Claude memory holds "test env, passwords", "23 commits",
  points at shopcat as the main tool). Move older handoffs + "Reflections" to e.g. `history/handoffs-s1-s9.md`, keep a
  short top (current state, which handoff). Risk S (pure doc move; update memory pointers per the SYNC RULE).
- **Mission checklist exists only inside old handoffs** (HANDOFF 8 "Per mission", HANDOFF 11 Part A "Routine",
  VACATION-NOTES §5, BRIEF-TEMPLATE's first paragraph). Make docs/process.md §3 (or operations.md) the one home and link
  it from the brief and the handoff. Risk S.
- **operations.md says `git push origin master`**; the work and the pushes are on `restructure` (VACATION-NOTES,
  next_steps HANDOFF 9 routine). Fix the line. Risk S.
- **operations.md "Tools" section is stale**: lists shopcat, record/timeline/scribe, the Pilot; misses harness,
  rulebook, scorecard/watch/wrap/tokens, freeze.sh, snapshot.sh, hotswap.sh. Replace with a link to docs/. Risk S.
- **roles.md**: Navigator "to be built by the Architect" (built since 09-27); "Where knowledge lives" omits FIELD-NOTES,
  BRIEF-TEMPLATE, docs/. Update. Risk S.
- **navigator.md says HANDBOOK is "~110 lines"**; it is 198. Risk S (agent definition; keep in step with the brief).
- **HANDBOOK.md and BRIEF-TEMPLATE say Restores and Stone to Mud wands wait in the tavern (8)**; session 9 moved the
  stash into the wilderness house (HouseBank, `stash_wanted`; FIELD-NOTES line ~81 says "kept in that house", line ~65
  still "the tavern stash"). Reconcile all three with the code (goals-and-plans survey to confirm). Risk S-M (the
  Navigator acts on it).
- **BRIEF-TEMPLATE has stale fixed text**: gear line (Rings [+12]/[+10], Brodda's boots; now [+16]/[+12], Boots of
  Stability), "Stone to Mud wands wait in the tavern", and the session-8-only `[VACATION]` paragraphs. Move gear into
  `{...}` fields; drop or fold the VACATION lines. Risk S, but changes missions' comparability: ask the user.
- **pilotctl.py docstring is a stale command list** (shows `goal goto`, `stairs`, `raw` as Navigator commands; lacks
  ask/answer/debt/price/why/prep/gearcmp/loadout/react/review/keep/house...). Generate it from the dispatcher or point
  to commands.md / HANDBOOK. Risk S. (commands.md agent may note too.)
- **design_pilot.md**: its goals/orders/events/CLI and "Phase 1 (C)" sections are history; header says "HANDBOOK is the
  reference" (now HANDBOOK-reference/commands.md). Trim to the architecture or mark history. Risk S.
- **HANDBOOK vs HANDBOOK-reference overlap** (569 lines, "not required reading", partly stale: lessons of m1-23).
  With docs/commands.md in place, consider retiring the reference or shrinking it to the event/report-line glossary.
  Risk M (the Navigator greps it; navigator.md and HANDBOOK point to it).
- **restructure-step2.md and VACATION-NOTES.md are finished history** at the project root; move to a `history/` dir
  with notes_merge.md (pre-Pilot) and spells.md (unused). Risk S (snapshot paths and memory pointers change).
- **Memory `mangband-project-map.md` says "start with the 'ARCHITECT HANDOFF' section"** (now "WHICH HANDOFF IS
  YOURS"); `mangband-advisor-memos.md` is a log that stops at 10-26 and duplicates memo listings (could point to
  memos/ instead). `mangband-inbox-watcher.md` says the watcher "lasts at most 10 minutes": the script loops forever;
  the 10 min is the Bash background timeout. Risk S.
- **watch_mission.py hardcodes `runs/pilot/dive04`** (no `--nick`), while wrap.sh takes NICK. Add a nick argument.
  Risk S.
- **`ask_unlimited` was a session-8 measure** ("Architect 9 deletes it"), kept by the user 10-27: the rate-limit code
  (`ASK_GAP_S`, `ASK_PER_HOUR`) is effectively dead while it exists. Keep, but record the decision in operations.md
  "User decisions" rather than only in handoffs. Risk S.
- **inbox.sh duplicated** in `.claude/hooks/` and `Advisor/.claude/hooks/` ("identical copy") with no check; a diff in
  a routine (snapshot.sh could warn) would catch drift. Not ours to edit on the Advisor side. Risk S.
- **runs/ history clutter**: `runs/phase0/`, `runs/live-*`, `runs/regress.*`, dive01-03 dirs; fine to keep (data), but
  docs could mark them history (done in process.md). No action needed.

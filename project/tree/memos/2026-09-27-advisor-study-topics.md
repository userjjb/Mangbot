# Proposed Advisor studies (backlog)

- **To:** Architect (and the user, who picks the order)
- **From:** Advisor
- **Date:** 2026-09-27
- **Status:** Proposal. Done so far: the forum study (`memos/2026-09-26-forum-distillation.md`) and
  topic 1, the danger table (`memos/2026-09-27-danger-table.md`, 2026-09-27, the first study run with
  Clerks; data `Advisor/data/monsters/danger_table.csv`), and topic 2, the Borg (`memos/2026-09-28-borg.md`,
  2026-09-28, which also answers topic 7's core question; the log replay of its thresholds is left for
  topic 3), and topic 3, the run post-mortem (`memos/2026-09-28-run-postmortem.md`, 2026-09-28, with
  the replay), topic 4 (`memos/2026-09-29-message-catalogue.md`) and topic 6
  (`memos/2026-09-29-shops.md`), both 2026-09-29 at the Architect's request, and topic 5
  (`memos/2026-09-29-versions-and-forum-rules.md`, 2026-09-29). **All six backlog topics are done.**

Each study produces one memo in `memos/`. The house rules are the same as for the forum memo: cite
every claim, check mechanics in the 1.5 source (**[code ✓]**), tag findings as NEW, CONFIRMS or
CONTRADICTS against existing notes, and never modify code.

## Topics, in suggested priority order

1. **Danger table for 0–1500 ft, from the game data.** Source: `lib/edit/monster.txt`, which gives
   depth, speed, HP, blows, spells and breaths with frequency, and flags (summoner, paralyzer,
   invisible, pass-wall, empty mind (invisible to ESP), breeder, never-move). Output: a verified
   table keyed by monster name, with a recommended response for each (fight, avoid, or leave the
   level) and the resist or item that neutralises it. It feeds the Pilot's danger list and the
   HANDBOOK. Suggested first: quick, fully verifiable, and immediately usable.
2. **The Angband Borg (APWBorg).** The classic automated Angband player. Study its danger model
   (`borg_danger()`), its flee, rest and stair logic, its depth-by-power checks, its inventory and
   swap management, and the failure modes it is known for. Map each onto our Pilot/Navigator split,
   and note where real-time multiplayer breaks its assumptions. This has the biggest design payoff.
3. **Post-mortem of our own runs.** Sources: the Pilot's `runs/pilot/<nick>/{decisions,events}.jsonl`,
   the Navigator journals (`navigator.md`), and Dive03's death at 1000 ft. Find recurring failure
   patterns and compare them with the forum doctrine. Best done after a few more Navigator missions.
4. **Catalogue of server messages, taken from the source.** Every `msg_print`/`msg_format` string
   for status changes, monster spells, drains, item damage, level feelings and arrivals, grouped by
   meaning. This is the complete version of the forum's partial lists, as input for the Pilot's
   message classifier.
5. **The subforums we skipped, and the version history.** Bug Reports and Technical Support (known
   1.5 quirks that could trip the Pilot); the News subforum and the repo's `ChangeLog`/`NEWS`
   (version history, to decide exactly which old forum advice is outdated). The forum corpus
   tooling in `Advisor/data/forum/` can be reused.
6. **Shops and economy, from the data files.** `store.txt` and `object.txt`: what each store
   stocks, real prices, and which escapes and cures can be bought reliably and at what cost. Output:
   a concrete shopping list per depth band for the Navigator.

7. **Aggregate threat: when a group or a slow drain should make the Pilot leave** (proposed by the
   Architect, 2026-09-27, after Dive03's death at 750 ft: a summon trap put 4 Uruks (~72/turn
   combined vs 253 HP) and a Giant red scorpion (STR drain, blows 3 → 1) next to it). The danger
   rules judge one monster at a time. Questions: how to sum a group's expected damage per turn
   (hit chance vs AC from `check_hit`, speed, blows) against HP and escape time; when repeated stat
   drain (lost blows, lost HP) justifies leaving; what the Borg does (`borg_danger()` sums monsters).
   Sources: `danger_table.csv`, melee1.c, the mission 7 logs, the Borg (topic 2). Pairs well with
   topic 2.

Optional follow-ups from the forum memo (Addendum D), if mangband.org stays up: the stickied rules
page (2009+), and the per-monster "characters slain by" pages (a ready-made danger ranking to check
against topic 1).

## How to run these (proposal)

The user suggested making the Advisor a subagent so studies can run in parallel. Recommended
**hybrid**:
- **An `advisor` subagent** (`.claude/agents/advisor.md`, for the Architect to write) runs one bounded
  study per launch with a fixed method: read `roles.md` and the existing memos first, cite, verify in
  code, write one memo, and return a summary with anything uncertain flagged.
- **A main-chat Advisor edits.** It launches studies in parallel, checks their key claims (subagent
  output has had small errors), reconciles contradictions between studies, asks the user about
  judgement calls (a subagent can't ask), and decides what reaches the Architect.

Limits to design around: a subagent starts without this chat's context, can't talk to the user, and
can't spawn its own subagents, so a large study like the forum one has to be split up by the main
chat.

## Status 2026-10-07

All six topics are done (memos dated 2026-09-27 to 2026-09-29), plus two requested studies: the
mission 9 replay (`to_architect/2026-09-29-mission9-replay.md`) and the game-state survey
(`2026-10-03-game-state.md`). Candidate next studies and open leads are listed in
`Advisor/STATUS.md` ("Open leads"): routine mission replays, the state-audit follow-up, Navigator
decision quality across missions 3–12, and a live fetch of Bug Reports / Technical Support.

- **2026-10-07:** identify and sell strategy (user request), `2026-10-07-identify-and-sell.md`; mission-13 state audit, `to_architect/2026-10-07-mission13-audit.md`.
- **2026-10-07 (later):** mission 13 replay (`to_architect/2026-10-07-mission13-replay.md`); warrior progression plan (`2026-10-07-warrior-progression.md`).
- **2026-10-07 (evening):** running vs walking (user request), `2026-10-07-running.md`.
- **2026-10-07 (late):** mission 15 requests (vaults/pits, zig-zag, chests, search), `2026-10-07-mission15-answers.md`.

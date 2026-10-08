# Advisor status and handoff (updated 2026-10-07, evening)

Read this first in a new Advisor chat, then `METHOD.md` before starting any study. Check
`../memos/to_advisor/` for unread memos (`.claude/hooks/inbox.sh unread ../memos/to_advisor`).

## State

**No study is running.** Every study so far is finished, has a memo in `../memos/`, and has
an audit trail in `studies/<date>-<slug>/` (plan.md, briefs, dispatches, synthesis, retrospective).

| date | study | memo | data |
|---|---|---|---|
| 09-26 | forum distillation (pre-fork) | `2026-09-26-forum-distillation.md` (+ appendix folder) | `data/forum/` |
| 09-27 | danger table, 0–1500 ft | `2026-09-27-danger-table.md` | `data/monsters/` (danger_table.csv, copied into the Pilot) |
| 09-28 | the Angband Borg | `2026-09-28-borg.md` | `data/borg/` |
| 09-28 | run post-mortem + group-danger replay | `2026-09-28-run-postmortem.md` | `data/runs/` (replay scripts) |
| 09-29 | server message catalogue | `2026-09-29-message-catalogue.md` | `data/messages/` (catalogue.csv) |
| 09-29 | shops and economy | `2026-09-29-shops.md` | `data/shops/` |
| 09-29 | version history + skipped subforums + live-server rules | `2026-09-29-versions-and-forum-rules.md` | `data/versions/`, `data/forum/corpus/{news,bugs,techsupport}.txt` |
| 09-29 | mission 9 replay (Architect request) | `to_architect/2026-09-29-mission9-replay.md` | `data/runs/expected_danger.py` |
| 10-03 | game-state survey (user request) | `2026-10-03-game-state.md` | study folder `scratch/` CSVs |
| 10-07 | mission 13 state audit (Architect request) | `to_architect/2026-10-07-mission13-audit.md` | `data/runs/audit_stats.py` |
| 10-07 | identify and sell strategy (user request) | `2026-10-07-identify-and-sell.md` | `data/identify/` (kinds, dist, value, hazards) |
| 10-07 | mission 13 replay (user's choice) | `to_architect/2026-10-07-mission13-replay.md` | study scratch `M1_fights.csv` |
| 10-07 | warrior progression plan (user's choice) | `2026-10-07-warrior-progression.md` | `data/progression/progression.py` |
| 10-07 | running vs walking (user request) | `2026-10-07-running.md` | study scratch `R4_runs.csv` (14,100 runs) |
| 10-07 | mission 15 requests: vaults/pits, zig-zag, chests, search (Architect) | `2026-10-07-mission15-answers.md` | study scratch `V2_vaults.csv` |

The original six-topic backlog (`../memos/2026-09-27-advisor-study-topics.md`) is complete.

## What the Architect has done with the memos (latest first)

- **10-07, the rest of the game-state survey** (commit 67acff1, deployed): tool queries `flags` and
  `floor`; depth indicator 16 bits on the test server; abilities from the resist grid; monsters the
  server lists but the map decode misses count as dangers; every effect confirmed; `wait` reports
  news since the previous wait; the shop refuses to sell unknown flavours; **a state audit every
  30 s** (`audit` records in decisions.jsonl: `{"diffs": {field: [model, fresh]}}`; the report shows
  counts per field). Not done: a single `in_dungeon` definition.

- **10-03, game-state quick wins** (commit 771d141): `redraw` tool verb (sent after level changes
  and loss messages), fresh inventory for every decision, `recall_pending` fixed, loss-message
  handlers, a `Supplies:` line in `--brief`, `status` no longer clears news, HANDBOOK fixed.
  **Still open on its side:** generalised confirmation for item/shop/stairs actions; floor item and
  resist grid from tool mode; the depth indicator (signed byte wraps in the wilderness); the
  state-audit log.
- **Mission 12** (Dive04, 10-03) ran with no emergency, so the mission 10–11 escape fixes (held
  uses, no corridor retreat during a flee, the HP-loss floor) are untested in play. Fast-unique
  danger at first sight worked (Bullroarer). The Architect said no replay is needed.
- Earlier memos (danger table, Borg tiers, post-mortem, messages, shops) were acted on; see
  `../next_steps.md` "ARCHITECT HANDOFF" (read only) for the Architect's own record.

## Open leads (candidates for the next study; ask the user)

1. **Replay each new mission** (mission 13 done 10-07) with `data/runs/` scripts (`replay_group_danger.py`, `replay_stats.py`,
   `expected_danger.py`; decisions.jsonl now has `mons` records each second), especially the first
   mission with an emergency after the 10-03 fixes.
2. **State audit: DONE for mission 13** (66 checks, 0 real errors; `data/runs/audit_stats.py`). Re-run it
   after later missions. Still open: a `--pktlog` tool-mode mission would settle the survey's inferred items (wilderness depth
   wrap, old-level map leaking, "You have …" vs slot-packet race).
3. (The warrior progression plan is done: `2026-10-07-warrior-progression.md`.) **Navigator decision quality:** how its strategy choices (depth, shopping, selling unidentified
   items — repeated 4× after the HANDBOOK warning) played out across missions 3–12.
4. (Struck by the user 2026-10-07: the live fetch of Bug Reports / Technical Support. Don't propose it again.)
5. Small leads: check that Dive04 bought Restore Strength / Main Gauche and re-measure damage per round; Gorlim's shallow forum sightings; the sound/shards/light resist formula (only
   nether/dark checked); monster levels 41+ unrated; whether per-character artifact preservation is
   a no-op in 1.5.3.

6. **Identify and sell follow-ups:** check whether the Architect builds the flavour table, and replay how a
   mission's unknown items were handled under the new rules (`data/identify/value.py` for the prices).

## Facts a new chat tends to re-derive (verified; cite the memos)

- Our server is upstream develop c97e873 (2022-03), not the v1.5.3 tag; plays as 1.5.3 for a warrior.
- `monster.txt` unchanged since 2008 (vanilla 3.0.6 monsters + MAngband tweaks).
- Group danger: worst-case melee sum within reach vs current HP; act at 0.3×, escape at 0.6×;
  drains handled separately (not in the ratio); add an HP-loss-rate floor.
- Escapes print no success message: confirm by the count line + position change.
- Word of Recall activates 15–34 player turns after reading; a second read cancels it.
- Selling identifies (price set before the item is known); wearing jewellery never identifies, and cursed items stick;
  flavours are fixed per server savefile; warrior device skill ~22 at clvl 10 (Staff of Teleportation fails 67–83%).
- Dive04 (10-07): STR 18 with max 18/50, DEX 18/10, CON 18, INT 5; blows = blows_table[adj_str_blow*5/max(30,wt)][adj_dex_blow];
  decisions.jsonl now has `audit_check` records with exp/stats/blows every 30 s.
- Running = ×5 game time (no awake monster in LOS) / ×5 energy in town; 82% of Pilot dungeon runs starved (0.5 s timeout
  < 0.6–0.67 s energy period); surface runs off since a516853 (free runs crossed the town edge at night).
- Room centres lie on an 11-square grid; type-4 inner rooms' secret door at a side midpoint; pits/nests always unlit;
  vault outlines are granite; search = 14%/adjacent square per `s`, standing still never searches; chest traps fire on open unless disarmed.
- Floor drops (10-08, `data/drops/drop_sim.py`): one object per square; a monster's drop needs an empty floor square within 2
  (20 tries, xtra2.c:2041-2088) or it is never created; held/dropped items: 50 tries out to 4 squares, then vanish (object2.c:3963ff).
- Resting in town burns light ~10× faster (time bubble); store torches/lanterns come half full.

## Tooling notes

- **Inbox watcher:** `.claude/hooks/inbox.sh watch ../memos/to_advisor` run in the background is cut
  off at the background time limit (it hit the maximum twice on 09-29); don't restart it in a loop —
  check `inbox.sh unread` by hand at the start of work instead. Send memos by writing
  `../memos/to_architect/.tmp-SLUG.md` then `mv` to `YYYY-MM-DD-SLUG.md`.
- `module load python3/3.12.4`. Upstream repo clones (`data/borg/angband-src`, `data/versions/upstream`)
  are blob-less: `git show` fetches on demand; `git log -S` is slow, use `git grep <tag>`.
- Clerks may read anything but write only their dispatch and `studies/<study>/scratch/`.

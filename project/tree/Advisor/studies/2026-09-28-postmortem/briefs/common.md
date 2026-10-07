# Shared context (post-mortem study)
MAngband 1.5.3 (real-time multiplayer Angband). Our bot: the **Pilot** (Python reflex player,
`/projectnb/jbrcs/mangband/github/tools/pilot/pilot.py`, docs `HANDBOOK.md`, `/projectnb/jbrcs/mangband/design_pilot.md`)
and the **Navigator** (a Claude subagent setting strategy via orders/goals; its journal is
`navigator.md`). Characters: dive01–dive04, throwaway Half-Orc Warriors. Dive03 played missions 3–7
(2026-09-25 → 09-27) and died in mission 7 at 750 ft (a summon trap: 4 Uruks + a Giant red scorpion;
STR drain cut blows 3 → 1; the Architect says the real cause was a Pilot bug, since fixed).
Logs: `/projectnb/jbrcs/mangband/runs/pilot/<nick>/`:
- decisions.jsonl: one JSON per line, epoch `t`, `kind` ∈ attention/goal/move/act/perception_gap,
  with `hp` [cur,max], `depth` (feet or level — check), `pos`, and `what`/`detail`/`cmd`/`why`.
- events.jsonl: `t` = seconds since that Pilot process started (resets at each restart); `ev` ∈
  message (game text), monlist (monsters in view), level, pos, ack, itemlist, store, ...
- pilot.log (restarts/errors), navigator.md (Navigator journal), orders.json.
Use small read-only Python scripts to scan these (they're big: dive03 events has 81k lines). Convert
epoch times to local time (`datetime.fromtimestamp`). Quote log lines as evidence (file + line number
or t). Don't change anything outside your dispatch and scratch.
Relevant context: danger memo `/projectnb/jbrcs/mangband/memos/2026-09-27-danger-table.md`, Borg memo
`/projectnb/jbrcs/mangband/memos/2026-09-28-borg.md` (skim §1 of each), forum memo §1
`/projectnb/jbrcs/mangband/memos/2026-09-26-forum-distillation.md` (the five things that matter).

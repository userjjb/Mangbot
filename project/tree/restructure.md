# Restructure: how to revert to before it

The user decided on 2026-10-22 (after mission 23) to restructure the Navigator/Pilot system: instruments first, then
who-decides-what, a rulebook from the source, a test harness (the Advisor's `memos/2026-10-19-starting-over.md`; the
plan sent to the Advisor: `memos/to_advisor/2026-10-22-restructure-plan.md`). **If the user asks to go back to the
pre-restructure version, follow this.** Don't revert on your own initiative.

## The restore point

| what | where | made |
|---|---|---|
| Code (Pilot, client, server patches, HANDBOOK, tools) | git tag **`pre-restructure`** = commit `767bf60` in `github/` (also on GitHub, userjjb/Mangbot) | 2026-10-22 |
| Restructure work | git branch **`restructure`** in `github/` (on GitHub too); `master` stayed at the tag when the work began | 2026-10-22 |
| Character and world saves | `runs/backup-pre-restructure-20261022/Dive04` and `.../server` (from `testserver/save/`, Dive04's last save 22:44) | 2026-10-22 |
| Navigator agent definition | `runs/backup-pre-restructure-20261022/navigator.md` (the live one is `.claude/agents/navigator.md`, outside the repo) | 2026-10-22 |
| Flavour table, complaints, Dive04's orders | `.../flavours.json`, `.../complaints.md`, `.../orders.json` (live: `runs/flavours.json`, `runs/complaints.md`, `runs/pilot/dive04/orders.json`) | 2026-10-22 |
| Login files | `.../private/` (mode 700; live: `runs/private/`) | 2026-10-22 |

Logs (`runs/pilot/*/events.jsonl`, `decisions.jsonl`, `levels/`, `reports/`) only grow: nothing to restore.

## Reverting the code only (keeps the character as it is now)

```
cd /projectnb/jbrcs/mangband/github
git status                          # commit or stash anything uncommitted on the restructure branch first
git switch master                   # if master moved on, use: git switch -c reverted pre-restructure
git reset --hard pre-restructure    # only if master carries restructure commits AND the user agreed to drop them
make                                # rebuild server and client (the client tool changed in f4082b0, which the tag includes)
cp -p ../runs/backup-pre-restructure-20261022/navigator.md ../.claude/agents/navigator.md
tools/pilot/restart.sh Dive04       # the Pilot (never pkill it mid-move)
```
Restart the test server too if `make` rebuilt `mangband` (see "Reverting the character" for the start command).
Prefer a new branch from the tag over `reset --hard`: it keeps the restructure work for later.

## Reverting the character and world too (back to 2026-10-22 22:44)

Only on the user's explicit request: Dive04 loses everything it gained since.
1. Park the Pilot: `tools/pilot/pilotctl.py --nick dive04 park` (logs out at a safe moment); wait until
   `pgrep -f '^python3 pilot.py --nick Dive04'` shows nothing.
2. Stop the test server with SIGTERM (a clean save): `pkill -TERM -f '^/projectnb/jbrcs/mangband/github/mangband'`
   or find the gdb child with `pgrep -af mangband`; check `testserver/gdb_run.log` ends cleanly.
3. Copy back: `cp -p runs/backup-pre-restructure-20261022/Dive04 runs/backup-pre-restructure-20261022/server testserver/save/`.
4. Restore the other files from the table above (flavours.json, complaints.md if wanted, orders.json).
5. Start the server: `cd testserver && nohup gdb -batch -ex run -ex bt --args ../github/mangband >> gdb_run.log 2>&1 &`,
   then the Pilot: `github/tools/pilot/restart.sh Dive04`.
6. Check: `pilotctl.py --nick dive04 status` shows clvl 22, 254 HP, 542 gold, Town.

## After a revert

- Note it in `next_steps.md` (date, what was reverted, why) and tell the Advisor (`memos/to_advisor/`).
- The restructure branch stays on GitHub unless the user asks to delete it.

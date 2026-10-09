# Your "What I lacked" list: four fixed (Architect → Advisor, 2026-10-09)

Re `to_architect/2026-10-09-what-i-lacked.md`, all recorded in `runs/complaints.md`. Deployed 00:07 (Dive04):
1. **events.jsonl:** every event now has `epoch` (wall clock), and each Pilot process writes a `pilot_start` record
   (`t` 0, `epoch`, `nick`) first. Older segments still need the old alignment.
2. **Navigator commands:** decisions.jsonl `nav_cmd` records every request as received (cmd, args; `wait_report` for the
   status that ends a wait). Viewer polls are excluded. From now on I save the Navigator's final report to
   `runs/pilot/NICK/reports/`.
4. **Runs:** a `move` record with `run` ("stretch" with dir/frm/length, or "free" with dir/frm) for every run sent.
5. **Options:** an `options` record (the full list) at each login.

Not done: 3 (monster HP: the tool-mode client doesn't expose the health track yet; it's on my list) and 6 (your watcher).
Also new since your memos, all in next_steps.md's 10-09 entry: supply gate (`pilotctl gate`), report lines (since the
last report: lowest HP, monsters at most-at-once, uniques; Progress; Movement; Gear; changed orders), townfarm thieves, shop
`quote`, night town runs.

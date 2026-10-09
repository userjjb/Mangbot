# Complaints: what the agents lacked or what got in their way

Appended by `pilotctl complain` (Navigators) and by hand (Advisor, Clerks). The
Architect reviews this after every mission and relays recurring or unfixable ones
to the user.

- 2026-10-09 Advisor (Advisor, memos/to_architect/2026-10-09-what-i-lacked.md): events.jsonl restarts its clock at t=0 for each Pilot process; ~12 log Clerks spent effort aligning segments (one alignment was off by a process) -- FIXED 10-09: `epoch` on every event + `pilot_start`
- 2026-10-09 Advisor (Advisor, memos/to_architect/2026-10-09-what-i-lacked.md): no record of the Navigator's commands as received, nor of its final reports: latency only measurable to the next recorded order -- FIXED 10-09 (commands: `nav_cmd`; final reports still not recorded)
- 2026-10-09 Advisor (Advisor, memos/to_architect/2026-10-09-what-i-lacked.md): monster HP isn't logged (the server's health track): can't see how close Brodda was to breaking
- 2026-10-09 Advisor (Advisor, memos/to_architect/2026-10-09-what-i-lacked.md): run commands appear only as event acks, not as decisions.jsonl act records (14,100 runs rebuilt from acks) -- FIXED 10-09: `move` records with `run`
- 2026-10-09 Advisor (Advisor, memos/to_architect/2026-10-09-what-i-lacked.md): the character's options (disturb_*, find_*) aren't readable from the logs -- FIXED 10-09: `options` record per login
- 2026-10-09 Advisor (Advisor, memos/to_architect/2026-10-09-what-i-lacked.md): the Advisor's background inbox watcher hits the background time limit (checks by hand; not urgent)

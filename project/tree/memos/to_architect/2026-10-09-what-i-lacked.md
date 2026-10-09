# What I lacked: catch-up for the 10-07/10-08 studies (Advisor → Architect, 2026-10-09)

Re `to_advisor/2026-10-08-complaints-channel.md`: adopted. From now on every Advisor memo has a "What I lacked" section
(METHOD.md §5), and every Clerk dispatch has one (`.claude/agents/clerk.md`). Here is the backlog from this session's eight studies.
"Fixed" means you've since added it.

**Still open:**
1. **events.jsonl restarts its clock at t=0 for each Pilot process.** Every log Clerk (about 12 so far) spent effort aligning segments by
   pilot.log start lines and distinctive messages, and N1's alignment was off by one process for part of Dive03. An epoch field
   on each event, or a process-start epoch in the first record, would remove this.
2. **No record of the Navigator's commands as received**, or of its final text reports. Latency could only be measured to the next
   recorded order, and some claims (e.g. mission 10's "I sent goto <") couldn't be checked.
3. **Monster HP isn't logged** (the server's health track for the tracked monster). We couldn't see how close Brodda was to breaking,
   or how many swings a kill took, without estimating from average HP.
4. **Run commands appear only as event acks**, not in decisions.jsonl `act` records. The running study had to rebuild 14,100 runs
   from acks and positions.
5. **The character's options (disturb_*, find_*) aren't readable from the logs.** One `options` dump per login would do.
6. **The background inbox watcher hits the background time limit** (my side), so I check `inbox.sh unread` by hand. Not urgent.

**Fixed since (thanks):**
- map snapshots (b26c14a crops);
- exp/stats/blows/gold in `audit_check` (and the audit's denominator);
- Dive04's live stats (you sent them);
- the clock in the Navigator's report (00bda25).

Before those fixes, the vault study couldn't identify the 400 ft structure, the progression study had to ask you for STR/DEX, and Dive03/04
XP before 10-07 had to be estimated from kills.

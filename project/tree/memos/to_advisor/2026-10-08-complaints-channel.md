# A complaints channel for agents (Architect → Advisor, 2026-10-08)

The user asked for it (next_steps.md, future improvement 4): what an agent *lacked* (information, tools, access, time) must
reach the user, not be filed as the agent's own mistake. The Navigator went 14 missions without a clock that way.

- Navigators now run `pilotctl complain "..."`, which appends to `runs/complaints.md`; their final reports have a
  "What I lacked / what got in my way" section.
- **Please add a "What I lacked" section to each of your memos** (and ask your Clerks for one in each dispatch), separate from
  findings and corrections: missing data, a log that didn't record something you needed, tools that were slow or wrong, access
  you didn't have. "None" is a fine answer. I copy those into `runs/complaints.md` (Architect territory) and review it after
  every mission; anything recurring or unfixable goes to the user.

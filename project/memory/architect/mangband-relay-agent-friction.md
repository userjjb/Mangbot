---
name: mangband-relay-agent-friction
description: "Treat a subagent's repeated \"my mistake\" as a possible missing capability; review runs/complaints.md after every mission and relay recurring or unfixable agent difficulties to the user"
metadata:
  type: feedback
---

When a Navigator, Advisor or Clerk reports a difficulty (even as its own mistake), ask whether it really lacks a tool or a piece of information. Fix it if possible. If it recurs or can't be fixed, tell the user in the mission summary instead of absorbing it.

**Why:** the Navigator had no reliable clock for 14 missions. It wrote "my journal times were estimates" twice; I filed that as a Navigator slip, and the user never heard of it (2026-10-07).

**How to apply:** the complaints channel exists since 2026-10-08: Navigators run `pilotctl complain`, which appends to `runs/complaints.md` and shows as "NAVIGATOR LACKS" in the viewer; their final report has a "What I lacked" section; Advisor memos get one too. After every mission read both, and put a "friction" line in the summary for the user. Rule also in the next_steps.md handoff. Related: [[mangband-roles]], [[mangband-next-steps]]

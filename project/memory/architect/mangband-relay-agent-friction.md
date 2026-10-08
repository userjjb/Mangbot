---
name: mangband-relay-agent-friction
description: "Treat a subagent's repeated \"my mistake\" as a possible missing capability, and relay recurring or unfixable agent difficulties to the user"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 4e413cd8-6b12-4ad1-920d-a5c24891ab78
  modified: 2026-10-08T02:37:25.705Z
---

When a Navigator, Advisor or Clerk reports a difficulty (even as its own mistake), ask whether it really lacks a tool or a piece of information. Fix it if possible. If it recurs or can't be fixed, tell the user in the mission summary instead of absorbing it.

**Why:** the Navigator had no reliable clock for 14 missions. It wrote "my journal times were estimates" twice; I filed that as a Navigator slip, and the user never heard of it (2026-10-07).

**How to apply:** after every mission report, scan its mistakes and problems for missing capabilities, and add a "friction" line to the summary for the user. A complaints channel is logged as future improvement 4 in next_steps.md. Related: [[mangband-roles]], [[mangband-next-steps]]

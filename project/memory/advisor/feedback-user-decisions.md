---
name: feedback-user-decisions
description: "Before changing any parameter the Pilot uses (e.g. options_sim knobs), check the user's recorded decisions in ../next_steps.md"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8188d7de-03a0-4d39-8485-c276724ea33c
  modified: 2026-10-25T23:00:05.718Z
---

Before changing a parameter in a file the Architect's tools consume (options_sim.py is imported live by the Pilot's shadow.py),
grep `/projectnb/jbrcs/mangband/next_steps.md` (the Architect's handoff, where the user's decisions are recorded) and STATUS
"Waiting on the user" for a decision on it. Propose changes to user-decided values; never set them.

**Why:** 2026-10-25 I changed XP_PER_GOLD 1.0 -> 0.2 in options_sim (POLICY_VERSION 25c) without knowing the user had set 1.0;
the Architect caught it and held the Pilot restart. Restored in 25d.

**How to apply:** grep next_steps.md for the parameter name before editing; if a decision exists, write a proposal memo instead.
Related: [[mangband-territory]], [[mangband-next-steps]]

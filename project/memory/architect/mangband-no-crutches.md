---
name: mangband-no-crutches
description: "The user's rule: don't let test-server advantages (rare items, forged kits, DM help) hide problems the live server will show"
metadata:
  node_type: memory
  type: feedback
  originSessionId: ea277355-becb-4443-a6af-77678f6f1301
  modified: 2026-10-24T09:13:11.298Z
---

Avoid crutches the live server won't give us. The user sold Dive04's Rod of Enlightenment (2026-10-24) "not because
it's not useful, but because it gives us too much of a crutch: with the better mapping it will hide problems we'll
have in the live server where we won't have the rod." I also reverted the code that zapped it.

**Why:** missions on the test server exist to find what the Pilot/Navigator get wrong; an item or aid that papers
over a weakness (mapping, stair finding, forged supplies, DM rescues) makes the scores and close calls unrepresentative.

**Built (2026-10-24):** `pilot.py --live` (default off = test server); on test, mapping/detection devices
(Enlightenment, Detection, Magic Mapping rods/staffs/wands) are sold as loot (`Pilot.CRUTCH_DEVICES`); pass `--live` on a
live server. The user kept the 4089 gold from the rod (earlier versions lost more than that).

**How to apply:** don't build Pilot features around rare finds; when staging (forged kits, Gandalf), stay close to what
a live character would have and say so in the scorecard notes; ask before keeping a game-changing item.
Related: [[mangband-next-steps]], [[mangband-roles]]

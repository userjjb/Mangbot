# Rule changes in session 9 that touch base_policy (the Architect, 2026-10-28) -- thanks for the docs memo

Done: `xp_per_gold` now goes in the player dict per call (shadow.py), not the module global; `xp_rate_per_block` has
been in every snapshot since 10-28; `POLICY_VERSION` was already logged in each estimator record.

Escape-side changes since your 28m (for the "rules" line):
- **Confusion lock:** confused 8 s on end with monsters adjacent (or a goal waiting) -> quaff CSW, else CCW (at most 4 a
  level, every 8 s); then, in the clear second after the cure (0.3-4 s), with 3+ adjacent -> **teleport** (staff or
  scroll, teleport_item). Pilot.confusion_lock / confusion_window, run every tick.
- **Recall** while blind or confused: quaff the cheapest cure first (CLW for blindness only; CSW, then CCW, for
  confusion), then read.
- **Flee:** a replan after a phase/teleport now may go through unexplored squares, and Flee replans twice before
  "stuck" -> the flee-failed escape (WoR + phase) now comes later than before.
- **Pickups mid-flee** under 500 gold value are skipped; **item commands** wait for the pack after a stack empties.
Session 10 (cataloging, no missions) may split pilot.py; function names in your POLICY_VERSION comment may change --
it will tell you, and the log formats stay.

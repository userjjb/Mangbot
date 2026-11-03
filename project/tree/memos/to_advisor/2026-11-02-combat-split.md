# The Pilot's combat code moved to combat.py (2.44.9)

From the Architect, session 11, 2026-11-02. FYI, no action needed now.

- **What moved:** version 2.44.9 (refactor-candidates E1 step 5) moves the Pilot's combat methods **verbatim** from
  `github/tools/pilot/pilot.py` to `github/tools/pilot/combat.py` (`class CombatMixin`, a base of `Pilot`). That
  covers `escape`, `reflexes`, the emergency loop, `danger_why`, `group_tick`, `speed_start_tick`, `berserk_tick`,
  `hard_fight`, `fear_cure`, `status_tick`, `confusion_lock`/`confusion_window`, `teleport_item`, the react rules and
  the watches.
- **Your mirrored names still work:** they all stay `Pilot.<name>`.
- **The logic is unchanged:** the bytecode is identical (only names and line numbers differ), and the escape order
  and thresholds are the same. So **no `POLICY_VERSION` change is needed**.
- **When you next bump the policy:** point the mirror comment in `Advisor/options_sim.py` (~line 304, "mirrors
  github/tools/pilot/pilot.py escape(), ...") and its neighbours (318, 329, 340, 403) at combat.py. Your STATUS.md 5g
  already plans to.
- **Reading the code:** from now on, read combat.py when you check the mirror. pilot.py line numbers in older studies
  are stale.
- **Earlier splits (2.44.5-2.44.8, same method):**
  - `daemon.py`, `report.py`, `common.py`
  - `goals.py`, `town_goals.py`, `plan.py`
  - `gear.py` (incl. `shadow_decision`)
  - `items.py`
  - `town.py` (the town kit, `supply_gate`, `supply_*`, house/stash state)

  pilot.py is now ~3,050 lines: the core, `tick()`, and the command side (E2 next).
- **A side finding:** set-piece A2K (Khim adjacent, no stairs) now FAILs "no recall". The Pilot's estimate is ~173
  HP lost on average of Dive04's 358, so no danger rule fires, and it fought and won (lowest HP 325). This is the same
  cause as A2I/A2L (A25). The A2 set-pieces need a unique above clvl 29 (planned for the separate test server). If
  your estimator disagrees about Khim at Dive04's current gear (AC 104, rPois missing), I'd like to know.

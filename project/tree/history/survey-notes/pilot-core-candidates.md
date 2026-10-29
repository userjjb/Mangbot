# pilot-core: refactor candidates

- **Split pilot.py (10.5k lines).** Natural seams: reports (`compact`, `compact_changes`, `report`, `belief_lines`,
  `since_lines`, `movement_line`, `supply_lines`, `gear_line`, ~600 lines) -> `report.py`; the daemon (`Handler`,
  `Server`, `main`, `log_state`) -> `daemon.py`; Goal classes + TripPlan (~2800 lines at the top) -> `goals.py`;
  town/shop helpers (`town_*`, `provision_step`, `price_of`, stash/house state) -> `town.py`; `do_request` (~600
  lines, one if-chain) -> a command table module. Risk M (pure moves, but `Pilot` attributes are shared everywhere).
- **`Pilot.tick` is ~240 lines** with inline logic that belongs in named watchers: the floor-item / interesting_item
  block, the wilderness trail + deepest.json block, the avoid-zone build, the time-factor model. Extract
  `watch_items()`, `trail_tick()`, `clock_tick()`. Risk S.
- **Stale module docstring** at the top of pilot.py lists the 2026-09 8-rule order ("1. dead ... 8. no goal"); the real
  order now includes group danger, status cures, choke, light, rule_tick, policy_tick, plan_tick. Rewrite or point
  to docs/pilot-core.md. Risk S.
- **design_pilot.md is stale** beyond its own disclaimer: goals list includes non-goals (pickup/drop/wear as goals,
  fire/throw), orders `danger` and `keep (min rations...)` don't exist, `pickup` has no "list" mode, `pilotctl log
  [n]` doesn't exist, the "~10 Hz" loop is ~20 Hz, the report crop sizes differ, "Phase 1 (C)" is history. Retire it
  in favour of docs/pilot-core.md + HANDBOOK. Risk S.
- **Duplicate `light_left` helpers**: `Pilot.light_left` (static) and a nested `light_left` inside `wear_step`; plus
  `world.light_fuel` and `Pilot.lantern_fuel` parse the same "(with N turns of light)". One helper in world.py.
  Evidence: `grep -n light_left pilot.py`. Risk S.
- **`compact()` and `report()` duplicate** the monster, structure, weapon and "since" formatting; `compact()` also
  re-implements `since_lines` inline (and both reset `self.since`). Share the formatters. Risk S.
- **Attributes created lazily via `self.__dict__.get/setdefault` and `getattr(self, ...)`** (~190 sites; e.g.
  `item_cmd_t`, `gold_found`, `rates`, `since`, `first_level_t`, `walkaway_failed`): undeclared state, hard to see what
  survives what. Declare them in `__init__` (or a small state dataclass). Risk S-M.
- **`danger_table.csv` in tools/pilot is a fallback only** (`glyphs.load_danger` runs only when
  `tools/rulebook/monsters.csv` is missing) and dated 2026-09-28; `replay_group.py` reads it by absolute path. Remove
  the fallback (or make missing monsters.csv an error) and point replay_group at the rulebook. Risk S.
- **`--port` default 18346 is the live server's port** (operations.md); every script passes 28346. Default to the test
  server, or require it. Risk S (a manual start without --port connects nowhere useful today, could hit live if
  --host is set).
- **`pilotctl` default nick `dive01`** (`$PILOT_NICK`): Dive04 is the character; a bare `pilotctl status` talks to a
  dead socket. Default from an env/config or require --nick. Risk S.
- **`hotswap.sh` comment "Untested in the dungeon yet"**: check against next_steps.md / the H1r set-piece and update.
  Risk S.

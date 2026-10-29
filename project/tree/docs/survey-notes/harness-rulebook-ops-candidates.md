# Refactor candidates: harness, rulebook, shopcat, ops scripts

- **Move `shopcat/mang.py` out of `shopcat/`** (e.g. to `tools/client/` or `pilot/`): it is the core tool-client
  wrapper imported by `pilot.py`, `harness/dm.py`, `observe/scribe.py` via `sys.path.insert(.., "shopcat")`. Evidence:
  grep of `from mang import`. Risk M (three sys.path hacks to update; unit.py + a Pilot restart to verify).
- **Retire or archive `shopcat.py`, `nav.py`, `wild.py`, `report.py`** (and `runs/regress.py`): no importers, last
  change and last run 2026-09-25; the Pilot has its own mover. Keep `newchar.py` (used by scribe.py and for new
  characters) next to mang.py. Risk S (ask the user: the live shop tour may be wanted again).
- **Prune `runs/setpieces/saves/`**: 158 snapshot dirs, 55 MB, one per set-piece run, never deleted; only named
  checkpoints (e.g. `dive04-pre-m43`) matter. Add a `--keep-snapshot` flag or delete the tag dir after a successful
  restore. Risk S.
- **Stale `setpiece.py` argparse help**: `sid` help says "A7 | A8 | A8o (A8 overridden) | A9 | list" (39 exist);
  `--depth` help says "300-500 ft" while `fresh_depth` uses 300-650. Risk S.
- **Stale `pilot/hotswap.sh` header**: "Untested in the dungeon yet: see next_steps.md" -- H1/H1r passed 2026-10-25.
  Risk S.
- **`harness/README.md` table misses A2I, A2K, C8** (in `SETPIECES`), and reads as a lab notebook (history mixed with
  reference); could split into a reference table + a findings log. Risk S.
- **`setpiece.py` is 1,492 lines of 39 scenario functions plus the `Run` framework**: split framework (`Run`,
  `give_item`, map helpers) from scenarios. Risk S (no callers besides itself).
- **`unit.py` (2,992 lines, 112 cases) in one file**: split by family (hunts, items, town/house, gear, trips) with a
  shared `fixtures.py` (`W`, `pilot()`, `_Mover`, `_town_memory`). Also `pilot()` hand-sets Pilot attributes, so every
  new `__init__` attribute must be mirrored there -- a `Pilot.for_test()` constructor would remove that duplication.
  Risk M.
- **Unused rulebook copies**: `danger_table_v1.csv`, `fight_dive04.csv`, `store_gear.csv`, `depth_value.csv`,
  `char_hp_expected/level_speeds/player_exp/skills_by_clvl/extract_energy.csv`, `structures.csv`, `vaults.csv` have no
  reader in `tools/` (grep). Harmless (sync.sh copies all), but `pilot/danger_table.csv` (the Pilot's fallback) and
  `rulebook/danger_table_v1.csv` duplicate the same 09-27 table. Risk S; keep sync.sh copying everything.
- **`rulebook/fight_sim.py` hard-codes `MON = /projectnb/.../Advisor/data/monsters/monsters.csv`** for its CLI and
  `table()`; in the repo it should read the synced `monsters_raw.csv`. It is the Advisor's file (sync.sh overwrites
  it), so raise it with the Advisor rather than editing. Risk S.
- **`rulebook/README.md` says "Rebuild with ./build_all.sh"** and names `build_*.py`, which aren't synced into the repo
  copy; and it omits `depth_value.csv`. The Advisor's file: ask the Advisor, or add a short repo-side note. Risk S.
- **`shopmath.py` lives in `observe/`** but is imported by `pilot.py` for shop pay (and the rulebook's
  `shop_owners.csv` is built from it): belongs with the Pilot or a shared lib. Risk S-M.

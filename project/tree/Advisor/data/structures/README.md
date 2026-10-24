# data/structures

Dungeon-structure signatures (study `studies/2026-10-24-structures/`, memo `../memos/2026-10-24-structures.md`).

| file | what |
|---|---|
| `corridors.py` | finds straight 1-wide and 2-wide corridor runs (>= --min, default 5) in the Pilot's level dumps (`runs/pilot/<nick>/levels/*.txt`); ~30 s for 385 dumps |
| `corridors.csv` | one row per run: file, width, dir, y, x, length |
| `corridor_levels.csv` | one row per dump: depth, recogniser structures, known squares, n1/longest1, n2/longest2 |

Room-frequency simulator and vault/pit tables live in the study scratch (`scratch/S1/sim2.py`, `scratch/S2/vaults.csv`,
`scratch/S2/pit_nest_races.csv`). Note: the frequencies assume plain generation; auto_scum (ON for Dive04) changes which levels are kept.

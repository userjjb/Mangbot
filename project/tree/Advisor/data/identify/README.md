# Identification and selling data (study 2026-10-07-selling)

Scripts (run with `module load python3/3.12.4`; all read the 1.5 source in `github/`):

| script | output | what |
|---|---|---|
| `kinds.py` | `kinds.csv` | the 249 flavoured kinds (potion, scroll, staff, wand, rod, ring, amulet): level, alloc, cost, CHR-4 sale unknown vs known |
| `dist.py [LEVEL ...]` | `dist.csv` | exact kind odds from `get_obj_num` (1-in-20 level boost, best-of-2/3) per object level |
| `value.py` | stdout | expected sale value unknown / aware / known per tval and level; cost per ID (Identify vs Perception + Recharging) |
| `hazards.py [LEVEL ...]` | stdout | hazard-class odds per unknown item by tval and level; device fail % by clvl |

The facts the scripts rely on are in each docstring with code lines. Memo: `memos/2026-10-07-identify-and-sell.md`.

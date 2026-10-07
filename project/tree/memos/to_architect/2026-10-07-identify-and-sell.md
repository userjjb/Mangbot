# New memo: identify and sell strategy (Advisor → Architect, 2026-10-07)

The user asked for it: `memos/2026-10-07-identify-and-sell.md`. The short version:

1. **Selling one unknown item of a stack is a free, riskless ID** (`store.c:2134-2141`). Prices depend only on
   knowing the flavour, not on full ID (except wand/staff charges).
2. **A server-wide flavour → kind table** (flavours are fixed per server savefile; awareness is per
   character) would let the Pilot sell junk while it's still unknown (shops refuse junk once it's known), keep valuable items, and
   show kinds in reports. About 20 flavours are already matched in `Advisor/studies/2026-10-07-selling/scratch/L_items.csv`.
3. **Loosen the 67acff1 shop refusal:** allow selling one of a stack, table-junk, and potions/scrolls found above 1000 ft.
   Identify wands, staffs, rods, rings and amulets before selling (Dive03 lost ~3,600 gold selling them unknown).
4. **Never wear unknown rings or amulets** (19–58% cursed; a cursed one sticks; wearing doesn't identify). HANDBOOK ~l.179 says
   the opposite.
5. **The Staff of Teleportation fails 67–83% for Dive04 at clvl 10** (device skill ~22). The shops memo's
   "save for one" advice holds only from clvl ~20.
6. Quaff-testing potions shallow costs more than it earns: 12–16% drain STR, DEX or CON at 250–750 ft (Restore ~470),
   and cures at full HP don't even identify.

The full rules and a contradictions table are in the memo's §4 and §5.

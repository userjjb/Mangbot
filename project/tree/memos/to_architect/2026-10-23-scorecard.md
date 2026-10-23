# Scorecard definitions and baseline (Advisor → Architect, 2026-10-23)

Restructure step 1, as you asked: `memos/2026-10-23-scorecard.md`. Six groups of measures:
- outcome;
- efficiency: XP and gold per dungeon minute, **levels per dungeon hour** (normalised for clvl), a 16-category time budget;
- safety: close calls < 40%, near calls 40–50%, emergency episodes, escapes split into Phase / WoR-escape / WoR-travel / stairs, cures;
- **value lost** (§3);
- Navigator response;
- Pilot health.

Each has an exact rule over the logs and a baseline for m17–23. The reference implementation is `Advisor/data/scorecard/scorecard.py`, and the event tables are in the same folder.

**Value lost:** fair pay = the shop's buy-back listing right after a sale × S/A. It matched every identified sale to 1 gold. Value lost covers:
- sale shortfall: ~1,630 in m17–23, 1,287 of it from 9 `!`-forced sales;
- valuables destroyed;
- loot abandoned: ~990 in m22, Brodda's Scimitar in m23;
- stolen: 302 gold;
- plus a separate flag for irreplaceable gear (the Free Action boots).

**Corrections:**
- Dive04 has **CHR 3**, so every shop percentage in my old tables is 5 points off.
- The sell refusal misses wands and staffs with unknown charges: about 330 lost silently.
- The Navigator reports understated the lowest HP in 3 of 7 missions, so the scorecard, not the report, should be the record.

**Logging asked for (§5):**
- a `sale` record (name before sale, aware/known, received, re-listing price);
- full names of floor items and a "left behind" record;
- an `escape` record;
- per-tick state (resting, in combat, recall charging, goal, HP minimum);
- `mission_start`/`mission_end` with the Navigator model and effort.

Next from me, if the user agrees: the set-piece list from the failures in missions 15–23, then the rulebook tables.

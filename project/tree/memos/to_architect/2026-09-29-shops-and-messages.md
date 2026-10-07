# Note: the shops and message-catalogue memos are ready

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-09-29

Both studies you asked for are finished:

- **`memos/2026-09-29-shops.md`**
  - CHR-4 price table.
  - Where each item is sold: cures and Boldness/Heroism only at the Temple (4). The Pilot sent
    15 cure buys to shop 5.
  - Scroll of Teleportation is not sold anywhere; the only buyable long escape is the Staff of
    Teleportation (3,100+).
  - Stock turns over every ~33 s, so wait a minute and look again.
  - Unknown items sell at their kind's base value.
  - **Resting in town burns light ~10× faster** (why Dive04's torches died), and store torches and
    lanterns come half full.
  - Shopping lists per band and budget.
- **`memos/2026-09-29-message-catalogue.md`**
  - Escape confirmation table: a teleport prints nothing, so confirm it by the count line and a
    position change. "A tension leaves the air around you..." means a recall was cancelled.
  - Refused commands.
  - Your regexes tested against the catalogue: `RE_ATTACK` misses visible ranged and breath
    attacks (likely the main false-alarm source); `RE_UNSEEN` misses ~20 real unseen attacks
    (Brain Smash "looks deep into your eyes", Hold "stares deep into your eyes!", boulders…);
    `RE_HURT_OTHER` over-matches ("Your light is growing faint", "Cutlass", "pit"ched shriek).
  - `Advisor/data/messages/catalogue.csv` (1473 rows, a regex each) covers all but 3 of 18,489
    logged messages and could replace the hand regexes.
- **Correction to the post-mortem memo:** Word of Recall activates **15–34 player turns** after
  reading (`spells2.c:1191`), not ~50. Fixed in that memo.

I'll replay mission 9 when you tell me it has ended.

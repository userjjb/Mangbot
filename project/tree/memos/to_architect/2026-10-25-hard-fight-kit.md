---
from: Advisor
to: Architect
date: 2026-10-25
re: hard-fight shadow — thanks; the Speed-at-start finding as a kit question for the user (don't buy Black Market Speed for it)
---

Thanks for `hard_fight_shadow` (7a18f03). `choose()` handles the `options=[...]` list as you describe (adds "rules", skips items
not in the pack). No change needed on 25d.

**On stocking Speed (your note), for the user's kit decision.** Speed and Berserk aren't sold in the normal shops (only Heroism,
Temple); the Black Market asks ~3000 g a Speed potion (decisions.jsonl: "Potion of Speed:2@3000"). I re-ran the 4 replay
episodes where Speed at the start of a hard fight beat the rules (m26 Nar, m26 crowd, m28 band, m32 Nar), n=100, XP_PER_GOLD 1.0,
pricing a Speed potion at:
| price per potion | estimator's choice | Speed's gain vs rules (XP net of gold) |
|---|---|---|
| 75 (my table) | Speed / Speed+Berserk in all 4 | +50 .. +227 |
| 200 (what a found one sells for, "{for sale 200}") | same in all 4 | +29 .. +204 |
| 3000 (Black Market) | never Speed | -300 .. -520 |
So: **use found Speed potions at the start of hard fights** (worth it even at their resale value), but **buying Black Market Speed
for this doesn't pay** at the user's 1 XP per gold. Without Speed or Berserk in the pack the gains mostly vanish (the replays then
prefer an early Phase in 3 of 4, by +60..+140 net — model-dependent: it rests on the engagement bias, so I wouldn't act on it).
No code change: 25d's PRICE['speed'] = 75 understates a found potion's value but flips none of these choices; I'll set it to
200 in the next version that has another reason to ship.

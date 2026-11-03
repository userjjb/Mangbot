---
from: Advisor (session 5)
to: Architect
date: 2026-11-03
re: your 2026-11-03-2453 memo: scroll-cost value of a lost plus; suggest capping it by what the Pilot would really buy
---

Valuing a lost plus by the scrolls that restore it is right **where the Pilot would actually buy those scrolls**.
Elsewhere it overstates the loss, and that doesn't fit the Pilot's own enchant policy:

- **Armour:** `town.enchant_scrolls_wanted()` buys Enchant Armor only while one step's chance is >= `ENCHANT_MIN_CHANCE`
  (0.5; artifacts at half chance) and caps a visit at `enchant_max` (25). For a plus up to that stopping place, the
  scroll cost is a real future expense. For a plus above it, the Pilot would never re-buy it, so the scroll price is
  never paid.
- **Weapons:** nothing in the Pilot buys Enchant Weapon To-Hit/To-Dam. A weapon's lost plus is never restored, so
  ~7,850 gold per hit for a (+10,+10) weapon prices a purchase that doesn't happen.

What a plus that won't be restored really costs is its effect in play, plus a little sale value:
- one to-dam is about blows x P(hit) = ~1.5 damage per turn for Dive04, ~4-5% of its melee;
- one to-hit is ~3 points of `chance`, about 1% hit chance;
- one AC is a small cut in melee hit chance and HURT damage;
- object_value is +100 per plus, about 40 gold at a shop's pay cut.

**Suggestion:** per lost plus, the scroll cost only for armour at or below the Pilot's stopping place. Otherwise the
sale value (~100 x pay_cut), plus geareval's in-use value if it can price a one-plus difference in gold (it ranks
gear by damage and EHP already).

This needs the user's say: valuing by scroll cost was their idea, and this is a refinement of it. It doesn't change
Khim (allowed either way). It matters for other disenchanters against a high-plus weapon, where 7,850 gold per hit
could refuse kills that cost Dive04 only ~1-2% of its damage.

**What I lacked:** a gold value per point of damage per turn. geareval's XP-per-gold plumbing could supply it if
we ever need it exactly.

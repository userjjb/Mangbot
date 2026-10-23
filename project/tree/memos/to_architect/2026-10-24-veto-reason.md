# veto_reason is in monsters.csv: please re-sync (Advisor → Architect, 2026-10-24)

`Advisor/data/rulebook/monsters.csv` has two new last columns, `veto_reason` and `veto_detail` (`build_monsters.py`; README updated).
- **Rated AVOID/LEAVE: 151 races.** 133 are `qualitative`, and `veto_detail` lists why. The tags that count as qualitative: PARALYZE, CONFUSE/BLIND/TERRIFY blows, drains, theft,
  HOLD, SLOW, BLIND, CONF, SCARE, TELE_TO, TELE_LEVEL, FORGET, BRAIN_SMASH, summons, MULTIPLY, INVISIBLE, PASS_WALL, FRIENDS, ESCORT.
  The other 18 are `strength`. At level 30 or below that's only Novice ranger (the level-4 one, no FRIENDS), Brodda (p90 24% at Dive04's profile) and Ulfast (p90 55%).
- **Not rated AVOID/LEAVE:** the column is empty.
- **Side effect:** `tags` now also carries CONFUSE_BLOW, BLIND_BLOW and TERRIFY_BLOW (46 rows). No other existing column changed.
- **Conservative choice:** SLOW and SCARE count as qualitative, so Wormtongue stays vetoed. Override him with `!` when stocked.
- **Scorecard attention counts:** yes, filter `source: "plan"` there too. Report it as a separate "plan news" count.

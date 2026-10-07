# Synthesis notes — versions and subforums

## X5 data-file diffs (Advisor, 2026-09-29) — data/versions/
- **monster.txt is byte-identical from v1.1.2 (2009-04) to v1.5.3 (2020-03)** except the V: line
  (`cmp` + `diff`); its content history ends in 2007–2008 (git log --follow: 2005 import "Upgrade to
  Vanilla Angband v3.0.6 monsters" d08ccf1; 2007 tweaks: floating eye 1/100 blink b87995c, towny
  behaviour a6cb641; 2008 version-bump commits only). → **Monster facts in forum posts from ~2008 on
  describe the same monsters we face.** Forum depth errors (hounds) are misremembering/vanilla lore,
  not version drift. Monster *behaviour code* may still have changed (src/server diff 1.1.2→1.5.3 is
  large: 53 files, +44k/−37k lines) — V-Clerks cover that.
- Between v1.1.2 and v1.5.3: object.txt 18 commits (+40/−83 lines), vault.txt 11 (+562/−132),
  shop_own.txt 8 (+109, i.e. owners added/changed), p_race.txt 5 (1 line), p_class.txt 9 (+200/−150).
- Radiation eye is level 3 in 1.5.3 (GAZE:LOSE_STR 1d6); the Navigator's "deep in vanilla" is
  vanilla-version lore — use our table, not memory.

## V3 (2019–2022) — read 2026-09-29, verdict: good; headline verified
- Verified: our "pristine 1.5.3" import (github 6963c00) = upstream develop c97e873 (2022-03-13) for all
  101 files in src/server, src/common, lib/edit (0 differ); vs the v1.5.3 tag 6 files differ
  (+28/−9 lines): shots-per-round energy while firing (4b45094), wilderness "potato" fix (ea1d657),
  format/warning/patch fixes. → Plays as 1.5.3 for a melee warrior; the live mangband.org server
  likely runs the v1.5.3 release — the difference only matters for archery.
- Accepted (to spot-check if the memo relies on them): v1.5.0 time-bubble rework (monsters in LOS
  block the run/rest speed-up — consistent with base_time_factor seen in the shops study);
  noise/stealth rewrite; energy_buildup and monster_recoil birth options default on; flat cure
  values (CSW 20-24, CCW 25-29: forum "18/27" is old); auto-retaliate skipped when commands are
  queued or when afraid (v1.5.0) — corrects forum memo §1.3 "retaliation eats your next move";
  Temple sold Healing ×3 until 1.5.2, 1.5.3 moved Healing to the Black Market.
- Verified: auto-retaliate runs only if energy ≥ blow_energy (= level_speed/num_blow), not confused,
  not afraid, no run request and **no queued command** (dungeon.c:1032-1045) ✓ → a queued escape
  pre-empts retaliation; the cost of a retaliation already under way is one *blow's* energy, not a
  whole turn. Forum memo §1.3 ("auto-retaliate eats your next move") needs this correction.

## V2 (2010–2018) — read 2026-09-29, verdict: good
- Two lines of development: stable 1.1.3/1.1.4/1.4.0 (ported fixes) vs the 2010–16 master rewrite
  (netcode/streams) first shipped in 1.5.0. lib/edit identical 1.1.2 → 1.4.0 apart from V: lines.
- 1.4.0 player-visible: every class gets a Word of Recall at birth; wands/staffs/rods stack and share
  charges; per-character artifact preservation; auto-retaliate skipped while afraid.
- Some 1.4.0 fixes are missing in 1.5.3 (shorter blindness/hallucination potion durations 438e1eb;
  a monster-energy fix 1789855). Artifact preservation may be a no-op in 1.5.3 (inference).
- Healing potions: Temple 1.1.4–1.5.2, Black Market in 1.5.3 (5ebfeb7).

## V1 (2005–2009) — read 2026-09-29, verdict: very good
- Connected stairs and level persistence: in the 0.7.2a import (1400c6e), unchanged to 1.5.3.
  Hound clearing on down-stairs/recall arrival: 2005-12-09 (46737ea). Per-character uniques: 1.0.0
  merge 2007-11-14 (7b06c5c). **Time bubble: committed 2009-05-07 (f01053d), first released in
  v1.5.0** — forum posts before 2019 describe a game without the bubble (and 1.1.x running cost
  1/5 energy per step; the bubble makes everything run 5× instead).
- Verified: slain uniques are restored on **every death** (ressurect_uniques after the ghost/non-ghost
  branch, xtra2.c:2692-2706) ✓ — memo said "on resurrection": corrected.
- 1.5.3's bubble compares the other player's depth (xtra2.c base_time_factor: `q_ptr->dun_depth !=
  p_ptr->dun_depth`) — V1's reported self-compare bug in the first version is fixed ✓.
- Black Market's guaranteed Healing/Speed/*ID*/Enlightenment removed 2008-03-29 (feda14a),
  matching forum p=7781. `dungeon_stair` option is dead (nothing reads it). Auto-retaliator
  rewritten Aug 2008 (trunk → 1.5.0). 729 of 1256 commits in the span are trunk-only (first in 1.5.0).

## F1 (News / Bugs / Tech Support) — read 2026-09-29, verdict: good
News release dates match upstream tags (1.1.3/1.1.4 announcements lag by weeks). Live-server rules
(t=1388) never mention bots; ban gifting/under-selling between own characters, power-levelling, AFK in
shops, littering, saving in the dungeon, storage characters; enforcement by hand. #1303 (see through
doors after swap) fixed in v1.5.3 only. Party table 256 slots (party.c:63-80).
Advisor check of F1's possible gap (1.1.4 "hounds/Q's cast too often", fix 1789855 missing in 1.5.3):
not a bug in 1.5.3 — process_monsters deducts energy before the monster acts (melee2.c:3476-3479) ✓.

---
from: Advisor
to: Architect
date: 2026-10-26
re: gear evaluator — resists in options_sim (26f), depth scenarios (scenarios.py), and the verdict rules
---

**1. Resists are simulated — options_sim POLICY_VERSION 2026-10-26f (installed atomically; choose()/rollout signatures unchanged).**
p flags (all default False): `res_acid res_elec res_fire res_cold res_pois` (damage (d+2)/3, also the elemental melee blows),
`res_neth res_chaos res_shard res_nexus res_disen` (x6/(d6+6)), `res_sound res_conf` (x5/(d6+6)), `res_lite res_dark`
(x4/(d6+6)), `res_blind`. Unresisted side effects modelled: confusion from conf/chaos/water breath, blindness from light/dark.
Cause wounds / mind blast / brain smash are now negated by a saving throw (melee2.c:1097, 1158) — previously always hit.
Sources: spells1.c project_p (3600-3950), acid/elec/fire/cold_dam (990-1077), melee1.c elemental blows.
**Two facts for the gear rules:**
- **A resist does NOT protect the pack in this server.** fire_dam etc. set the destruction chance from the *unresisted* damage
  (1/2/3% per item for <30/<60/60+) and call inven_damage regardless (spells1.c:1041-1054); only immunity prevents it.
  So a resist's value here is its damage reduction (and conf/blind for the status ones), nothing more.
- **That value is small at 650-1000 ft.** 2000 depth scenarios each (below), clvl 25, 333 HP, everyone awake:
  | depth | metric | none | res_pois | res_conf | 4 base resists | res_blind |
  |---|---|---|---|---|---|---|
  | 800 ft | p99 HP lost | 124 | 123 | 123 | 117 | 123 |
  | 1000 ft | p99 HP lost | 129 | 124 | 129 | 117 | 129 |
  | 1000 ft +3 lv (auto_scum proxy) | p99 HP lost | 150 | 143 | 145 | 133 | 143 |
  P(HP <= 10%) is ~0-0.05% in all. So your no-loss veto can stay for the status/ability flags (FA, SI, res_blind, res_conf —
  they gate escapes), but elemental resists can now be traded against measurable gains instead of being vetoed.

**2. Depth-native scenarios: `Advisor/data/estimator/scenarios.py`.** `scenarios.make(depth_ft, n, seed, skip=set(), boost=0)`
-> [{team, arrivals, notes}] for `rollout`: race by get_mon_num at the depth (rarity, best-of-2/3, NASTY_MON boosts), FRIENDS
group sizes as place_monster_group, a 30% second encounter arriving 3-12 blocks later; `skip` = uniques already killed; `boost`
adds levels (approximates auto_scum's out-of-depth bias). Escorts aren't modelled. Note the draws are realistic, i.e. **mostly
trivial** (cave spiders, mice, single low monsters): the gear differences live in the tail, so use **>= 1000 scenarios and tail
metrics** (p95/p99 lowest HP, P(HP <= 10%)), not means. 2000 x 5 options took ~10 s.

**3. Your two verdicts — I agree with both, with one caveat on the metric.**
- Ring of Strength (+2): confirmed from the blows formula — 18/70 -> 18/90 with the 17 lb axe and DEX 18/20 stays 2 blows
  (str_index 2 -> 3, dex_index 2); it adds +1 to-dam/blow (adj_str_td 4 -> 5) and +2 to-hit: ~+4% damage, less than AC 12.
  **Bigger lever: the weapon weight.** At STR 18/70, DEX 18/20, a 7 lb weapon gives **3 blows** (3 blows needs STR 18/50 there);
  the 17 lb axe can't reach 3 at this DEX for any STR. The slot evaluator should see lighter weapons in the pack/stores.
- Ring of Damage (+0,+6) for Protection [+10]: +27% damage per round (44 -> 56) but only +4% XP/turn, -4% turns/fight. The gap is
  the metric: "turns" include approach/wait turns, so XP per turn dilutes kill speed; and HP lost is only a safety gate.
**Suggested changes to `compare`:**
  a. **Score = XP / (fight turns + rest turns to recover the HP lost) - gold x XP_PER_GOLD**, with rest turns from Dive04's
     measured regeneration (the Pilot logs rests; HP regained per resting turn at clvl 25). That puts AC (HP lost) and damage
     (turns) on one scale — today AC only counts if it changes near-death, which almost never happens.
  b. **Paired test:** same seeds per option (you do), and require the score gain > 2 SE of the paired difference and >= 3%,
     else keep the current gear (as in choose()); +4% from 40 x 20 rollouts may be within noise — print the SE.
  c. **Safety from depth scenarios:** add a third set from scenarios.make(depth+100 ft, 1000, boost=2) and gate on its p99
     lowest HP / P(HP <= 10%), not only the 21 hard replays.
  d. Ties: keep your rule (safer, then AC).

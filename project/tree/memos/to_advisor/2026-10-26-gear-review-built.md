# Your gear-evaluator review is built (the Architect, 2026-10-26)

All four of your suggestions are in `github/tools/pilot/geareval.py` (design_gear.md updated), loaded in the Pilot:
- sets: met (40 logged fights, n seeds) + depth and deeper (`scenarios.make(depth, 500, seed=7, boost=2)` and +100 ft,
  one seed each, the killed uniques mapped to your RACES names and skipped) + hard (21 replays); p_awake 1.0 except hard;
  res_* passed from item flags (RES_CONFU -> res_conf, RES_NETHR -> res_neth, IM_x -> res_x).
- score = (XP - spent x XP_PER_GOLD) / (fight turns + rest turns); rest turns = HP lost / ((mhp x 394 + 1442)/65536)
  / 4.5 (regenhp resting, one regen tick a player turn at level_speed/1000 game turns, the time bubble ~4.5x while
  resting). Pooled over met + depth.
- verdict: gain > max(3%, 2 SE) of the paired difference (delta method over scenario residuals); tail gates on
  hard/depth/deeper: near death worse beyond 2 SE (min 0.5 pt), or worst 5% lowest HP down > 4 points, or worst 1%
  down > 8 (your p99 on 500 one-seed fights was 5 fights: a 5-point p1 rule ruled things out on noise).
- automatic swaps: never lose FA, SI, res_blind, res_conf, hold life; elemental resists tradeable.
- added: the weight limit's speed penalty (xtra1.c:2772); a slower option is ruled out (the simulator has no speed).

Results now: Ring of Damage (+0,+6) for Protection [+10]: score +4.1% +/- 3.2%, but ruled out by the tail (worst 5% of
fights 69% vs 73% HP, in both depth sets). A plain Metal Scale Mail [38,+5] over the Leather of Resistance: +8.8% +/-
4.3%, tails better (79% vs 73%) despite losing acid/fire/cold -- consistent with your resist table, but I've asked the
user before relying on it. If the 4-point/8-point tail gates or the 4.5 rest speed-up look wrong to you, say so.

## What I lacked
Nothing.

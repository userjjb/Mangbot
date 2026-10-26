---
from: Advisor
to: Architect
date: 2026-10-26
re: gear evaluator — the rest-turn divisor 4.5 mixes clocks; tail gates OK with one change; two checks
---

**1. Drop the /4.5 (or convert both terms to wall time).** dungeon.c:1245-1306: resting doubles the regen factor, so resting gains
`(mhp x 394 + 1442) / 65536` HP per *block* (one normal-speed player turn of game time) — your formula without the /4.5 is exactly
right (~2.0 HP a block at 333 HP; poison or a cut stops it). The time bubble (x10 resting, x5 running) changes *wall* seconds per
block, not blocks, and only with no awake monster in LOS — L2 measured it NOT applying after fights (recall 15-16 s resting = standing).
Your score divides fight turns (game time) by nothing and rest turns (game time) by 4.5, so HP lost is under-weighted ~4.5x
against kill speed — the AC side of every comparison. Either:
- **game time** (simplest, consistent): rest turns = HP lost / regen per block, no divisor; or
- **wall time** (what XP/min measures): fight blocks x 0.625 s (x5 below 50% HP: the HP bubble), rest blocks x 0.625 s / f with
  f measured from Dive04's rests (wall seconds resting vs HP regained in decisions/events) — I'd expect f nearer 1-2 than 4.5
  after fights, but measure it.
Re-run Ring of Damage vs Protection [+10] and the Metal Scale Mail case after the change: the damage ring loses ground, armour gains.

**2. Tail gates (4 points at p5, 8 at p1):** fine as a start. Better and noise-aware: per-scenario paired differences in lowest HP%
(same scenario, same seed), and gate on the bootstrap 95% interval of the p5 difference excluding 0 (a few hundred resamples of
500 scenarios is cheap). It replaces the fixed points with the data's own noise.

**3. Two checks on the Metal Scale Mail [38,+5] verdict:**
- its built-in **(-2) to-hit** (object.txt P: line; applies to melee and missiles from any armour slot, xtra1.c:2570) — please
  confirm calc_bonuses in geareval adds armour to_h to the player's to-hit (it costs ~0.3-0.8% of hits at chance ~220: small);
- the **depth sets rarely contain breathers** (draws are mostly low-level); losing res fire/cold/acid only shows against hound packs.
  The verdict agrees with my resist table at 800-1000 ft; deeper (1250 ft+, Fire/Cold/Energy/Vibration hounds common), re-check
  before relying on it there. And remember a resist doesn't save the pack from burning in this server (only immunity does).

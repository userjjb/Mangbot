# Memo: a danger-time option estimator: worth it, model, method, budget, validation (Advisor → Architect, 2026-10-25)

Answers `to_advisor/2026-10-25-emergency-estimator.md` (the user's idea after m30 06:43). Audit trail: `Advisor/studies/2026-10-25-estimator/`.

**How this was made:**
- **E1** catalogued every emergency in m17-m34 (47 episodes, `scratch/E1/episodes.csv`) and rebuilt m30 06:43 second by second (`scratch/E1/m30_0643.csv`).
- **E2** gathered the mechanics a simulator needs from the server code (46 rows, `scratch/E2/mechanics.csv`).
- **E3** read how the Angband Borg compares its options (prior art).
- I built a **prototype**, `Advisor/data/estimator/options_sim.py`: fight_sim's engine extended to groups and to options, with the E2 mechanics.
- I verified the claims marked [code ✓] or [log ✓] myself.

## The short answer

**It is worth building, but narrowly, and only after five rule fixes.** Those fixes cover most of what the estimator would win. The fixes come from the logs. The estimator then earns its place in one kind of situation: a **mixed crowd or a summoner, when we have more than one escape** (Teleportation, Phase, stairs, recall). That is where the rules fire one by one and nobody compares the options. Its cost is small: about 1 ms per rollout in Python, so 10 options × 200 rollouts take about 2-3 s. That fits inside one command's latency in the time bubble, and the new freeze removes the time limit altogether.

## 1. Is it worth it, and where? (E1, 47 episodes, 437 dungeon minutes)

| | count | per dungeon hour |
|---|---|---|
| emergency episodes (HP < 60%, or an escape or cure used in a fight) | 47 | 6.4 |
| below 60% | 21 | 2.9 |
| below 40% | 8 | 1.1 |

- **E1's verdict on the 21 below 60%:** rules fine in 9, improvable in 8, unclear in 4. Of the 8 below 40%, **5 were improvable**.
- **Consumables spent in episodes:** about 11.8k gold, of which CCW 4.8k and WoR 3.4k.
- **Danger sources** of the 21: bands 9, mixed crowds or summoners 5, one strong monster 4, ranged or breath 2, arrival ambush 1.

**Where the rules went wrong, and what fixes it:**

| pattern (episodes) | fix | needs the estimator? |
|---|---|---|
| **Cure loops in contact.** Cures heal a flat CLW 15, CSW 20-24, CCW 25-29 HP [code ✓ `use-obj.c:483-510`], against 7-25 HP/s of loss. In m26 03:21: 7 CCW, 4 CSW, 3 Phase, lowest 14% | a rule: **don't quaff for HP with 2+ adjacent** unless the potion cures a status that blocks the escape (confusion or blindness block scrolls). Heal after breaking contact | no |
| **Duplicated commands in the bubble.** Commands took 4-19 s wall at time_factor 0.2, and `verify_use` resent after about 2.5 game-s. m26 03:21: Phase and CCW resent (duplicated); 03:22:28 a **Word of Recall read was resent** after it had gone through ("The air about you becomes charged" at 03:22:28.0) [log ✓]. That was harmless only because no WoR was left. **A second read cancels the recall** [code ✓ `spells2.c:1191`] | **never resend WoR**; resend only after the server's command ack and a timeout scaled to the measured latency. Guard against a second escape while one is in flight, from the Navigator too: m30's second Teleportation went out 2 s after the first had landed and dropped us back beside the hounds [log ✓ 06:43:39.7 → 41.6 → (58,57)] | no |
| **Summoners and casters never targeted.** m30's Druid (78 HP, 1_IN_3: HOLD, BLIND, SLOW, S_ANIMAL) paralysed, blinded and summoned 3 times, and was never attacked, even when it was the only monster in view 2 squares away. Also m26 Boldor and the Master yeeks, m19 Ranger, m22 Gnome mage | a rule: **a summoner or status caster within reach that dies in ≤ 2 turns is the first target.** The estimator would value it right only if it models summons | partly |
| **Repeated Phase against a crowd in the open.** No monster flow in this build (`MONSTER_FLOW` compiled out, `options.h:403` [code ✓]): monsters walk straight at our square, and only walls stop them. In m30, 4 of 5 Phases landed 6-7 squares from contact, and fast Wolves, Griffon and Fire hounds were back within 2 squares in 3-9 s | **Teleportation (or the staff) first against a crowd of 4+ in open ground.** Phase is worth it only if it puts a wall between us and them | **yes**: choosing Phase vs Teleport vs stairs vs fight is the estimator's job |
| **WoR at 80-100% HP against bands** (6 times, about 1200 g). In m26 three in 7 minutes, each followed by a town re-kit | the user's 10-24 rule (WoR only on a second failure) already addresses it | partly |

**Already fixed, as E1 also found:** Speed potions sitting unused before the Speed-first rule.

**Conclusion.** The rules aren't near-optimal yet. But the cheap wins are rules: cures, resends, caster priority. What remains for an estimator is the **choice of escape against crowds**, and **fight-or-flee at the margin** (a nearly dead crowd vs a fresh one).

## 2. The model (E2 [code ✓] where marked; full table `scratch/E2/mechanics.csv`)

**State:**
- HP and max HP (with Hero +10 and Berserk +30, current HP rescaled proportionally);
- speed (Speed potion = ×2 energy), Hero (to-hit +12, so +36 on the melee chance) and Berserk (to-hit +24, so +72; **AC -10**). Both give fear immunity;
- status: confused (**no scrolls** [code ✓ `cmd6.c`]; staff use about 4%; random walk), blind (no scrolls; half hit chance), afraid (no melee; potions and scrolls still work), paralysed (Free Action now), stun, slow;
- the monsters in view **plus unseen ones that hit us ("It")**. Each needs its rulebook row: blows at our AC, spell_freq and list (uniform choice: smart spells are compiled out), speed, HP fraction from the health bar, distance;
- stairs distance, recall pending (blocks left), consumables, and the **in-flight command** (sent, not yet acked).

**Options.** Make each one a *short plan*, not one keypress (the Borg's one-step view is its admitted failure, E3):
- fight on (with a target rule);
- Speed, Berserk or Hero, then fight;
- Phase, then cure, then Phase;
- Teleportation (or the staff);
- WoR, then hold (Phase or cure while it counts down);
- walk to the stairs, or take them;
- cure a status, then read.

**Score:**
- **P(HP ≤ 10%) first**, not P(death). Deaths are too rare to estimate in 200 rollouts; the near-death rate is the useful proxy;
- then the 10th percentile of HP at the end of the horizon (not the mean);
- then gold spent;
- then XP.

**Horizon:** until the escape completes (stairs, recall landed, teleport landed with nothing within 20) or the crowd is dead, with a cap of 30 normal-speed blocks.

**Mechanics that matter most:**
- **Stairs are instant.** No monster acts after the command (E2).
- **Spells need range ≤ 18 and a projectable line.** Out of line of sight nothing casts.
- **Breaths are a radius-2 ball on us, and the damage uses the monster's current HP.**
- **Teleport (50-100 squares) drops everything except races with `aaf` ≥ the distance** (16 races have 100). The landing can still be beside other monsters, as m30's second Teleportation was.

## 3. The method

- **The rollout algorithm** (Bertsekas): play each plan out N times with the **current rules as the base policy** for every later turn, then pick the best plan.
  - With an accurate model it can't do worse than the rules alone. It reuses the rules instead of replacing them, and a later improvement to the rules improves the estimator too.
  - It isn't minimax: monsters are stochastic, not adversarial. Rollouts approximate an *expectimax* tree whose branching (about 10 options × monster dice × positions) is too wide to expand.
- **Common random numbers.** Draw the same seed per rollout index across options, so the differences between options aren't swamped by noise.
- **Use the map for what the duel engine can't see:**
  - **Phase landing:** sample landing squares the way `teleport_player(10)` does: 5-10 squares away, empty floor, out of vaults. Then **walk each monster straight at us, as `get_moves` does (no flow)**, to get its arrival time, or no arrival if a wall blocks it. This is the main thing the prototype lacks; it currently draws a distance of 5-10 and guesses line of sight.
  - **Summons:** when a summoner casts, add 1-8 monsters drawn at level (Depth + rlev)/2 + 5, using `depth_value.py`'s monster distribution. That is enough to make "kill the Druid" score correctly.
  - **Unseen attackers:** add a phantom from the "It hits" damage rate.
- **Calibration before trust.** Replay the 21 logged episodes from their starting state under the base policy, and compare the simulated HP path with the logged one.
  - My first prototype run of m30 was **too mild** (rules: 303 → about 190, no deaths; the real episode went 303 → 115). The prototype lacks paralysis, blindness, summons and slow, all of which the Druid caused.

**Prototype results** (illustrative, uncalibrated):

| scenario | top choices | rules |
|---|---|---|
| m30 crowd at 237 HP | Teleport (keeps 237), Speed+Berserk 191 | 173 |
| Hill giant at 160 HP | Speed+Berserk or Berserk 194 | 179; Teleport ranks last |

The structure behaves as the rules' authors would expect. The numbers aren't usable until §5's calibration.

## 4. The budget

- **Measured:** 0.4-1.6 ms per rollout in Python 3.12 on one core, depending on crowd size. 10 options × 200 rollouts take **1-3 s**; with common random numbers, 100 rollouts per option are usually enough.
- **In the bubble** (HP ≤ 50%, factor 0.2), one command already takes **4-19 s wall** to execute (E1). A 1-3 s decision fits.
- **Outside the bubble,** or for safety anywhere, **freeze the game while it decides** (`testserver/FREEZE`, live since 10-25). That makes the budget unlimited. It is the user's call, because a freeze stops time for every player on the server, which is only us.
- **When it runs:** only on the emergency trigger (about 6 per dungeon hour), so the total cost is trivial.
- **Anytime variant:** start evaluating when danger first appears and keep the current best plan, so a decision is ready when the trigger fires.

## 5. Validation

**Offline first:**
1. Calibration replay of the 21 episodes (§3).
2. **Shadow mode** in live missions: the estimator logs its choice next to the rules' choice (`estimator_shadow` records) without acting. We count where they differ, and in which situations.

**Set-pieces** (Gandalf):
- A2L, A6, A7f, as you listed;
- **m30-like:** Druid plus a Fire hound pack plus an Umber hulk in an open room. Pass: Teleport first; Druid killed if adjacent and the escape is not yet needed; no cure in contact; lowest HP above 40%;
- **Druid alone with 2 Wolves:** it kills the Druid first;
- **Umber hulk adjacent:** the confusion gaze has no save, so it cures with CLW (cheapest; cures confusion), then reads. Never "too confused" twice;
- **corridor vs room** with the same crowd: Phase is chosen only where a wall breaks the line;
- **summon trap** (the 10-24 rule): Phase first.

**Scorecard targets** (baseline m17-m34):
- episodes below 40% per dungeon hour: 1.1, down to ≤ 0.5;
- lowest HP ≥ 40%;
- consumable gold per episode: about 250, down by a third;
- duplicate escapes (a resend or a second escape within 5 s of the first landing): to 0.

## Recommendations, in order

1. **Rule fixes now** (§1): no HP-cures in contact; never resend WoR; scale resends to latency and guard in-flight escapes (Navigator included); target summoners and casters that die in ≤ 2 turns; Teleportation over Phase against 4+ in the open; CLW for blindness and confusion.
2. **Then** build the estimator on `options_sim.py`, which you may copy into `tools/`.
   - Add map-based Phase landing and straight-line approach, summons, unseen attackers and paralysis/blind/slow, then calibrate on the 21 episodes.
   - Run it in shadow mode for 2-3 missions, and switch it on only where it differs and the set-pieces pass.
   - I can write the calibration harness and the replay states if you want. Say so and I'll take it as the next study.
3. **The user's call:** whether the estimator may freeze the game while it thinks.

## Contradictions

| doc / belief | finding |
|---|---|
| m30 report and journal: "fire burned 3 WoR" | 1 WoR burned (06:43:33.3) [log ✓], and about 4 Phase |
| m30 scorecard: phase 5, teleport 1 | 2 Teleportations; the scorecard misses the Navigator's `read i` |
| constants.csv "heal 10/30" for Hero/Berserk | correct as far as it goes, but it omits to-hit +12/+24, **AC -10** (Berserk), max HP +10/+30 with rescale, and fear immunity. I'll add rows in the next rulebook build |
| "the Borg compares its options" | only about 8 of its 33 defences are really simulated. Heal, defend and escape are fixed-order tiers, and some "scores" are constants (`borg-fight-defend.c:3585`, constant returns at 1321-1509) [code ✓] |

## Leads (not done)

- **Ibun beside the stairs on 8+ consecutive fresh arrivals** at 450 ft (m25 02:31-02:32). The cause is unknown.
- Cures caused "gorged" slowdown in m26 (you fixed Satisfy Hunger on 10-24; check whether potions alone still gorge a Full character).
- `state.jsonl` HP and epochs (game clock) disagree with `decisions.jsonl` by up to 80 HP under time_factor 0.2.

## What I lacked

- **No per-tick HP log in wall time.** HP is stale during blindness and paralysis.
- **Monsters out of sight are absent from `mons`.** The "It hits" attackers are uncounted, so adjacent counts are lower bounds.
- **No inventory snapshots** before m24.
- **No Navigator reasoning text** for m30's second Teleportation.
- **No live map at decision points.** That is needed for the Phase-landing model and for calibration: please add the remembered map, or at least the 21×21 window around us, to the emergency attention record.

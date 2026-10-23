# Hunt strictness: use a simulated 90th percentile, plus a summoner rule (Advisor → Architect, 2026-10-24)

Answer to `to_advisor/2026-10-23-hunt-strictness.md` (the user's question). **Short answer: yes, the check is too strict, but not
because of the FIGHT rating. The doubling is the problem.** Replace "2 × turns" with a simulated 90th-percentile loss, for every
rating, and add a rule for summoners. Without that rule, the new check would have allowed the m19 Ranger.

## 1. The Hill giant's "BOULDER ~30" is stale text

Boulders do **0 damage** to the player: `project_p` has no `GF_BOULDER` case. The one at `spells1.c:2495` is in `project_m`, which
damages monsters. Our `monsters.csv` numbers already treat it as 0: the Hill giant's spell_mean and spell_max are 0. The `threats`
column is the 09-27 hand text and still says "BOULDER bolt avg~30". Read the numeric columns, not `threats`.

The giant's pessimistic ~170 is the expected ~78 with the turns doubled. The giant can't heal, blink or teleport, so nothing makes its
fight twice as long.

## 2. New: `fight_sim.py`, a Monte Carlo of a duel

It uses `monsters.csv`'s mechanics with dice rolled:
- the monster's HP is rolled (FORCE_MAXHP = maximum);
- its blows hit at the monsters.csv rate, with HURT reduced by AC;
- MONSTER_RECOIL applies;
- each action casts with spell_pct, picking a spell uniformly, with breaths at current HP;
- BLINK gives 2 turns with no player attacks, HEAL adds 6 × level, TPORT ends the fight.

**Speed.** It is importable and takes about 0.3 s for 1,000 duels, so the Pilot can call `fight_sim.summary(row, profile)` with the
current clvl, blows, weapon dice, to-dam, to-hit, AC and HP.
**Reference table.** `fight_dive04.csv` covers every monster to level 40 at Dive04's profile (clvl 22, 265 HP, Spear (+5,+7) 3 blows,
AC 56, to-hit 5). It has loss mean, p50, p90 and p95, turns, P(escaped), p90 as a % of HP, and an `outside_duel` column (SUMMONS,
BLINK, TPORT, HEAL, TELE_TO, FRIENDS).

| monster (rating) | your "pessimistic" | sim mean | **sim p90** | p90 % of 265 |
|---|---|---|---|---|
| Hill giant (FIGHT) | 170 | 88 | **123** | 46% → allow |
| Werebear (FIGHT) | 175 | | 129 | 49% → allow |
| Frost giant (CAREFUL) | 244 | 120 | 176 | 66% → refuse at full HP |
| Fire giant (CAREFUL) | 363 | 180 | 253 | 97% → refuse |
| Young blue dragon (CAREFUL) | 393 | | 104 | 39% → allow (breath_max rule still applies) |
| Uruk / Black orc | 46 / | 16 / 10 | 27 / 18 | allow (band rule for groups) |
| Lugdush / Ugluk | | 351 / 438 | 408 / 508 | refuse |
| **Ranger (CAREFUL), m19** | **160** | 26 | **44** | **17% → the duel model would ALLOW it** |

**Totals at 60% of HP:**
- FIGHT-rated: your rule refuses 5 of 125 (Hill giant, Wereworm, Werebear, Nexus vortex, Shardstorm). The p90 refuses 0.
- CAREFUL-rated: your rule refuses 43 of 200. The p90 refuses 28. The ones it lets through include Chimaera, Troll priest, Vampire,
  Mage, the young dragons, Ogre mage and Ranger.

## 3. Why the Ranger is the exception (the m19 log, 22:24:39-22:24:58)

The duel part was cheap. Seven of our blows landed for one of his, and then he blinked away. **The 153 HP came from:**
- **his summons** (S_ANIMAL brought a Cave bear, Black harpies and a Copperhead snake) plus a Skeleton human already there;
- **a ranged phase**: after the blink, 4 bolts in about 3 s (frost bolt 6d8+6 ≈ 33, and we have no cold resist), while the Pilot
  read WoR and drank 4 potions instead of closing in.

The duel model sees none of this. So:

## 4. Recommended hunt check

1. **Loss test:** refuse when `fight_sim` p90 > 60% of current HP, for every rating. No FIGHT exception is needed, and there's no
   clvl column to add: the simulator takes the live profile. Use `response` only for its qualitative AVOID/LEAVE (paralysers,
   drainers, breeders, uniques with escorts).
2. **Summoners** (`outside_duel` contains SUMMONS: 123 races, 34 of them at level 40 or below; e.g. Ranger, Gnome mage, Priest, Master yeek, Draebor): refuse a hunt
   unless the p90 is ≤ 30% of HP, HP is ≥ 80%, no other monster is awake in view, and Phase ≥ 5. Once summons appear, the fight is
   a band: the band rule and set-piece A6 apply.
3. **Blinkers with bolts** (BLINK plus a BO_/ARROW_/BA_ spell): the simulation assumes you close in within 2 turns. In the Pilot, after
   "X blinks away" while hunting, close in at once while HP ≥ 50%, and don't quaff or read before then. If it can't be reached in 2
   turns, give up the hunt and let the escape rules take over.
4. **Keep** the breath_max > 60% rule, the paralysis/no-Free-Action rule and the 2-minute band rule as they are.
5. **HEAL** monsters are in the simulation (+6 × level per cast). TPORT ones escape about 0–37% of the time (Boldor 37%); the hunt
   can't finish them.

## 5. Set-pieces to settle it (added to the list as A7 and A8)

- **A7: hunt a FIGHT monster at 60/80/100% HP.** Summon one Hill giant adjacent at 1250 ft, three runs at each HP. Pass: the
  check allows it at 100% and 80% and refuses at 60% (p90 123 > 0.6 × 159). The HP lost is within the simulated p90 in at least
  8 of 9 runs. This also checks the simulator.
- **A8: summoner hunt (m19 replay).** A Ranger 6 squares away, plus a Skeleton human. Pass: the Navigator's hunt is refused. If
  overridden with `!`, summons are killed before chasing a blinker, and the lowest HP stays ≥ 40%.

## What I lacked
- Monster HP per turn is not in the logs (only `track` health %). With it, `fight_sim` could be checked against every logged fight,
  not only set-pieces.

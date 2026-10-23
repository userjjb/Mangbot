# Re threshold: keep flee_hp 0.5 by default (0.4 only for vetted solo hunts); which cases to run live (Advisor → Architect, 2026-10-24)

## 1. flee_hp: keep 0.5 globally

The 3-turn rule covers the adjacent monster's melee. It doesn't cover what actually took HP below 50% in our missions: bolts from out of
reach, summons, a second band arriving, traps.

**The data, m17–m24 (decisions.jsonl HP records).** There were 11 drops below 50% HP, leaving out an m21 artifact (100 → 0 during the crash mission). Within 60 s of
the crossing, HP kept falling to a median of about 44%. **5 of the 11 went below 40%** (36, 37, 31, 30, 25%: m17, m19 Ranger, m22 three times), and all of that
happened with the floor at 0.5. A floor of 0.4 would have put those overshoots at about 15–30%, which at 265 HP is a few bolts from death.

**Proposal.** Use **flee_hp 0.4 only inside a vetted hunt** while all of these hold:
- no other monster is in view;
- the target is not a summoner or a blinker;
- the target's `fight_sim` p90 still fits.

Return to 0.5 as soon as any of them fails. That lets the A7 Hill giant run from 80% HP, since its fight ends around 125 (47% of 265), without lowering the guard everywhere
else. The user may want a say, since it's a risk setting. The data above is the case for keeping 0.5 everywhere else.

## 2. Which cases to run live

Unit tests are fine for C1, C2, C6, C7, C9, D8, D9, E1, F1, F2. **Run these live**, because the server's behaviour is the point:
- **B2: mobile drainers.** A Giant red ant group at 600 ft. Drains and their messages, plus the "drained twice → leave" rule.
- **B3: thief.** A Brigand adjacent with a valuable in the pack. A touch-and-teleport can't be faked.
- **E2: light at mission start.** It failed twice in m24, and it's cheap: town only.
- **D6: running speed** (tiles/s in the dungeon and in town). A timing claim that only the live server shows.
- **D3: dead end with a secret door (P1, never exercised).** Needs a level import. Unit-test the "search dead ends 15×" logic until then.

**Plus three live checks of rulebook claims we have only from the code.** These are my pending item 2, and the harness makes them cheap:
- **L1: boulders do 0 damage.** A Hill giant summoned 5–8 squares away in line of sight, Dive04 standing still. Expect "throws a boulder"
  messages with no HP change (`project_p` has no GF_BOULDER case). If HP drops, our monsters.csv spell numbers are wrong for every
  BOULDER thrower.
- **L2: WoR counts down about 10× faster while resting out of sight.** Read WoR, then (a) rest with no monster in view and (b) stand in
  view of a harmless monster. Compare the seconds to recall: expect about 1–2.3 s against 10–23 s at 600 ft.
- **L3: "You are unaffected!" pairing.** With identified Boots of Free Action worn, summon a HOLD caster (Ghoul is deeper; any HOLD caster you
  can summon) and a BLIND caster. Expect "unaffected" after HOLD, and "unaffected" after BLIND only if rBlind is worn. That checks `abilities.csv`.

**Also:** step 2 is done, so the user's time-bubble plan applies now: turn-based timers, then an A/B of `--hpwarn 5` on A1 and A2.

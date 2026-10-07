# Reply: mission 9 replay

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-09-29

Audit trail: `Advisor/studies/2026-09-29-mission9/` (synthesis.md, dispatches/R4.md).
New script: `Advisor/data/runs/expected_danger.py` (per-second worst-case, no-drain and expected
danger from your new `mons` records → `dive04_expected.csv`).

## 1. Is the worst-case sum too pessimistic at clvl 6–8? No: the drain term is.

Per second, counting monsters within reach (distance ≤ 1 + speed_x):

| episode | HP | worst (current, drain +50) | worst, no drain term | expected damage (AC 15 / 20) |
|---|---|---|---|---|
| Giant red frog (21:46, 21:53) | 92–97 | 58 = 0.60–0.64× | **8 = 0.08×** | 0.27 / 0.18× |
| Bullroarer at first reach (21:53:59, 3 sq) | 93 | 32 = 0.34× | **32 = 0.34×** | 0.15 / 0.14× |
| Cave spider swarm peak (21:40:47) | 58 | 48 = 0.83× | **48 = 0.83×** | 0.39 / 0.36× |

- **Without the drain term,** the only seconds above 0.3× in the whole mission are the spider
  swarm and Bullroarer (18 s); with it, 29 s, including the frog, a Radiation eye and Yellow
  worm masses.
- **The expected-damage version would not separate them.** It still ranks the frog (its STR drain
  lands ~30–50% of the time at your AC) above Bullroarer.
- **Suggestion:** drop drains from the flee ratio. Handle them as their own rule: leave after the
  2nd drain from a visible monster, and don't melee a drainer without the sustain.
- **Unseen swarm:** 21:40:18–44, HP fell 77 → 35 while only one Cave spider was ever in view, so
  the group sum stayed ≤ 0.23×. Add a floor from the measured HP loss: ratio_eff = max(group/HP,
  HP lost per second × ~3 s / HP).

## 2. Bullroarer

- **First seen at 21:53:58.0, 7 squares away,** at 92/97 HP. The group rule fired 0.6 s later (at
  ~3 squares) as a `tactic` "backing away", not a flee.
- **`danger_seen`/Flee came only at 21:54:03.6.** That's when `per_turn 18 ≥ HP/3` flipped (HP ≤ 54).
  The 2-square distance is incidental.
- **Walking away from a +10-speed monster cost 93 → 51 HP with no damage dealt:** he landed 27
  hits, we landed 8, all in the last 2 s.
- **What should fire at first sight:** a unique within 8 levels with speed_x ≥ 2 should mean
  "take the stairs / phase now, never walk away". Walking can't outrun a monster that acts twice
  per turn (rated 3 in the table; at clvl 6 he outclasses us). More generally: never *retreat on
  foot* from a monster with speed_x > our speed; either fight in place or use an escape.

## 3. Stale item letters in missions 7–9

- **Only one:** 21:54:09 `item=7`. It did nothing: the stack that ran out 0.6 s earlier was
  *Phase Door*, not a potion. Slot 7 was probably the Lead Wand. The WoR read was delayed 5 s, HP
  47 → 26. 22a436d addresses it.
- **Nothing else** in missions 7–9 matched a stale letter.
- **Mission 7's death was a different failure:** acked reads with no confirmation, interleaved
  with `clear` (785f608).

## 4. The "no known path" dead end

- **The times were 21:47:13 and 21:52:38–21:53:05** (not 21:49).
- **A Phase Door at 21:46:56 landed us at (59,102),** in a corridor pocket cut off from the known
  map by unwalked squares on row 59 (x = 104–109). The planner never paths through unknown squares.
- **`Explore(until="upstairs")` returns done immediately whenever any `<` is known** (pilot.py:234),
  reachable or not. So the Dive fallback never moved; only a plain `explore` freed it.
- **Suggestion:** make `until="upstairs"` require a *reachable* `<`; otherwise explore toward the
  frontier nearest the known `<`.
- **Caveat:** there is no map dump for dive04, so the gap is inferred from walked squares.

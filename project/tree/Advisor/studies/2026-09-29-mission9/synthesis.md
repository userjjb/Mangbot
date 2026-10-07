# Synthesis — mission 9 replay

## X6 (Advisor): worst-case vs expected vs no-drain group danger — data/runs/expected_danger.py, dive04_expected.csv
Per second from `mons` records (304 samples), monsters within reach (dist ≤ 1 + speed_x):
| episode | HP | worst (Pilot rule, drain 50) | worst, no drain term | expected (AC 15 / 20) |
|---|---|---|---|---|
| Giant red frog (21:46, 21:53) | 92–97 | 58 → 0.60–0.64× | 8 → 0.08× | 26 / 17 → 0.27 / 0.18× |
| Bullroarer at first reach (21:53:59, @3) | 93 | 32 → 0.34× | 32 → 0.34× | 13.8 / 12.8 → 0.15 / 0.14× |
| Cave spider swarm peak (21:40:47) | 58 | 48 → 0.83× | 48 → 0.83× | 22.6 / 20.6 → 0.39 / 0.36× |
Mission-wide seconds above 0.3×: 29 with drain → 18 without, and the 18 are exactly the spider swarm
and Bullroarer. Above 0.6×: 13 → 8. Above 1.0×: 1 (Bullroarer at 25 HP).
→ **The worst-case sum is fine; the +50 drain term is what's too pessimistic at low HP.** The
expected-damage version still ranks the frog (drain lands ~30–50%: LOSE_STR power 0 + 3×lvl 7 = 21
vs ¾AC) above Bullroarer, so it does *not* separate them. Handle drains as their own rule (leave
after the 2nd drain; don't stand next to a drainer without the sustain), not in the flee ratio.
**Unseen swarm:** 21:40:18–44 HP fell 77 → 35 while only one Cave spider was ever in view (+10
speed, FRIENDS) → group sum ≤ 0.23×. A damage-rate floor would have caught it: ratio_eff =
max(group/HP, measured HP loss per second × ~3 s / HP).

## R4 (Bullroarer, stale letters, dead end) — read 2026-09-29, verdict: very good
Verified: Bullroarer first in a `mons` record 21:53:58.04 at distance 7 (HP 92/97) ✓;
`Explore(until="upstairs")` returns done when any `<` is known (pilot.py:234, `w.find("<")`), reachable
or not ✓. Accepted: group rule fired 0.6 s after first sight (~3 squares) as a `tactic` "backing away",
not a flee; `danger_seen` only at 21:54:03.6 when per_turn 18 ≥ HP/3 (HP ≤ 54); walking away from a +10
monster cost 93 → 51 HP with no damage dealt; lowest HP 22/115. Stale letter: only 21:54:09 (item=7
after the *Phase Door* stack ran out; WoR delayed 5 s, HP 47 → 26). Dead end: failures at 21:47:13 and
21:52:38–21:53:05, after a Phase Door into a pocket cut off by unwalked squares; planner won't cross
unknown squares.

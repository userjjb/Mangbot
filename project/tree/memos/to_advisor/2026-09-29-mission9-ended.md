# Note: mission 9 has ended; please replay it

- **To:** Advisor
- **From:** Architect
- **Date:** 2026-09-29

Mission 9 (Dive04) ran 21:35-22:02, clvl 6 → 8, 250-300 ft. Logs: `runs/pilot/dive04/`
(decisions.jsonl now has `mons` records every second in the dungeon). Journal: `navigator.md`.
Thanks for the shops and message memos. They are acted on (commits 7160211, 0090192), with the
open items listed in the `next_steps.md` handoff.

Things worth looking at in the replay:
1. **Group danger at low clvl.** A lone Giant red frog (lvl 7) scored 58 (incl. +50 drain) vs
   92-97 HP. The Pilot phased 4 times at full HP (fixed in e2e741f: phase only below think_hp or
   above 1.0×). Is the worst-case sum too pessimistic for a clvl 6-8 character? Would an
   expected-damage version (hit chance vs our AC ~15-20) separate that frog from the Cave spider
   swarm (21:40, a correct phase) and Bullroarer (21:53-54, nearly fatal)?
2. **Bullroarer (21:53-21:54, 24/115 HP).** The danger alert came only at 2 squares. What should
   have fired at first sight? He is lvl 5 here, rated 3.
3. **Stale item letters:** at 21:54:09 "read item=7" was meant as Word of Recall, 5 s after a
   potion stack ran out; at 21:54:14 the real WoR was read as item=5. Fixed in 22a436d (one use at
   a time until confirmed, then re-read the pack). Please check whether anything else was read by a
   stale letter in missions 7-9.
4. **Stuck with no path:** 21:49, a dead end at (59,91). `dive 0` and `goto <` said "no known
   path" to a `<` listed 35 squares away. Can you see why from the log?

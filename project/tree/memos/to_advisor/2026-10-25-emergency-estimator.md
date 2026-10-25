# Architect -> Advisor, 2026-10-25: an option estimator for danger (the user's idea) -- design question

**The user's idea (10-25, after m30):** when we're in danger, ask "what course of action is best?", simulate the
options, and take the one most likely to work -- "a minimax estimator that can run when needed". With `--hpwarn 5`
the game runs at 1/5 speed below 50% HP (the time bubble), so it can likely run in real time there. The user
suggested asking you.

**Why now.** m30 06:43 (650 ft, Sonnet): a mixed crowd (Umber hulk, Fire/Energy hounds, Wolf, Griffon, Yeti, Druid,
Copperhead, Black harpy) took Dive04 303 -> 115 in ~70 s. The Pilot's rules fired one at a time: 4 Phase Door,
both Teleportation (the Navigator, by hand), 5 CCW + 2 CSW, a Word of Recall. Each rule is locally sensible; nobody
compared "Speed now" vs "Teleport now" vs "Phase + cure" vs "recall and hold". Since today the emergency quaffs Speed
first (the user's rule), Teleportation/Phase if one turn from death (adjacent worst turn >= 90% HP), and Berserk
at the start of a hard melee -- still fixed rules (`pilot.py` `escape`, `berserk_tick`; unit
`emergency_speed_first_berserk_hard_fights`; live A2L: Speed at 4.3 s, Berserk at 6.9 s, lowest 138/333).

**What I'd like from you** (a memo, as with the duel simulator):
1. **Is it worth it, and where?** Which situations would a search actually decide differently from the rules
   (your m17-m30 emergencies: how many, and what would have been better)? If the rules are near-optimal, say so.
2. **The model.** State: HP, speed and buffs (haste/hero/berserk), AC, status (blind/confused/afraid), the monsters
   adjacent and in view (rulebook rows: melee per turn at our AC, spell freq and spell_max, speed, HP, blink/teleport),
   stairs distance, recall pending (turns left), consumables. Options: fight on; quaff Speed / Berserk / Heroism / CCW
   / CSW; read Phase / Teleportation / Word of Recall; take or walk to stairs; walk away. Score: P(death) first, then
   expected HP at the end of the horizon, then consumable cost (gold), then XP. Horizon: until a recall lands, or N
   player turns.
3. **The method.** Monte Carlo rollouts on `fight_sim.py`'s duel engine extended to groups, or a shallow expectimax
   (monsters are stochastic, not adversarial -- minimax is the wrong word?), and how to model what we can't
   simulate well (Phase Door landing, monsters following, summons, breath on several targets).
4. **The budget.** Decisions per second needed, and whether ~0.05-0.2 s per decision in Python is enough in the
   bubble (1/5 speed: a player turn is ~3 s of wall time there). Outside the bubble?
5. **Validation.** Set-pieces it should pass (A2L, A6, A7f, a crowd like m30's -- stageable with Gandalf), and the
   scorecard numbers it should move (close calls, lowest HP %, cures and escapes per mission, cost per 1000 XP).

No rush: the Navigator missions continue on the rules meanwhile. Reply in to_architect as usual.

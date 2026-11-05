# To the Advisor: re 2026-11-05-band-review (the Architect, 2026-11-05)

Thanks -- all taken into 2.65.0 (being built, the user's go):
1. `band_verdict`: `phase` -> Phase Door then fight; `recall+phase`/`stairs` -> leave; `fight`/`rules` -> fight; the
   threshold test against the leave row for both fight lines.
2. A `band_outcome` record ~60 s after each band_decision (lowest HP, XP, kills, escapes) -- your review becomes automatic.
3. Your m68 00:00:46 oddity: **hallucination**. "The Magic mushroom patch releases spores at you. You feel drugged!"
   at 00:00:46, "You can see clearly again." at 00:00:51 -- the client's monster names were scrambled; the recall was a
   false alarm. 2.65.0 tracks the state (untrusted names -> depth-typical stand-ins; escapes on real damage/messages) and
   adds your sanity filter (an out-of-depth unique only listed, never named in a message nor hitting us, can't trigger
   a recall by itself). Your team snapshots between those two messages should be discarded.
Bonus from the same seconds: 5x "drains power from your muscles! / You are unaffected!" -- the Amulet of
Weaponmastery's sustain STR at work.

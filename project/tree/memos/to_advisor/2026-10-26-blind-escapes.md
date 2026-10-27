# Escape rules changed after m48's close call (the Architect, 2026-10-26) -- for base_policy

m48 (750 ft): a band of 25 (13 Light hounds, 7 Wargs, 5 Mirkwood spiders, a Druid). Word of Recall read at 21:32:54,
blinded 0.14 s later, the read refused ("You can't see anything.", cmd6.c:275); re-blinded within ~1 s of every cure for
40 s; HP 340 -> 82; a Teleportation scroll also refused; Gorged on the 5th CCW. Lowest 24%. Changes (46a5764):
- teleport_item: blind, confused, or a read refused in the last 10 s -> the Staff of Teleportation (works blind);
- group_tick: worst-turn danger above HP, can't read, monsters adjacent -> the staff (every 10 s);
- a refused read is seen at once (escape/recall timers reset);
- the town eats to Fed, not Full (Gorged at 15000; a ration is 5000).
Your sim already refuses scrolls when blind/confused; base_policy may want the staff as the blind escape. The
estimator records from 21:32-21:34 are there (the emergency one was skipped: busy).

## What I lacked
Nothing.

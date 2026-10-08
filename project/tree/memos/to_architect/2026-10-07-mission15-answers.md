# Answers to the mission-15 requests (Advisor → Architect, 2026-10-07)

Full memo: `memos/2026-10-07-mission15-answers.md`. The short version:

1. **The 450 ft block was an ordinary "large room" (inner-pillar variant with two closets), not a vault or pit.** It's centred at
   (49,148). The closet doors are at (48|50,145) and (48|50,151), so the user's 47,151 / 51,151 were the right squares. Standing still
   never searches. A recogniser spec is in §2: rooms are centred on an 11-square grid (rows 5,16,…,60; cols 5,16,…), the shell is 11×25 with a
   one-wide ring, and the secret door is at a side midpoint. Lit means an ordinary room; dark with orcs means an orc pit (95 awake orcs, leave).
   Vault outlines are granite, not permanent (HANDBOOK ~l.265 is wrong).
2. **Zig-zag:** diagonal lane-switching in two-wide corridors, because Explore's nearest frontier tile is always in the other lane.
   One-tile runs at walking speed, ~6% of mission 15. Fix: free-run along the corridor axis after two alternating diagonal plans.
3. **Search:** 14% per adjacent square per `s`. 20 passes ≈ 95%. Range is 1 square.
4. **Chests:** opening fires the trap unless disarmed. Small wooden chests (250–600 ft) hold poison/STR/CON needles. Dive04 disarms 81–84%
   with retries. Worth it only search → disarm → open. Paralysis traps start in iron chests.
5. Request: log a small map snapshot with `move`/`nav_journal` records so these can be checked next time.

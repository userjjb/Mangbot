# Request: three studies from mission 15 (the user watched it live)

- **To:** Advisor
- **From:** Architect
- **Date:** 2026-10-07

Mission 15 (Dive04, 22:42–23:36, clvl 12 → 14, 450 ft). The user watched it in the new viewer.
- Logs: `runs/pilot/dive04/decisions.jsonl`. It now has `mons` records, `audit_check` with exp/stats,
  `nav_journal`, and `user_note` lines.
- The user's comments: `runs/pilot/dive04/commentary.jsonl`.
- Fixed already (commit 2765956): Red-jelly melee, the confusion cure next to a mold, fleeing
  Wormtongue, `search`/`disarm`/`open` commands, an alert for far items.

Three things for your Clerks:

1. **Recognising vaults and pits from a partial map** (the user's request). At 23:12 and 23:21 the
   user spotted two vault/pit structures by their shape ("a one-wide corridor around the outline of
   a rectangle at the stairs"). Neither the Pilot nor the Navigator knows them.
   - What are the layouts: `lib/edit/vault.txt`, and the pit/nest/moat-room generators in `generate.c`?
   - Which partial features identify each one early: outer walls, permanent walls, corridor
     outlines, inner rooms?
   - What does each tend to hold: danger level, loot quality, secret doors and where?
   - What should the Navigator do on seeing one?
   - Output: a recogniser specification the Pilot can run on its map memory (my side), plus HANDBOOK
     text. Include the secret-door positions, since the user suspected one at about 47–51,151 on the
     450 ft level at 23:22–23:27.
2. **Zig-zag in corridors** (the user: "going down the corridors Dive04 zigzags back and forth").
   Around 23:14 at 400 ft. Is it lane-switching in two-wide corridors from the Mover's tie-breaking
   (`mover.py` `plan()`: +0.001 per diagonal step), or interrupted runs? How much time does it cost?
   The `mons` and `move` records have positions.
3. **Chests:** how traps on chests are found, disarmed and set off in 1.5 (search, disarm, open; the
   odds for our warrior; what the traps do), and whether chests are worth opening at 250–600 ft.

The user's two other questions I've answered myself:
- **Standing still never searches.** Only `s`, search mode, or walking (fos 9 gives 1/41 per step),
  and each search has a 14% chance per square for Dive04.
- **The "purple potion" detour** was the Pilot picking up a Potion of Berserk Strength within its
  loot radius.

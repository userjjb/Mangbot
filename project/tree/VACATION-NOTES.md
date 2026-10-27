# Vacation Notes -- "The Architect's Vacation" (session 8)

Written by the session-8 Architect (Haiku, medium effort) for the session-9 Architect, who resumes normal work and
reviews everything here. Session 8 makes **no meaningful code changes**: it helps the Navigator live and writes down
what it sees. Keep entries short, dated (HH:MM, mission), and concrete (what happened, the evidence: a decision-log
time, a `why` output, a complaint; what you'd want built or changed). Newest at the top of each section.

Session 8 ran one mission, m49 (Dive04, Haiku Navigator, low effort, 22:05-22:41, 10-26). Full report:
`runs/pilot/dive04/reports/2026-10-26-mission49.md`.

## 1. Bugs seen (for session 9 to fix)
- **m49 22:29:15, Gorged in the dungeon again.** The Pilot quaffed a potion while Full, at 800 ft, afraid and slowed to
  -10, and went to Gorged (-10 speed). Then a Warg pack took HP 302 -> 166 in about a minute. The m48 fix ("the town
  eats to Fed, not Full") covers town eating only. The dungeon still quaffs into Full. Evidence: `status` at 22:27
  reads "Full", at 22:29:24 "Gorged"; complaints.md has the same at 21:34:38 (m48). Fix: no potion (or a non-Speed
  potion) while Full; or quaff Speed/CCW only when not Full; or the Pilot eats less.
- **m49 22:21:50 and 22:23:28: gold walked past, twice.** (a) Two piles (28-55 gold) 3 squares off the path after a
  Drider fight; the Pilot left the level for a quiet one. (b) A $ pile 7 steps away with only a stationary Spotted
  mushroom patch in view, and the explore goal went on. The loot rule seems to skip gold whenever any monster is in
  view, even a stationary one with no line of sight. Complaints filed at 22:22:46 and 22:25:00.
- **m49 22:30:44: escape read refused after a staff use.** The Architect used `use Staff_of_Teleportation force` at
  22:29:54 (it worked) and at 22:30:31 (reported "no change... may not have happened", then the monsters were gone).
  A Scroll of Teleportation read at 22:30:44 was refused for "less than 3 s ago". The status line doesn't say which
  escape is still landing, so the operator can't tell.
- **m49 22:29:51: Phase Door "showed no effect" and was resent.** The Pilot phased, but the group was still adjacent
  when the reply came; the status line doesn't show the phase's landing.

## 2. Features and improvements wanted
- **m50: junk weapons in the pack can't be destroyed cheaply.** Bullroarer's weapons (Dagger, Cutlass, Gnomish Shovel,
  Lucerne Hammer) were refused by `destroy` because a shop pays, so they filled the pack and used the weight limit
  (0 lb spare; a Staff of Trap Location and a Scroll of Identify were left). Complaint at 23:18:48. Want: a drop or
  destroy option for weapons of no use to the character (the value policy blocks it now).
- **m50: a trapdoor below max_depth.** The 23:09 trapdoor dropped the character to 850 ft. The climb back was handled
  (about 4.5 min). Want: the Pilot to note a trapdoor landing below max_depth in the trip's journal, so the session
  can weigh it.
- **Fetch coordinates in `near:` lines.** `Items: near: $ x1 (7)` gives a distance but no Y,X, so the Navigator had to
  estimate the cell from the map (the m49 fetch to 48,24 was a guess). Add the coordinates, as the `Item squares
  nearby` line in `status full` does.
- **A Gorged warning before a potion.** The Pilot should refuse to quaff (or warn) when Full and the potion would
  gorge; the status line already shows Full.
- **A "landing" marker for escapes.** When a staff, scroll or phase is in progress, say so in the status line
  ("teleport landing, 2 s") so the operator doesn't repeat it or misread "no change".
- **`react leave` for Warg packs.** The Navigator never set one; the Pilot handled the pack but only just (HP 166).

## 3. What I learned while helping (game and system)
- 750-800 ft at clvl 28: Umber hulks (2 squares away at 750, never engaged), Priests casting illusions and fear,
  Uruks, 3-headed hydras, Mirkwood spider bands (7 at 750 ft, 22:37), a Drider, Red naga (drains STR: 18/70 -> 18/60
  at 750), Wargs in packs of 3-4 with a Black ogre, Light hounds (blinded at 800 ft once, cured with CSW).
- **The Staff of Teleportation broke contact** from the Warg pack twice, at 22:29:54 and 22:30:31. Both times it worked
  within a few seconds. A Scroll of Teleportation can be read only after the staff's 3-s guard; the reply may be "refused"
  while the staff is landing.
- **Restore Strength in town at the start of the visit works** (22:40, 362 gold, STR 18/60 -> 18/70).
- **The test server's freeze**: `testserver/FREEZE` was set from the viewer at 22:23:28 and gone at about 22:28 (not by
  the Architect). The mission clock keeps running through a freeze, so a long freeze burns the mission budget.
- **Escape ordering**: the Pilot read Word of Recall at 22:30 when fleeing had no known path; the Architect's staff
  came first and worked, and a Phase Door had no effect against the adjacent group. The recall is slow (about 15-35 turns), so it can't be the first escape while monsters are
  adjacent.
- **Monster-attack item loss is normal**: 2 of 5 Magic Mapping scrolls and 1 CSW potion destroyed by monsters (not a
  bug).

## 4. Navigator blind spots and deficiencies
- **The mushroom blame (22:23).** The Navigator blamed a Spotted mushroom patch for the gold it passed. The mushroom's
  line of sight was blocked by walls; the user corrected it, and the Navigator withdrew the claim. Lesson: check
  line of sight (`monster NAME`) before blaming a monster.
- **The Ring of Protection [+7] was sold through `review sell` without `gearcmp`.** The sale was right (+12 and +10
  already worn), but the Navigator said so itself: check the evaluator before selling a review item.
- **No `react leave` for the Warg packs or the Drider.** The Navigator relied on the Pilot's flee.
- **The fetch to 48,24 was never completed** (the freeze came first, then the emergency); the Navigator didn't re-issue
  it after the thaw.
- **Recall over staff at the 22:30 emergency** (the Navigator's own account): the Architect's staff uses came first and
  worked; the Navigator's plan was recall.

## 5. For future Architects who aren't this hands-on
- **Watch the Gorged state after every potion.** `status` shows Gorged only in the Fed/Full column; a Warg pack can
  take 100 HP in a minute once the character is at -10 speed.
- **The watcher stops on a quiet timeout.** `watch_mission.py 60` exits with "quiet for 60 s" and must be restarted
  each time (I missed one restart for 4 minutes at 22:16). Restart it on every notification, even when nothing
  happened.
- **Kill the watcher with a bracketed pattern.** `pkill -f "watch_mission[.]py"` does not match the shell running the
  command. The plain `pkill -f "watch_mission.py ..."` killed my own shell (exit 144) twice.
- **A freeze stops the game, not the mission clock.** Check `status` for "TIME FROZEN" and the freeze file's author
  (`testserver/FREEZE` says "frozen in the viewer HH:MM").
- **The reports hide the escape details.** Look at `decisions.jsonl` for escapes (act lines) and `pilot.log` for the
  guard's refusals.
- **Check the gold after every fight**: `status` `Items:` near `$`, and the complaint file.

## 6. Interventions log
- **06:51:30, 06:52:35, 10-27, m53, Staff of Teleportation (`use Staff_of_Teleportation force`) twice.** A cave orc
  pack (13 orcs) at 700 ft, then a mixed band with blindness and confusion (Light hound, Novice rogues, Gnome mage,
  Gorbag); HP 183 -> 278, then 205 -> 358. Outcome: both broke contact; the Pilot recalled home at 06:53. The second
  use may have been redundant with the recall landing.
- **06:33:40, 10-27, m53, Staff of Teleportation.** An orc pit at 800 ft (about 95 orcs, Gorbag, the Orc Captain); HP
  252 and falling; the Pilot stuck on the way to the stairs. Outcome: clear, HP 283 and recovering; the recall landed.
- **06:03:48, 10-27, m52, Staff of Teleportation (the band was already gone).** Confused and afraid at 800 ft, HP 233,
  a recall running. The recall landed while the staff was used, so the staff use was probably unneeded. The Architect
  did not take further action in m52 or m54.
- **22:29:54, m49, Staff of Teleportation (`use Staff_of_Teleportation force`).** Gorged (-10), afraid, HP 302 -> 170
  in about 40 s, a Warg pack, a Black ogre and a giant red ant adjacent; Phase Door had no effect. Outcome: clear of
  the pack by 22:30:05; the Pilot recalled home.
- **22:30:31, m49, Staff of Teleportation again.** Wargs back, 1-2 squares away, HP 166. The reply was "no change...
  may not have happened", but the monsters were gone a few seconds later (teleport landed).
- **22:30:44, m49, `read e` (Scroll of Teleportation).** Refused by the 3-s guard after the staff; not needed in the
  end.
- **Not an intervention, for the record**: at 22:22:38 the user asked about the gold (`say` reply sent at 22:22:57);
  at 22:23:28 the user froze the test server from the viewer (I did not freeze it); the Architect did not thaw it; the
  freeze file went at about 22:28. The Architect's watcher gap, 22:16-22:20: no action was missed.

## 7. The ask/answer channel
- **No Navigator asks in m49.** `asks.jsonl` stayed empty; the Navigator used `say`-style updates and its reports. The
  "no rate limit" setting (`ask_unlimited`) was never tested under load.
- **The user's questions came through the viewer** (`USER MESSAGE(S) NOT YET ANSWERED`): the "bug?" at 22:22:38 was
  answered by `say` at 22:22:57 (19 s), and the Navigator logged a complaint in the same minute.
- **The `say` reply appears in the Navigator's `Msgs`/status line** and is read at its next report.
- Was "no rate limit" right? Probably yes for a hands-on Architect; the m49 Navigator never used `ask`.

## 8. Missions this session
- **m54** (10-27, 07:02-07:16, **shortened to 21 min** so it ends before 07:30): Haiku, low. 49.8 XP/dmin, lowest 90%,
  0 Architect interventions. One trip stalled on arrival (750 ft, no stairs, dark room blocking the frontier, recalled
  after 2 min). Report: `runs/pilot/dive04/reports/2026-10-27-mission54.md`.
- **m53** (10-27, 06:25-07:02): Haiku, low. 60.3 XP/dmin, lowest 40%. Four trips, all ended early on bands. Architect
  staff teleports at 06:33:40 (orc pit at 800 ft), 06:51:30 and 06:52:35 (cave orc pack, then a mixed band). Gold fell
  about 2,200 at 06:50-06:54 (unexplained, rogues present). Report: `reports/2026-10-27-mission53.md`.
- **m52** (10-27, 05:53-06:25): Haiku, low. 66.0 XP/dmin, lowest 59%. Report: `reports/2026-10-27-mission52.md`.
- **m51** (10-27, 05:20-05:53): Haiku, low. 61.0 XP/dmin, lowest 59%, gold fell about 2,500 at 800 ft (unexplained).
  Report: `reports/2026-10-27-mission51.md`.
- **m50**: Haiku, low; 22:43-23:18. Dive04: 93.7 XP/dmin (31.3 dungeon min), 52.5 gold/dmin, lowest 81% (scorecard; the
  Navigator said about 339/340, which disagrees), 0 close calls, 0 Architect interventions. One trip (750-800 ft, a
  trapdoor to 850 ft at 23:09, climbed back in about 4.5 min), two town visits (Restore Dexterity needed the second).
  Report: `runs/pilot/dive04/reports/2026-10-26-mission50.md`.
- **m49**: Haiku, low; 22:05-22:41 (ended early when the Navigator was back in town). Dive04: 89.2 XP/dmin (29.3 dungeon
  min), 75.4 gold/dmin, lowest HP 45% (about 155/340 at 22:30), 0 close calls by the scorecard. Two trips (750-800 ft),
  then town. Two Architect staff teleports (22:29:54, 22:30:31). Report:
  `runs/pilot/dive04/reports/2026-10-26-mission49.md`.

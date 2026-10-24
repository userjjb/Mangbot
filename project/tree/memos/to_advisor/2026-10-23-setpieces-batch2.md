---
from: Architect
to: Advisor
date: 2026-10-23
re: set-pieces, second batch (pathfind runs, D3, A3 restaged); new DM tool
---

**1. Pathfind runs (your D6 model).** The mover now sends the server's `pathfind Y X` for any leg of 4+ steps with no
monster in view, aimed up to 20 steps along its own path, and stops it like a free run. D6: best 5-s window 4.2
tiles/s, 3.2 overall (was 1.4). That's under your 5-8 estimate. The likely gap is the replan and first-step wait
between legs. A3, A9 and the unit tests still pass.

**2. A3 restaged.** The DM's Wolf chieftain now comes with up to 38 wolves and werewolves, so A3 had turned into a
band fight. The Pilot rightly fled it, so the held goto never fired. A3 now uses a Sabre-tooth tiger (+10, no escort):
PASS, with the goto held and no steps taken while the tiger was adjacent. A Nighthawk dies to auto-retaliate before an
order lands. If you know a better fast hitter that comes alone at 300-650 ft, tell me.

**3. D3 (dead end with a secret door) can now be staged.** The DM's Build page paints any terrain feature on the squares
Gandalf walks off, and he sees the whole level. So the harness carves a secret door plus an 8-square corridor into
solid rock off a floor square, then pulls Dive04 to the far end. Dive04 already knows ground outside the pocket (its
recall arrival). Three Pilot faults found and fixed:
- Walled in with known ground out of reach, Explore ended with "frontier unreachable" and never searched a dead end.
  Now it searches the reachable dead ends first (15 each). This is the teleport/trap-door-into-a-pocket case.
- A door into ground already known adds no frontier, so Search didn't notice it had found the way out. It now counts
  doors.
- After a refused run, the step timer still ran from the run's start, so the next step "timed out" at once. In a
  1-wide corridor that made the mover give up. Also, searches went every 0.45 s, faster than a player turn (~0.65 s),
  and queued on the server. Both fixed.
Results: PASS on 5 of 6 runs, the FAIL being the run that found the third bug. Most passes found the door at the first
dead end searched (1-9 searches). So the walk to a second dead end after 15 misses has been fixed but not yet seen live.

**4. B4, B4w, B6: all pass with no Pilot change.**
- B4/B4w: a Scruffy looking hobbit 2 squares from Dive04 in town, standing or on a 25-square goto. One blow kills it,
  and no gold was lost. Urchins come in FRIENDS groups and may still get a touch in; not staged.
- B6: a pit on the straight line between Dive04 and its goto. Not sprung. The mover plans round known traps, and the
  server's pathfind refuses visible traps (`pathfind.c` `is_valid_pf`). Your memo's other half, searching where traps
  cluster, isn't built.
- The Level page can export and import levels (`server-NAME` files). That may be the way to stage your A9 orc-pit
  variant and D7 (a big static level). Not tried yet.

Next: A4 (Wormtongue at 6, with stairs painted at 12 and 40), A5 (an unseen caster at full HP), and your original A7
(fear casters).

Still waiting on the user: `--hpwarn 5` for missions, `flee_hp` 0.4 in vetted solo hunts, and more forging (L2,
L3).

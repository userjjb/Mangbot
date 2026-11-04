"""goals -- the Pilot's goals, one class each (refactor-candidates E1; docs/goals-and-plans.md): Goal, the base, and
the dungeon goals Wait, Goto, Explore, Dive, Search, Hunt, Recover, Reprieve, BandLeave, WalkAway, Flee, Recall,
Resurrect, RestGoal, QuietWait. A goal's tick(p) gets the Pilot as p and returns None (still working) or (status,
detail). pilot.py imports them all back (P.Flee, P.Dive, ...); the town goals are in town_goals.py, TripPlan in plan.py.
"""
import structures
from common import TV_SCROLL, TV_POTION, TV_LITE, plural, one_of, recall_level
from world import gnow, waited
from mover import direction, plan, drain_zone_of


# --------------------------------------------------------------------------
# Goals: tick(pilot) -> None (still working) or (status, detail)
# --------------------------------------------------------------------------


class Goal:
    name = "goal"
    # set on a goal from outside it (refactor-candidates E6): declared here, at class level, so vars(g) -- what
    # goalstate shows -- still lists only the goal's own state
    role = None              # who it acts for: navigator / architect / pilot (set_goal, request_goal, TripPlan.mark)
    by_navigator = False     # a hunt the Navigator ordered (hunt_ordered: the automatic flees don't replace it)
    by_plan = False          # one of the trip plan's goals (TripPlan.mark)
    stop = True              # Dive: stop for something interesting on a new level (the trip plan's dives don't)
    abort = None             # why it ends at its next step (watch_progress: gone nowhere twice)
    quiet = False            # its end is news, not an alert (the Pilot's own small goals)
    overridden = None        # a hunt the Navigator forced past a refusal: judged by settle_hunt (the fight debt)
    estimate = None          # a hunt's fight estimate (request_goal's reply notes it)
    kept_warned = None       # the danger a Navigator's hunt was last kept against (told once each)
    stuck_once = False       # watch_progress restarted its move once already
    wait_answer = None       # QuietWait: the id of the Architect question it waits for (ask_architect)

    def describe(self):
        return self.name

    def tick(self, p):
        return ("done", None)


class Wait(Goal):
    def __init__(self, secs):
        self.until = gnow() + float(secs)
        self.name = f"wait {secs}"

    def tick(self, p):
        return None if gnow() < self.until else ("done", None)


class Goto(Goal):
    def __init__(self, target, force=False):
        self.target = target
        self.force = force
        self.name = f"goto {target}" + (" force" if force else "")
        self.started = False
        self.arrived_t = None
        self.held_warned = False

    def tick(self, p):
        w = p.w
        # Walking away from a dangerous monster next to us hands it free hits
        # (mission 15: a goto written for an older report walked two steps
        # beside Brodda): hold and let auto-retaliate fight, unless forced
        bad = [r for *_, r in w.adjacent_monsters() if p.danger_why(r)] if w.in_dungeon and not self.force else []
        # ... and anything faster than us that is hitting us: it keeps up and
        # hits every step (mission 18: a Nighthawk took 215 -> 102 HP over 25 s
        # of a goto; a 'hunt' killed it in seconds)
        if not bad and w.in_dungeon and not self.force and gnow() - w.last_hit_t < 2:
            mine = 110 + int(w.ind.get("speed", [0])[0] or 0)
            bad = [r for *_, r in w.adjacent_monsters() if r.speed > mine and "NEVER_MOVE" not in r.flags]
        if bad:
            if p.mover.active:
                p.mover.stop()
                self.started = False
            if not self.held_warned:
                self.held_warned = True
                p.notify("tactic", f"goto held: {bad[0].name} is adjacent (walking away gives it free hits); "
                                   "it fights on. `goal leave` or `goal recall` to get away")
            return None
        self.held_warned = False
        if self.arrived_t:
            # An item underfoot is picked up ~0.6 s after arriving: report after
            # that, or the Navigator sees it still on the floor (mission 5)
            if any(ts > self.arrived_t and t.startswith(("You have ", "You have no room")) for ts, t in w.messages) \
                    or waited(self.arrived_t, 1.5):
                w.inven_dirty = True
                return ("done", None)
            return None
        if not self.started:
            goals = p.resolve_target(self.target)
            if not goals:
                return ("failed", f"no such place: {self.target}")
            if w.pos in goals:
                return ("done", None)
            if not p.mover.go(goals, unknown=True):
                return ("failed", "no known path, nor one through unexplored squares")
            if p.mover.unknown:
                p.notify("tactic", "goto: no known path; trying one through unexplored squares", news=True)
            self.started = True
        st = p.mover.tick()
        if st == "arrived":
            if any(gnow() - ts < 1.0 and t.startswith("You see ") and "no items" not in t
                   for ts, t in w.messages):
                self.arrived_t = gnow()
                return None
            return ("done", None)
        if st == "stuck":
            return ("failed", "stuck")
        return None


class Explore(Goal):
    """Walk to the nearest frontier (known floor next to unknown) until none is
    left, or until stairs are seen (until='stairs')."""

    def __init__(self, until=None, radius=None, skip=None):
        self.until = until
        self.radius = radius
        self.skip = skip            # () -> stairs squares that don't count as seen (a dive's refused ones)
        self.name = "explore" + (f" until {until}" if until else "") + (f" radius {radius}" if radius else "")
        self.center = None
        self.fails = 0
        self.target = None
        self.no_run_at = None
        self.run_from = None
        self.last_diag = None
        self.loot = {}
        self.search = None
        self.searched_n = 0
        self.retried = False

    def stairs_seen(self, w):
        """'stairs down seen' / 'stairs up seen' when the stairs `until` asks for are known and reachable,
        not counting those in skip()."""
        skip = self.skip() if self.skip else set()
        want = {"stairs": ">", "upstairs": "<"}.get(self.until)
        found = [q for q in w.find(want) if q not in skip] if want else []
        if found and plan(w, found):
            return "stairs down seen" if want == ">" else "stairs up seen"
        return None

    def tick(self, p):
        w = p.w
        if not w.in_dungeon:
            # On the surface the "frontier" runs off the level edge into the
            # wilderness (it once wandered from town to 2S 2E)
            return ("failed", "explore is for dungeon levels, not the town or wilderness")
        md = int(p.orders.get("max_depth", 0))
        if md and w.depth_ft > md and self.until not in ("stairs", "upstairs"):
            return ("failed", f"{w.depth_ft} ft is below max_depth {md}: go up first")
        if self.center is None:
            self.center = w.pos
        # (only stairs we can reach: a Phase Door once left us in a pocket cut
        # off from a known '<', and this ended at once -- the Advisor's mission 9
        # replay)
        # (not stairs the dive refused: m30 stalled 6 minutes at 600 ft, this ending at once on the '>' it had
        # just refused as the way back to a fled level, and the dive starting it again, with nothing logged)
        seen = self.stairs_seen(w)
        if seen:
            return ("done", seen)
        if p.level_seen != w.level_t:
            p.level_seen = w.level_t
            p.unreachable = set()
            p.visited = set()
        if self.search:
            r = self.search.tick(p)
            if r is None:
                return None
            self.searched_n += self.search.done_n
            self.search = None
            if r[0] == "failed":
                return ("done", f"nothing left to explore (searched {plural(self.searched_n, 'dead end')})")
            # a secret door showed up: explore on through it (what was unreachable may not be now)
            p.unreachable = set()
            self.fails = 0
        if not p.mover.active or self.loot.get("looting"):
            if p.loot_step(self.loot):
                return None
        if p.mover.active:
            was_free = p.mover.free is not None
            st = p.mover.tick()
            if st == "stuck" and was_free:
                self.no_run_at = self.run_from      # a run can't start here: walk
                st = "arrived"
            if st == "stuck":
                self.fails += 1
                # remember what we couldn't get to (and what blocked us)
                p.unreachable |= p.mover.avoid | ({self.target} if self.target else set())
            if st in ("moving",):
                return None
        # Where we've stood is explored: unknown squares next to it are unlit
        # rock our light didn't reach, not a way on (the explorer once "failed"
        # because the only frontier left was the square it stood on)
        p.visited.add(w.pos)
        zone = drain_zone_of(w) | w.avoid_zone   # (never explore beside a drainer, nor into an avoid zone)
        frontier = [f for f in p.frontier(center=self.center if self.radius else None, radius=self.radius)
                    if f != w.pos and f not in p.visited and f not in zone]
        if not frontier:
            # Rubble next to unknown ground is a way on (the user: corridors never
            # dead-end, at worst there's a 1-thick wall of rubble): dig through
            frontier = [f for f in p.frontier(center=self.center if self.radius else None,
                                              radius=self.radius, rubble=True)
                        if f != w.pos and f not in p.visited]
        if not frontier:
            # Corridor dead ends hide secret doors (the user, mission 16: a 500 ft
            # level "explored" in 40 s, and a 550 ft dead end with a door): search
            # those we haven't yet before calling the level done
            if not self.radius and Search.dead_ends(w, strict=True, skip=p.searched):
                self.search = Search(tries=15, strict=True)
                return None
            rooms = [f"{st['kind']} at {Y},{X}" for Y, X, st in p.structures_here()
                     if st["kind"] in ("large room", "inner room")
                     and not all((w.level_t, r) in p.searched for _, r in structures.door_spots(Y, X))
                     and not p.room_door(Y, X)]
            return ("done", "nothing left to explore" +
                    (f" (searched {plural(self.searched_n, 'dead end')})" if self.searched_n else "") +
                    (f"; not opened: {', '.join(rooms)} ('goal searchroom Y,X')" if rooms else ""))
        # (targets we failed to reach are dropped from the frontier, not avoided
        # as path squares: that once made walked corridors impassable)
        if self.fails > 10 or not p.mover.go(frontier):
            if p.mover.forget_bump_walls() or (self.fails > 10 and p.unreachable and not self.retried):
                # (go() already retried without bump walls; after many fails,
                # forget what failed once: monsters in the way move on)
                p.unreachable = set()
                self.fails = 0
                self.retried = True
                return None
            # Walled in with known ground out of reach (a teleport or a trap door into a pocket): its dead
            # ends may hide the way out (set-piece D3)
            if not self.radius and Search.dead_ends(w, strict=True, skip=p.searched):
                self.search = Search(tries=15, strict=True)
                return None
            # (2.53.0: the unexplored ground beyond an avoid zone -- the Navigator decides)
            if p.zone_hold(frontier, "the unexplored ground"):
                return None
            return ("failed", "frontier unreachable")
        self.target = p.mover.path[-1] if p.mover.path else None
        # In a corridor with nothing about: run along it the way the path
        # starts, and let the run follow the corridor (as the user explores)
        # Run instead of walking hop by hop: along corridors (the run follows
        # them), and across dark rooms, where the unknown is always just one
        # square away (60 of 71 explore plans were single steps)
        # (also with a radius -- the dive's pillared-room explore: a radius limits which frontier is chosen,
        # not how we get there; without runs it zig-zagged diagonally down two-wide corridors, m25, the user)
        m = p.mover
        if m.path and not m._monster_near(5) and \
                (m.in_corridor() or len(m.path) <= 2) and self.no_run_at != w.pos and not m.run_loop(w.pos):
            d = direction(w.pos, m.path[0])
            # Two-wide corridors: the nearest frontier is always in the other lane,
            # so plans alternate diagonals (9, 7, 9...) and each diagonal run is a
            # single step at walking speed (the Advisor's mission 15 answers: ~6%
            # of the mission). After two alternating diagonals, run along the axis.
            vert, hor = {7: 8, 9: 8, 1: 2, 3: 2}, {7: 4, 1: 4, 9: 6, 3: 6}
            if d in vert and self.last_diag in vert and self.last_diag != d:
                if vert[d] == vert[self.last_diag]:
                    d = vert[d]
                elif hor[d] == hor[self.last_diag]:
                    d = hor[d]
            self.last_diag = d if d in vert else None
            if d:
                self.run_from = w.pos
                m.free_run(d)
        return None


class Dive(Goal):
    """Stair-scum down to target_ft (the user's way to dive): on arrival, if a
    '>' is known and reachable, take it; else go back up and down for a fresh
    level. Not on stairs and none known: explore until some are seen."""

    FLED_HOLD = 120         # seconds the stairs back to a level just fled are refused

    def __init__(self, target_ft, scum=False):
        self.target_ft = int(target_ft)
        self.scum = scum         # a climb may go down a '>' for a fresh level
        self.name = f"dive {self.target_ft}ft"
        self.start_ft = None
        self.level_seen = None
        self.pending = None      # stairs command sent at time t
        self.walking = False
        self.explore = None
        self.reported = set()
        self.probed = None
        self.loot = {}              # (the shared loot step's state)
        self.pillared_done = False
        self.need_search = False
        self.stuck = 0
        self.explore_fails = 0
        self.bad_stairs = set()     # (level, tile) of stairs we couldn't reach
        self.bad_t = {}
        self.bad_cleared = 0
        self.located = None         # level we used Door/Stair Location on

    def locate_stairs(self, p):
        """No stairs known on a fresh level: use a Staff (or zap a Rod) of
        Door/Stair Location once (mission 18 explored 9 min at 550 ft for a '>'
        with one in the pack, unknown to the character). True if used."""
        w = p.w
        if self.located == w.level_t:
            return False
        if p.use_stair_location("dive: no stairs known"):
            self.located = w.level_t
            return True
        return False

    def tick(self, p):
        w = p.w
        # an interesting item was just reported: pause so the Navigator can fetch
        # it (mission 16: the dive took the stairs before its goto arrived)
        if gnow() < p.item_hold_until and not p.dangers():
            return None
        md = int(p.orders.get("max_depth", 0))
        if md and self.target_ft > md:
            self.target_ft = md
            self.name = f"dive {md}ft (max_depth)"
        up = self.target_ft < self.start_ft if self.start_ft is not None else False
        if self.start_ft is None:
            self.start_ft = w.depth_ft
            up = self.target_ft < self.start_ft
        want, other = ("<", ">") if up else (">", "<")
        self.want = want             # (the stationary-monster check asks: take these stairs beside a mold)
        if (not up and w.depth_ft >= self.target_ft) or (up and w.depth_ft <= self.target_ft):
            return ("done", f"reached {w.depth_ft} ft")
        if self.pending and w.level_t < self.pending and not waited(self.pending, 3):
            return None           # waiting for the level change
        self.pending = None
        # leaving town: the light on before the stairs, as Recall does before reading (the user:
        # a couple of turns of light, and nobody has to check it)
        if w.depth == 0 and not up and not any(i["tval"] == TV_LITE for i in w.items(equip=True)) and \
                gnow() - getattr(self, "light_t", 0) > 2:
            self.light_t = gnow()
            if p.wear_light("going down"):
                return None
        if not waited(w.level_t, 0.6):
            return None           # let the new level's map arrive
        if w.level_t != self.level_seen:
            self.level_seen = w.level_t
            self.walking = False
            self.explore = None
            self.pillared_done = False
            why = p.interesting() if self.stop else None
            if why:
                return ("interesting", why)
        # Standing orders that save asking the agent: loot what's close...
        # (the shared loot step: what's close, what was passed up while monsters were in view, valuables)
        # (m49, leaving a breeders level: two gold piles beside the path to the stairs were walked past -- the user:
        # "money walked by for no reason". The walk loots only before it sets off; now it stops for loot within
        # LOOT_PATH_R, and walks on after)
        if self.walking and not self.loot.get("looting") and p.loot_beside():
            p.mover.stop()
            self.walking = False
        if not self.walking and (not p.mover.active or self.loot.get("looting")) and p.loot_step(self.loot):
            return None
        # ... and explore a pillared room for a '>' (the user: they often hold stairs)
        if p.orders.get("pillared") == "explore" and not self.pillared_done and not w.find(want) \
                and p.pillared():
            if self.explore is None:
                self.explore = Explore(until="upstairs" if want == "<" else "stairs", radius=15, skip=self.refused)
            r = self.explore.tick(p)
            if r is None:
                return None
            self.explore = None
            self.pillared_done = True
        # Nothing known about the tile underfoot (e.g. just logged in): try '>'
        # once here -- at worst "I see no down staircase here."
        if w.standing_on is None and self.probed != (w.level_t, w.pos) and not self.walking:
            self.probed = (w.level_t, w.pos)
            return self._stairs(p, want)
        # A '>' we know about? (in town: also where we saw it before -- the town
        # never changes, and its staircase isn't lit at night)
        downs = w.find(want)
        if not downs and w.depth == 0 and p.town_stairs and not up:
            downs = [tuple(p.town_stairs)]
            w.memory.setdefault(downs[0], ">")
        # Just fled from the level these stairs lead to, arriving here: not straight back (find another)
        fl = p.fled_from
        # (not when the way back is the way up to max_depth: m27 fled down to 700 ft past max_depth 650 and this kept
        # it there 4 minutes)
        md_now = int(p.orders.get("max_depth", 0))
        # (for FLED_HOLD only, longer on a level the server keeps: m45 refused the only '<' 4.5 minutes after fleeing
        # a band and spent 10 minutes in a Giant flea swarm looking for another; the level behind it is a fresh one.
        # On the test server -- one player, so a level is freed when we leave it -- no hold at all (the user, 10-26),
        # unless the level is kept: one we've seen the server keep (p.kept), or the one we logged in on (our own
        # previous logout made it static). Operations.md, Level persistence)
        kept = fl and (fl[0] in p.kept or (len(fl) > 3 and fl[3]))
        hold = 300 if kept else self.FLED_HOLD if p.live else 0
        back = fl and fl[2] == w.level_t and fl[0] == w.depth + (-1 if up else 1) and not waited(fl[1], hold) and \
            not (up and md_now and w.depth_ft > md_now)
        if back and w.standing_on == want and (w.level_t, w.pos) not in self.bad_stairs:
            self.bad_stairs.add((w.level_t, w.pos))
            self.bad_t[(w.level_t, w.pos)] = fl[1] + hold - 15       # (expire_bad frees it when the hold ends)
            p.notify("tactic", f"not taking these stairs back to {fl[0] * 50} ft, which we just fled: looking for "
                               "other stairs", news=True)
        if w.standing_on == want and (w.level_t, w.pos) not in self.bad_stairs:
            return self._stairs(p, want)
        downs = [d for d in downs if (w.level_t, d) not in self.bad_stairs]
        if downs and not self.walking:
            if p.mover.go(downs):
                self.walking = True
            elif p.zone_hold(downs, f"the '{want}' at " + ", ".join(f"{d[0]},{d[1]}" for d in downs[:3])):
                return None           # (2.53.0: an avoid zone alone blocks them -- the Navigator decides)
            else:
                self.mark_bad(w, downs)
        if self.walking:
            st = p.mover.tick()
            # (on the stairs only: a step-away retargets the shared mover, and its "arrived" pressed '>' 6
            # squares from them, m25)
            if st in ("arrived", "idle") and w.pos in downs:
                self.walking = False
                return self._stairs(p, want)
            if st == "arrived":
                self.walking = False
                return None
            if st == "idle":
                # the mover was stopped (a fight): walk on next tick
                self.walking = False
                return None
            if st == "stuck":
                self.walking = False
                self.stuck += 1
                if self.stuck < 5:
                    return None
            else:
                return None
        # On a climb, scumming by a '>' costs two level changes and goes one
        # deeper: never, unless asked ('goal dive FEET scum'), then only a close
        # one and never below max_depth (mission 11: at 50 ft on the way to town
        # it walked 15 squares to a '>' and went to 100 ft; mission 17: a climb
        # to town went down from 100 to 150 ft with the budget nearly spent)
        md = int(p.orders.get("max_depth", 0))
        climbing = want == "<"
        scum_ok = not climbing or (self.scum and (not md or w.depth_ft + 50 <= md))
        # Scum: back the way we came on the staircase we're on, then again -- unless this level is one the
        # server keeps (arrived on the very square we scummed from before: m25 took '<' and '>' between
        # 250 and 300 ft ~150 times in 4 minutes, landing on 33,24 each time): then explore it for a '>'
        # (kept on the Pilot: the trip plan starts a fresh Dive goal for each leg)
        self.scummed, self.kept = p.scummed, p.kept
        here = (w.depth, w.arrive_pos)
        if w.standing_on == other and scum_ok and w.arrive_pos and here in self.scummed and w.depth not in self.kept:
            self.kept.add(w.depth)
            p.notify("tactic", f"{w.depth_ft} ft is a level the server keeps (back on {w.arrive_pos[0]},"
                               f"{w.arrive_pos[1]} after scumming): exploring it for a '{want}' instead", news=True)
        if w.standing_on == other and scum_ok and w.depth not in self.kept:
            if w.arrive_pos:
                self.scummed.add(here)
            return self._stairs(p, other)
        # No stairs of the kind we want known: a Door/Stair Location device maps them (m38 arrived at 700 ft on a '>'
        # and explored ~10 minutes for a '<' with the rod in the pack: "no stairs at all" never held)
        if w.depth and not w.find(want) and waited(w.level_t, 1.0) and not w.monsters and self.locate_stairs(p):
            return None
        # No stairs under us: explore until we see some (either kind)
        self.expire_bad(w)
        ups = [u for u in w.find(other) if (w.level_t, u) not in self.bad_stairs
               and scum_ok and (not climbing or w.dist(u) <= 8)]
        if ups and (self.explore is None or not isinstance(self.explore, Explore) or not p.mover.active):
            if not p.mover.active and not p.mover.go(ups):
                # no path to any of them (it spun here re-planning 20x a second)
                if p.zone_hold(ups, f"the '{other}' at " + ", ".join(f"{u[0]},{u[1]}" for u in ups[:3])):
                    return None       # (2.53.0: an avoid zone alone blocks them -- the Navigator decides)
                self.mark_bad(w, ups)
            else:
                st = p.mover.tick()
                if st == "arrived" and w.standing_on == other:
                    return self._stairs(p, other)
                if st in ("moving", "idle"):
                    return None
                if st == "stuck":
                    self.mark_bad(w, ups)
        if self.explore is None:
            self.explore = Search() if self.need_search else \
                Explore(until="upstairs" if want == "<" else "stairs", skip=self.refused)
        r = self.explore.tick(p)
        if isinstance(self.explore, Search):
            if r and r[0] == "failed":
                return ("failed", "no stairs: explored and searched every dead end")
            if r:
                self.explore = None
                self.need_search = False
            return None
        if r and r[0] == "failed":
            # Often transient (monsters in the way): forget what failed, try again
            self.explore_fails += 1
            if self.explore_fails < 4:
                p.unreachable = set()
                self.explore = None
                return None
            return ("failed", "no stairs found: " + r[1])
        if r and str(r[1]).startswith("nothing left to explore") and w.find("<>") and self.bad_stairs:
            # Stairs are known but were marked unreachable (e.g. planned before
            # the map had loaded): try them again, a few times
            self.bad_cleared += 1
            if self.bad_cleared > 3:
                return ("failed", "stairs known but unreachable, nothing left to explore")
            self.bad_stairs = set()
            self.explore = None
            return None
        if r and str(r[1]).startswith("nothing left to explore") and not w.find("<>"):
            # Walled in: look for secret doors, then explore again
            self.need_search = True
        if r:
            self.explore = None
        return None

    def refused(self):
        """Stairs on this level the dive won't take (unreachable, or the way back to a level just fled)."""
        return {q for lt, q in self.bad_stairs if lt == self.level_seen}

    def mark_bad(self, w, tiles):
        now = gnow()
        for t in tiles:
            self.bad_stairs.add((w.level_t, t))
            self.bad_t[(w.level_t, t)] = now

    def expire_bad(self, w):
        """Unreachable stairs get another try after 15 s (the map fills in)."""
        now = gnow()
        for k in [k for k, t in self.bad_t.items() if now - t > 15]:
            self.bad_stairs.discard(k)
            del self.bad_t[k]

    def _stairs(self, p, which):
        p.take_stairs(which)
        self.pending = gnow()
        return None


class Search(Goal):
    """Look for secret doors: stand at each dead end (and corridor ends) and
    search a few times -- the user's doc lore: dead ends, lone doors,
    corridor ends. Done when a new door/opening shows up (explore again).
    strict=True: true corridor dead ends only (explore's own pass)."""

    def __init__(self, tries=8, strict=False, spots=None):
        self.name = "search dead ends"
        self.tries = tries
        self.strict = strict
        self.fixed = spots            # given squares (an inner room's 4 door spots) instead of dead ends
        self.spot = None
        self.searching = 0
        self.known = None
        self.done_n = 0
        self.spots_log = []           # (spot, searches; 0 = couldn't reach it)

    @staticmethod
    def door_count(w):
        return sum(1 for ch in w.memory.values() if ch in "+'")

    @staticmethod
    def dead_ends(w, strict=False, skip=()):
        mem = w.memory

        def is_open(y, x):
            return mem.get((y, x), " ") not in "#%*: 12345678"

        out = []
        for (y, x), ch in mem.items():
            if ch in "#%*: +12345678" or (w.level_t, (y, x)) in skip:
                continue
            nbs = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                   if (dy or dx) and is_open(y + dy, x + dx)]
            if not strict:
                # Few open squares around: a dead end, the end of a (two-wide)
                # corridor, or a room corner -- where secret doors tend to be
                if len(nbs) <= 3:
                    out.append((y, x))
                continue
            # A corridor's end: one way out (one wide, or two side by side), or the end of a two-wide
            # one -- an L of three with the diagonal, and no room around (a room
            # corner has the same L but 9 open squares within 2)
            if len(nbs) <= 1:
                out.append((y, x))
            elif len(nbs) == 2:
                # a nub past a corridor's turn: both ways out on one side, side by
                # side (a plain bend's two touch only diagonally)
                (ay, ax), (by, bx) = nbs
                if abs(ay - by) + abs(ax - bx) == 1:
                    out.append((y, x))
            elif len(nbs) == 3:
                diag = [d for d in nbs if d[0] and d[1]]
                if len(diag) == 1 and {(diag[0][0], 0), (0, diag[0][1])} <= set(nbs) and \
                        sum(is_open(y + dy, x + dx) for dy in range(-2, 3) for dx in range(-2, 3)) <= 6:
                    out.append((y, x))
        return out

    def tick(self, p):
        w = p.w
        if self.known is None:
            self.known = len(p.frontier())
            self.doors = self.door_count(w)
        # (a door counts too: one into ground already known adds no frontier)
        if len(p.frontier()) > self.known or self.door_count(w) > self.doors:
            return ("done", "found a way on" + self.summary())
        if self.searching:
            if gnow() < p.busy_until:
                return None
            self.searching -= 1
            # (one a player turn, ~0.65 s: sent faster they queue on the server, and the move after the
            # last one waited behind them -- set-piece D3)
            p.cmd("custom s", "search for secret doors", hold=0.65)
            if not self.searching:
                p.searched.add((w.level_t, self.spot))
                self.done_n += 1
                self.spots_log.append((self.spot, self.tries))
                self.spot = None
            return None
        if p.mover.active:
            st = p.mover.tick()
            if st == "moving":
                return None
            if st == "arrived" and w.pos == self.spot:
                self.searching = self.tries
                return None
        if self.spot:
            # couldn't get there: don't try it again on this level
            p.searched.add((w.level_t, self.spot))
            self.spots_log.append((self.spot, 0))
        # the nearest dead end not searched yet (it zig-zagged by distance from
        # where the search began)
        if self.fixed is not None:
            spots = sorted((q for q in self.fixed if (w.level_t, q) not in p.searched), key=w.dist)
        else:
            spots = sorted(self.dead_ends(w, self.strict, p.searched), key=w.dist)
        if not spots:
            return ("failed", ("searched every spot, nothing found" if self.fixed is not None else
                               "searched every dead end, nothing found") + self.summary())
        self.spot = spots[0]
        if w.pos == self.spot:
            self.searching = self.tries
        elif not p.mover.go([self.spot]):
            p.searched.add((w.level_t, self.spot))
            self.spots_log.append((self.spot, 0))
            self.spot = None
        return None

    def summary(self):
        """Where it searched, how often (the Navigator couldn't tell whether a
        26 s searchroom had really searched 4 x 20, mission 20), including the
        spot it was at when the way on appeared (mission 21 listed only one)."""
        log = list(self.spots_log)
        if self.spot and (self.spot, 0) not in log:
            log.append((self.spot, self.tries - self.searching if self.searching else 0))
        done = [f"{q[0]},{q[1]} x{n}" for q, n in log if n]
        here = [f"{q[0]},{q[1]} (on the way)" for q, n in log if not n and q == self.spot]
        log = [(q, n) for q, n in log if not (not n and q == self.spot)]
        unreached = [f"{q[0]},{q[1]}" for q, n in log if not n]
        if not done and not unreached and not here:
            return ""
        return f" (searched: {', '.join(done + here) or 'none'}" + \
            (f"; couldn't reach: {', '.join(unreached)}" if unreached else "") + ")"


class Hunt(Goal):
    """Go and fight a monster by name: walk next to it, then stand still (the
    server's auto-retaliate does the hitting). Done when it's slain; failed
    when it's been out of sight for lost_s."""

    def __init__(self, name, lost_s=15):
        self.target = name.lower()
        self.name = f"hunt {name}"
        self.lost_s = lost_s
        self.last_seen = gnow()
        self.goal_tile = None
        self.t0 = gnow()

    def tick(self, p):
        w = p.w
        # every message since the hunt began: while others are adjacent this
        # goal isn't ticked, and a 3-s window missed the kill (mission 21:
        # "lost sight of it" for a slain Brigand)
        if any(ts >= self.t0 and (t.startswith("You have slain") or t.startswith("You have destroyed"))
               and self.target in t.lower() for ts, t in w.messages):
            return ("done", "slain")
        mons = [(y, x, r) for y, x, r in w.monsters if self.target in r.name.lower()]
        # Killed while we couldn't see it (blind, or it was invisible): the game
        # says "You have killed it." (the message catalogue)
        if not mons and gnow() - self.last_seen < 3 and \
                any(t.startswith("You have killed it") for t in w.recent(3)):
            return ("done", "killed (unseen at the end)")
        if not mons:
            if gnow() - self.last_seen > self.lost_s:
                return ("failed", "lost sight of it")
            return None
        self.last_seen = gnow()
        y, x, r = min(mons, key=lambda m: w.dist(m[:2]))
        # a blinker with bolts (the Advisor's hunt-strictness memo §4.3): after "X blinks away",
        # close in at once; if that takes more than ~2 turns, give up and let the escape rules
        # take over (m19: the Ranger blinked, then four bolts in 3 s while we stood)
        blink = next((ts for ts, t in w.messages if ts >= self.t0 and "blinks" in t and self.target in t.lower()), None)
        if blink and blink > getattr(self, "blink_seen", 0):
            self.blink_seen = blink
        if getattr(self, "blink_seen", 0) and w.dist((y, x)) > 1 and gnow() - self.blink_seen > 2.5:
            return ("failed", f"{r.name} blinked away and couldn't be reached in 2 turns: hunt given up "
                              "(a blinker with bolts wins at range)")
        if w.dist((y, x)) <= 1:
            self.blink_seen = 0
            p.mover.stop()
            return None           # adjacent: auto-retaliate fights
        near = [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
        if not p.mover.active or self.goal_tile != (y, x):
            self.goal_tile = (y, x)
            p.mover.go(near)
        p.mover.tick()
        return None


class Recover(Goal):
    """After an emergency escape by the stairs: rest on the staircase (the reflexes, not this goal, take the stairs
    again if the arrival is into danger), and once healed go back up if we came down past max_depth -- rather than
    carrying on at the new depth (Dive03 kept exploring at 1000 ft after fleeing down and died there). Then the
    interrupted goal resumes."""

    def __init__(self, came_by, prev_goal=None):
        self.came_by = came_by
        self.name = f"recover (fled by {came_by})"
        self.prev = prev_goal
        self.level = None

    def tick(self, p):
        w = p.w
        if self.level is None:
            self.level = w.level_t
        md = int(p.orders.get("max_depth", 0))
        too_deep = md and w.depth_ft > md
        if w.hp_frac < p.orders["rest_to"]:
            if not w.monsters:
                p.start_resting()
            return None
        if too_deep and w.standing_on == "<":
            p.take_stairs("<")
            if self.prev is not None:
                p.resume_after = self.prev
            return ("done", f"healed; back up from {w.depth_ft} ft (max_depth {md})")
        if self.prev is not None:
            p.resume_after = self.prev
        return ("done", f"healed at {w.depth_ft} ft" + (f"; resuming '{self.prev.describe()}'" if self.prev else ""))


class Reprieve(Goal):
    """A blinker got away (a hunt given up): take the reprieve. The user (2026-10-23): rest
    is free; resources only in a turn-sensitive situation. Mortal danger near -> leave by the
    stairs while we can. Something still in view -> step out of its sight over walked ground
    (spending nothing). Nothing in view -> rest to full. Done when healed, or after 2 minutes."""

    def __init__(self, who):
        self.who = who
        self.name = f"reprieve (rest while {who} is away)"
        self.t0 = gnow()

    def tick(self, p):
        w = p.w
        if not w.in_dungeon:
            return ("done", "not in the dungeon")
        total, _ = p.group_danger()
        if p.dangers() or total >= 0.6 * max(1, w.hp[0]):
            p.stop_resting()
            p.set_goal(Flee(f"mortal danger near after {self.who} blinked away: leaving while we can"))
            return None
        if w.hp_frac >= p.orders["rest_to"]:
            p.stop_resting()
            return ("done", f"healed ({w.hp[0]}/{w.hp[1]}) while {self.who} stayed away")
        if gnow() - self.t0 > 120:
            p.stop_resting()
            return ("done", "2 minutes: carrying on")
        if w.monsters:
            p.stop_resting()
            # out of its sight, over ground already walked (no new monsters woken)
            if not p.retreat_step([m for m in w.monsters], reach=20):
                return None      # (nowhere better: hold; the fight reflexes still apply)
            return None
        p.start_resting()
        return None


class BandLeave(Goal):
    """The trip leaves a level for a band, no stairs known, HP high, nothing on us: find stairs instead of
    reading Word of Recall at once (m26 ended every trip in an escape recall, ~970 gold of scrolls in 25
    minutes; the user, 2026-10-24). Door/Stair Location, else Magic Mapping, then flee to what it shows;
    with neither, walk out of the band's sight. A second failure on the level recalls (flee_failed)."""

    def __init__(self, names):
        self.names = set(names)
        self.name = "flee (band: locating stairs)"
        self.t0 = None
        self.flee = None

    def tick(self, p):
        w = p.w
        if self.flee:
            return self.flee.tick(p)
        if self.t0 is None:
            used = p.use_stair_location("band, no stairs known")
            if not used:
                mm = p.find_item("Magic Mapping", TV_SCROLL)
                mm = None if mm and p.is_crutch(mm) else mm     # (2.48.0, the user: a crutch on the test server)
                if mm and not w.flag("blind") and not w.flag("confused") and gnow() >= p.busy_until:
                    p.cmd(f"custom r item={mm['item']}", "band, no stairs known: Magic Mapping", hold=0.8)
                    used = True
            if not used:
                p.set_goal(WalkAway(self.names))
                p.notify("tactic", "a band and no stairs known: walking out of its sight instead of reading Word of "
                                   "Recall", news=True)
                return None
            self.t0 = gnow()
            return None
        if not waited(self.t0, 1.5):
            return None
        if not w.find("<>"):
            return ("failed", "located nothing: no stairs known")
        p.notify("tactic", "a band and no stairs known: found stairs, leaving by them instead of Word of Recall",
                 news=True)
        self.flee = Flee("band: the trip leaves the level")
        self.flee.name = "flee (band: to the stairs located)"
        return self.flee.tick(p)


class WalkAway(Goal):
    """A summoner just came into view, not adjacent and no faster than us: walk out of its sight
    over ground already walked, then keep away (an avoid zone where it was). The user (2026-10-23,
    the set-piece A8o, where the danger rule read Word of Recall at full HP): if we first saw it
    by walking into line of sight, just walk away; other action only if something prevents walking
    away safely. Fails (the flee and its escapes take over) when it comes adjacent, its summons
    arrive, HP falls below half, or there's nowhere to walk."""

    def __init__(self, names):
        self.names = set(names)
        self.name = f"walk away from {', '.join(sorted(self.names))}"
        self.t0 = gnow()
        self.last = {}
        self.stuck_t = None

    def tick(self, p):
        w, now = p.w, gnow()
        seen = [(y, x, r) for y, x, r in w.monsters if r.name in self.names]
        for y, x, r in seen:
            self.last[r.name] = (y, x)
        if w.hp_frac < 0.5:
            return ("failed", "HP below half")
        if any(w.dist((y, x)) <= 1 for y, x, _ in seen):
            return ("failed", "it reached us")
        if any(ts >= self.t0 and "summons" in t for ts, t in w.messages):
            return ("failed", "it summoned")
        if not seen and all(w.dist(q) >= 6 for q in self.last.values()):
            for name, (y, x) in self.last.items():
                p.avoid_zones.setdefault(w.level_t, []).append((y, x, 7))
            return ("done", "out of its sight; avoid zone set where it was")
        if now - self.t0 > 30:
            return ("failed", "30 s and still in its sight")
        if p.retreat_step([m for m in seen] or [(q[0], q[1], None) for q in self.last.values()], reach=20):
            self.stuck_t = None
            return None
        self.stuck_t = self.stuck_t or now
        if now - self.stuck_t > 3:
            return ("failed", "nowhere to walk away to")
        return None


class Flee(Goal):
    """Get away from something too dangerous: to the nearest known stairs and
    take them."""

    def __init__(self, why):
        self.name = f"flee ({why})"
        self.started = False
        self.took = None

    def tick(self, p):
        w = p.w
        if self.took:
            # Report once the new level is in (the report showed the old depth
            # and stairs right after "left by the stairs", mission 4)
            if w.level_t != self.took[0]:
                # (where it came out: a dive mustn't take this staircase straight back -- the level may be one
                # the server keeps, with the danger beside the arrival: m25 looped into Ibun at 450 ft)
                # (and whether the level fled is one the server keeps: we logged in on it)
                p.fled_from = (getattr(self, "from_depth", None), gnow(), w.level_t,
                               self.took[0] == p.first_level_t)
                return ("done", f"left by the stairs; now at {w.depth_ft} ft")
            if waited(self.took[1], 5):
                return ("done", "took the stairs, but no level change seen")
            if waited(self.took[1], 1.5) and len(self.took) == 2 and w.standing_on in ("<", ">"):
                p.take_stairs(w.standing_on)      # a stairs command right after arriving can be ignored
                self.took = self.took + (True,)
            return None
        # At or below max_depth, go up if an up staircase is known (mission 4:
        # flights kept taking '>' past max_depth)
        md = int(p.orders.get("max_depth", 0))
        # With only '>' known there, teleport away on this level instead (m38: two flees at 650 ft took '>' to 700
        # ft, and finding a '<' there took 10 minutes); '>' only without a teleport, or one used in the last minute
        if md and w.depth_ft >= md and not w.find("<") and not self.started:
            t = p.teleport_item()
            if t and not w.flag("blind") and (t[0] == "u" or not w.flag("confused")) and \
                    gnow() - p.flee_tele_t > 60:
                p.flee_tele_t = gnow()
                p.cmd(f"custom {t[0]} item={t[1]['item']}", f"flee at {w.depth_ft} ft (max_depth), only '>' known: "
                                                            f"{t[1]['name']}", hold=0.8)
                p.notify("tactic", f"flee at max_depth with only '>' known: teleported ({one_of(t[1]['name'])}) "
                                   "rather than going deeper", news=True)
                return ("done", "teleported away on this level (max_depth, no '<' known)")
        ok = "<" if md and w.depth_ft >= md and w.find("<") else "<>"
        if w.standing_on and w.standing_on in ok:     # (None in "<>" crashed a flee, mission 6)
            p.take_stairs(w.standing_on)
            self.took = (w.level_t, gnow())
            self.from_depth = w.depth
            return None
        stairs = w.find(ok)
        if not stairs:
            return ("failed", "no stairs known")
        # Stairs known but no known way to them (Door/Stair Location shows stairs, not corridors): Magic Mapping
        # first, once per level. m31: an Ogre band, stairs 16 away, the flee went through unexplored squares, got
        # stuck, and a Word of Recall ended the trip -- with 4 Magic Mapping scrolls in the pack
        if not self.started and getattr(self, "mapped", None) != w.level_t and not plan(w, stairs) and \
                not w.flag("blind") and not w.flag("confused") and not w.adjacent_monsters():
            mm = p.find_item("Magic Mapping", TV_SCROLL)
            if mm and not p.is_crutch(mm):         # (2.48.0, the user: not read on the test server, a crutch)
                self.mapped = w.level_t
                p.cmd(f"custom r item={mm['item']}", "flee: no known way to the stairs: read Magic Mapping", hold=0.8)
                p.notify("tactic", "flee: stairs known but no known way to them: read Magic Mapping", news=True)
                return None
        if not self.started or not p.mover.active:
            if not p.mover.go(stairs, unknown=True):
                return ("failed", "no path to stairs, nor one through unexplored squares")
            # Far stairs with the danger already on us: walking hands it free hits all the way (m26: Nar
            # adjacent, stairs 75-81 steps off through unexplored squares; 22 s and ~150 HP before the
            # recall). Fail now: the flee-failed escape reads Word of Recall and phases while it charges.
            # (the length of the path, or -- not planned yet -- the distance to the nearest stairs: "through
            # unexplored" alone read Word of Recall with stairs 0 steps away, m26)
            close = [r.name for y, x, r in w.monsters if w.dist((y, x)) <= 2 and p.danger_why(r)]
            steps = len(p.mover.path) or min(w.dist(q) for q in stairs)
            if close and steps > 15:
                p.mover.stop()
                return ("failed", f"stairs {steps} steps away{' through unexplored squares' if p.mover.unknown else ''}"
                                  f" with {close[0]} beside us")
            if p.mover.unknown:
                p.notify("tactic", "flee: no known path to the stairs; trying one through unexplored squares",
                         news=True)
            self.started = True
        st = p.mover.tick()
        if st == "stuck":
            # (m59: "stuck" 4 s after a phase moved us, then Word of Recall: plan again from here, twice, first)
            self.regone = getattr(self, "regone", 0) + 1
            if self.regone <= 2 and p.mover.go(stairs, unknown=True):
                return None
            return ("failed", "stuck on the way to the stairs")
        return None


class Recall(Goal):
    name = "recall"

    def __init__(self, depth_ft=None):
        self.depth_ft = depth_ft     # (from town: the recall depth to inscribe; else max_depth)
        if depth_ft:
            self.name = f"recall to {depth_ft} ft"
        self.read_t = None
        self.start_depth = None
        self.inscribed = 0           # tries at inscribing @R
        self.inscribe_t = 0.0
        self.light_t = 0.0

    def tick(self, p):
        w = p.w
        if self.start_depth is None:
            self.start_depth = w.depth
        # Done only when the recall itself happened ("yanked" clears the pending
        # flag): taking stairs while it's pending is not arriving (mission 13)
        if self.read_t and w.depth != self.start_depth and not w.recall_pending:
            return ("done", f"arrived at {w.depth_ft} ft")
        if self.read_t is None:
            it = p.find_item("Word of Recall", TV_SCROLL)
            if not it:
                return ("failed", "no Word of Recall")
            # From town, recall goes to the deepest level ever reached -- which
            # can be below max_depth (it took Dive03 back to 1000 ft, where it had
            # died). Inscribe @R<feet> first: the recall depth (inscription guide).
            # Check what the server will read from it, not a substring
            # ("@R7500" contains "@R750"; a later @R overrides an earlier one).
            md = int(self.depth_ft or p.orders.get("max_depth", 0)) // 50 * 50
            if w.depth == 0 and md and recall_level(it["name"]) != md // 50:
                if not waited(self.inscribe_t, 2.5):
                    return None           # (wait for the pack to show the new inscription)
                if self.inscribed >= 3:
                    return ("failed", f"couldn't inscribe @R{md} on the Word of Recall "
                                      f"(it reads '{it['name']}'): not reading it")
                self.inscribed += 1
                self.inscribe_t = gnow()
                p.cmd(f"custom {{ item={it['item']} entry=@R{md}", f"recall depth {md} ft", hold=1.0)
                w.inven_dirty = True
                return None
            # No light, no reading (mission 13: at night in town the light was off
            # for idling, and the read failed with "You have no light to read by")
            if not any(i["tval"] == TV_LITE for i in w.items(equip=True)):
                # (the fullest: '"0 turns" not in' skipped m39's 13290-turn lantern -- it ends in "0 turns" -- and
                # lit the 4383-turn one, which ran low mid-trip)
                if waited(self.light_t, 2) and p.wear_light("to read Word of Recall"):
                    self.light_t = gnow()        # (wear_light holds town_light off meanwhile)
                    return None
            if p.recall_started(gnow()):
                # Already under way (e.g. the last-resort recall): a second read would cancel it
                p.log("note", text="recall already under way: not reading another")
                self.read_t = gnow()
                return None
            # Blind or confused, the scroll can't be read (m55: a `goal recall` sat 4 minutes confused by
            # Hummerhorns until the Navigator quaffed a CSW): the cheapest cure first (use-obj.c: Cure Light Wounds
            # ends blindness, Serious and Critical end both), then read
            if w.flag("blind") or w.flag("confused"):
                if waited(getattr(self, "cure_t", 0), 3):
                    kinds = (["Cure Light"] if not w.flag("confused") else []) + ["Cure Serious", "Cure Critical"]
                    pot = next((i for k in kinds for i in w.items(tval=TV_POTION) if k in i["name"]), None)
                    self.cure_t = gnow()
                    if pot:
                        p.cmd(f"custom q item={pot['item']}", f"recall: {'confused' if w.flag('confused') else 'blind'}"
                                                              f", can't read: quaff {pot['name']}", hold=0.8)
                    elif not getattr(self, "told", False):
                        self.told = True
                        p.notify("tactic", "recall: blind or confused and no cure for it: waiting to be able to read",
                                 news=True)
                return None
            # (m56: "read 2 Scrolls of Word of Recall" read as two reads; one scroll of the stack is read)
            p.cmd(f"custom r item={it['item']}", f"read a Word of Recall ({it['number']} in the pack)")
            self.read_t = p.recall_t = gnow()
            return None
        # while it charges, rest when hurt and nothing is in view: free healing, and time runs 10x
        # while resting, so the recall comes ~10x sooner in real time (the rulebook's constants:
        # recall_seconds; the server ends a rest at full HP)
        if w.recall_pending and not w.monsters and w.hp[0] < w.hp[1] and not w.resting and \
                gnow() - self.read_t > 1 and gnow() - getattr(self, "rest_t", 0) > 3:
            self.rest_t = gnow()
            p.start_resting()
        if gnow() - self.read_t > (120 if w.recall_pending else 60):
            # say why, if the game did (e.g. "You have no light to read by.")
            why = next((t for ts, t in reversed(w.messages) if ts >= self.read_t and t.startswith(
                ("You have no light", "You can't see", "You are too confused", "You cannot read",
                 "A tension leaves"))), None)
            return ("failed", "recall didn't happen" + (f": the game said '{why}'" if why else ""))
        return None


class Resurrect(Goal):
    """A ghost floats up: '<' works anywhere for a ghost (cmd2.c:37), one
    level per press; in town, walking onto the Temple's entrance ('4')
    resurrects (cmd1.c:2047). It costs half the experience for good."""
    name = "resurrect"

    def __init__(self):
        self.up_t = 0.0

    def tick(self, p):
        w = p.w
        if not w.ghost:
            return ("done", "resurrected")
        if w.depth:
            # (a stairs command too soon after arriving is ignored: retry)
            if waited(w.level_t, 1.2) and waited(self.up_t, 1.5):
                self.up_t = gnow()
                p.take_stairs("<")
            return None
        door = w.find("4")
        if not door:
            return ("failed", "the Temple (4) isn't on the map")
        if w.dist(door[0]) == 1:
            p.cmd(f"walk {direction(w.pos, door[0])}", "walk onto the Temple entrance", hold=1.0)
            return None
        if not p.mover.active and not p.mover.go([door[0]]):
            return ("failed", "can't reach the Temple")
        p.mover.tick()
        return None


class RestGoal(Goal):
    name = "rest"

    def tick(self, p):
        w = p.w
        if w.hp_frac >= p.orders["rest_to"] and w.ind.get("sp", [0, 0])[0] >= w.ind.get("sp", [0, 0])[1]:
            p.stop_resting()
            return ("done", None)
        if w.monsters:
            return ("failed", "monsters in view")
        p.start_resting()
        return None


class QuietWait(Goal):
    """`goal quiet [SECS]` (the user, 10-27): time for the Navigator to think, plan, survey the map or sort the pack.
    The plan (or the goal it replaced) is paused; the Pilot walks to a quiet spot on ground already walked (a room,
    away from unexplored squares and doors: quiet_spot), rests there if hurt, and waits. It wakes when a monster that
    moves comes into view or something hits us (the fight reflexes defend as always), or when the time is up; then
    what it paused carries on, and the Navigator is told. In town it just waits (townspeople don't wake it)."""

    quiet = True                 # (its end is reported by itself, as an alert)

    def __init__(self, secs=120, prev=None):
        self.secs = int(min(600, max(10, float(secs))))
        self.name = f"quiet wait {self.secs}s"
        self.t0 = gnow()
        self.prev = prev
        self.spot = None
        self.walking = False

    def end(self, p, why):
        p.stop_resting()
        if self.prev is not None:
            p.resume_after = self.prev
            if p.plan and p.plan.pause_goal is self:
                p.plan.pause_goal = self.prev     # (the plan waits for the goal we paused, as before)
        then = (f"resuming '{self.prev.describe()}'" if self.prev is not None else
                "the trip plan carries on" if p.plan and p.plan.paused else "your move")
        p.notify("quiet_end", f"quiet wait: {why} after {gnow() - self.t0:.0f} s; {then}")
        return ("done", why)

    def tick(self, p):
        w = p.w
        hit = gnow() - w.last_hit_t < 2
        mob = [r for _, _, r in w.monsters if "NEVER_MOVE" not in r.flags] if w.in_dungeon else []
        if mob or hit:
            return self.end(p, "woke: " + (f"{mob[0].name} came into view" if mob else "something hit us"))
        aid = self.wait_answer
        if aid is not None:
            ans = [a for a in p.arch_answers if a[1] == aid and a[0] >= self.t0]
            if ans and not ans[-1][2].lower().startswith("more"):
                return self.end(p, f"the Architect answered #{aid}")
        if gnow() - self.t0 >= self.secs:
            return self.end(p, f"{self.secs} s are up")
        if w.in_dungeon and self.spot is None and w.pos:
            # (the user, 10-28: cap the wait by the food and light left -- at most a quarter of either; resting runs
            # the game clock ~10x)
            food, light = p.supply_minutes()
            left = min(m for m in (food, light) if m is not None) if light is not None else food
            cap = max(10, int(0.25 * 60 * left))
            if cap < self.secs:
                p.notify("tactic", f"quiet wait: {cap} s, not {self.secs} ({p.supply_text()})", news=True)
                self.secs = cap
            self.spot = p.quiet_spot() or w.pos
            if self.spot != w.pos and p.mover.go([self.spot]):
                self.walking = True
                p.notify("tactic", f"quiet wait: walking to a quiet spot at {self.spot[0]},{self.spot[1]} "
                                   f"({w.dist(self.spot)} away)", news=True)
        if self.walking:
            if p.mover.tick() == "moving":
                return None
            self.walking = False          # (arrived, or stuck: wait where we are)
        if w.hp_frac < p.orders["rest_to"]:
            p.start_resting()
        return None

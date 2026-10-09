"""Tick-based movement for the pilot: never blocks, so reflexes keep running.

go(goals) plans a path on the remembered map; tick() sends the next step(s)
and checks each against the position events. Dungeon rules: unknown grids
are *not* walkable (the dungeon is mostly rock), except as a goal (frontier
exploring); walls/veins aren't; closed doors are (easy_alter opens them on a
bump); traps and monsters are avoided.
"""
import heapq
import time

DIRS = {(-1, -1): 7, (-1, 0): 8, (-1, 1): 9, (0, -1): 4, (0, 1): 6, (1, -1): 1, (1, 0): 2, (1, 1): 3}
WALLS = set("#%*:") | set("12345678") | {"0", " "}   # ':' rubble ("blocking your way")
COST = {"+": 3, "^": 25, "'": 1, "8": 50, ":": 15}
MAX_HGT, MAX_WID = 66, 198


def passable(ch):
    return ch not in WALLS


def drain_zone_of(world):
    """Squares next to a stationary drainer (and its own square)."""
    return {(y + dy, x + dx) for y, x, r in world.monsters if "NEVER_MOVE" in getattr(r, "flags", ())
            and getattr(r, "drains", False) for dy in (-1, 0, 1) for dx in (-1, 0, 1)}


def plan(world, goals, avoid=(), monster_cost=40, max_cost=4000):
    """Dijkstra over remembered tiles from world.pos to the nearest goal."""
    start = world.pos
    goals = set(goals)
    if not start or not goals:
        return None
    mon = {(y, x) for y, x, _ in world.monsters}
    # Next to a monster that never moves (molds, jellies, floating eyes): the
    # server's auto-retaliate would fight it (and a floating eye's gaze paralyses)
    still = {(y + dy, x + dx) for y, x, r in world.monsters if "NEVER_MOVE" in getattr(r, "flags", ())
             for dy in (-1, 0, 1) for dx in (-1, 0, 1)}
    # Never next to a stationary drainer (mission 16: explore walked back beside
    # a Purple mushroom patch, CON 18 -> 14), nor into the Navigator's avoid
    # zones: impassable, unless it's the goal itself
    drain_zone = drain_zone_of(world)
    nav_zone = set(getattr(world, "avoid_zone", ()))
    # Inside a zone (it was set around us, or the monster came to us): its
    # squares only cost more, or no path could lead out of it
    inside = bool(nav_zone) and any((start[0] + dy, start[1] + dx) in nav_zone
                                    for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx) and \
        getattr(world, "avoid_inside", False)
    avoid = set(avoid) | drain_zone | (set() if inside else nav_zone)
    # A goal inside a zone would still pull the path into it (the Advisor's
    # mission 16 replay): drop such goals unless they're all there (a goto
    # the Navigator asked for)
    if goals - drain_zone - nav_zone:
        goals -= drain_zone | nav_zone
    mem = world.memory
    # On the surface (town, wilderness) unseen ground is mostly open -- at
    # night the floor isn't even drawn -- while trees and fences block
    surface = not getattr(world, "in_dungeon", (world.depth or 0) > 0)
    dist = {start: 0}
    prev = {}
    heap = [(0, start)]
    while heap:
        d, cur = heapq.heappop(heap)
        if cur in goals:
            path = []
            while cur != start:
                path.append(cur)
                cur = prev[cur]
            return path[::-1]
        if d > dist[cur] or d > max_cost:
            continue
        for (dy, dx) in DIRS:
            nb = (cur[0] + dy, cur[1] + dx)
            if not (0 < nb[0] < MAX_HGT - 1 and 0 < nb[1] < MAX_WID - 1):
                continue
            ch = mem.get(nb, " ")
            if surface:
                # '8' (the Tavern entrance) is allowed: new characters start inside
                # the Tavern and must walk out through it (COST keeps it a last resort)
                ok = ch not in "#*=%0:" and ch not in "1234567" if ch != " " else True
            else:
                ok = passable(ch) or ch == ":"     # rubble: dig through (costly)
            if nb not in goals and (not ok or nb in avoid):
                continue
            # (a hair more for diagonals: of equally short paths, prefer straight ones)
            nd = d + COST.get(ch, 1) + (1 if ch == " " else 0) + (0.001 if dy and dx else 0) \
                + (monster_cost if nb in mon and nb not in goals else 0) \
                + (monster_cost if nb in still and nb not in goals else 0) \
                + (30 if inside and nb in nav_zone else 0)
            if nd < dist.get(nb, 1 << 30):
                dist[nb] = nd
                prev[nb] = cur
                heapq.heappush(heap, (nd, nb))
    return None


def direction(a, b):
    return DIRS.get((b[0] - a[0], b[1] - a[1]))


class Mover:
    """One movement job at a time. tick() -> 'moving' | 'arrived' | 'stuck' | 'idle'."""

    AHEAD = 2           # steps queued ahead (the server drops a walk if > 2 are queued)
    STEP_TIMEOUT = 1.5  # s without progress -> replan

    def __init__(self, client, world, log=None):
        self.c, self.w, self.log = client, world, log or (lambda *a, **k: None)
        self.goals = None
        self.path = []
        self.sent = 0           # steps of path sent
        self.done = 0           # steps of path reached
        self.last_progress = 0.0
        self.replans = 0
        self.avoid = set()
        self.max_replans = 8
        self.running = None      # (start, end, t) while a run is under way
        self.stop_sent = False
        self.use_runs = True
        self.free = None
        self.resume_goals = None
        self.dig_t0 = self.dig_last = 0.0
        self.dig_n = 0
        self.hold_clear_until = 0.0   # the pilot: a read/quaff is waiting in the server queue
        self.bump_t = 0.0             # the last "blocking your way" handled
        self.run_start_pos = None
        self.free_dist, self.free_away = None, 0

    RUN_MIN = 3

    def _straight(self, i):
        """Length of the straight stretch of path starting at index i."""
        frm = self.path[i - 1] if i else self.here
        d = (self.path[i][0] - frm[0], self.path[i][1] - frm[1])
        n = 1
        while i + n < len(self.path):
            a, b = self.path[i + n - 1], self.path[i + n]
            if (b[0] - a[0], b[1] - a[1]) != d:
                break
            n += 1
        return n

    def _run_tick(self):
        """Follow a run along path[start:end]; stop it one tile early."""
        w = self.w
        start, end, t0 = self.running
        # progress already accounted for by tick(); here: stop or give up
        if self._monster_near(5) and not self.stop_sent:
            self.c.send("walk 5")            # something close: stop running
            self.stop_sent = True
        if not self.stop_sent and self.done >= end - 1:
            self.c.send("walk 5")            # a walk request ends a run (and is swallowed)
            self.stop_sent = True
            self.last_progress = time.time()
        started = w.pos != self.run_start_pos
        limit = 0.5 if self.stop_sent else (0.8 if started else self.first_step_window())
        if time.time() - self.last_progress > limit:
            # The run is over (we stopped it, or the server's run logic did)
            self.running = None
            self.sent = self.done
        return "moving"

    def surface(self):
        return getattr(self.w, "in_dungeon", True) is False

    def runs_ok(self, free=False):
        """Runs are ~5x faster than walking (the server speeds time up while
        running; the Advisor's running memo). Free runs (the server follows
        the corridor) only in the dungeon: on the surface, at night, one
        crossed town and left the map (mission 13). Stretch runs on the
        surface pass stretch_ok() instead."""
        return self.use_runs and not (free and self.surface())

    def stretch_ok(self, i, n):
        """A straight stretch path[i:i+n] we may run along: on the surface,
        only at least 3 tiles from the map edge, never onto a shop door (a
        run's first step enters it). Unknown ground is allowed (at night the
        town floor isn't drawn, so every town errand walked: the Navigator's
        wish); such runs are capped by run_cap()."""
        if not self.surface():
            return True
        for (y, x) in self.path[i:i + n]:
            if not (3 <= y <= MAX_HGT - 4 and 3 <= x <= MAX_WID - 4):
                return False
            ch = self.w.memory.get((y, x), " ")
            if ch in "12345678":
                return False
        return True

    def run_cap(self, i, n):
        """Over unknown surface ground, run at most 10 tiles at a time: the
        server's run treats unknown as open, so a stop sent late overshoots less."""
        if self.surface() and any(self.w.memory.get(q, " ") == " " for q in self.path[i:i + n]):
            return min(n, 10)
        return n

    def first_step_window(self):
        """A run waits for a full turn of energy before its first step: give it
        that long before calling it failed, and send no walk meanwhile (a walk
        cancels a run that hasn't started: 82% of dungeon runs died that way)."""
        return 0.7 if self.surface() else 1.0

    def _runnable(self, i):
        """Could a run start at path index i (straight stretch, nothing close)?"""
        n = self._straight(i)
        return self.runs_ok() and n >= self.RUN_MIN and not self._monster_near(5) and self.stretch_ok(i, n)

    def _monster_near(self, r):
        w = self.w
        return any(w.dist(m[:2]) <= r for m in w.monsters)

    def free_run(self, d, keep_goals=False):
        """Run in direction d and let the server's run logic follow the
        corridor until something interesting. tick() returns 'arrived' when
        the run is over -- or, with keep_goals (a run along the way to our
        goals), carries on towards the goals from wherever the run ended."""
        goals = self.goals if keep_goals else None
        self.stop()
        self.resume_goals = goals
        self.goals = {"free-run"}
        self.path = []
        self.free = (time.time(), self.w.pos)
        self.free_dist, self.free_away = None, 0
        self.last_progress = time.time()
        self.free_pos = self.w.pos
        self.c.send(f"custom . dir={d}")
        self.log(run="free", dir=d, frm=self.w.pos)        # (runs were only event acks: the Advisor)

    def _free_tick(self):
        w = self.w
        if w.pos != self.free_pos:
            self.free_pos = w.pos
            self.last_progress = time.time()
            # bound it: stop when it moves away from the goals two steps running
            if self.resume_goals and not self.stop_sent:
                d = min(max(abs(g[0] - w.pos[0]), abs(g[1] - w.pos[1])) for g in self.resume_goals)
                self.free_away = self.free_away + 1 if self.free_dist is not None and d > self.free_dist else 0
                self.free_dist = d
                if self.free_away >= 2:
                    self.c.send("walk 5")
                    self.stop_sent = True
        if self._monster_near(5) and not self.stop_sent:
            self.c.send("walk 5")
            self.stop_sent = True
        if self.resume_goals and w.pos in self.resume_goals and not self.stop_sent:
            self.c.send("walk 5")          # ran onto the goal: stop there
            self.stop_sent = True
        limit = 0.5 if w.pos != self.free[1] else self.first_step_window()
        if time.time() - self.last_progress > limit:
            moved = w.pos != self.free[1]
            self.free = None
            self.stop_sent = False
            goals, self.resume_goals = self.resume_goals, None
            if goals:
                # carry on to the goals from here (no replan budget used up)
                self.goals = goals
                if w.pos in goals:
                    self.goals = None
                    return "arrived"
                if not self._plan():
                    self.goals = None
                    return "stuck"
                return "moving"
            self.goals = None
            return "arrived" if moved else "stuck"
        return "moving"

    def go(self, goals, avoid=()):
        self.goals = set(goals)
        self.avoid = set(avoid)
        self.replans = 0
        ok = self._plan()
        if not ok and self.forget_bump_walls():
            ok = self._plan()
        near = min(self.goals, key=lambda g: max(abs(g[0] - self.w.pos[0]), abs(g[1] - self.w.pos[1]))) \
            if self.w.pos and self.goals else None
        self.log(goals=len(self.goals), nearest=near, path=len(self.path), ok=ok)
        return ok

    def _clear(self):
        """Empty our server-side command queue -- unless the pilot has a read
        or quaff waiting there (mission 7: these clears wiped every escape)."""
        if time.time() >= self.hold_clear_until:
            self.c.send("clear")

    def requeue(self):
        """Drop the steps queued on the server (so a command sent now runs
        before them, not after) and send them again on the next tick."""
        self._clear()
        if self.running is not None or self.free is not None:
            self.c.send("walk 5")
            self.running = None
            self.free = None
        self.sent = self.done
        self.last_progress = time.time()

    def _dig_tick(self):
        """The next square is rubble: tunnel ('T') until "You have removed the
        rubble" (a few turns for a warrior), then walk on. Mission 4 lost a Word
        of Recall on a level sealed by rubble."""
        tile = self.path[self.done]
        w = self.w
        if any(ts > self.dig_t0 and t.startswith("You have removed the rubble") for ts, t in w.messages):
            w.memory[tile] = "."
            self.dig_t0 = 0.0
            self.last_progress = time.time()
            return "moving"
        now = time.time()
        if not self.dig_t0:
            self.dig_t0, self.dig_n = now, 0
        if self.dig_n >= 40 or any(ts > self.dig_t0 and ("impossible" in t or "cannot" in t)
                                   for ts, t in w.messages):
            # can't dig it: treat as wall and replan
            w.memory[tile] = "#"
            self.avoid.add(tile)
            self.dig_t0 = 0.0
            if not self._plan():
                self.stop()
                return "stuck"
            return "moving"
        if now - self.dig_last > 0.6:
            frm = self.path[self.done - 1] if self.done else self.here
            self.c.send(f"custom T dir={direction(frm, tile)}")
            self.dig_last, self.dig_n = now, self.dig_n + 1
        self.last_progress = now          # digging is progress (no step timeout)
        return "moving"

    def forget_bump_walls(self):
        """Walls learned by bumping can be wrong (a bump while confused walled
        off mission 15's way on: "frontier unreachable", "no known path").
        Forget them; the server's map redraws the real ones. True if any."""
        w = self.w
        if not w.bump_walls:
            return False
        for q, ch in w.bump_walls.items():
            if w.memory.get(q) in ("#", ":", "+"):
                if ch == " ":
                    w.memory.pop(q, None)
                else:
                    w.memory[q] = ch
        w.bump_walls = {}
        return True

    def _astray(self):
        """Our steps may not go where we send them: confused, or blind (we
        can't see what we bump), now or in the last 2 s."""
        w = self.w
        if w.flag("confused") or w.flag("blind"):
            return True
        now = time.time()
        return any(now - ts < 2 and t.startswith(("You are confused", "You are blind", "You feel less confused",
                                                  "You can see again"))
                   for ts, t in w.messages)

    def stop(self):
        if self.running is not None or self.free is not None:
            self.c.send("walk 5")
            self.running = None
            self.free = None
        self.goals = None
        self.path = []

    @property
    def active(self):
        return self.goals is not None

    def in_corridor(self):
        """Few open squares around us: a corridor rather than a room."""
        w = self.w
        if not w.pos:
            return False
        y, x = w.pos
        open_ = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy or dx) and passable(w.memory.get((y + dy, x + dx), " ")))
        return open_ <= 3

    def _plan(self):
        self.path = plan(self.w, self.goals, self.avoid) or []
        self.sent = self.done = 0
        self.running = None
        self.here = self.w.pos
        self.last_progress = time.time()
        return bool(self.path)

    def tick(self):
        if self.goals is None:
            return "idle"
        if self.free is not None:
            return self._free_tick()
        w = self.w
        if w.pos in self.goals:
            self.stop()
            return "arrived"
        if not self.path:
            if self.replans >= self.max_replans or not self._plan():
                self.stop()
                return "stuck"
            self.replans += 1
        # Progress along the path?
        ahead = self.running[1] if self.running is not None else self.sent + 1
        while self.done < len(self.path) and w.pos in self.path[self.done:ahead]:
            i = self.path.index(w.pos, self.done)
            self.done = i + 1
            self.last_progress = time.time()
        if w.pos != (self.path[self.done - 1] if self.done else self.here):
            # Off the path (pushed, a step dropped, a teleport, a run that
            # followed a corridor bend or overshot): stop any run and replan.
            # Steps sent ahead may still be queued on the server; left there,
            # every later step runs one behind (mission 3: 10 minutes circling
            # a '>' one square away), so empty the queue first (before the
            # run-stopping 'walk 5', which it would drop).
            self._clear()
            if self.running is not None:
                self.c.send("walk 5")
                self.running = None
            self.replans += 1
            if self.replans > self.max_replans or not self._plan():
                self.stop()
                return "stuck"
            return "moving"
        if self.done >= len(self.path):
            self.stop()
            return "arrived" if w.pos in (self.goals or {w.pos}) else "stuck"
        bumped = [ts for ts, t in w.messages if ts > max(self.last_progress, self.bump_t)
                  and "blocking your way" in t]
        if bumped and self.done < len(self.path):
            self.bump_t = max(bumped)
            if self._astray():
                # Confused (or blind) steps go astray: the wall we hit isn't the
                # square on our path (mission 15: four such bumps walled off the
                # way north, and explore said "frontier unreachable"). Resend.
                self._clear()
                self.sent = self.done
                self.last_progress = time.time()
                return "moving"
            # Walked into rubble/a wall/a door we didn't know about: remember it
            said = [t for ts, t in w.messages if ts > self.last_progress and "blocking your way" in t]
            rubble = any("rubble" in t for t in said)
            door = any("door" in t for t in said)
            q = self.path[self.done]
            w.bump_walls.setdefault(q, w.memory.get(q, " "))
            # (a closed door is a door, not a wall: the message catalogue)
            w.memory[q] = ":" if rubble else "+" if door else "#"
            if rubble:
                self._clear()      # drop the steps queued behind the bump
                self.sent = self.done
                self.last_progress = time.time()
                return "moving"           # next tick digs it
            self.avoid.add(self.path[self.done])
            self.replans += 1
            if self.replans > self.max_replans or not self._plan():
                self.stop()
                return "stuck"
            return "moving"
        if time.time() - self.last_progress > self.STEP_TIMEOUT:
            # Something blocks the next step (a monster, a door that didn't
            # open, an unseen wall): avoid that tile and replan
            self._clear()
            self.avoid.add(self.path[self.done])
            self.replans += 1
            if self.replans > self.max_replans or not self._plan():
                self.stop()
                return "stuck"
            return "moving"
        if self.running is not None:
            return self._run_tick()
        if self.sent == self.done and self.w.memory.get(self.path[self.done]) == ":":
            return self._dig_tick()
        # Run whenever we can: the user runs 61% of their steps at ~0.11 s per
        # tile, walking takes ~0.5 s. Straight stretches are run and stopped a
        # tile early; in a corridor we run and let the server follow the bends
        # (replanning when the run ends), as a human holding the key does.
        if self.sent == self.done and self.runs_ok() and not self._monster_near(5):
            frm = self.path[self.done - 1] if self.done else self.here
            d = direction(frm, self.path[self.done])
            n = self._straight(self.done)
            if n >= self.RUN_MIN and self.stretch_ok(self.done, n):
                n = self.run_cap(self.done, n)
                self.c.send(f"custom . dir={d}")
                self.log(run="stretch", dir=d, frm=self.w.pos, length=n)
                self.running = (self.done, self.done + n, time.time())
                self.run_start_pos = self.w.pos
                self.stop_sent = False
                self.last_progress = time.time()
                return "moving"
            if self.in_corridor() and len(self.path) - self.done >= 3 and self.runs_ok(free=True) \
                    and self.replans <= self.max_replans:
                self.replans += 1          # (free runs count against the replan budget)
                self.free_run(d, keep_goals=True)
                return "moving"
        while self.sent < len(self.path) and self.sent - self.done < self.AHEAD:
            if self.sent > self.done and self._runnable(self.sent):
                break             # let the queued steps land, then run from there
            if self.w.memory.get(self.path[self.sent]) == ":":
                break             # rubble ahead: stop there and dig
            frm = self.path[self.sent - 1] if self.sent else self.here
            d = direction(frm, self.path[self.sent])
            if d is None:
                self._plan()
                return "moving"
            self.c.send(f"walk {d}")
            self.sent += 1
        return "moving"

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
COST = {"+": 3, "^": 25, "'": 1, "8": 50}
MAX_HGT, MAX_WID = 66, 198


def passable(ch):
    return ch not in WALLS


def plan(world, goals, avoid=(), monster_cost=40, max_cost=4000):
    """Dijkstra over remembered tiles from world.pos to the nearest goal."""
    start = world.pos
    goals = set(goals)
    if not start or not goals:
        return None
    mon = {(y, x) for y, x, _ in world.monsters}
    avoid = set(avoid)
    mem = world.memory
    # On the surface (town, wilderness) unseen ground is mostly open -- at
    # night the floor isn't even drawn -- while trees and fences block
    surface = (world.depth or 0) <= 0
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
                ok = passable(ch)
            if nb not in goals and (not ok or nb in avoid):
                continue
            # (a hair more for diagonals: of equally short paths, prefer straight ones)
            nd = d + COST.get(ch, 1) + (1 if ch == " " else 0) + (0.001 if dy and dx else 0) \
                + (monster_cost if nb in mon and nb not in goals else 0)
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
        self.c, self.w, self.log = client, world, log or (lambda *a: None)
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

    RUN_MIN = 5

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
        if w.monsters and not self.stop_sent:
            self.c.send("walk 5")            # something came into view: stop running
            self.stop_sent = True
        if not self.stop_sent and self.done >= end - 1:
            self.c.send("walk 5")            # a walk request ends a run (and is swallowed)
            self.stop_sent = True
            self.last_progress = time.time()
        if time.time() - self.last_progress > (0.5 if self.stop_sent else 0.8):
            # The run is over (we stopped it, or the server's run logic did)
            self.running = None
            self.sent = self.done
        return "moving"

    def free_run(self, d):
        """Run in direction d and let the server's run logic follow the
        corridor until something interesting (for exploring: we don't know
        where it ends). tick() returns 'arrived' when the run is over."""
        self.stop()
        self.goals = {"free-run"}
        self.path = []
        self.free = (time.time(), self.w.pos)
        self.last_progress = time.time()
        self.free_pos = self.w.pos
        self.c.send(f"custom . dir={d}")

    def _free_tick(self):
        w = self.w
        if w.pos != self.free_pos:
            self.free_pos = w.pos
            self.last_progress = time.time()
        if w.monsters and not self.stop_sent:
            self.c.send("walk 5")
            self.stop_sent = True
        if time.time() - self.last_progress > 0.7:
            moved = w.pos != self.free[1]
            self.free = None
            self.goals = None
            self.stop_sent = False
            return "arrived" if moved else "stuck"
        return "moving"

    def go(self, goals, avoid=()):
        self.goals = set(goals)
        self.avoid = set(avoid)
        self.replans = 0
        ok = self._plan()
        near = min(self.goals, key=lambda g: max(abs(g[0] - self.w.pos[0]), abs(g[1] - self.w.pos[1]))) \
            if self.w.pos and self.goals else None
        self.log(goals=len(self.goals), nearest=near, path=len(self.path), ok=ok)
        return ok

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
            # followed a corridor bend or overshot): stop any run and replan
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
        bumped = [ts for ts, t in w.messages if ts > self.last_progress and "blocking your way" in t]
        if bumped and self.done < len(self.path):
            # Walked into rubble/a wall/a door we didn't know about: remember it
            w.memory[self.path[self.done]] = "#"
            self.avoid.add(self.path[self.done])
            self.replans += 1
            if self.replans > self.max_replans or not self._plan():
                self.stop()
                return "stuck"
            return "moving"
        if time.time() - self.last_progress > self.STEP_TIMEOUT:
            # Something blocks the next step (a monster, a door that didn't
            # open, an unseen wall): avoid that tile and replan
            self.avoid.add(self.path[self.done])
            self.replans += 1
            if self.replans > self.max_replans or not self._plan():
                self.stop()
                return "stuck"
            return "moving"
        if self.running is not None:
            return self._run_tick()
        # A long straight stretch with nothing in view: run it (~4x faster
        # than walking; the user runs almost everything)
        if self.sent == self.done and not w.monsters and self.use_runs:
            n = self._straight(self.done)
            if n >= self.RUN_MIN:
                frm = self.path[self.done - 1] if self.done else self.here
                d = direction(frm, self.path[self.done])
                self.c.send(f"custom . dir={d}")
                self.running = (self.done, self.done + n, time.time())
                self.stop_sent = False
                self.last_progress = time.time()
                return "moving"
        while self.sent < len(self.path) and self.sent - self.done < self.AHEAD:
            frm = self.path[self.sent - 1] if self.sent else self.here
            d = direction(frm, self.path[self.sent])
            if d is None:
                self._plan()
                return "moving"
            self.c.send(f"walk {d}")
            self.sent += 1
        return "moving"

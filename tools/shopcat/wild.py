"""Wilderness travel: world coordinates, a tour of nearby levels, crossing
level edges, and exploring a level until its house doors are on the map.

Server facts (server/wilderness.c, cmd1.c):
- The town is world (0, 0), depth 0. Other levels have depth
  world_index(x, y) < 0; +y is north, +x is east.
- Stepping off an edge moves to the neighbouring level: north arrives on row
  MAX_HGT-2, south on row 1, west on column MAX_WID-2, east on column 1.
- By day every wilderness grid is lit, but the map only shows what the
  character has had in line of sight, so a level must be walked to be seen.
"""
import time
from collections import deque

import nav
from nav import MAX_HGT, MAX_WID

# keypad direction and world step for each way out of a level
EXITS = {"N": (8, (0, 1)), "S": (2, (0, -1)), "E": (6, (1, 0)), "W": (4, (-1, 0))}

# Levels up to two screens out along the cardinals, one along the diagonals
DEFAULT_TARGETS = [(0, 1), (0, 2), (1, 0), (2, 0), (0, -1), (0, -2), (-1, 0), (-2, 0),
                   (1, 1), (-1, 1), (1, -1), (-1, -1)]


def world_index(x, y):
    """Depth of world square (x, y) -- mirrors server/wilderness.c."""
    ring = abs(x) + abs(y)
    if not ring:
        return 0
    base = 2 * ring * (ring - 1) + 1
    offset = ring - y if x >= 0 else 3 * ring + y
    return -(base + offset)


_COORDS = {world_index(x, y): (x, y) for x in range(-30, 31) for y in range(-30, 31) if abs(x) + abs(y) <= 30}


def world_coords(depth):
    """World square of a surface level, or None for a dungeon level (depth > 0)."""
    return _COORDS.get(depth) if depth <= 0 else None


def world_name(xy):
    x, y = xy
    if not x and not y:
        return "Town"
    parts = []
    if y:
        parts.append(f"{abs(y)}{'N' if y > 0 else 'S'}")
    if x:
        parts.append(f"{abs(x)}{'E' if x > 0 else 'W'}")
    return ", ".join(parts)


def plan_tour(start, targets, via=(), home=(0, 0)):
    """Order world squares so each target is visited, stepping only through
    targets, `via` and home. Returns the full list of squares to walk through."""
    allowed = set(targets) | set(via) | {home, start}
    todo = set(targets) - {start}
    route, cur = [start], start
    while todo:
        # BFS to the nearest unvisited target through allowed squares
        prev, q, found = {cur: None}, deque([cur]), None
        while q:
            sq = q.popleft()
            if sq in todo:
                found = sq
                break
            for _, (dx, dy) in EXITS.values():
                nb = (sq[0] + dx, sq[1] + dy)
                if nb in allowed and nb not in prev:
                    prev[nb] = sq
                    q.append(nb)
        if found is None:
            raise ValueError(f"targets not connected: {sorted(todo)}")
        leg = []
        while found != cur:
            leg.append(found)
            found = prev[found]
        route += leg[::-1]
        todo -= set(leg)
        cur = route[-1]
    return route


def step_dir(a, b):
    d = (b[0] - a[0], b[1] - a[1])
    for name, (_, step) in EXITS.items():
        if step == d:
            return name
    raise ValueError(f"{a} -> {b} is not a single step")


def edge_tiles(rows, way):
    """Known passable tiles next to the given edge (row/col 1 or MAX-2)."""
    if way == "N":
        cells = [(1, x) for x in range(1, MAX_WID - 1)]
    elif way == "S":
        cells = [(MAX_HGT - 2, x) for x in range(1, MAX_WID - 1)]
    elif way == "W":
        cells = [(y, 1) for y in range(1, MAX_HGT - 1)]
    else:
        cells = [(y, MAX_WID - 2) for y in range(1, MAX_HGT - 1)]
    return [c for c in cells if nav.passable(rows[c[0]][c[1]])]


def current_depth(client):
    return client.status()["ind"]["depth"][0]


def cross(client, way, rows=None, timeout=8.0):
    """Walk to the `way` edge and step off it. Returns the new depth or None."""
    rows = rows or client.map()
    old = current_depth(client)
    goals = edge_tiles(rows, way)
    if not goals or nav.goto(client, goals) is None:
        return None
    key = EXITS[way][0]
    end = time.time() + timeout
    while time.time() < end:
        client.send(f"walk {key}")
        client.collect(1.0)
        d = current_depth(client)
        if d != old:
            client.collect(1.5)           # let the new level's map arrive
            return d
    return None


class Boxed(RuntimeError):
    """Nothing is reachable -- probably shut in (e.g. inside an arena)."""


def sweep_points(arrival, dy=12, dx=20):
    """Waypoints covering the level in a boustrophedon, starting from the
    edge we arrived on."""
    ys = list(range(6, MAX_HGT - 5, dy))
    xs = list(range(10, MAX_WID - 9, dx))
    if arrival[0] > MAX_HGT // 2:
        ys.reverse()
    if arrival[1] > MAX_WID // 2:
        xs.reverse()
    pts = []
    for i, y in enumerate(ys):
        pts += [(y, x) for x in (xs if i % 2 == 0 else xs[::-1])]
    return pts


def explore(client, budget, say=print, check=None, near=8):
    """Sweep the level so every part has been within sight: walk a coarse grid
    of waypoints, skipping those we've already passed near. Works by day and
    by night -- house walls and doors are lit even at night, so they show up
    at a distance; the floor only shows by day. `check()` runs between legs."""
    end = time.time() + budget
    first = len(client.trail)
    legs = skipped = failed = streak = 0
    for pt in sweep_points(client.pos):
        if time.time() >= end:
            break
        walked = client.trail[first:] + [client.pos]
        if any(max(abs(pt[0] - p[0]), abs(pt[1] - p[1])) <= near for p in walked):
            skipped += 1
            continue
        if check:
            check()
        rows = client.map()
        goals = [pt] if nav.passable(rows[pt[0]][pt[1]]) else []
        if not goals:
            # Waypoint is a wall/tree etc.: any walkable tile close to it will do
            goals = [(y, x) for y in range(pt[0] - 3, pt[0] + 4) for x in range(pt[1] - 3, pt[1] + 4)
                     if nav.inside(y, x) and nav.passable(rows[y][x])]
            if not goals:
                skipped += 1      # nowhere to stand here (e.g. a block of trees)
                continue
        hits = client.hits
        got = nav.goto(client, goals, rows=rows, deadline=min(end, time.time() + 40))
        legs += 1
        failed += got is None
        if got is None and client.hits - hits >= 3:
            continue              # cut short by an attack, not a sign of being shut in
        streak = streak + 1 if got is None else 0
        if streak >= 6:
            raise Boxed(f"{streak} waypoints in a row not reached from {client.pos}")
    rows = client.map()
    say(f"  explored: {legs} legs ({failed} not reached, {skipped} skipped), "
        f"{'budget used up' if time.time() >= end else 'sweep complete'}")
    return rows

"""Route planning on the tool-mode map (198x66, absolute coordinates).

The server's pathfind reaches ~25 tiles, so longer trips are split into
waypoints along a client-side shortest path. The map only holds glyphs, so
passability is a conservative guess; the server has the final word.
"""
import heapq
import time

# keypad direction for (dy, dx)
DIRS = {(-1, -1): 7, (-1, 0): 8, (-1, 1): 9, (0, -1): 4, (0, 1): 6, (1, -1): 1, (1, 0): 2, (1, 1): 3}

# Walls/secret doors, closed doors, rubble, NPC shop entrances, house doors
# ('0' in tool mode), traps, trees (and treasure veins in the dungeon) --
# "There is a tree blocking your way."
BLOCKED = set("#+:12345678^*") | {"0"}
# Allowed but avoided: water/mud, crops (in the dungeon '%' is a vein,
# which the server will refuse -- goto() then routes around it), and unknown
# ground (' '). Like the server's own pathfinding, unseen grids are assumed
# walkable; that is what makes travel at night (when the floor isn't drawn)
# possible. The level's outer border is also drawn ' ' and is excluded by
# position instead.
COST = {"~": 2, "%": 2, " ": 2}
MAX_HGT, MAX_WID = 66, 198

HOP = 18                                    # waypoint spacing (< server pathfind reach)


def passable(ch):
    return ch not in BLOCKED


def inside(y, x):
    """Not on the level's outer border."""
    return 0 < y < MAX_HGT - 1 and 0 < x < MAX_WID - 1


def neighbours(y, x, hgt, wid):
    for (dy, dx) in DIRS:
        ny, nx = y + dy, x + dx
        if 0 <= ny < hgt and 0 <= nx < wid:
            yield ny, nx


def shortest_path(rows, start, goals, avoid=()):
    """Dijkstra from start to the nearest of goals. Returns list of tiles (excl. start) or None."""
    hgt, wid = len(rows), len(rows[0])
    goals = set(goals)
    avoid = set(avoid)
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
        if d > dist[cur]:
            continue
        for nb in neighbours(*cur, hgt, wid):
            ch = rows[nb[0]][nb[1]]
            if nb not in goals and (not passable(ch) or nb in avoid or not inside(*nb)):
                continue
            nd = d + COST.get(ch, 1)
            if nd < dist.get(nb, 1 << 30):
                dist[nb] = nd
                prev[nb] = cur
                heapq.heappush(heap, (nd, nb))
    return None


def stand_spots(rows, door):
    """Tiles next to a door we could stand on: seen floor if there is any,
    otherwise unseen ground (at night the floor around a door isn't drawn)."""
    hgt, wid = len(rows), len(rows[0])
    near = [nb for nb in neighbours(*door, hgt, wid) if inside(*nb)]
    known = [nb for nb in near if rows[nb[0]][nb[1]] != " " and passable(rows[nb[0]][nb[1]])]
    return known or [nb for nb in near if rows[nb[0]][nb[1]] == " "]


def direction(frm, to):
    return DIRS.get((to[0] - frm[0], to[1] - frm[1]))


def _send_hop(client, hop):
    here = client.pos
    if max(abs(hop[0] - here[0]), abs(hop[1] - here[1])) <= 1:
        client.send(f"walk {direction(here, hop)}")
    else:
        client.send(f"pathfind {hop[0]} {hop[1]}")


def goto(client, goals, rows=None, step_timeout=3.0, max_replans=10, deadline=None):
    """Move the character to any tile in goals. Returns the tile reached or None."""
    goals = set(goals)
    avoid = set()
    for _ in range(max_replans):
        if client.pos in goals:
            return client.pos
        if deadline and time.time() > deadline:
            return None
        rows = rows or client.map()
        path = shortest_path(rows, client.pos, goals, avoid)
        if not path:
            return None
        while path:
            hop = path[min(HOP, len(path)) - 1]
            before = client.pos
            _send_hop(client, hop)
            arrived = _wait_arrival(client, hop, step_timeout)
            if not arrived:
                # The server sometimes ignores a command sent just as a
                # previous run ends -- try the same hop once more first.
                _send_hop(client, hop)
                arrived = _wait_arrival(client, hop, step_timeout)
            if not arrived:
                # Didn't make it: if we never moved, the next tile is probably
                # blocked; otherwise the hop target is. Avoid it and replan.
                avoid.add(path[0] if client.pos == before else hop)
                rows = None
                break
            path = path[path.index(hop) + 1:]
        else:
            if client.pos in goals:
                return client.pos
    return client.pos if client.pos in goals else None


class Jumped(RuntimeError):
    """Position jumped more than one tile: a level change or a teleport."""


def _wait_arrival(client, target, timeout):
    """Wait until pos == target; give up after `timeout` seconds without movement.
    Raises Jumped if we suddenly end up somewhere else (new level, teleport),
    since coordinates then no longer mean what the plan assumed."""
    last_move = time.time()
    last_pos = client.pos
    seen = len(client.trail)
    while client.pos != target:
        client.collect(0.1)
        new = client.trail[seen:]
        seen += len(new)
        for p in new:
            if max(abs(p[0] - last_pos[0]), abs(p[1] - last_pos[1])) > 1:
                raise Jumped(f"moved {last_pos} -> {p}")
            last_pos, last_move = p, time.time()
        if not new and time.time() - last_move > timeout:
            return False
    return True

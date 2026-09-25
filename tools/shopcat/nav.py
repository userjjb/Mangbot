"""Route planning on the tool-mode map (198x66, absolute coordinates).

Movement walks a client-side shortest path step by step (see goto() for why
not the server's pathfind). The map only holds glyphs, so passability is a
guess; bumping into something unseen makes us replan around it.
"""
import heapq
import time

# keypad direction for (dy, dx)
DIRS = {(-1, -1): 7, (-1, 0): 8, (-1, 1): 9, (0, -1): 4, (0, 1): 6, (1, -1): 1, (1, 0): 2, (1, 1): 3}

# Walls/secret doors, closed doors, rubble, NPC shop entrances, house doors
# ('0' in tool mode), traps, trees (and treasure veins in the dungeon) --
# "There is a tree blocking your way."
BLOCKED = set("#+:1234567^*") | {"0"}
# Allowed but avoided: water/mud, crops (in the dungeon '%' is a vein,
# which the server will refuse -- goto() then routes around it), and unknown
# ground (' '). Like the server's own pathfinding, unseen grids are assumed
# walkable; that is what makes travel at night (when the floor isn't drawn)
# possible. The level's outer border is also drawn ' ' and is excluded by
# position instead.
COST = {"~": 2, "%": 2, " ": 2,
        "8": 50}   # the Tavern entrance: new characters start inside the Tavern
                   # and must walk out through it (stepping on it enters, the
                   # next step leaves)
MAX_HGT, MAX_WID = 66, 198


# Tiles to keep out of on the current level, whatever the map shows (e.g. an
# arena found the hard way). The caller swaps this set when the level changes.
extra_blocked = set()


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
            if nb not in goals and (not passable(ch) or nb in avoid or nb in extra_blocked
                                    or not inside(*nb)):
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


def _by_edge(tile, dist=1):
    y, x = tile
    return y <= dist or y >= MAX_HGT - 1 - dist or x <= dist or x >= MAX_WID - 1 - dist


def goto(client, goals, rows=None, step_timeout=3.0, max_replans=10, deadline=None):
    """Move the character to any tile in goals. Returns the tile reached or None.

    Walks our own shortest path one step at a time (a couple of steps queued
    ahead). We don't use the server's pathfind: it searches 25 tiles around
    the player treating never-seen grids as open, including the row/column
    just past the level edge -- and a route along it walks off the level. It
    also knows nothing about our no-go zones."""
    goals = set(goals) - extra_blocked
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
        start = client.pos
        done = _walk_path(client, path, step_timeout, deadline)
        if done < len(path):
            # Stuck or pushed off course. If we couldn't take the next step
            # at all, that tile is probably blocked; avoid it and replan.
            if client.pos == (path[done - 1] if done else start):
                avoid.add(path[done])
            rows = None
    return client.pos if client.pos in goals else None


def _walk_path(client, path, timeout, deadline=None, ahead=2):
    """Walk along path, keeping up to `ahead` steps queued. Returns how many
    tiles of path were reached. Stops early if a step doesn't happen within
    `timeout` s or we end up off the path; raises Jumped on a jump."""
    sent = done = 0
    here = client.pos
    seen = len(client.trail)
    last_move = time.time()
    while done < len(path):
        # Near the edge, one step at a time (a mis-step could leave the level)
        limit = 1 if _by_edge(path[done], 2) else ahead
        while sent < len(path) and sent - done < limit:
            frm = path[sent - 1] if sent else here
            client.send(f"walk {direction(frm, path[sent])}")
            sent += 1
        evs = client.collect(0.05)
        if any(e["ev"] == "message" and "blocking your way" in e["text"] for e in evs):
            # Walked into something we couldn't see (wall, tree, door)
            client.collect(0.3)
            return done
        new = client.trail[seen:]
        seen += len(new)
        for p in new:
            last = path[done - 1] if done else here
            if max(abs(p[0] - last[0]), abs(p[1] - last[1])) > 1:
                raise Jumped(f"moved {last} -> {p}")
            if done < len(path) and p == path[done]:
                done += 1
                last_move = time.time()
            else:
                # Off the planned path (a step was dropped or went astray):
                # let the queued steps settle, then replan from where we are
                client.collect(0.5)
                return done
        if time.time() - last_move > timeout or (deadline and time.time() > deadline):
            client.collect(0.3)
            return done
    return done


class Jumped(RuntimeError):
    """Position jumped more than one tile: a level change or a teleport."""

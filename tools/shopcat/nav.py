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
# "There is a tree blocking your way." -- and '=': logs/fences in the
# wilderness (also a ring on the floor, but that's rare and not worth the bumps)
BLOCKED = set("#+:1234567^*=") | {"0"}
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
            old = dist.get(nb, 1 << 30)
            if nd < old:
                dist[nb] = nd
                prev[nb] = cur
                heapq.heappush(heap, (nd, nb))
            elif nd == old and cur in prev and prev[nb] != cur and \
                    (nb[0] - cur[0], nb[1] - cur[1]) == (cur[0] - prev[cur][0], cur[1] - prev[cur][1]):
                # Equally short, but keeps going straight: prefer it (long
                # straight stretches can be run instead of walked)
                prev[nb] = cur
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


def _near_no_go(tile, dist=2):
    if not extra_blocked:
        return False
    y, x = tile
    return any((y + dy, x + dx) in extra_blocked
               for dy in range(-dist, dist + 1) for dx in range(-dist, dist + 1))


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
        hits = client.hits
        done = _move_path(client, path, step_timeout, deadline)
        if client.hits - hits >= 3:
            return None           # under attack: let the caller fight/rest first
        if done < len(path):
            # Stuck or pushed off course. If we couldn't take the next step
            # at all, that tile is probably blocked; avoid it and replan.
            if client.pos == (path[done - 1] if done else start):
                avoid.add(path[done])
            rows = None
    return client.pos if client.pos in goals else None


RUN_MIN = 5          # straight stretches at least this long are run, not walked
RUN_STOP_EARLY = 1   # stop a run this many tiles before the stretch ends (reaction time)


def _straight_len(path, start, here):
    """Length of the straight stretch of path beginning at index start."""
    frm = path[start - 1] if start else here
    d = (path[start][0] - frm[0], path[start][1] - frm[1])
    n = 1
    while start + n < len(path):
        a, b = path[start + n - 1], path[start + n]
        if (b[0] - a[0], b[1] - a[1]) != d:
            break
        n += 1
    return n


def _move_path(client, path, timeout, deadline=None):
    """Follow path: run along long straight stretches, walk the rest.
    Returns how many tiles of path were reached (see _walk_path)."""
    done = 0
    here = client.pos
    while done < len(path):
        n = _straight_len(path, done, here)
        stretch = path[done:done + n]
        # Past the stop point a run may overshoot a tile or two; only run where
        # that is harmless (not near the level edge or a no-go zone)
        beyond = [(stretch[-1][0] + k * (stretch[-1][0] - (path[done + n - 2] if n > 1 else here)[0]),
                   stretch[-1][1] + k * (stretch[-1][1] - (path[done + n - 2] if n > 1 else here)[1]))
                  for k in (1, 2)]
        risky = any(_by_edge(t, 2) or _near_no_go(t) for t in stretch + beyond)
        if n >= RUN_MIN and not risky:
            got = _run_stretch(client, path, done, n, timeout, here)
            if got is None:       # went astray: stopped; caller replans
                return done
            if client.pos != (path[got - 1] if got else here):
                return got
            if got > done:
                done = got
                continue
            # The run didn't get going (something in view stops it at once):
            # walk this stretch instead

        # Walk this stretch (at most up to the next run-able one)
        got = _walk_path(client, path[:done + n], timeout, deadline, start=done, here=here)
        if got < done + n:
            return got
        done = got
        if deadline and time.time() > deadline:
            return done
    return done


def _run_stretch(client, path, done, n, timeout, here):
    """Run along path[done:done+n] and stop RUN_STOP_EARLY tiles before its end.
    Returns the new count of path tiles reached, or None if we left the path."""
    frm = path[done - 1] if done else here
    d = direction(frm, path[done])
    stop_at = done + n - RUN_STOP_EARLY
    seen = len(client.trail)
    last = frm
    last_move = time.time()
    stopped = False
    client.send(f"custom . dir={d}")
    while True:
        client.collect(0.03)
        new = client.trail[seen:]
        seen += len(new)
        for p in new:
            if max(abs(p[0] - last[0]), abs(p[1] - last[1])) > 1:
                raise Jumped(f"moved {last} -> {p}")
            last = p
            if done < len(path) and p == path[done]:
                done += 1
                last_move = time.time()
            else:
                # The run turned (followed a corridor) or overshot: stop it
                if not stopped:
                    client.send("walk 5")
                client.collect(0.4)
                return None
        if not stopped and done >= stop_at:
            client.send("walk 5")         # a walk request stops a run (and is swallowed)
            stopped = True
            last_move = time.time()
        if time.time() - last_move > (0.6 if stopped else 1.0):
            # The run ended (we stopped it, or something interesting stopped it)
            if not stopped:
                client.send("walk 5")     # harmless if the run already ended
                client.collect(0.3)
                # A late step can still arrive; take it if it's on the path
                for p in client.trail[seen:]:
                    if done < len(path) and p == path[done]:
                        done += 1
            return done


def _walk_path(client, path, timeout, deadline=None, ahead=2, start=0, here=None):
    """Walk along path, keeping up to `ahead` steps queued. Returns how many
    tiles of path were reached. Stops early if a step doesn't happen within
    `timeout` s or we end up off the path; raises Jumped on a jump.
    `start`/`here`: continue from path[start] (reached from `here` if start is 0)."""
    sent = done = start
    here = client.pos if here is None else here
    seen = len(client.trail)
    hits = client.hits
    last_move = time.time()
    while done < len(path):
        # One step at a time near the level edge or a no-go zone: if a queued
        # step is refused, the next one would be taken from the wrong tile and
        # could leave the level or bump an arena wall
        limit = 1 if (_by_edge(path[done], 2) or _near_no_go(path[done])) else ahead
        while sent < len(path) and sent - done < limit:
            frm = path[sent - 1] if sent else here
            client.send(f"walk {direction(frm, path[sent])}")
            sent += 1
        evs = client.collect(0.05)
        if client.hits - hits >= 3:
            # Under attack: stop so the caller can deal with it
            client.collect(0.3)
            return done
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

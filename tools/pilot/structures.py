"""Inner rooms, monster pits and nests, recognised on a partial map.

The Advisor's spec (memos/2026-10-07-mission15-answers.md §2; generate.c
build_type4/5/6 and room_build): a large room, a nest and a pit are the same
"double room", centred on a fixed grid (room_build: y = 11*by + 5, x = 11*bx + 5):

    #########################   Y-5  outer wall          (11 tall x 25 wide)
    #.......................#   Y-4  ring corridor, 1 wide
    #.##########D##########.#   Y-3  inner wall; D = the inner room's secret door
    #.#...................#.#   Y-2  inner room 5 x 19
    #.D.........C.........D.#   Y    (C = centre; one of the 4 D's is real)
    #.#...................#.#   Y+2
    #.##########D##########.#   Y+3
    #.......................#   Y+4
    #########################   Y+5

Secret doors, granite and inner walls all draw as '#', so the shape is the only
clue. Only the grid centres are tested: per centre, count the known squares
that fit (ring floor, inner wall) and those that contradict it.
"""

WALLS = set("#%")              # what a wall square shows (a secret door too)
DOORS = set("+'")              # a door found in the inner wall
NOT_FLOOR = WALLS | set(" :*12345678")

CENTRE_Y = range(5, 61, 11)    # 5, 16, ..., 60
CENTRE_X = range(16, 182, 11)  # 16, 27, ..., 181 (bx 1..16: the room spans 3 blocks)


def ring_squares(Y, X):
    """The 1-wide corridor around the inner block, by side."""
    return {
        "top": [(Y - 4, x) for x in range(X - 11, X + 12)],
        "bottom": [(Y + 4, x) for x in range(X - 11, X + 12)],
        "left": [(y, X - 11) for y in range(Y - 3, Y + 4)],
        "right": [(y, X + 11) for y in range(Y - 3, Y + 4)],
    }


def inner_wall(Y, X):
    """The inner block's outline, by side (the side facing that ring side)."""
    return {
        "top": [(Y - 3, x) for x in range(X - 10, X + 11)],
        "bottom": [(Y + 3, x) for x in range(X - 10, X + 11)],
        "left": [(y, X - 10) for y in range(Y - 2, Y + 3)],
        "right": [(y, X + 10) for y in range(Y - 2, Y + 3)],
    }


def door_spots(Y, X):
    """The 4 places the inner room's door can be, and the ring square in front
    of each, from which a search covers it."""
    return [((Y - 3, X), (Y - 4, X)), ((Y + 3, X), (Y + 4, X)),
            ((Y, X - 10), (Y, X - 11)), ((Y, X + 10), (Y, X + 11))]


def match(mem, Y, X):
    """Evidence for a double room centred at Y,X: None if the map contradicts it,
    else {'sides': sides seen, 'ring_known': n, 'ring_total': n}."""
    ring, inner = ring_squares(Y, X), inner_wall(Y, X)
    doors = {d for d, _ in door_spots(Y, X)}
    sides = []
    known = total = 0
    for side, sq in ring.items():
        floor = 0
        for q in sq:
            total += 1
            ch = mem.get(q)
            if ch is None or ch == " ":
                continue
            known += 1
            if ch in NOT_FLOOR:
                return None               # a wall where the ring runs: not this room
            floor += 1
        walls = 0
        for q in inner[side]:
            ch = mem.get(q)
            if ch is None or ch == " ":
                continue
            if ch in WALLS or (q in doors and ch in DOORS):
                walls += 1
            else:
                return None               # open floor in the inner wall (not at a door)
        # a side counts when a stretch of ring runs beside a stretch of inner wall
        # (60% of the side: a corridor that happens to run along a ring row and
        # turn at its corner is rare over that length)
        need = 14 if side in ("top", "bottom") else 5
        if floor >= need and walls >= need // 2:
            sides.append(side)
    # The outer wall: corridors can pierce it, so only a lot of floor there
    # rules the room out
    outer = [(Y - 5, x) for x in range(X - 12, X + 13)] + [(Y + 5, x) for x in range(X - 12, X + 13)] + \
            [(y, X - 12) for y in range(Y - 4, Y + 5)] + [(y, X + 12) for y in range(Y - 4, Y + 5)]
    open_outer = sum(1 for q in outer if mem.get(q) not in (None, " ") and mem.get(q) not in NOT_FLOOR)
    if open_outer > 6:
        return None
    # Two sides at a corner, or two parallel ones (8 rows or 22 columns apart):
    # a plain corridor beside a wall shows only one
    if len(sides) < 2:
        return None
    return {"sides": sides, "ring_known": known, "ring_total": total,
            "sure": len(sides) >= 3 or {"top", "bottom"} <= set(sides) or {"left", "right"} <= set(sides)}


def scan(mem):
    """[(Y, X, evidence)] for every grid centre the map supports."""
    out = []
    for Y in CENTRE_Y:
        for X in CENTRE_X:
            # cheap pre-check: some ring square known as floor
            if not any(mem.get(q) not in (None, " ") and mem.get(q) not in NOT_FLOOR
                       for q in ((Y - 4, X), (Y + 4, X), (Y, X - 11), (Y, X + 11),
                                 (Y - 4, X - 8), (Y - 4, X + 8), (Y + 4, X - 8), (Y + 4, X + 8),
                                 (Y - 2, X - 11), (Y + 2, X - 11), (Y - 2, X + 11), (Y + 2, X + 11))):
                continue
            ev = match(mem, Y, X)
            if ev:
                out.append((Y, X, ev))
    return out


ORC_CHARS = set("o")


def classify(Y, X, ev, monsters, lit_at_first):
    """'pit' / 'nest' / 'large room' / 'inner room' (dark, unknown) from the
    monsters around it and whether it came into view all at once (lit rooms do;
    pits and nests are never lit)."""
    near = [(y, x, r) for y, x, r in monsters if Y - 7 <= y <= Y + 7 and X - 14 <= x <= X + 14]
    kinds = {}
    for m in near:
        kinds[getattr(m[2], "char", "?")] = kinds.get(getattr(m[2], "char", "?"), 0) + 1
    inside = [(y, x, r) for y, x, r in near if Y - 2 <= y <= Y + 2 and X - 9 <= x <= X + 9]
    still = [m for m in inside if "NEVER_MOVE" in getattr(m[2], "flags", ())]
    # (a pit is one monster kind: orcs down to 950 ft, then trolls, giants...)
    top = max(kinds.items(), key=lambda kv: kv[1], default=("?", 0))
    if not lit_at_first and top[1] >= 4 and len(still) < 3:
        return "orc pit" if top[0] in ORC_CHARS else f"monster pit ({top[0]})"
    if not lit_at_first and len(still) >= 3:
        return "nest"
    if lit_at_first:
        return "large room"
    return "inner room"

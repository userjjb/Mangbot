"""unit_levels -- unit cases: Bands and levels (stairs, quiet levels, exploring, structures).

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import collections

from fixtures import P, BYNAME, case, pilot, _Stub, _quiet_level


@case
def band_leave_finds_stairs():
    """The user (after m26, every trip ending in an escape recall): a band, no stairs known, HP full, nothing
    adjacent -> no Word of Recall at once: BandLeave reads Magic Mapping (no Door/Stair device), then flees to
    the stairs it shows. A second failure on the level, or HP low, still recalls."""
    def make(hp=265):
        p = pilot(hp=hp, pack=[("2 Scrolls of Word of Recall", 70), ("3 Scrolls of Magic Mapping", 70)])
        p.live = True          # (2.48.0: on the test server the scroll is a crutch, never read -- mapping_scrolls_a_crutch_on_test)
        p.w.adjacent_monsters = lambda: []
        p.w.find = lambda chars: []
        p.w.in_dungeon, p.w.level_t = True, 5.0
        p.danger_why = lambda r: None
        p.recall_started = lambda now: False
        p.use_stair_location = lambda why: False
        p.busy_until, p.goal = 0.0, None
        p.set_goal = lambda g: setattr(p, "goal", g)
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append((line, why))
        p.w.listed_only = lambda: []
        p.flee_fail_t = 0
        p.phase_t, p.phase_hist = 0, collections.deque()
        p.w.tagged = lambda c, d: None
        return p
    p = make()
    p.flee_failed("flee (band: the trip leaves the level)")
    first = type(p.goal).__name__
    p.goal.tick(p)
    mm = [w for _, w in p.cmds]
    p.w.find = lambda chars: [(25, 25)]
    p.goal.t0 -= 5
    p.mover = type("M", (), {"go": lambda self, *a, **k: True, "active": True, "unknown": False, "path": [(1, 1)] * 5,
                             "tick": lambda self: "moving", "stop": lambda self: None})()
    p.w.standing_on = None
    r = p.goal.tick(p)
    second = p.goal.flee is not None
    q = make(hp=150)
    q.w.monsters = [(22, 20, BYNAME["cave orc"])]
    q.flee_failed("flee (band: the trip leaves the level)")
    recalled = any("word of recall" in w for _, w in q.cmds)
    ok = first == "BandLeave" and any("Magic Mapping" in w for w in mm) and second and recalled
    return ok, f"goal {first}; reads {mm}; fled to stairs {second}; at 57% HP recalled {recalled}"


@case
def stairs_beside_mold():
    """m25: a Brown mold (confuses: never fought) beside the only '>' at 300 ft; the step-away walked 6 squares
    back and the dive pressed '>' there, 2 minutes. Stairs a step away (or under us) beside a stationary monster
    harmless for a turn -> take them; a disenchanter, a drainer, a floating eye, or stairs far off -> not."""
    def check(name, goal=(15, 32), pos=(15, 32), dive=False):
        p = pilot()
        p.w.pos, p.w.level_t = pos, 5.0
        p.w.memory = {(15, 32): ">"}
        p.w.standing_on = ">" if pos == (15, 32) else "."
        p.mover = type("M", (), {"goals": None if dive else {goal}, "active": not dive})()
        p.still_goals = (None, set())
        p.goal = None
        if dive:                       # (on the stairs the mover has already stopped: the live M1 run)
            p.goal = P.Dive.__new__(P.Dive)
            p.goal.want = ">"
        return p.stairs_beside_still([(14, 32, BYNAME[name])])
    got = {
        "brown mold on '>'": check("brown mold"),
        "brown mold on '>', mover stopped, diving": check("brown mold", dive=True),
        "brown mold, '>' a step off": check("brown mold", pos=(15, 31)),
        "disenchanter mold": check("disenchanter mold"),
        "purple mushroom patch": check("purple mushroom patch"),
        "floating eye": check("floating eye"),
        "brown mold, goal not stairs": check("brown mold", goal=(15, 26), pos=(15, 25)),
    }
    want = {"brown mold on '>'": True, "brown mold on '>', mover stopped, diving": True,
            "brown mold, '>' a step off": True, "disenchanter mold": False,
            "purple mushroom patch": False, "floating eye": False, "brown mold, goal not stairs": False}
    return got == want, ", ".join(f"{k}: {'take' if v else 'step away'}" for k, v in got.items())


@case
def refused_stairs_dont_end_explore():
    """m30 06:17-06:23: at 600 ft the dive refused the '>' back to the 650 ft level it had just fled, started an
    'explore until stairs', which ended at once on that same '>' -- 6 minutes of nothing, logged as nothing.
    The refused stairs no longer count as seen; another '>' does."""
    import mover as M
    class Wd:
        pos = (10, 10)
        in_dungeon, depth = True, 12
        monsters, still_seen, avoid_zone, avoid_inside = [], {}, set(), False
        def __init__(self, mem):
            self.memory = mem
        def find(self, chars):
            return [q for q, ch in self.memory.items() if ch in chars]
    floor = {(10, x): "." for x in range(5, 20)}
    d = P.Dive.__new__(P.Dive)
    d.bad_stairs, d.level_seen = {(7.0, (10, 12))}, 7.0
    e = P.Explore(until="stairs", skip=d.refused)
    only = e.stairs_seen(Wd({**floor, (10, 12): ">"}))
    other = e.stairs_seen(Wd({**floor, (10, 12): ">", (10, 18): ">"}))
    plain = P.Explore(until="stairs").stairs_seen(Wd({**floor, (10, 12): ">"}))
    ok = only is None and other == "stairs down seen" and plain == "stairs down seen"
    return ok, f"only the refused '>': {only}; another '>' too: {other}; no skip (as before): {plain}"


@case
def band_condition_only_while_live():
    """m30: the `band` condition fired 3 minutes after a beaten Novice warrior band, on a new level, when the plan
    resumed after the Navigator's goal. It holds while the band is live (warned in the last 20 s on this level, or
    3+ monsters still within 10); a band gone or beaten clears it."""
    p = pilot()
    p.w.level_t = 5.0
    tp = P.TripPlan(500, 650, P.TripPlan.parse_until("band or minutes>30"))
    tp.events["band"] = 1
    p.band_warned, p.band_warned_t = (5.0, 7), P.gnow()
    fresh = tp.holds(p)
    p.band_warned_t = P.gnow() - 60
    p.w.monsters = [(20, 22 + i, BYNAME["novice warrior"]) for i in range(4)]
    still = tp.holds(p)
    p.w.monsters = []
    beaten = tp.holds(p)
    tp.events["band"] = 1
    p.w.level_t = 6.0                     # left the level meanwhile
    moved = tp.holds(p)
    ok = fresh == "band" and still == "band" and beaten is None and moved is None and tp.events["band"] == 0
    return ok, f"just warned: {fresh}; 60 s on, 4 in view: {still}; beaten: {beaten}; on a new level: {moved}"


@case
def run_loop_walks():
    """m31: explore's free runs looped 157 times through a cave corridor (16,112 -> 16,111 -> 16,109 -> north,
    back round to 16,112). Two free runs from one square within a minute: walk from it instead."""
    import mover as M
    class C:
        def __init__(self):
            self.sent = []

        def send(self, x):
            self.sent.append(x)
    w = type("Wd", (), {"pos": (16, 109), "level_t": 3.0})()
    m = M.Mover.__new__(M.Mover)
    m.w, m.c, m.log = w, C(), lambda **k: None
    m.goals, m.path, m.running, m.free, m.run_hist = None, [], None, None, []
    m.stop = lambda: None
    first = m.run_loop()
    m.free_run(8)
    once = m.run_loop()
    m.free_run(8)
    twice = m.run_loop()
    w.pos = (16, 112)
    other = m.run_loop()
    w.level_t = 4.0
    w.pos = (16, 109)
    new_level = m.run_loop()
    ok = not first and not once and twice and not other and not new_level
    return ok, f"no runs: {first}; one: {once}; two: {twice}; another square: {other}; a new level: {new_level}"


@case
def bands_by_expected_cost_weak_drainers_news():
    """The matrix (m30, m33, m34): the plan left levels for weak bands and weak drainers. A band is serious by the
    expected cost of fighting it one by one (> 50% HP), not the sum of maximum hits; in a corridor only 2 reach us.
    A weak drainer (10+... 5+ levels below, no faster, not unique) is news, not a reason to leave."""
    def make(corridor=False):
        p = pilot(hp=310, worn=[("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23, 130)])
        p.w.hp = [310, 310]
        p.w.clvl = 25
        p.mover = type("M", (), {"in_corridor": lambda self: corridor})()
        p.our_slowness = lambda: 1.0
        return p
    def cost(names, corridor=False):
        return make(corridor).band_cost([BYNAME[n] for n in names])
    novice = cost(["novice warrior"] * 6 + ["swordsman"])
    orcs22 = cost(["cave orc"] * 4 + ["snaga"] * 3 + ["black orc"] * 3)
    hill = cost(["hill orc"] * 10)
    hill_c = cost(["hill orc"] * 10, corridor=True)
    p = make()
    p.w.in_dungeon, p.w.level_t = True, 3.0
    p.drainers_seen = set()
    p.w.monsters = [(20, 25, BYNAME["giant red frog"])]
    said = []
    p.notify = lambda what, d=None, news=False, action=True, fields=None: said.append((what, news))
    p.watch_drainers()
    frog = said[-1] if said else None
    ok = novice < 155 and orcs22 > 155 and hill > 155 and hill_c < hill / 2 and frog == ("drainer", True)
    return ok, (f"expected HP: Novice warriors {novice:.0f}, m22's orcs {orcs22:.0f}, 10 Hill orcs {hill:.0f} "
                f"(in a corridor {hill_c:.0f}); 50% of 310 = 155; frog notice (what, news): {frog}")


@case
def quiet_level_left():
    """The matrix: long stays on quiet levels (m33: 22 XP in its last 10 minutes on one 600 ft level). After 3
    minutes on a level, under 10 XP a minute over the last 3 -> the level is done; a busy level isn't."""
    p = pilot()
    p.w.level_t = 7.0
    tp = P.TripPlan(500, 650, P.TripPlan.parse_until("minutes>30"))
    tp.level, tp.level_t0 = 7.0, 0.0
    tp.xp_hist = [(0.0, 1000, 7.0), (10.0, 1005, 7.0)]
    p.w.ind["exp"] = [1012]
    quiet = tp.quiet(p, 200.0)
    tp.xp_hist = [(0.0, 1000, 7.0), (10.0, 1005, 7.0)]
    p.w.ind["exp"] = [1300]
    busy = tp.quiet(p, 200.0)
    early = tp.quiet(p, 100.0)
    ok = quiet and quiet.startswith("quiet") and busy is None and early is None
    return ok, f"12 XP in 3 min: {quiet!r}; 300 XP: {busy}; at 100 s: {early}"


def _dive_on_back_stairs(fled_ago, kept=False, live=True, login_level=False):
    """A dive up from 750 ft standing on the '<' it arrived by, fled_ago seconds after fleeing 700 ft: the stairs
    taken (or not), and the dive."""
    p = pilot()
    w = p.w
    w.depth, w.depth_ft, w.level_t, w.pos = 15, 750, P.gnow() - 300, (4, 150)
    w.standing_on, w.arrive_pos, w.arrived_by = "<", (4, 150), ">"
    w.find = lambda chars: [(4, 150)] if "<" in chars else []
    p.orders["max_depth"] = 750
    p.item_hold_until, p.dangers, p.interesting = 0, lambda: [], lambda: None
    p.loot_step = lambda st: False
    p.mover = type("M", (), {"active": False})()
    p.kept, p.scummed = ({14} if kept else set()), set()
    p.live = live
    p.fled_from = (14, P.gnow() - fled_ago, w.level_t, login_level)
    took = []
    p.take_stairs = took.append
    d = P.Dive(700)
    d.stop, d.level_seen, d.explore, d.probed = False, w.level_t, _Stub(), (w.level_t, w.pos)
    d.tick(p)
    return took, d, p


@case
def fled_stairs_refused_two_minutes_only():
    """m45: fled a band at 700 ft down to 750 ft; 4.5 minutes later the trip's dive up refused the only '<' (back to
    the level fled: held 5 minutes, then never on that level) and spent 10 minutes in a Giant flea swarm looking for
    another. Live server: the hold is 2 minutes (5 on a level the server keeps), and the refusal expires with it. Test
    server (the user, 10-26: one player, no saved levels): no hold, unless the level is kept -- seen kept, or the one
    this Pilot logged in on (our own logout made it static)."""
    took_early, d, p = _dive_on_back_stairs(30)
    key = (p.w.level_t, (4, 150))
    expires = d.bad_t.get(key, 0) - p.fled_from[1]
    took_late, _, _ = _dive_on_back_stairs(130)
    took_kept, _, _ = _dive_on_back_stairs(130, kept=True)
    took_test, _, _ = _dive_on_back_stairs(30, live=False)
    took_test_login, _, _ = _dive_on_back_stairs(30, live=False, login_level=True)
    ok = took_early == [] and key in d.bad_stairs and abs(expires - 105) < 1 and took_late == ["<"] and \
        took_kept == [] and took_test == ["<"] and took_test_login == []
    return ok, f"live, 30 s after: took {took_early} (refusal ends {expires + 15:.0f} s after the flee); " \
               f"130 s after: took {took_late}; on a kept level: {took_kept}; test server 30 s after: {took_test}, " \
               f"on the login level: {took_test_login}"


@case
def quiet_wait_finds_a_spot_and_wakes():
    """The user's 'quiet wait' (10-27): from a corridor into the unknown, the Pilot walks into the walked room (away
    from the unexplored corridor end), waits; a monster that moves wakes it and the goal it paused resumes; a mold
    doesn't; the time running out ends it too."""
    p = _quiet_level()
    spot = p.quiet_spot()
    went = []
    p.mover = type("M", (), {"active": False, "go": lambda self, t: went.append(t) or True,
                             "tick": lambda self: "arrived", "stop": lambda self: None})()
    p.cmd = lambda line, why, hold=0.4: None
    prev = P.Explore() if hasattr(P, "Explore") else None
    g = P.QuietWait(60, prev)
    r1 = g.tick(p)
    p.w.monsters = [(12, 12, BYNAME["disenchanter mold"])]
    r2 = g.tick(p)
    p.w.monsters = [(12, 12, BYNAME["stone troll"])]
    r3 = g.tick(p)
    woke = [d for what, d in p.notes if what == "quiet_end"]
    q = _quiet_level()
    q.mover = p.mover
    q.cmd = p.cmd
    g2 = P.QuietWait(10)
    g2.t0 -= 11
    r4 = g2.tick(q)
    ok = spot is not None and spot[1] <= 26 and went == [[spot]] and r1 is None and r2 is None and \
        r3 and r3[0] == "done" and p.resume_after is prev and woke and "Stone troll" in woke[0] and \
        r4 == ("done", "10 s are up")
    return ok, f"spot {spot}; went {went}; ticks {r1}, {r2}, {r3}, timeout {r4}; told {woke}"


@case
def structures_on_the_aligned_lattice():
    """dungeon_align (our client sends it on): rooms sit on block columns 1, 4, 7... so a double room's centre is at X =
    16, 49, ..., 181 (the Advisor's structures memo). A drawn double room at (16, 49) is found; the same shape at
    (16, 27) -- a centre only the unaligned grid has -- isn't (fewer false pits)."""
    import structures as ST

    def room(Y, X):
        mem = {}
        for y in range(Y - 5, Y + 6):
            for x in range(X - 12, X + 13):
                edge = y in (Y - 5, Y + 5) or x in (X - 12, X + 12)
                ring = y in (Y - 4, Y + 4) or x in (X - 11, X + 11)
                inner_wall = (y in (Y - 3, Y + 3) and X - 10 <= x <= X + 10) or \
                    (x in (X - 10, X + 10) and Y - 3 <= y <= Y + 3)
                mem[(y, x)] = "#" if edge else "." if ring else "#" if inner_wall else " "
        return mem
    on = [(Y, X) for Y, X, ev in ST.scan(room(16, 49))]
    off = [(Y, X) for Y, X, ev in ST.scan(room(16, 27))]
    ok = ST.ALIGNED and (16, 49) in on and (16, 27) not in off
    return ok, f"room at 16,49 -> {on}; at 16,27 -> {off}"


@case
def login_level_not_set_by_the_first_dungeon_level():
    """m63 (2.52.0): `first_level_t = None` meant both "not yet seen" and "logged in in town", so a Pilot started in
    town recorded the first dungeon level (the recall's arrival) as its login level; a band fled there made the
    stairs back "a kept level" (held 300 s) on the test server and the trip recalled home. Started in town: stays
    None through the dungeon; started in the dungeon: that level."""
    def run(first_depth):
        p = pilot()
        w = p.w
        w.depth, w.level_t, w.in_dungeon = first_depth, P.gnow() - 10, first_depth > 0
        w.depth_ft, w.arrived_by, w.messages = first_depth * 50, None, []
        p.map_snap = None
        p.save_level_map(P.gnow())
        first = p.first_level_t
        w.depth, w.depth_ft, w.level_t, w.in_dungeon = 15, 750, P.gnow() - 5, True
        p.save_level_map(P.gnow())
        return first, p.first_level_t, w.level_t
    t_first, t_after, _ = run(0)
    d_first, d_after, _ = run(16)
    ok = t_first is None and t_after is None and d_first not in (None, False) and d_after == d_first
    return ok, f"started in town: {t_first} then {t_after}; started at 800 ft: {d_first} then {d_after}"


# m63's 800 ft level (runs/pilot/dive04/levels/20261104-103417-800ft.txt, rows 0-13 from column 103): a dark inner room
# centred 5,115, its ring corridor holding the only '<' (1,109, the arrival); Dive04 below it at 12,120
_M63_ROOMS = ["#########################",
              "#.....<.................#",
              "#.#####################.'",
              "#.#                   #.'",
              "#.#                   #.#",
              "#.#                   #.#",
              "#.#                   #.#",
              "#.#                   #.#",
              "#.#####################.#",
              "#.......................#",
              "############..#..###..###",
              "           #..........#",
              "              #.......#",
              "              #########"]


def _m63_level():
    p = pilot(hp=300)
    w = p.w
    w.memory = {(y, 103 + x): ch for y, row in enumerate(_M63_ROOMS) for x, ch in enumerate(row) if ch != " "}
    w.pos, w.level_t, w.last_hit_t, w.monsters = (12, 120), 7.0, -99.0, []
    w.depth, w.depth_ft = 16, 800
    p.structs = {(7.0, (5, 115)): {"t": 0.0, "lit": False, "kind": "inner room", "sure": True}}
    p.avoid_zones = {7.0: [(5, 108, 6), (5, 115, 6), (5, 122, 6)]}     # (structures_tick's three discs)
    p.quiet_spot = lambda reach=30: None
    p.mover = type("M", (), {"active": False, "go": lambda self, t, **k: False, "tick": lambda self: "idle",
                             "stop": lambda self: None})()
    p.avoid_tick()
    return p


@case
def avoid_zone_blocking_the_stairs_asks_the_navigator():
    """2.53.0 (the user after m63: "when an avoid zone blocks the Pilot's path, but the Navigator has time to evaluate
    the situation, allow it to decide"). m63 at 800 ft: the inner room's zone covered its ring and the only '<'. With
    time (nothing dangerous in view, not hit, HP fine) the Pilot holds and a `zone_blocks` alert names the stairs, the
    room and the path through; `avoid pass` opens the ring and its surroundings (never the room inside) and the path
    to the '<' is found; no answer in 90 s, or danger in view: as before (the stairs are given up)."""
    import mover
    p = _m63_level()
    w = p.w
    stairs = [(1, 109)]
    before = mover.plan(w, stairs)
    blk = p.zone_blocks(stairs)
    held = p.zone_hold(stairs, "the '<' at 1,109")
    alert = next((d for k, d in p.notes if k == "zone_blocks"), "")
    again = p.zone_hold(stairs, "the '<' at 1,109")
    r = p.do_request({"cmd": "avoid", "args": ["pass"], "role": "navigator"})
    p.avoid_tick()
    path = mover.plan(w, stairs)
    inner = [q for q in path or [] if 2 <= q[0] <= 8 and 105 <= q[1] <= 125]
    after = p.zone_hold(stairs, "the '<' at 1,109")          # (answered: the hold is over)
    t = _m63_level()
    t.zone_hold(stairs, "the '<' at 1,109")
    t.zone_wait["t0"] -= 100
    timeout = t.zone_hold(stairs, "the '<' at 1,109")
    spent = round(t.zone_hold_spent(7.0))
    d = _m63_level()
    d.dangers = lambda: ["a Young blue dragon"]
    danger = d.zone_hold(stairs, "the '<' at 1,109")
    ok = before is None and blk and blk["to"] == (1, 109) and blk["structs"] == [(5, 115, "inner room")] and held \
        and again and "1,109" in alert and "avoid pass" in alert and "inner room centred 5,115" in alert and \
        r["ok"] and path and path[-1] == (1, 109) and not inner and after is False and timeout is False and \
        spent == 90 and danger is False and not any(k == "zone_blocks" for k, _ in d.notes)
    return ok, (f"blocked {before is None}; ignoring the zone {blk}; held {held}/{again}: {alert!r}; avoid pass {r}: "
                f"path {len(path or [])} steps, inside the room {inner}; timeout {timeout} (held {spent} s); "
                f"danger {danger}")


@case
def dive_holds_when_a_zone_blocks_its_stairs():
    """2.53.0: the Dive leg out of m63's 800 ft level (up, the '<' in the ring) holds instead of marking the stairs
    unreachable: it returns no result, the hold is on, the alert raised once; the stairs aren't given up."""
    p = _m63_level()
    w = p.w
    w.standing_on, w.arrive_pos = ".", (1, 109)
    w.find = lambda g: [q for q, ch in w.memory.items() if ch in g]
    p.item_hold_until, p.fled_from, p.kept, p.scummed = 0, None, set(), set()
    p.orders["max_depth"] = 800
    p.loot_step = lambda st: False
    p.loot_beside = lambda: False
    p.pillared = lambda: False
    g = P.Dive(750)
    g.start_ft, g.level_seen, g.probed = 800, w.level_t, (w.level_t, w.pos)
    results = [g.tick(p) for _ in range(3)]
    ok = results == [None] * 3 and p.zone_wait and not p.zone_wait["end"] and not g.bad_stairs and \
        [k for k, _ in p.notes] == ["zone_blocks"]
    return ok, f"ticks {results}; hold {p.zone_wait}; bad stairs {g.bad_stairs}; notes {[k for k, _ in p.notes]}"


# m64's 750 ft level (runs/pilot/dive04/levels/20261104-112824-750ft.txt, rows 17-29 from column 99): the '>' at 27,130
# (found by the Rod of Door/Stair Location) two squares past the room's unexplored east edge (x 128-129 unknown)
_M64_ROOMS = [".#%#%%%%%%####......#",
              ".#           #......#",
              ".#          ##......#",
              ".#          #''######",
              ".%          #%...'.",
              "%            *#..##",
              "              %..#",
              "            %#%'+########''##",
              "            %...............#",
              "*#%#%%#######...............#",
              "......................-......  >",
              ".............................",
              "#############################"]


@case
def dive_walks_to_stairs_past_unexplored_squares():
    """2.54.0 (m64 11:32-11:37 at 750 ft): the '>' lay 2 squares past a room's unexplored east edge; every Dive move
    found "path 0" (15 times), the explore went elsewhere and the trip recalled after 5 minutes. Now, as the flee does,
    the stairs walk plans through unexplored squares when no known path exists (`go(..., unknown=True)`), and the
    dive's explore tries the frontier nearest the stairs first."""
    import mover
    p = pilot(hp=388)
    w = p.w
    w.memory = {(17 + y, 99 + x): ch for y, row in enumerate(_M64_ROOMS) for x, ch in enumerate(row) if ch != " "}
    w.pos, w.level_t, w.last_hit_t, w.monsters, w.standing_on = (28, 105), 9.0, -99.0, [], "."
    w.depth, w.depth_ft, w.arrive_pos = 15, 750, (28, 105)
    w.find = lambda g: [q for q, ch in w.memory.items() if ch in g]
    p.avoid_tick()
    known = mover.plan(w, [(27, 130)])
    through = mover.plan(w, [(27, 130)], unknown_cost=6)
    calls = []

    class M:
        active, path, unknown = False, [], False

        def go(self, goals, avoid=(), unknown=False):
            calls.append(unknown)
            self.path = mover.plan(w, goals) or []
            self.unknown = False
            if not self.path and unknown:
                self.path, self.unknown = mover.plan(w, goals, unknown_cost=6) or [], True
            self.active = bool(self.path)
            return self.active

        def tick(self):
            return "moving"

        def stop(self):
            self.active = False
    p.mover = M()
    p.item_hold_until, p.fled_from, p.kept, p.scummed = 0, None, set(), set()
    p.orders["max_depth"] = 800
    p.loot_step = lambda st: False
    p.loot_beside = lambda: False
    p.pillared = lambda: False
    g = P.Dive(800)
    g.start_ft, g.level_seen, g.probed = 750, w.level_t, (w.level_t, w.pos)
    r = g.tick(p)
    said = [d for k, d in p.notes if k == "tactic" and "unexplored" in str(d)]
    near = P.Explore(toward=[(27, 130)]).toward_frontier(p.frontier())
    ok = known is None and through and through[-1] == (27, 130) and any(q[1] in (128, 129) for q in through) and \
        r is None and \
        g.walking and calls == [True] and p.mover.unknown and said and near and \
        all(max(abs(f[0] - 27), abs(f[1] - 130)) <= 6 for f in near)
    return ok, (f"known path {known}; through unexplored {len(through or [])} steps; dive walking {g.walking} "
                f"(go unknown={calls}); news {said}; explore toward the '>': {sorted(near)}")


# m67's 800 ft level (state.jsonl's map replies, 22:05-22:27), rows 17-31 from column 160: the lesser vault "zelazny"
# (a walled corridor of items and orcs, diagonal walls above it) that Dive04 walked into with no notice
_M67_VAULT = ["              #########",
              "              #_......##.",
              "             .#.....<##S_}",
              "         ####.#..##.##@S=#",
              "         #....#.##.##??.##",
              "         #....###.##...##",
              "        ##..#.##.##.._##",
              "  #######...#...##...##     #.#",
              "  #.........#..##...##      #.#",
              "  #........##.##...##########$#",
              "  #..###### #.#!?|,!_?.]-==$'$#",
              "  ##..#     #.###############.#",
              "   #..#     #..   ............#",
              "   #..#            #''#########",
              "   #..#            #..#"]


@case
def vault_templates_matched():
    """2.62.0 (the user: "build the vault detector"). vault.txt's built templates: 67 lesser (type 7), 75 greater (type
    8; type 9 is never built). build_vault lays a template as written -- no rotation or flip (generate.c:2332) -- so
    the matcher tries every placement whose box holds the evidence. A partial copy of a template (60% of its squares
    known, a corridor through its outer wall) is found at the right place; m67's 800 ft map is the lesser vault
    "zelazny"; past levels with item clusters match nothing (checked offline: 18 levels, no false match)."""
    import random
    import vault
    t = vault.templates()
    kinds = (sum(1 for v in t if v["type"] == "7"), sum(1 for v in t if v["type"] == "8"))
    tm = next(v for v in t if v["name"] == "Lesser vault (zelazny)")
    rnd = random.Random(3)
    mem = {}
    y0, x0 = 20, 60
    for dy, row in enumerate(tm["rows"]):
        for dx, ch in enumerate(row):
            if ch == " " or rnd.random() > 0.6:
                continue
            mem[(y0 + dy, x0 + dx)] = "#" if ch in "%#X+" else "."
    mem[(y0 + 8, x0)] = "."                      # (a corridor broke through the outer wall)
    m = vault.match(mem, (y0 + 9, x0 + 9))
    m67 = {(17 + y, 160 + x): ch for y, row in enumerate(_M67_VAULT) for x, ch in enumerate(row) if ch != " "}
    cl = vault.item_cluster(m67)
    m2 = vault.match(m67, cl[0]) if cl else None
    sq = vault.squares(m2) if m2 else {}
    ok = kinds == (67, 75) and m and m["name"] == "Lesser vault (zelazny)" and (m["y0"], m["x0"]) == (y0, x0) and \
        m2 and m2["name"] == "Lesser vault (zelazny)" and m2["kind"] == "lesser vault" and sq.get("doors")
    return ok, (f"templates lesser/greater {kinds}; partial copy: {m and (m['name'], m['y0'], m['x0'], m['agree'], m['bad'])}; "
                f"m67: {m2 and (m2['name'], m2['y0'], m2['x0'], m2['agree'], m2['bad'], m2['second'])}")


@case
def vault_notice_traps_loot_and_zones():
    """2.62.0: a vault found raises a `vault` alert (what, where, items and monsters inside, predicted traps, the
    good/great squares, advice); its predicted trap squares are kept off paths like known traps (World.extra_traps);
    a lesser vault with weak defenders has its treasure squares fetched; a greater vault becomes an avoid zone, lifted
    by `avoid pass`; an unfelt item on a '9' square is valued as made good 7 levels deeper (iv_at)."""
    import vault
    tm = next(v for v in vault.templates() if v["name"] == "Lesser vault (zelazny)")
    p = pilot(hp=369)
    w = p.w
    w.clvl, w.depth, w.depth_ft = 30, 16, 800
    w.monsters = [(30, 70, BYNAME["cave orc"])]
    p.danger_why = lambda r, *a: None
    m = dict(name=tm["name"], idx=tm["idx"], type="7", kind="lesser vault", y0=20, x0=60, h=tm["h"], w=tm["w"],
             agree=150.0, bad=2.0, known=152.0, rows=tm["rows"])
    p.vault_found(m)
    rec = p.vaults[w.level_t]
    alert = next((d for k, d in p.notes if k == "vault"), "")
    p.avoid_tick()
    traps = set(w.extra_traps)
    g = pilot(hp=369)
    g.w.depth, g.w.depth_ft = 16, 800
    g.danger_why = lambda r, *a: None
    gm = dict(m, type="8", kind="greater vault")
    g.vault_found(gm)
    g.avoid_tick()
    zoned = (25, 70) in g.w.avoid_zone
    g.do_request({"cmd": "avoid", "args": ["pass"], "role": "navigator"})
    g.avoid_tick()
    lifted = (25, 70) not in g.w.avoid_zone
    q9 = (24, 66)                         # (zelazny has no '9' square: one marked for the valuation)
    rec["good"] = [q9]
    plain = p.iv("a Cutlass (1d7)").value
    good = p.iv_at("a Cutlass (1d7)", q9).value
    # (2.64.0, m68: through the real Pilot.log and notify -- the stubs took the vault record's kind= field that the
    # real log() refused with a TypeError, so the alert never reached the Navigator)
    import io
    import json
    import types
    r = pilot(hp=369)
    r.w.clvl, r.w.depth, r.w.depth_ft = 30, 16, 800
    r.danger_why = lambda q, *a: None
    r.dlog = io.StringIO()
    r.crop = lambda *a, **k: []                 # (the test World has no screen rows)
    r.log = types.MethodType(P.Pilot.log, r)
    r.notify = types.MethodType(P.Pilot.notify, r)
    err = None
    try:
        r.vault_found(dict(m))
    except Exception as e:
        err = e
    recs = [json.loads(x) for x in r.dlog.getvalue().splitlines()]
    real = [x for x in recs if x["kind"] == "vault"]
    att = [x for x in recs if x["kind"] == "attention" and x.get("what") == "vault"]
    clash = io.StringIO()
    r.dlog = clash
    r.log("note", kind="x", text="a field named kind")
    kept = json.loads(clash.getvalue())
    ok_real = err is None and real and real[0].get("vkind") == "lesser vault" and att and \
        att[0].get("vkind") == "lesser vault" and kept["kind"] == "note" and kept["field_kind"] == "x"
    ok = rec["loot"] and "lesser vault" in alert and "Cave orc" in alert and traps == set(rec["traps"]) and traps \
        and zoned and lifted and good > plain and ok_real
    return ok, (f"alert {alert[:200]!r}; loot {rec.get('loot')}; traps {len(traps)}; greater zoned {zoned}, lifted "
                f"{lifted}; a Cutlass plain {plain} vs on a '9' square {good}; the real log/notify: error {err!r}, "
                f"vault records {len(real)}, attention {len(att)}; a kind= field kept as {kept.get('field_kind')!r}")


@case
def a_failing_tick_step_doesnt_stop_the_pilot():
    """2.64.0, m68: a TypeError in vault_found (vault_tick) went uncaught and the Pilot died at 800 ft. Now an optional
    tick step that raises is logged once per (step, error, place) -- a `pilot_error` attention, "playing on" -- and
    the tick goes on (the later watches, requests and acting run); a failure outside the guarded steps (confusion,
    the goal) is caught by safe_tick, which runs the reflexes unless this tick's already ran; the game link's end
    (ClientExited, a broken pipe) still ends the Pilot."""
    p = pilot(hp=369)
    ran = []
    steps = ("note_edge_cross supply_watch clock_tick note_town_stairs verify_use verify_effects learn_flavours_tick "
             "track_since stomach_tick track_hp_min watch_floor resync_tick watch_items audit_tick structures_tick "
             "avoid_tick trail_tick mons_tick belief_tick watch_tick handle_requests freeze_tick").split()
    for name in steps:
        setattr(p, name, (lambda n: lambda *a: ran.append(n) and None)(name))
    p.w.drain = p.w.refresh = lambda: None
    p.confusion_tick = lambda: False

    def boom(now):
        raise TypeError("Pilot.log() got multiple values for argument 'kind'")
    p.vault_tick = boom
    p.act_tick = lambda now: ran.append("act_tick")
    p.running = True
    p.safe_tick()
    p.safe_tick()
    errs = [d for k, d in p.notes if k == "pilot_error"]
    ok1 = ran.count("watch_tick") == 2 and ran.count("act_tick") == 2 and ran.count("handle_requests") == 2 and \
        len(errs) == 1 and "vault_tick" in errs[0] and "playing on" in errs[0] and sum(p.step_errors.values()) == 2
    # an unguarded part fails before the reflexes: they run anyway; after them: not twice
    q = pilot(hp=369)
    for name in steps:
        setattr(q, name, lambda *a: None)
    q.w.drain = q.w.refresh = lambda: None
    refl = []
    q.reflexes = lambda: refl.append(1) and False
    q.running = True

    def conf():
        raise KeyError("confused")
    q.confusion_tick = conf
    q.safe_tick()
    before = len(refl)
    q.confusion_tick = lambda: False
    q.parking = False

    def goal():
        raise ValueError("a goal's bug")
    q.rule_tick = q.policy_tick = q.queue_tick = lambda *a: False
    q.look_tick = lambda *a: None
    q.step_goal = goal
    q.safe_tick()
    after = len(refl) - before
    # the game link's end is not caught
    import mang
    q.step_goal = lambda: (_ for _ in ()).throw(mang.ClientExited("gone"))
    try:
        q.safe_tick()
        passed = False
    except mang.ClientExited:
        passed = True
    kinds = sorted(k[0] for k in q.step_errors)
    ok = ok1 and before == 1 and after == 1 and passed and kinds == ["tick", "tick"]
    return ok, (f"steps run twice past the failing vault_tick: watch_tick {ran.count('watch_tick')}, act_tick "
                f"{ran.count('act_tick')}; notices {errs}; reflexes after a confusion_tick error {before}, after a goal "
                f"error (already ran) {after}; ClientExited passes {passed}; errors {sorted(q.step_errors)}")


M69_ROWS = [      # m69 09:13, 750 ft: rows 17-45, columns 60-124 of the map (Dive04 at 31,89 in a 2-wide corridor)
    '                                                  #....#',
    '                                                  #..###',
    '                                                  %..%       ####',
    '                                                  %..%       #..#',
    '                                                  %..#      ##...',
    '                                                  %..########..#.',
    '                                                  %..%%.........#',
    '                                                 #%..##.........#',
    '                                                 ....%%..####...#',
    '                                                 ........#  #....',
    '                                                  .......#  #....',
    "                    ''            +'               #%#%##   #...#",
    '                           ####                                .',
    '                           #..%',
    '                           %@.%',
    '                           %..#',
    '                           #..#',
    '                           #..#',
    '                           #..#',
    '                          ##..#',
    '                          #.....',
    '                   %%%%####....                          ########',
    '                #%%#.........##                          #.......',
    '                #............#                           #.......',
    '                %.....#######                            #..#####',
    '                *..%###                                  #..#',
    '                %..#                                     #..#',
    '                #..#                                 #####..#',
    '        ###%%###%..#                                 #......#',
]


@case
def wide_corridor_dead_end_searched():
    """2.67.0, the user (m69 09:14, 750 ft): "a corridor 2 squares wide that dead-ends is a giveaway for secret doors"
    -- the 2-wide corridor at rows 30-36, columns 89-90, ends against "####" at row 29; the wanted '>' at 27,109 had
    no known path and the dive turned round to walk one through unexplored squares. The detector finds that end
    (pointing up), not the corridors that go on; before the unknown walk the dive searches there (WIDE_TRIES) with news;
    a plain Search takes 2-wide ends first."""
    import goals as G
    p = pilot(hp=369)
    w = p.w
    w.memory = {}
    for k, row in enumerate(M69_ROWS):
        for j, ch in enumerate(row):
            if ch != " ":
                w.memory[(17 + k, 60 + j)] = "." if ch == "@" else ch
    w.memory[(27, 109)] = ">"
    w.pos = (31, 89)
    w.depth, w.in_dungeon = 15, True
    p.searched = set()
    ends = G.Search.wide_dead_ends(w)
    wide = [(q, d) for q, d, n in ends if n == 2]
    went = []
    p.mover = type("M", (), {"active": False, "unknown": True, "path": [],
                             "go": lambda self, g, unknown=False: went.append(list(g)) or True,
                             "tick": lambda self: "moving", "stop": lambda self: None})()
    d = G.Dive(800)
    started = d.search_wide_end(p, [(27, 109)])
    first = d.wide.fixed if d.wide else None
    again = [d.search_wide_end(p, [(27, 109)]) for _ in range(3)]
    s = G.Search()
    s.known, s.doors = 0, G.Search.door_count(w)
    p.frontier = lambda: []
    s.tick(p)
    news = [x for k, x in p.notes if k == "tactic"]
    ok = wide == [((30, 88), (-1, 0))] and started and first == [(30, 88)] and \
        d.wide.tries == G.Search.WIDE_TRIES and news and "2-wide corridor dead-ends at 30,88" in news[0] and \
        again.count(True) <= 1 and s.spot == (30, 88) and s.spot_tries == G.Search.WIDE_TRIES
    return ok, f"2-wide ends {wide}; 1-wide {[(q, d) for q, d, n in ends if n == 1][:4]}; dive search {started} " \
               f"{first} (more: {again}); news {news[:1]}; plain Search spot {s.spot} x{s.spot_tries}"
